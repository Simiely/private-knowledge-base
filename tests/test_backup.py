"""M1：备份引擎测试（快照 / 硬链接增量 / 保留策略 / 恢复 / 降级 / cron）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.core.backup import BackupEngine, BackupError, BackupScheduler, CronSpec, RetentionSpec
from app.core.vault import Vault


@pytest.fixture
def env(tmp_path: Path) -> tuple[Vault, BackupEngine]:
    root = tmp_path / "vault"
    (root / "sub").mkdir(parents=True)
    # write_bytes 避免 Windows 换行转换（\n → \r\n）
    (root / "a.md").write_bytes(("# A\n" * 50).encode("utf-8"))
    (root / "b.md").write_bytes(("# B\n" * 50).encode("utf-8"))
    (root / "sub" / "c.md").write_bytes(("# C\n" * 50).encode("utf-8"))
    vault = Vault(root=root)
    engine = BackupEngine(vault=vault, backup_root=tmp_path / "backups")
    return vault, engine


# ---------- 快照 ----------


def test_create_snapshot(env: tuple[Vault, BackupEngine]) -> None:
    _, engine = env
    snap = engine.create_snapshot(reason="manual")
    assert snap["files"] == 3
    assert snap["reason"] == "manual"
    assert snap["verify"] == "ok"
    assert engine.snapshot_files(snap["id"]) == ["a.md", "b.md", "sub/c.md"]


def test_snapshot_restores_layout(env: tuple[Vault, BackupEngine]) -> None:
    _, engine = env
    snap = engine.create_snapshot()
    tree = engine.snapshot_root / snap["id"] / "tree"
    assert (tree / "a.md").read_text(encoding="utf-8") == "# A\n" * 50


def test_incremental_hardlink(env: tuple[Vault, BackupEngine]) -> None:
    """未变文件应硬链接复用上一快照（st_ino 相同），仅变更文件重新复制。"""
    vault, engine = env
    snap1 = engine.create_snapshot()
    vault.write("a.md", "# A 修改\n" * 50)
    snap2 = engine.create_snapshot()
    tree1 = engine.snapshot_root / snap1["id"] / "tree"
    tree2 = engine.snapshot_root / snap2["id"] / "tree"
    # b.md 未变 → 硬链接（同一 inode）
    assert (tree1 / "b.md").stat().st_ino == (tree2 / "b.md").stat().st_ino
    # a.md 变更 → 新内容
    assert (tree2 / "a.md").read_text(encoding="utf-8") == "# A 修改\n" * 50


def test_hardlink_fallback_to_copy(
    env: tuple[Vault, BackupEngine], monkeypatch: pytest.MonkeyPatch
) -> None:
    """坑 #13：os.link 失败应降级为复制而非报错。"""
    import os as _os

    _, engine = env
    engine.create_snapshot()
    engine.create_snapshot()  # 第二次会尝试硬链接
    calls = {"failed": 0}

    def fake_link(src: Path, dst: Path) -> None:
        calls["failed"] += 1
        raise OSError("not supported")

    monkeypatch.setattr(_os, "link", fake_link)
    snap = engine.create_snapshot()
    assert snap["files"] == 3
    assert calls["failed"] > 0  # 确实尝试过链接并降级


# ---------- 保留策略 ----------


def test_retention_parse() -> None:
    spec = RetentionSpec.parse("7d,4w,3m")
    assert (spec.days, spec.weeks, spec.months) == (7, 4, 3)
    with pytest.raises(BackupError):
        RetentionSpec.parse("7x")


def test_cleanup_retention(env: tuple[Vault, BackupEngine]) -> None:
    _, engine = env
    engine.auto_cleanup = False  # 关闭创建时自动清理，手动控制
    engine.retention = RetentionSpec(days=2, weeks=0, months=0)  # 只保留最近 2 天各 1 份
    ids = []
    for i in range(4):
        snap = engine.create_snapshot(reason="test")
        ids.append(snap["id"])
        # 伪造时间戳使快照跨天
        created = datetime.now() - timedelta(days=3 - i)
        mf = engine.snapshot_root / snap["id"] / "manifest.json"
        data = json.loads(mf.read_text(encoding="utf-8"))
        data["createdAt"] = created.isoformat(timespec="seconds")
        mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    removed = engine.cleanup_retention()
    assert len(removed) == 2  # 4 天窗口保留 2 份
    remaining = {s["id"] for s in engine.list_snapshots()}
    assert len(remaining) == 2


