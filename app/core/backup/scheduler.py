"""定时快照调度线程（从 backup.py 拆出，S2）。

注意：BACKUP_SCHEDULE cron 定时已废弃（改为前端活跃式自动备份），
本调度器仅在显式配置 cron 表达式时生效（默认空 = 不启动）。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from app.core.backup.engine import BackupEngine
from app.core.backup.specs import CronSpec

logger = logging.getLogger("obsidian-agent.backup")


class BackupScheduler:
    """定时快照线程：每 30s 检查 cron 是否到点。"""

    def __init__(self, engine: BackupEngine, cron_expr: str) -> None:
        self.engine = engine
        self.spec = CronSpec.parse(cron_expr) if cron_expr.strip() else None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fired: datetime | None = None

    def start(self) -> None:
        if self.spec is None:
            logger.info("备份调度未启用（BACKUP_SCHEDULE 为空）")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="backup-scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                now = datetime.now()
                assert self.spec is not None
                if self._last_fired is None or now >= self.spec.next_run(self._last_fired):
                    if self._last_fired is not None:
                        self.engine.create_snapshot(reason="scheduled")
                    self._last_fired = now
            except Exception:  # pragma: no cover
                logger.exception("定时快照失败")
            self._stop.wait(30)
