import asyncio
import logging
import sys
import time
from sqlalchemy import exc

import aiogram.utils.exceptions
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.contrib.fsm_storage.redis import RedisStorage2

from config import config
from app.handlers.common import register_handlers_common
from app.handlers.adding import register_adding_handlers
from app.handlers.lessons import register_lesson_handlers
from app.handlers.statistic import register_statistic_handlers
from app.handlers.checking import register_checking_handlers
from app.handlers.updating import register_updating_handlers
from app.handlers.api import register_api_handlers


logger = logging.getLogger(__name__)


########################################################################################################################
async def set_commands(bot: Bot):
    """
    Sets valid bot hint commands
    """
    commands = [
        BotCommand(command="/start", description="Greetings"),
        BotCommand(command="/help", description="View commands"),
        BotCommand(command="/cancel", description="Cancel current action")
    ]
    await bot.set_my_commands(commands)


async def main():
    """
    Assembly and launch of all functions of the part of the telegram bot
    """
    # Setting up logging to stdout
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )
    logger.info("Starting bot")

    # Declaration and initialization of bot and dispatcher objects
    bot = Bot(token=config.TOKEN_TG)
    storage = RedisStorage2(host=config.REDIS_HOST,
                            port=config.REDIS_PORT,
                            password=config.REDIS_PASSWORD
                            )
    dp = Dispatcher(bot, storage=storage)    # redis + mysql + search engine ElasticSearch

    # Handlers registration
    register_handlers_common(dp, config.ADMIN_ID_TG)
    register_adding_handlers(dp)
    register_lesson_handlers(dp)
    register_statistic_handlers(dp)
    register_checking_handlers(dp)
    register_updating_handlers(dp)
    register_api_handlers(dp)

    # Setting commands
    await set_commands(bot)

    # Start pooling after skipping the updates
    await dp.skip_updates()
    await dp.start_polling()


########################################################################################################################
if __name__ == '__main__':     # You can run separately only the telegram part from this module
    while True:
        try:
            asyncio.run(main())
        except aiogram.utils.exceptions.NetworkError as e:
            second = 2.5
            logger.error(f'NetworkError. Restart after {second} (sec.) \n\n{e}\n\n')
            time.sleep(second)
        except exc.DatabaseError as e:
            second = 0.5
            logger.error(f'MySQL server NetworkError. Restart after {second} (sec.) \n\n{e}\n\n')
            time.sleep(second)
