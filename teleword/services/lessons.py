"""Lesson building, answer checking and result bookkeeping.

A lesson is 15 multiple-choice tasks. The five words with the highest rating (the ones the user
struggles with most) open the lesson as "work on mistakes" and close it as the "final boss";
the middle is filled with random other words. Even tasks ask for the description of a word,
odd tasks ask for the word by its description.
"""

import random
from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.db.models import DailyStat, Example, User, Word
from teleword.services import vocabulary
from teleword.services.streak import streak_after_lesson

LESSON_SIZE = 15
OPTION_KEYS = ("a", "b", "c", "d")
HARD_WORDS = 5
HARD_WORDS_FIRST = 3
POINTS_PER_LESSON = 15

PICK_DESCRIPTION = "pick_description"
PICK_WORD = "pick_word"


class NotEnoughWords(Exception):
    def __init__(self, have: int):
        super().__init__(f"A lesson needs at least {LESSON_SIZE} words, the user has {have}")
        self.have = have


@dataclass(frozen=True)
class Card:
    id: int
    word: str
    description: str
    example: str
    category: str | None
    rating: int

    @classmethod
    def from_word(cls, word: Word) -> "Card":
        return cls(word.id, word.word, word.description, word.example.text, word.category, word.rating)

    @property
    def key(self) -> str:
        return self.word.strip().lower()


def _pick_distractors(main: Card, pool: list[Card], rng: random.Random) -> list[Card]:
    """Three wrong answers: same part of speech first, then anything else.

    Cards spelling the same word as the main one are used only as a last resort, because they
    would be a second correct answer.
    """
    candidates = [c for c in pool if c.id != main.id]
    rng.shuffle(candidates)
    picked: list[Card] = []
    seen = {main.key}

    def take(predicate) -> None:
        for card in candidates:
            if len(picked) == len(OPTION_KEYS) - 1:
                return
            if card not in picked and predicate(card):
                picked.append(card)
                seen.add(card.key)

    take(lambda c: c.key not in seen and c.category and c.category == main.category)
    take(lambda c: c.key not in seen)
    take(lambda c: True)
    return picked


def build_lesson(cards: list[Card], rng: random.Random | None = None) -> list[dict]:
    """Builds JSON-serialisable tasks: {"word_id", "kind", "options": {"a": {...}, ...}}."""
    if len(cards) < LESSON_SIZE:
        raise NotEnoughWords(len(cards))
    rng = rng or random.Random()

    by_rating = sorted(cards, key=lambda c: c.rating, reverse=True)
    hard = by_rating[:HARD_WORDS]
    rng.shuffle(hard)
    rest = by_rating[HARD_WORDS:]
    rng.shuffle(rest)
    sequence = hard[:HARD_WORDS_FIRST] + rest[: LESSON_SIZE - HARD_WORDS] + hard[HARD_WORDS_FIRST:]

    tasks = []
    for number, main in enumerate(sequence):
        options = [main, *_pick_distractors(main, cards, rng)]
        rng.shuffle(options)
        tasks.append(
            {
                "word_id": main.id,
                "kind": PICK_DESCRIPTION if number % 2 == 0 else PICK_WORD,
                "options": {
                    key: {**asdict(card), "is_correct": card.key == main.key}
                    for key, card in zip(OPTION_KEYS, options, strict=True)
                },
            }
        )
    return tasks


def main_option(task: dict) -> dict:
    return next(o for o in task["options"].values() if o["id"] == task["word_id"])


def resolve_answer(task: dict, raw: str) -> str | None:
    """Maps user input ("b", "2", or the word itself for word tasks) to an option key."""
    answer = raw.strip().lower()
    if answer in OPTION_KEYS:
        return answer
    if answer in {"1", "2", "3", "4"}:
        return OPTION_KEYS[int(answer) - 1]
    if task["kind"] == PICK_WORD:
        for key, option in task["options"].items():
            if option["word"].strip().lower() == answer:
                return key
    return None


async def load_cards(session: AsyncSession, user_id: int) -> list[Card]:
    return [Card.from_word(w) for w in await vocabulary.list_words(session, user_id)]


@dataclass(frozen=True)
class LessonSummary:
    first_try: int
    mistakes: int
    points: int
    streak: int

    @property
    def success_percent(self) -> int:
        return round(self.first_try / LESSON_SIZE * 100)


async def finish_lesson(session: AsyncSession, user: User, results: list[dict], today: date) -> LessonSummary:
    """Applies lesson results.

    `results` holds one {"word_id", "attempts", "mistakes"} per task. Each mistake raises the word
    rating by one and the final correct answer lowers it by one.
    """
    first_try = sum(1 for r in results if r["attempts"] == 1)
    mistakes = sum(r["mistakes"] for r in results)

    ratings = {r["word_id"]: r["mistakes"] - 1 for r in results}
    words = await session.scalars(
        select(Word).join(Word.example).where(Example.user_id == user.id, Word.id.in_(ratings))
    )
    for word in words:  # words deleted mid-lesson are simply skipped
        word.rating += ratings[word.id]

    stat = await session.scalar(select(DailyStat).where(DailyStat.user_id == user.id, DailyStat.day == today))
    if stat is None:
        stat = DailyStat(user_id=user.id, day=today, first_try=0, mistakes=0, points=0)
        session.add(stat)
    stat.first_try += first_try
    stat.mistakes += mistakes
    stat.points += POINTS_PER_LESSON

    user.points += POINTS_PER_LESSON
    user.streak = streak_after_lesson(user.streak, user.last_lesson_date, today)
    user.last_lesson_date = today
    await session.flush()

    return LessonSummary(first_try, mistakes, POINTS_PER_LESSON, user.streak)