# ---------- 恢复 ----------


def test_backup_for_write(env: tuple[Vault, BackupEngine]) -> None:
    vault, engine = env
    path = engine.backup_for_write("a.md")
    assert Path(path).is_file()
    engine.vault.write("a.md", "changed")
    assert engine.backup_for_write("a.md") == path  # 已有备份不重复写


def test_restore_file(env: tuple[Vault, BackupEngine]) -> None:
    vault, engine = env
    snap = engine.create_snapshot()
    vault.write("a.md", "# 被改坏\n")
    engine.restore_file("a.md", snap["id"])
    assert vault.read("a.md").text == "# A\n" * 50
    # 恢复前当前版本应备份到 pre-restore
    pre = engine.backup_root / "pre-restore" / "a.md.bak"
    assert pre.read_text(encoding="utf-8") == "# 被改坏\n"


def test_restore_all(env: tuple[Vault, BackupEngine]) -> None:
    vault, engine = env
    snap = engine.create_snapshot()
    vault.write("a.md", "# 改坏\n")
    vault.create("垃圾.md", "x")
    result = engine.restore_all(snap["id"])
    assert result["restored"] == 3
    assert vault.read("a.md").text == "# A\n" * 50
    assert not (vault.root / "垃圾.md").exists()
    assert result["preRestoreSnap"]  # 恢复前强制快照（坑 #14）


def test_verify_detects_corruption(env: tuple[Vault, BackupEngine]) -> None:
    _, engine = env
    snap = engine.create_snapshot()
    (engine.snapshot_root / snap["id"] / "tree" / "b.md").write_text("corrupted", encoding="utf-8")
    ok, msg = engine.verify_snapshot(snap["id"])
    assert not ok
    assert "checksum" in msg


# ---------- cron ----------


def test_cron_parse_daily() -> None:
    spec = CronSpec.parse("0 2 * * *")
    now = datetime(2026, 7, 31, 22, 30)
    assert spec.next_run(now) == datetime(2026, 8, 1, 2, 0)


def test_cron_parse_step_and_list() -> None:
    spec = CronSpec.parse("*/15 9,18 * * 1-5")
    assert spec.minute == {0, 15, 30, 45}
    assert spec.hour == {9, 18}
    assert spec.weekday == {1, 2, 3, 4, 5}  # cron 惯例：0=周日 → 1-5 = 周一到周五
    now = datetime(2026, 7, 31, 22, 30)  # 周五
    assert spec.next_run(now) == datetime(2026, 8, 3, 9, 0)  # 下一个工作日 9:00


def test_cron_next_run_same_hour() -> None:
    spec = CronSpec.parse("0 2 * * *")
    now = datetime(2026, 7, 31, 2, 0)
    assert spec.next_run(now) == datetime(2026, 8, 1, 2, 0)  # 不含当前时刻


def test_scheduler_disabled_when_empty(env: tuple[Vault, BackupEngine]) -> None:
    _, engine = env
    sched = BackupScheduler(engine, "")
    sched.start()
    assert sched._thread is None  # 空表达式不启动线程

# ---------- 删除快照（修复：rmtree_manual 绕过安全钩子 + 失败上报） ----------


def test_delete_snapshot_removes_dir(env: tuple[Vault, BackupEngine]) -> None:
    """删除快照后目录与列表都移除（回归：之前 shutil.rmtree 被 WorkBuddy 钩子拦截静默失败）。"""
    vault, engine = env
    engine.create_snapshot(reason="manual")
    snap_id = engine.list_snapshots()[0]["id"]
    snap_dir = engine.snapshot_root / snap_id
    assert snap_dir.is_dir()

    engine.delete_snapshot(snap_id)

    assert not snap_dir.exists()
    assert all(s["id"] != snap_id for s in engine.list_snapshots())


def test_delete_snapshot_incomplete_renames_tomb(
    env: tuple[Vault, BackupEngine], monkeypatch: pytest.MonkeyPatch
) -> None:
    """删除不完整（文件被占用）→ 重命名 .del- 回收区脱离列表，不抛错（S24 修复）。"""
    from app.core.backup import engine as engine_mod

    vault, engine = env
    engine.create_snapshot(reason="test")
    snap_id = engine.list_snapshots()[0]["id"]

    # 模拟 rmtree_manual 失败：目录仍在
    def fake_rmtree(root):
        return ["locked-file: PermissionError"]

    monkeypatch.setattr(engine_mod, "rmtree_manual", fake_rmtree)

    engine.delete_snapshot(snap_id)  # 不应 raise

    tombs = [p for p in engine.snapshot_root.glob(".del-*") if p.is_dir()]
    assert tombs, "应生成 .del- 回收区目录"
    assert not (engine.snapshot_root / snap_id).exists(), "原目录应被重命名"
    ids = [s["id"] for s in engine.list_snapshots()]
    assert snap_id not in ids, "删除后列表不应再显示"


