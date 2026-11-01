"""后台备份/恢复任务运行器（从 backup.py 拆出，S2）：单线程槽位，可查状态。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from app.core.backup.engine import BackupEngine
from app.core.backup.specs import BackupError

logger = logging.getLogger("obsidian-agent.backup")


class BackupRunner:
    """后台备份/恢复任务包装（API 层使用），单线程槽位，可查状态。"""

    def __init__(self, engine: BackupEngine) -> None:
        self.engine = engine
        self._thread: threading.Thread | None = None
        self.last: dict[str, Any] | None = None
        self.error: str | None = None
        self._kind: str | None = None

    def run_backup(self, reason: str = "manual") -> None:
        if self._busy():
            raise BackupError("已有备份/恢复任务进行中")
        self._start("backup", reason)

    def run_restore(self, snap_id: str, after: Callable[[], Any] | None = None) -> None:
        if self._busy():
            raise BackupError("已有备份/恢复任务进行中")
        self._start("restore", snap_id, after)

    def _start(self, kind: str, arg: str, after: Callable[[], Any] | None = None) -> None:
        self._kind = kind
        self.error = None
        self._thread = threading.Thread(
            target=self._work, args=(kind, arg, after), daemon=True, name=f"backup-{kind}"
        )
        self._thread.start()

    def _work(self, kind: str, arg: str, after: Callable[[], Any] | None) -> None:
        try:
            if kind == "backup":
                self.last = self.engine.create_snapshot(reason=arg)
            else:
                self.last = self.engine.restore_all(arg)
                if after:
                    after()  # 整库恢复后重建索引
        except Exception as e:  # pragma: no cover - 异常统一记录
            self.error = str(e)
            logger.exception("后台 %s 任务失败", kind)

    def _busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def status(self) -> dict[str, Any]:
        return {
            "running": self._busy(),
            "kind": self._kind,
            "lastAt": (self.last or {}).get("createdAt"),
            "lastReason": (self.last or {}).get("reason"),
            "error": self.error,
            "snapshots": len(self.engine.list_snapshots()),
        }
