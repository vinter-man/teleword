import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from teleword.bot.handlers import ROUTERS
from teleword.bot.middlewares import DbSessionMiddleware, UserMiddleware
from teleword.config import Settings
from teleword.db import create_engine, create_sessionmaker

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Let's start"),
    BotCommand(command="add", description="Add a new word"),
    BotCommand(command="lesson", description="Start a lesson"),
    BotCommand(command="statistic", description="Your progress"),
    BotCommand(command="data", description="Download your words"),
    BotCommand(command="change", description="Edit or delete your data"),
    BotCommand(command="api", description="Get a REST API key"),
    BotCommand(command="time", description="Bot time"),
    BotCommand(command="help", description="All commands"),
    BotCommand(command="cancel", description="Cancel the current action"),
]


def create_dispatcher(storage: BaseStorage, **workflow_data) -> Dispatcher:
    """Workflow data must provide `settings`, `sessionmaker` and `http` (an httpx.AsyncClient)."""
    dispatcher = Dispatcher(storage=storage, **workflow_data)
    dispatcher.update.outer_middleware(DbSessionMiddleware())
    dispatcher.update.outer_middleware(UserMiddleware())
    dispatcher.include_routers(*ROUTERS)
    return dispatcher


def create_storage(settings: Settings) -> BaseStorage:
    if settings.redis_url:
        return RedisStorage.from_url(settings.redis_url)
    logger.warning("REDIS_URL is not set: conversation state will be lost on restart")
    return MemoryStorage()


async def run(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    storage = create_storage(settings)
    bot = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    async with httpx.AsyncClient() as http:
        dispatcher = create_dispatcher(
            storage, settings=settings, sessionmaker=create_sessionmaker(engine), http=http
        )
        try:
            await bot.set_my_commands(COMMANDS)
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Bot @%s started", (await bot.get_me()).username)
            await dispatcher.start_polling(bot, handle_signals=True)
        finally:
            await storage.close()
            await bot.session.close()
            await engine.dispose()
