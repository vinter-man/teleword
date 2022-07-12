"""
CHECKING STATISTIC (all mysql skills)
1 print list where
(calendar(date, first try successes, mistakes, total words repeated ), shock_mode counter, 3 most important words)
"""


import asyncio
import copy
import logging
import sys
import time
import collections
import random

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram.dispatcher.filters import Text
from config.config import APP_KEY_OXF, APP_ID_OXF, URL_OXF

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
async def statistic_cmd(message: types.Message, state: FSMContext):

    username = message.from_user.username
    logger.info(f'{username} Start statistic')
    await state.reset_state(with_data=False)

    answer = text(
        emojize(r"Wait until we prepare your statistics \- it may take some time "
                                                    r":new_moon_with_face::chart_with_upwards_trend: "))
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)

    try:
        user = db_worker.get_user(tg_id=message.from_user.id)
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e, user_db}')
        answer = text(
            emojize(":oncoming_police_car:"), r"There was a big trouble when compiling your test\, "
                                              r"please write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        # * write subpartition / sql subquery
        total_words_count = db_worker.word_count(user_tg_id=message.from_user.id)
    except Exception as e:
        logger.error(f'{username} Houston, we have got a problem {e, message.from_user.id}')
        total_words_count = 'error, please write to the admin'

    answer = text(
        emojize(':stopwatch: Shock mode\n'),
        bold(f'{user.shock_mode} days\n'),
        '\n',
        emojize(':airplane_arriving: First Use\n'),
        bold(f'{user.creation_time}\n'),
        '\n',
        emojize(':gem: Total points\n'),
        bold(f'{user.points} points\n'),
        '\n',
        emojize(':blue_book: Total words\n'),
        bold(f'{total_words_count} words\n'),
        '\n')

    # photo = * drawing a graph from statistics data over the past 7 days
    photo = 'https://i.ytimg.com/vi/if-2M3K1tqk/maxresdefault.jpg'

    await message.answer_photo(
        photo=photo,
        caption=answer,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    logger.info(f'{username} Statistical data successfully sent to the user')


########################################################################################################################
def register_statistic_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register statistic handlers')
    dp.register_message_handler(statistic_cmd, commands=['statistic'], state='*')

