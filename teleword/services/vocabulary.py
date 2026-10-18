"""Words and examples: validation and CRUD scoped to a single user."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from teleword.db.models import Example, User, Word

LIMITS = {
    "example": (5, 400),
    "word": (1, 135),
    "description": (1, 400),
}


class ValidationError(ValueError):
    pass


def validate(field: str, value: str) -> str:
    """Strips the value and checks it against the field length limits."""
    value = (value or "").strip()
    low, high = LIMITS[field]
    if not low <= len(value) <= high:
        raise ValidationError(f"The {field} must be {low}-{high} characters long, yours is {len(value)}.")
    return value


async def add_entry(
    session: AsyncSession, user: User, example: str, word: str, description: str, category: str | None
) -> Word:
    """Adds a word with its example. An identical example of the same user is reused."""
    example_obj = await find_example(session, user.id, example)
    if example_obj is None:
        example_obj = Example(user_id=user.id, text=example)
        session.add(example_obj)
        await session.flush()

    existing = await session.scalar(
        select(Word).where(
            Word.example_id == example_obj.id, Word.word == word, Word.description == description
        )
    )
    if existing:
        return existing

    word_obj = Word(example_id=example_obj.id, word=word, description=description, category=category)
    session.add(word_obj)
    await session.flush()
    await session.refresh(word_obj, ["example"])
    return word_obj


def _user_words(user_id: int):
    return (
        select(Word).join(Word.example).where(Example.user_id == user_id).options(selectinload(Word.example))
    )


async def list_words(session: AsyncSession, user_id: int) -> list[Word]:
    return list(await session.scalars(_user_words(user_id).order_by(Word.id)))


async def count_words(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(
        select(func.count(Word.id)).join(Word.example).where(Example.user_id == user_id)
    )


async def get_word(session: AsyncSession, user_id: int, word_id: int) -> Word | None:
    return await session.scalar(_user_words(user_id).where(Word.id == word_id))


async def find_word(
    session: AsyncSession, user_id: int, *, word: str | None = None, description: str | None = None
) -> Word | None:
    """Case-insensitive lookup by the word text or by the description; returns the oldest match."""
    query = _user_words(user_id).order_by(Word.id).limit(1)
    if word is not None:
        query = query.where(func.lower(Word.word) == word.strip().lower())
    elif description is not None:
        query = query.where(func.lower(Word.description) == description.strip().lower())
    else:
        raise ValueError("word or description is required")
    return await session.scalar(query)


def _user_examples(user_id: int):
    return select(Example).where(Example.user_id == user_id).options(selectinload(Example.words))


async def list_examples(session: AsyncSession, user_id: int) -> list[Example]:
    return list(await session.scalars(_user_examples(user_id).order_by(Example.id)))


async def get_example(session: AsyncSession, user_id: int, example_id: int) -> Example | None:
    return await session.scalar(_user_examples(user_id).where(Example.id == example_id))


async def find_example(session: AsyncSession, user_id: int, text: str) -> Example | None:
    return await session.scalar(
        _user_examples(user_id)
        .where(func.lower(Example.text) == text.strip().lower())
        .order_by(Example.id)
        .limit(1)
    )


async def update_example(session: AsyncSession, example: Example, text: str) -> Example:
    duplicate = await find_example(session, example.user_id, text)
    if duplicate and duplicate.id != example.id:
        raise ValidationError(f"You already have this example (id {duplicate.id}).")
    example.text = text
    await session.flush()
    return example


async def delete_word(session: AsyncSession, word: Word) -> None:
    """Deletes the word, and its example too if no other words use it."""
    example = await session.get(Example, word.example_id, options=[selectinload(Example.words)])
    await session.delete(word)
    await session.flush()
    if example is not None:
        await session.refresh(example, ["words"])
        if not example.words:
            await session.delete(example)
            await session.flush()


async def delete_example(session: AsyncSession, example: Example) -> None:
    """Deletes the example together with all its words."""
    await session.delete(example)
    await session.flush()
