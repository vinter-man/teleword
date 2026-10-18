from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.db.models import DailyStat

WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


@dataclass(frozen=True)
class Series:
    days: list[str]
    points: list[int]
    mistakes: list[int]
    first_try: list[int]


async def recent_stats(session: AsyncSession, user_id: int, today: date, days: int = 7) -> Series:
    """Per-day series for the last `days` days, oldest first, today last. Days without lessons are zeros."""
    start = today - timedelta(days=days - 1)
    rows = await session.scalars(
        select(DailyStat).where(DailyStat.user_id == user_id, DailyStat.day >= start, DailyStat.day <= today)
    )
    by_day = {row.day: row for row in rows}
    dates = [start + timedelta(days=i) for i in range(days)]
    empty = DailyStat(points=0, mistakes=0, first_try=0)
    picked = [by_day.get(d, empty) for d in dates]
    return Series(
        days=[WEEKDAYS[d.weekday()] for d in dates],
        points=[s.points for s in picked],
        mistakes=[s.mistakes for s in picked],
        first_try=[s.first_try for s in picked],
    )
