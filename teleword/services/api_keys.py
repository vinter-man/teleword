"""API keys: users request one in the bot, the admin approves, the user receives it in a private message."""

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from teleword.db.models import ApiKey, User

PURPOSE_LIMITS = (20, 1000)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def get(session: AsyncSession, user_id: int) -> ApiKey | None:
    return await session.scalar(select(ApiKey).where(ApiKey.user_id == user_id))


async def request(session: AsyncSession, user: User, purpose: str) -> ApiKey:
    record = await get(session, user.id)
    if record is None:
        record = ApiKey(user_id=user.id, purpose=purpose)
        session.add(record)
    else:
        record.purpose = purpose
    await session.flush()
    return record


async def _issue(session: AsyncSession, record: ApiKey) -> str:
    key = secrets.token_urlsafe(32)
    record.key_hash = hash_key(key)
    record.is_active = True
    await session.flush()
    return key


async def approve(session: AsyncSession, user_id: int) -> str | None:
    """Activates a pending request and returns the plain key, or None if there is no request."""
    record = await get(session, user_id)
    if record is None:
        return None
    return await _issue(session, record)


async def rotate(session: AsyncSession, user_id: int) -> str | None:
    """Replaces an active key with a new one; the old key stops working immediately."""
    record = await get(session, user_id)
    if record is None or not record.is_active:
        return None
    return await _issue(session, record)


async def reject(session: AsyncSession, user_id: int) -> bool:
    record = await get(session, user_id)
    if record is None:
        return False
    await session.delete(record)
    await session.flush()
    return True


async def authenticate(session: AsyncSession, key: str) -> User | None:
    record = await session.scalar(
        select(ApiKey)
        .where(ApiKey.key_hash == hash_key(key), ApiKey.is_active)
        .options(selectinload(ApiKey.user))
    )
    if record is None or record.user.is_blacklisted:
        return None
    return record.user
