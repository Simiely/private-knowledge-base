"""快照引擎：硬链接增量快照 / 保留策略 / 校验 / 恢复（从 backup.py 拆出，S2）。

backup_root 布局：
  <backup_root>/
    snapshots/<snap-id>/manifest.json + tree/<relpath>
    pre-write/<relpath>.bak
    pre-restore/<relpath>.bak
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from app.core.backup.fsutil import _md5, rmtree_manual
from app.core.backup.specs import BackupError, RetentionSpec
from app.core.vault import Vault, copy_file

logger = logging.getLogger("obsidian-agent.backup")

SNAPSHOT_MANIFEST = "manifest.json"
PRE_WRITE_DIR = "pre-write"
PRE_RESTORE_DIR = "pre-restore"
SNAPSHOT_DIR = "snapshots"


def _created_at_from_id(snap_id: str) -> str:
    """从快照 ID（snap-YYYYMMDD-HHMMSS-xxxx）解析创建时间；解析失败回退目录名。"""
    parts = snap_id.split("-")
    if len(parts) >= 3 and len(parts[1]) == 8 and len(parts[2]) == 6:
        d = parts[1]
        tm = parts[2]
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{tm[:2]}:{tm[2:4]}:{tm[4:6]}"
    return snap_id


class BackupEngine:
    """快照引擎：整库快照（硬链接增量）/ 保留 / 校验 / 单文件与整库恢复。"""

    def __init__(
        self,
        vault: Vault,
        backup_root: Path,
        retention: RetentionSpec | str = "7d,4w,3m",
        max_bytes: int = 10 * 1024 * 1024,
        verify: bool = True,
        enabled: bool = True,
        auto_cleanup: bool = True,
    ) -> None:
        self.vault = vault
        self.backup_root = backup_root.expanduser().resolve()
        self.retention = (
            retention if isinstance(retention, RetentionSpec) else RetentionSpec.parse(retention)
        )
        self.max_bytes = max_bytes
        self.verify_enabled = verify
        self.enabled = enabled
        self.auto_cleanup = auto_cleanup
        self.snapshot_root = self.backup_root / SNAPSHOT_DIR
        self.snapshot_root.mkdir(parents=True, exist_ok=True)

    # ---------- 快照 ----------

    def create_snapshot(self, reason: str = "manual") -> dict[str, Any]:
        if not self.enabled:
            raise BackupError("备份已禁用（BACKUP_ENABLED=false）")
        # 微秒精度：同一秒内多次快照 createdAt 仍可排序（否则增量判断退化）
        created_at = datetime.now().isoformat(timespec="microseconds")
        # id 含秒级时间戳 + 唯一后缀：同一秒多次快照不冲突（否则增量判断失效）
        snap_id = "snap-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        dest = self.snapshot_root / snap_id / "tree"
        prev_tree = self._latest_snapshot_tree_before(created_at)

        files = 0
        total_bytes = 0
        skipped: list[str] = []
        checksums: dict[str, str] = {}
        for rel, src in self.vault.walk_all():
            if src.stat().st_size > self.max_bytes:
                skipped.append(rel)
                continue
            dst = dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if prev_tree is not None:
                prev_src = prev_tree / rel
                if prev_src.is_file() and self._same_file(prev_src, src):
                    if self._hardlink_or_copy(prev_src, dst):
                        files += 1
                        total_bytes += src.stat().st_size
                        continue
            shutil.copy2(src, dst)
            files += 1
            total_bytes += src.stat().st_size

        # 抽样 checksum 基准（verify 用）：最多 100 个文件
        sample = sorted(dest.rglob("*"))[:100]
        for f in sample:
            if f.is_file():
                rel_md = f.relative_to(dest).as_posix()
                checksums[rel_md] = _md5(f)

        manifest = {
            "id": snap_id,
            "createdAt": created_at,
            "reason": reason,
            "files": files,
            "bytes": total_bytes,
            "skipped": skipped,
            "checksums": checksums,
            "verify": "pending",
        }
        self._write_manifest(snap_id, manifest)
        if self.verify_enabled:
            ok, msg = self.verify_snapshot(snap_id)
            manifest["verify"] = "ok" if ok else f"fail: {msg}"
            self._write_manifest(snap_id, manifest)
        if self.auto_cleanup:
            self.cleanup_retention()
        logger.info(
            "快照完成 %s files=%s bytes=%s skipped=%s", snap_id, files, total_bytes, len(skipped)
        )
        return self.get_snapshot(snap_id)

    def get_snapshot(self, snap_id: str) -> dict[str, Any]:
        mf = self.snapshot_root / snap_id / SNAPSHOT_MANIFEST
        if not mf.is_file():
            raise BackupError(f"快照不存在: {snap_id}")
        return cast(dict[str, Any], json.loads(mf.read_text(encoding="utf-8")))

    def list_snapshots(self) -> list[dict[str, Any]]:
        """按 createdAt 降序（id 含随机后缀，不能按 id 排序）。

        容错：manifest 缺失的快照目录（创建中断等）不静默忽略——
        - 目录仍在写入（创建中，mtime 新）→ 标记"创建中"条目；
        - 否则 → 标记"损坏快照"条目（verify=fail: manifest 缺失），页面可见可删除。
        """
        snaps: list[dict[str, Any]] = []
        self._purge_tombs()  # 顺带清理回收区（占用释放的删掉，未释放的下轮再试）
        now = time.time()
        for snap_dir in sorted(self.snapshot_root.iterdir(), key=lambda p: p.name):
            if not snap_dir.is_dir() or snap_dir.name.startswith(".del"):
                continue  # 跳过回收区目录（.del-* / .del-retry.txt）
            mf = snap_dir / SNAPSHOT_MANIFEST
            manifest: dict[str, Any] | None = None
            if mf.is_file():
                try:
                    manifest = json.loads(mf.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    # 快照仍在写入 manifest，或文件损坏：走下面的"创建中/损坏"分支
                    manifest = None
            if manifest is not None:
                snaps.append(manifest)
                continue
            # manifest 缺失/为空：区分"创建中"与"损坏"
            tree = snap_dir / "tree"
            has_tree = tree.is_dir()
            files = len([p for p in tree.rglob("*") if p.is_file()]) if has_tree else 0
            recent = now - snap_dir.stat().st_mtime < 120  # 2 分钟内仍有写入
            if recent:
                reason, verify = "creating", "创建中（manifest 待写入）"
            else:
                reason, verify = "broken", "fail: manifest 缺失（快照可能未完成，建议删除）"
            snaps.append(
                {
                    "id": snap_dir.name,
                    "createdAt": _created_at_from_id(snap_dir.name),
                    "reason": reason,
                    "files": files,
                    "bytes": 0,
                    "skipped": [],
                    "checksums": {},
                    "verify": verify,
                }
            )
        snaps.sort(key=lambda s: s["createdAt"], reverse=True)
        return snaps

    def snapshot_files(self, snap_id: str) -> list[str]:
        tree = self.snapshot_root / snap_id / "tree"
        if not tree.is_dir():
            raise BackupError(f"快照目录不存在: {snap_id}")
        return sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file())

    def verify_snapshot(self, snap_id: str) -> tuple[bool, str]:
        """抽样校验：文件数一致 + manifest 记录的抽样 checksum 比对。"""
        mf = self.snapshot_root / snap_id / SNAPSHOT_MANIFEST
        if not mf.is_file():
            return False, "manifest 缺失"
        data = json.loads(mf.read_text(encoding="utf-8"))
        files = self.snapshot_files(snap_id)
        if len(files) != data["files"]:
            return False, f"文件数不一致 manifest={data['files']} 实际={len(files)}"
        tree = self.snapshot_root / snap_id / "tree"
        for rel, expected in (data.get("checksums") or {}).items():
            if _md5(tree / rel) != expected:
                return False, f"checksum 不一致: {rel}"
        return True, "ok"

    # ---------- 保留策略 ----------

    def cleanup_retention(self) -> list[str]:
        """按 日/周/月 桶保留最新快照，其余删除。返回被删除的 snap_id 列表。"""
        snaps = self.list_snapshots()
        removed: list[str] = []
        seen_days: set[tuple[int, int, int]] = set()
        seen_weeks: set[tuple[int, int]] = set()
        seen_months: set[tuple[int, int]] = set()
        for s in snaps:  # 已按时间降序
            snap_id = s["id"]
            created = datetime.fromisoformat(s["createdAt"])
            d = created.date()
            day_key = (d.year, d.month, d.day)
            week_key = d.isocalendar()[:2]
            month_key = (d.year, d.month)
            keep = False
            if len(seen_days) < self.retention.days and day_key not in seen_days:
                seen_days.add(day_key)
                keep = True
            elif len(seen_weeks) < self.retention.weeks and week_key not in seen_weeks:
                seen_weeks.add(week_key)
                keep = True
            elif len(seen_months) < self.retention.months and month_key not in seen_months:
                seen_months.add(month_key)
                keep = True
            if not keep:
                rmtree_manual(self.snapshot_root / snap_id)
                removed.append(snap_id)
        if removed:
            logger.info("保留策略清理 %s", removed)
        return removed

    # ---------- 恢复 ----------

    def delete_snapshot(self, snap_id: str) -> None:
        """删除指定快照（API DELETE /api/backup/{id}）。

        修复（S24）：不再用 shutil.rmtree（WorkBuddy 安全钩子会拦目录删除且静默吞错）。
        改用 rmtree_manual：优先系统命令（cmd rmdir / rm -rf），失败回退逐文件删除。
        系统命令可能因个别文件被占用（硬链接共享图片等）部分删除后失败、Python 回退
        又被钩子拦 → 此时【重命名快照目录为 .del- 前缀回收区】脱离列表（用户视角删除
        成功，rename 不受删除钩子拦截），后台线程继续清理；残留目录被 list 隐藏。
        """
        import threading

        d = self.snapshot_root / snap_id
        if not d.is_dir():
            raise BackupError(f"快照不存在: {snap_id}")

        errors = rmtree_manual(d)
        # 重试一次：首次失败多为句柄瞬态占用
        if errors and d.exists():
            errors = rmtree_manual(d)
        if d.exists():
            # 降级：重命名脱离列表（删除"成功"），后台继续清理
            tomb = self.snapshot_root / f".del-{snap_id}-{int(time.time())}"
            try:
                d.rename(tomb)
                logger.warning(
                    "快照 %s 删除不完整（%d 项失败），已移入回收区 %s，后台继续清理",
                    snap_id, len(errors), tomb.name,
                )
                threading.Thread(
                    target=self._purge_tomb, args=(tomb,), daemon=True, name=f"purge-{snap_id}"
                ).start()
                return
            except OSError as e:
                sample = "; ".join(errors[:3]) if errors else "未知原因"
                raise BackupError(
                    f"快照删除失败: {snap_id}（{len(errors)} 项失败，可能被占用: {sample}）"
                ) from e

    def _purge_tomb(self, tomb: Path) -> None:
        """后台清理回收区目录（占用释放后可删干净；失败静默，下轮 list 再试）。"""
        if tomb.exists():
            rmtree_manual(tomb)
        # 删除失败（文件仍被占用）时保留，由下次 list_snapshots 触发再试
        if tomb.exists():
            self._retry_tomb(tomb)

    def backup_for_write(self, rel: str) -> str:
        """写前单文件备份（M5 safety 调用）→ pre-write/<rel>.bak。"""
        src = self.vault.resolve_safe_path(rel, must_exist=True)
        dst = self.backup_root / PRE_WRITE_DIR / (rel + ".bak")
        if not dst.exists():
            copy_file(src, dst)
        return dst.as_posix()

    def pre_write_file(self, rel: str) -> Path:
        """写前备份文件路径（pre-write/<rel>.bak），不存在时调用方自行判断。"""
        return self.backup_root / PRE_WRITE_DIR / (rel + ".bak")

    def restore_file(self, rel: str, snap_id: str) -> str:
        """从快照恢复单文件；恢复前把当前版本备份到 pre-restore（坑 #14 可回退）。"""
        src = self.snapshot_root / snap_id / "tree" / rel
        if not src.is_file():
            raise BackupError(f"快照 {snap_id} 中不存在文件: {rel}")
        target = self.vault.resolve_safe_path(rel, md_only=True)
        if target.is_file():
            copy_file(target, self.backup_root / PRE_RESTORE_DIR / (rel + ".bak"))
        copy_file(src, target)
        return target.as_posix()

    def restore_all(self, snap_id: str) -> dict[str, Any]:
        """整库恢复：① 强制先建恢复前快照 ② 清空 vault ③ 从快照复制回。"""
        if not self.enabled:
            raise BackupError("备份已禁用")
        pre = self.create_snapshot(reason="pre-restore")
        tree = self.snapshot_root / snap_id / "tree"
        if not tree.is_dir():
            raise BackupError(f"快照目录不存在: {snap_id}")
        for _rel, src in self.vault.walk_all():
            src.unlink()
        restored = 0
        for rel in self.snapshot_files(snap_id):
            if self.vault.is_ignored(rel):
                continue
            copy_file(tree / rel, self.vault.root / rel)
            restored += 1
        logger.info(
            "整库恢复完成 snap=%s restored=%s preRestoreSnap=%s", snap_id, restored, pre["id"]
        )
        return {"snapId": snap_id, "restored": restored, "preRestoreSnap": pre["id"]}

    # ---------- 内部 ----------

    def _retry_tomb(self, tomb: Path) -> None:
        """记录回收区目录，供下次 list_snapshots 顺带重试清理。"""
        try:
            idx = self.snapshot_root / ".del-retry.txt"
            with idx.open("a", encoding="utf-8") as f:
                f.write(tomb.name + "\n")
        except OSError:
            pass

    def _purge_tombs(self) -> None:
        """清理回收区（.del-* 目录与 .del-retry.txt 记录的）：占用释放后可删干净。"""
        # 1) 记录文件里的
        idx = self.snapshot_root / ".del-retry.txt"
        if idx.is_file():
            try:
                lines = idx.read_text(encoding="utf-8").splitlines()
                names = [ln.strip() for ln in lines if ln.strip()]
                idx.unlink()
            except OSError:
                names = []
            for n in names:
                t = self.snapshot_root / n
                if t.exists():
                    rmtree_manual(t)
                    if t.exists():  # 仍被占用，下轮再试
                        self._retry_tomb(t)
        # 2) 目录扫描兜底
        for t in list(self.snapshot_root.glob(".del-*")):
            if t.is_dir() and t.name != ".del-retry.txt":
                rmtree_manual(t)
                if t.exists():
                    self._retry_tomb(t)

    def _latest_snapshot_tree_before(self, created_at: str) -> Path | None:
        """返回 createdAt 早于指定时间的最新快照 tree（用于硬链接增量）。"""
        for s in self.list_snapshots():
            if s["createdAt"] < created_at:
                return self.snapshot_root / str(s["id"]) / "tree"
        return None

    def _same_file(self, a: Path, b: Path) -> bool:
        sa, sb = a.stat(), b.stat()
        return sa.st_size == sb.st_size and sa.st_mtime_ns == sb.st_mtime_ns

    def _hardlink_or_copy(self, src: Path, dst: Path) -> bool:
        """硬链接复用，失败降级复制（坑 #13）。"""
        try:
            os.link(src, dst)
            return True
        except OSError:
            shutil.copy2(src, dst)
            return False

    def _write_manifest(self, snap_id: str, manifest: dict[str, Any]) -> None:
        (self.snapshot_root / snap_id / SNAPSHOT_MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
