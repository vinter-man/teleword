from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.db.models import User


async def get_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    return await session.scalar(select(User).where(User.tg_id == tg_id))


async def get_or_create(
    session: AsyncSession,
    *,
    tg_id: int,
    username: str | None,
    lang_code: str | None,
    is_bot: bool,
    today: date,
) -> tuple[User, bool]:
    """Returns (user, created). Keeps the stored nickname in sync with the Telegram username."""
    nickname = username or f"user{tg_id}"
    user = await get_by_tg_id(session, tg_id)
    if user is not None:
        if user.nickname != nickname:
            user.nickname = nickname
        return user, False

    user = User(tg_id=tg_id, nickname=nickname, lang_code=lang_code, is_bot=is_bot, created_at=today)
    session.add(user)
    await session.flush()
    return user, True


async def set_blacklisted(session: AsyncSession, tg_id: int, value: bool) -> User | None:
    user = await get_by_tg_id(session, tg_id)
    if user is not None:
        user.is_blacklisted = value
        await session.flush()
    return user


async def list_blacklisted(session: AsyncSession) -> list[User]:
    return list(await session.scalars(select(User).where(User.is_blacklisted).order_by(User.id)))


async def list_active_tg_ids(session: AsyncSession) -> list[int]:
    return list(await session.scalars(select(User.tg_id).where(~User.is_blacklisted).order_by(User.id)))
