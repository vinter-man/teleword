"""Daily streak: the number of consecutive days with at least one finished lesson."""

from datetime import date, timedelta


def streak_after_lesson(streak: int, last_lesson: date | None, today: date) -> int:
    if last_lesson == today:
        return max(streak, 1)
    if last_lesson == today - timedelta(days=1):
        return streak + 1
    return 1


def current_streak(streak: int, last_lesson: date | None, today: date) -> int:
    """The streak as of today: it is still alive if the last lesson was today or yesterday."""
    if last_lesson is None or (today - last_lesson).days > 1:
        return 0
    return streak
