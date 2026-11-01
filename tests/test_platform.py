"""platform.py 平台探测逻辑单测（重构计划 B4：补核心模块直接测试）。

覆盖：Obsidian 库检测（.obsidian 标志 / 深度限制 / 排序）、Windows/Linux 磁盘枚举的
挂载点过滤逻辑（用 monkeypatch 模拟，不依赖真实系统）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import platform as pf

# ---------- detect_vaults ----------


def test_detect_vaults_finds_obsidian_vault(tmp_path: Path) -> None:
    """含 .obsidian 标志的目录被识别为库，mdCount 正确。"""
    vault = tmp_path / "myvault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "a.md").write_text("a", encoding="utf-8")
    (vault / "sub").mkdir()
    (vault / "sub" / "b.md").write_text("b", encoding="utf-8")

    found = pf.detect_vaults(tmp_path)

    assert len(found) == 1
    assert found[0]["name"] == "myvault"
    assert found[0]["mdCount"] == 2  # 递归统计子目录 md


def test_detect_vaults_ignores_non_vault(tmp_path: Path) -> None:
    """没有 .obsidian 标志的目录不是库。"""
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "x.md").write_text("x", encoding="utf-8")
    assert pf.detect_vaults(tmp_path) == []


def test_detect_vaults_limit_and_depth(tmp_path: Path) -> None:
    """limit 上限与 max_depth 深度限制生效。"""
    for i in range(5):
        v = tmp_path / f"v{i}"
        (v / ".obsidian").mkdir(parents=True)
        (v / "x.md").write_text("x", encoding="utf-8")
    found = pf.detect_vaults(tmp_path, max_depth=1, limit=3)
    assert len(found) == 3

    # 深度限制：库在 max_depth 之外不被发现
    deep = tmp_path / "d1" / "d2" / "d3"
    (deep / ".obsidian").mkdir(parents=True)
    (deep / "x.md").write_text("x", encoding="utf-8")
    assert pf.detect_vaults(tmp_path / "d1", max_depth=1) == []


def test_detect_vaults_sorts_by_md_count_desc(tmp_path: Path) -> None:
    """多个库按 mdCount 降序。"""
    small = tmp_path / "small"
    (small / ".obsidian").mkdir(parents=True)
    (small / "a.md").write_text("a", encoding="utf-8")
    big = tmp_path / "big"
    (big / ".obsidian").mkdir(parents=True)
    for i in range(5):
        (big / f"{i}.md").write_text("x", encoding="utf-8")

    found = pf.detect_vaults(tmp_path)
    assert found[0]["name"] == "big"
    assert found[0]["mdCount"] == 5


def test_detect_vaults_start_not_dir(tmp_path: Path) -> None:
    """起始目录不存在时返回空。"""
    assert pf.detect_vaults(tmp_path / "nope") == []


# ---------- linux_disks：挂载点过滤（模拟 /proc/mounts） ----------


def _fake_mounts() -> str:
    return """rootfs / overlay rw 0 0
