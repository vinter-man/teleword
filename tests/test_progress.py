"""Lesson results, daily statistics and the weekly chart."""

from datetime import timedelta

from sqlalchemy import select

from teleword.bot.charts import render_stats_chart
from teleword.db.models import DailyStat
from teleword.services import lessons, stats, vocabulary
from teleword.services.starter_words import STARTER_WORDS, add_starter_words
from tests.conftest import TODAY


async def lesson_results(session, user, mistakes_for_first: int = 0) -> list[dict]:
    cards = await lessons.load_cards(session, user.id)
    tasks = lessons.build_lesson(cards)
    results = [{"word_id": t["word_id"], "attempts": 1, "mistakes": 0} for t in tasks]
    results[0] = {**results[0], "attempts": mistakes_for_first + 1, "mistakes": mistakes_for_first}
    return results


async def test_starter_words_are_idempotent(session, user):
    await add_starter_words(session, user)
    await add_starter_words(session, user)
    assert await vocabulary.count_words(session, user.id) == len(STARTER_WORDS) == 15


async def test_finish_lesson_updates_everything(session, user):
    await add_starter_words(session, user)
    results = await lesson_results(session, user, mistakes_for_first=2)

    summary = await lessons.finish_lesson(session, user, results, TODAY)

    assert (summary.first_try, summary.mistakes, summary.points, summary.streak) == (14, 2, 15, 1)
    assert summary.success_percent == 93
    ratings = {w.id: w.rating for w in await vocabulary.list_words(session, user.id)}
    assert ratings[results[0]["word_id"]] == 1  # two mistakes, one correct answer
    assert ratings[results[1]["word_id"]] == -1
    assert user.points == 15
    assert user.last_lesson_date == TODAY


async def test_daily_stat_accumulates_and_streak_counts_days(session, user):
    await add_starter_words(session, user)
    await lessons.finish_lesson(session, user, await lesson_results(session, user), TODAY)
    await lessons.finish_lesson(session, user, await lesson_results(session, user, 1), TODAY)

    stat = await session.scalar(select(DailyStat).where(DailyStat.user_id == user.id))
    assert (stat.first_try, stat.mistakes, stat.points) == (29, 1, 30)
    assert user.streak == 1

    tomorrow = TODAY + timedelta(days=1)
    summary = await lessons.finish_lesson(session, user, await lesson_results(session, user), tomorrow)
    assert summary.streak == 2


async def test_finish_lesson_skips_words_deleted_mid_lesson(session, user):
    await add_starter_words(session, user)
    results = await lesson_results(session, user)
    await vocabulary.delete_word(session, await vocabulary.get_word(session, user.id, results[0]["word_id"]))

    summary = await lessons.finish_lesson(session, user, results, TODAY)
    assert summary.first_try == 15


async def test_recent_stats_fills_gaps_with_zeros(session, user):
    session.add_all(
        [
            DailyStat(user_id=user.id, day=TODAY, first_try=10, mistakes=3, points=15),
            DailyStat(user_id=user.id, day=TODAY - timedelta(days=2), first_try=5, mistakes=9, points=30),
            DailyStat(user_id=user.id, day=TODAY - timedelta(days=30), first_try=1, mistakes=1, points=99),
        ]
    )
    await session.flush()

    series = await stats.recent_stats(session, user.id, TODAY)

    assert series.points == [0, 0, 0, 0, 30, 0, 15]
    assert series.mistakes == [0, 0, 0, 0, 9, 0, 3]
    assert series.first_try == [0, 0, 0, 0, 5, 0, 10]
    assert series.days[-1] == "Su"  # 2026-10-18 is a Sunday
    assert series.days == ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def test_chart_is_a_png():
    series = stats.Series(["Mo", "Tu", "We"], [15, 0, 30], [2, 0, 5], [10, 0, 14])
    assert render_stats_chart(series).startswith(b"\x89PNG")
    empty = stats.Series(["Mo"], [0], [0], [0])
    assert render_stats_chart(empty).startswith(b"\x89PNG")
