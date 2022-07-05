import asyncio
import logging
import sys
import time

import aiogram.utils.exceptions
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.contrib.fsm_storage.redis import RedisStorage2

from config import config
from app.handlers.common import register_handlers_common
from app.handlers.adding import register_adding_handlers
from app.handlers.lessons import register_lesson_handlers


logger = logging.getLogger(__name__)


########################################################################################################################
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Greetings"),
        BotCommand(command="/help", description="View commands"),
        BotCommand(command="/cancel", description="Cancel current action")
    ]
    await bot.set_my_commands(commands)


async def main():
    # Setting up logging to stdout
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )
    logger.info("Starting bot")

    # Declaration and initialization of bot and dispatcher objects
    bot = Bot(token=config.TOKEN_TG)
    storage = RedisStorage2(host='redis-11777.c293.eu-central-1-1.ec2.cloud.redislabs.com',
                            port=11777,
                            password='RLSHxZNn3NKF50b56mT1fpq7QoKVwuyy'
                            )
    dp = Dispatcher(bot, storage=storage)    # redis + mysql + search engine ElasticSearch

    # Handlers registration
    register_handlers_common(dp, config.ADMIN_ID_TG)
    register_adding_handlers(dp)
    register_lesson_handlers(dp)
    # register_handlers_drinks(dp)
    # register_handlers_food(dp)

    # Setting commands
    await set_commands(bot)

    # Start pooling after skipping the updates
    await dp.skip_updates()
    await dp.start_polling()


########################################################################################################################
while True:
    try:
        if __name__ == '__main__':
            asyncio.run(main())
    except aiogram.utils.exceptions.NetworkError as e:
        second = 2.5
        logger.error(f'NetworkError. Restart after {second} (sec.) \n\n{e}\n\n')
        time.sleep(second)
