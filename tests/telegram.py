"""Drives the real dispatcher with fake updates and records what the bot sends back, without network."""

from collections.abc import AsyncGenerator
from datetime import datetime
from itertools import count
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetMe, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from teleword.bot.app import create_dispatcher

BOT_ID = 42
ERROR_TEXT = "Something went wrong"


def build_dispatcher() -> Dispatcher:
    return create_dispatcher(MemoryStorage())


class FakeTelegramSession(BaseSession):
    """Answers every Bot API call locally and keeps the calls for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self._ids = count(1000)

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:  # noqa: ASYNC109
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=BOT_ID, is_bot=True, first_name="Teleword", username="teleword_test_bot")
        returning = str(method.__returning__)
        if "Message" in returning and hasattr(method, "chat_id"):
            return Message.model_validate(
                {
                    "message_id": next(self._ids),
                    "date": datetime.now(),
                    "chat": {"id": method.chat_id, "type": "private"},
                    "text": getattr(method, "text", None),
                },
                context={"bot": bot},
            )
        return True

    async def stream_content(self, *args, **kwargs) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError
        yield b""

    async def close(self) -> None:
        pass


class BotHarness:
    def __init__(self, dispatcher: Dispatcher, session: FakeTelegramSession, **deps: Any) -> None:
        self.dispatcher = dispatcher
        self.session = session
        self.bot = Bot("42:TEST", session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.deps = deps
        self._update_ids = count(1)
        self._message_ids = count(1)

    async def close(self) -> None:
        await self.bot.session.close()

    @staticmethod
    def _user(user_id: int, username: str | None) -> User:
        return User(id=user_id, is_bot=False, first_name="Test", username=username, language_code="en")

    async def _feed(self, update: Update, allow_error: bool) -> list[TelegramMethod]:
        before = len(self.session.calls)
        await self.dispatcher.feed_update(self.bot, update, **self.deps)
        calls = self.session.calls[before:]
        if not allow_error:
            assert not any(ERROR_TEXT in (getattr(c, "text", None) or "") for c in calls), "handler failed"
        return calls

    async def send(
        self, text: str, user_id: int = 1, username: str | None = "alice", allow_error: bool = False
    ) -> list[TelegramMethod]:
        message = Message(
            message_id=next(self._message_ids),
            date=datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=self._user(user_id, username),
            text=text,
        )
        return await self._feed(Update(update_id=next(self._update_ids), message=message), allow_error)

    async def click(
        self, data: str, user_id: int = 1, username: str | None = "alice", allow_error: bool = False
    ) -> list[TelegramMethod]:
        callback = CallbackQuery(
            id=str(next(self._update_ids)),
            from_user=self._user(user_id, username),
            chat_instance="test",
            data=data,
            message=Message(
                message_id=next(self._message_ids),
                date=datetime.now(),
                chat=Chat(id=user_id, type="private"),
                from_user=User(id=BOT_ID, is_bot=True, first_name="Teleword"),
                text="previous bot message",
            ),
        )
        return await self._feed(
            Update(update_id=next(self._update_ids), callback_query=callback), allow_error
        )

    async def state_data(self, user_id: int = 1) -> dict:
        context = self.dispatcher.fsm.get_context(self.bot, chat_id=user_id, user_id=user_id)
        return await context.get_data()

    async def state(self, user_id: int = 1) -> str | None:
        context = self.dispatcher.fsm.get_context(self.bot, chat_id=user_id, user_id=user_id)
        return await context.get_state()


def texts(calls: list[TelegramMethod]) -> list[str]:
    """Texts and captions of everything the bot sent."""
    return [t for c in calls if (t := getattr(c, "text", None) or getattr(c, "caption", None))]


def joined(calls: list[TelegramMethod]) -> str:
    return "\n".join(texts(calls))


def buttons(calls: list[TelegramMethod]) -> dict[str, str]:
    """Inline button text -> callback data, from the last message that had a keyboard."""
    for call in reversed(calls):
        markup = getattr(call, "reply_markup", None)
        if markup is not None and hasattr(markup, "inline_keyboard"):
            return {b.text: b.callback_data for row in markup.inline_keyboard for b in row}
    return {}


def of_type(calls: list[TelegramMethod], method_type: type) -> list:
    return [c for c in calls if isinstance(c, method_type)]
