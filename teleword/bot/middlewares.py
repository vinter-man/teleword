import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import TelegramObject, User

from teleword.config import Settings
from teleword.services import users

logger = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    """One database session per update, committed when the handler succeeds and rolled back otherwise.

    The sessionmaker comes from the dispatcher workflow data, so tests can swap it per update.
    """

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with data["sessionmaker"]() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result


class UserMiddleware(BaseMiddleware):
    """Registers unknown users on their first update and silently drops updates from blacklisted users."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user: User | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        settings: Settings = data["settings"]
        session = data["session"]
        user, created = await users.get_or_create(
            session,
            tg_id=tg_user.id,
            username=tg_user.username,
            lang_code=tg_user.language_code,
            is_bot=tg_user.is_bot,
            today=settings.today(),
        )
        # Release the SQLite write lock before the handler starts doing slow network calls.
        await session.commit()
        if created:
            logger.info("New user %s (%s)", user.nickname, user.tg_id)

        if user.is_blacklisted and tg_user.id != settings.admin_id:
            logger.info("Ignoring update from blacklisted user %s", tg_user.id)
            return None

        data["user"] = user
        return await handler(event, data)


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject, event_from_user: User, settings: Settings) -> bool:
        return event_from_user.id == settings.admin_id