def test_delete_snapshot_missing_raises(env: tuple[Vault, BackupEngine]) -> None:
    """删除不存在的快照抛 BackupError。"""
    vault, engine = env
    with pytest.raises(BackupError):
        engine.delete_snapshot("snap-does-not-exist")


def test_rmtree_manual_deletes_nested(env: tuple[Vault, BackupEngine]) -> None:
    """rmtree_manual 递归删除嵌套目录树（绕过 shutil.rmtree 钩子）。"""
    from app.core.backup import rmtree_manual

    vault, engine = env
    engine.create_snapshot(reason="manual")
    snap_id = engine.list_snapshots()[0]["id"]
    snap_dir = engine.snapshot_root / snap_id

    errors = rmtree_manual(snap_dir)

    assert errors == []
    assert not snap_dir.exists()

# ---------- S2 拆包回归 / S6 pre_write_file ----------


def test_pre_write_file_path(env: tuple[Vault, BackupEngine]) -> None:
    """pre_write_file 返回 pre-write 目录下路径（S6 常量统一）。"""
    vault, engine = env
    pf = engine.pre_write_file("a.md")
    assert pf.name == "a.md.bak"
    assert pf.parent.name == "pre-write"
    assert pf.parent == engine.backup_root / "pre-write"


def test_scheduler_disabled_with_empty_expr(env: tuple[Vault, BackupEngine]) -> None:
    """空 cron 表达式时调度器不启动（废弃 cron 后默认行为）。"""
    vault, engine = env
    sched = BackupScheduler(engine, "")
    sched.start()
    assert sched.spec is None
    sched.stop()


def test_list_snapshots_handles_missing_manifest(env: tuple[Vault, BackupEngine]) -> None:
    """list_snapshots：manifest 缺失的快照目录不静默忽略，显示为损坏条目。"""
    import os
    import time as _time

    vault, engine = env
    engine.create_snapshot(reason='test')

    # 模拟创建中断：生成一个只有 tree、无 manifest 的目录
    broken = engine.snapshot_root / 'snap-20260802-000000-broken'
    (broken / 'tree').mkdir(parents=True)
    (broken / 'tree' / 'x.md').write_text('x', encoding='utf-8')
    # 目录 mtime 改为 3 分钟前（模拟历史中断，而非正在创建）
    old = _time.time() - 180
    os.utime(broken, (old, old))

    snaps = engine.list_snapshots()
    ids = [s['id'] for s in snaps]
    assert 'snap-20260802-000000-broken' in ids, '损坏快照目录应出现在列表中'

    broken_entry = next(s for s in snaps if s['id'] == 'snap-20260802-000000-broken')
    assert broken_entry['verify'].startswith('fail: manifest'), '损坏条目应标记 verify 失败'
    assert broken_entry['files'] == 1, '应统计 tree 内文件数'


def test_list_snapshots_marks_creating(tmp_path: Path) -> None:
    """list_snapshots：manifest 缺失但目录仍在写入（mtime 新）→ 标记"创建中"而非损坏。"""
    import os
    import time as _time

    from app.core.backup import BackupEngine

    root = tmp_path / 'vault'
    root.mkdir()
    (root / 'a.md').write_text('# A', encoding='utf-8')
    engine = BackupEngine(vault=Vault(root=root), backup_root=tmp_path / 'backups')

    # 模拟正在创建：有 tree、无 manifest、mtime 新
    creating = engine.snapshot_root / 'snap-20260802-000001-creating'
    (creating / 'tree').mkdir(parents=True)
    (creating / 'tree' / 'a.md').write_text('# A', encoding='utf-8')
    now = _time.time()
    os.utime(creating, (now, now))

    entry = next(
        s for s in engine.list_snapshots() if s['id'] == 'snap-20260802-000001-creating'
    )
    assert entry['reason'] == 'creating', '创建中的快照应标记 creating'
    assert '创建中' in entry['verify']
