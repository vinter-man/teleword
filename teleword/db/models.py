from datetime import date, datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(250))
    lang_code: Mapped[str | None] = mapped_column(String(10))
    is_bot: Mapped[bool] = mapped_column(default=False)
    is_blacklisted: Mapped[bool] = mapped_column(default=False)

    points: Mapped[int] = mapped_column(default=0)
    # Consecutive days with at least one finished lesson.
    streak: Mapped[int] = mapped_column(default=0)
    last_lesson_date: Mapped[date | None]
    created_at: Mapped[date]

    examples: Mapped[list["Example"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    stats: Mapped[list["DailyStat"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    api_key: Mapped["ApiKey | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Example(Base):
    """A sentence the user met in the wild; one example can teach several words."""

    __tablename__ = "examples"
    __table_args__ = (UniqueConstraint("user_id", "text"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(400))

    user: Mapped[User] = relationship(back_populates="examples")
    words: Mapped[list["Word"]] = relationship(
        back_populates="example", cascade="all, delete-orphan", passive_deletes=True
    )


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    example_id: Mapped[int] = mapped_column(ForeignKey("examples.id", ondelete="CASCADE"), index=True)
    word: Mapped[str] = mapped_column(String(135))
    description: Mapped[str] = mapped_column(String(400))
    # Part of speech ("Noun", "Verb", ...) used to pick plausible wrong answers.
    category: Mapped[str | None] = mapped_column(String(20))
    # Grows with mistakes, shrinks with correct answers: higher = needs more practice.
    rating: Mapped[int] = mapped_column(default=0)

    example: Mapped[Example] = relationship(back_populates="words")


class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date]
    first_try: Mapped[int] = mapped_column(default=0)
    mistakes: Mapped[int] = mapped_column(default=0)
    points: Mapped[int] = mapped_column(default=0)


class ApiKey(Base):
    """One key per user. Only the SHA-256 hash is stored; the plain key is shown to the user once."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=False)
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="api_key")
