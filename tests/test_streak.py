from datetime import date, timedelta

import pytest

from teleword.services.streak import current_streak, streak_after_lesson

TODAY = date(2026, 10, 18)
YESTERDAY = TODAY - timedelta(days=1)
LONG_AGO = TODAY - timedelta(days=5)


@pytest.mark.parametrize(
    ("streak", "last", "expected"),
    [
        (0, None, 1),  # first lesson ever
        (3, YESTERDAY, 4),  # streak continues
        (3, TODAY, 3),  # second lesson on the same day
        (0, TODAY, 1),
        (7, LONG_AGO, 1),  # streak broken, starts again
    ],
)
def test_streak_after_lesson(streak, last, expected):
    assert streak_after_lesson(streak, last, TODAY) == expected


@pytest.mark.parametrize(
    ("streak", "last", "expected"),
    [(0, None, 0), (4, TODAY, 4), (4, YESTERDAY, 4), (4, LONG_AGO, 0)],
)
def test_current_streak(streak, last, expected):
    assert current_streak(streak, last, TODAY) == expected