/dev/root /rom squashfs ro 0 0
tmpfs /tmp tmpfs rw 0 0
/dev/sda1 /mnt/sda1 ext4 rw 0 0
/dev/sda2 /mnt/sda2 ext4 rw 0 0
/dev/sdb1 /mnt/usb ntfs rw 0 0
/dev/mmcblk0p1 /mnt/mmc0-1 ext4 rw 0 0
/dev/nvme0n1p1 /volume1 btrfs rw 0 0
proc /proc proc rw 0 0
sysfs /sys sysfs rw 0 0
cgroup2 /sys/fs/cgroup cgroup2 rw 0 0
overlay /overlay overlay rw 0 0
/dev/sda1 /mnt/data ext4 rw 0 0
"""


def test_linux_disks_filters_pseudo_fs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """伪文件系统（overlay/tmpfs/proc/sysfs/squashfs/cgroup）全部排除，真实挂载点保留。"""
    mounts_file = tmp_path / "mounts"
    mounts_file.write_text(_fake_mounts(), encoding="utf-8")
    monkeypatch.setattr(pf.os, "name", "posix")
    monkeypatch.setattr(pf, "_PROC_MOUNTS", str(mounts_file))
    monkeypatch.setattr(pf, "_running_in_docker", lambda: False)  # 裸机场景
    # 模拟挂载点路径存在（真实环境 /mnt/sda1 等存在；测试环境不存在需 mock）
    monkeypatch.setattr(pf.Path, "is_dir", lambda self: True)

    disks = pf.linux_disks()

    paths = [d["path"] for d in disks]
    assert "/mnt/sda1" in paths
    assert "/mnt/sda2" in paths
    assert "/mnt/usb" in paths
    assert "/mnt/mmc0-1" in paths
    assert "/volume1" in paths
    assert "/mnt/data" in paths
    # 伪文件系统必须被排除
    assert all(p not in paths for p in ("/", "/rom", "/tmp", "/proc", "/sys", "/overlay"))
    # fstype 拼在 name 中（如 "sda1 (ext4)"）
    assert any("ext4" in d["name"] for d in disks)


def test_linux_disks_docker_mode_only_mounted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Docker 容器内（/.dockerenv 存在）：只展示 bind 挂载盘，排除根挂载与兜底目录。"""
    mounts_file = tmp_path / "mounts"
    mounts_file.write_text(
        "/dev/sda1 / ext4 rw 0 0\n"
        "/dev/sda2 /vault ext4 rw 0 0\n"
        "/dev/sdb1 /data ext4 rw 0 0\n"
        "overlay /overlay overlay rw 0 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pf.os, "name", "posix")
    monkeypatch.setattr(pf, "_PROC_MOUNTS", str(mounts_file))
    monkeypatch.setattr(pf.Path, "is_dir", lambda self: True)
    monkeypatch.setattr(pf, "_running_in_docker", lambda: True)

    disks = pf.linux_disks()
    paths = [d["path"] for d in disks]
    assert "/vault" in paths
    assert "/data" in paths
    assert "/" not in paths  # 根挂载被排除
    # 兜底目录（/mnt /media /volume1…）在 Docker 模式不出现
    fallbacks = ("/mnt", "/media", "/volume1", "/volume2", "/share", "/userdisk")
    assert not any(p in paths for p in fallbacks)


def test_linux_disks_non_docker_keeps_root_and_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """非 Docker（本地裸机）：根挂载展示 + 常见目录兜底保留（本地部署仍可用）。"""
    mounts_file = tmp_path / "mounts"
    mounts_file.write_text("/dev/sda1 / ext4 rw 0 0\n", encoding="utf-8")
    monkeypatch.setattr(pf.os, "name", "posix")
    monkeypatch.setattr(pf, "_PROC_MOUNTS", str(mounts_file))
    monkeypatch.setattr(pf.Path, "is_dir", lambda self: True)
    monkeypatch.setattr(pf, "_running_in_docker", lambda: False)

    disks = pf.linux_disks()
    paths = [d["path"] for d in disks]
    assert "/" in paths  # 根挂载保留
    # 兜底目录仍出现
    assert "/mnt" in paths
    assert "/media" in paths

# ---------- S11：browse_dirs（收敛自 API 层） ----------


def test_browse_dirs_lists_subdirs(tmp_path: Path) -> None:
    """browse_dirs 列出子目录，不列文件。"""
    from app.core.platform import browse_dirs

    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()
    (tmp_path / "file.md").write_text("x")

    r = browse_dirs(str(tmp_path))
    assert r["path"] == str(tmp_path)
    assert "sub1" in r["dirs"]
    assert "sub2" in r["dirs"]
    assert "file.md" not in r["dirs"]


def test_browse_dirs_missing_raises(tmp_path: Path) -> None:
    """browse_dirs 不存在的目录抛 FileNotFoundError。"""
    import pytest as _pt

    from app.core.platform import browse_dirs

    with _pt.raises(FileNotFoundError):
        browse_dirs(str(tmp_path / "nope"))


def test_browse_dirs_empty_returns_roots(tmp_path: Path) -> None:
    """browse_dirs 空路径返回根列表（与 list_roots 一致）。"""
    from app.core.platform import browse_dirs, list_roots

    assert browse_dirs("") == list_roots()


def test_open_in_file_manager_missing_raises(tmp_path: Path) -> None:
    """打开不存在的目录抛 RuntimeError（不真正调系统命令）。"""
    import pytest as _pt

    from app.core.platform import open_in_file_manager

    with _pt.raises(RuntimeError):
        open_in_file_manager(str(tmp_path / "nope"))
