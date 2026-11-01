"""备份配置规格：领域异常 / 保留策略 / cron 表达式（从 backup.py 拆出，S2）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


class BackupError(Exception):
    """备份/恢复错误基类。"""


@dataclass
class RetentionSpec:
    days: int = 7
    weeks: int = 4
    months: int = 3

    @classmethod
    def parse(cls, expr: str) -> RetentionSpec:
        """解析 "7d,4w,3m" 形式。"""
        spec = cls()
        for part in expr.split(","):
            part = part.strip().lower()
            if not part:
                continue
            unit = part[-1]
            try:
                n = int(part[:-1])
            except ValueError as e:
                raise BackupError(f"无效保留策略: {expr!r}") from e
            if unit == "d":
                spec.days = n
            elif unit == "w":
                spec.weeks = n
            elif unit == "m":
                spec.months = n
            else:
                raise BackupError(f"无效保留策略单位: {expr!r}")
        return spec


@dataclass
class CronSpec:
    """极简 cron：支持 `*`、数字、`*/n`、`a,b,c`；仅分钟/小时/日/月/周 5 段。"""

    minute: set[int] | None = None  # None = 任意
    hour: set[int] | None = None
    day: set[int] | None = None
    month: set[int] | None = None
    weekday: set[int] | None = None  # 0=周日

    @classmethod
    def parse(cls, expr: str) -> CronSpec:
        parts = expr.split()
        if len(parts) != 5:
            raise BackupError(f"无效 cron 表达式（需 5 段）: {expr!r}")
        return cls(
            minute=_parse_field(parts[0], 0, 59),
            hour=_parse_field(parts[1], 0, 23),
            day=_parse_field(parts[2], 1, 31),
            month=_parse_field(parts[3], 1, 12),
            weekday=_parse_field(parts[4], 0, 6),
        )

    def next_run(self, after: datetime) -> datetime:
        """计算 after 之后的下一次触发时间（按分钟步进扫描，最多 7 天跨周末）。"""
        now = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(7 * 24 * 60):
            if self._match(now):
                return now
            now += timedelta(minutes=1)
        raise BackupError(f"无法在 7 天内找到 cron 触发点: {self}")  # pragma: no cover

    def _match(self, dt: datetime) -> bool:
        if self.minute is not None and dt.minute not in self.minute:
            return False
        if self.hour is not None and dt.hour not in self.hour:
            return False
        if self.month is not None and dt.month not in self.month:
            return False
        # day 与 weekday 的 OR 语义简化：day 任意时只看 weekday，否则两者都要匹配
        # cron 惯例 weekday 0=周日，Python weekday() 0=周一 → 转换 (wd+1)%7
        if self.day is None and self.weekday is None:
            return True
        day_ok = self.day is None or dt.day in self.day
        wd_ok = self.weekday is None or ((dt.weekday() + 1) % 7) in self.weekday
        if self.day is None:
            return wd_ok
        if self.weekday is None:
            return day_ok
        return day_ok and wd_ok


def _parse_field(field: str, lo: int, hi: int) -> set[int] | None:
    field = field.strip()
    if field == "*":
        return None
    values: set[int] = set()
    for part in field.split(","):
        if "/" in part:
            base, step_s = part.split("/")
            step = int(step_s)
            start = lo if base == "*" else int(base)
            values.update(range(start, hi + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            values.update(range(int(a), int(b) + 1))
        else:
            values.add(int(part))
    return values
