"""
REMOVE | UPDATE
1 move >>> change | delete
2 what >>> word | descr | ex |
3 for what >>> new
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

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class UpdateData(StatesGroup):

    waiting_for_data_to_change = State()
    waiting_for_action = State()
    waiting_for_new_data = State()
    waiting_for_next_step = State()


########################################################################################################################
async def change_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(f'[{username}]: Start updating data')
    await state.reset_state(with_data=False)

    answer = text(
        bold('Small reminder:'), '\n',
        bold('1.'), r'Choose what name you want to change or delete', '\n',
        bold('2.'), r'Then choose an action \(delete \| change\)', '\n',
        bold('3.'), r'And then enter the word\, or example', '\n',
        '\n')
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    answer = text(
        emojize(r"Let\'s decide what we will change \| delete :eyes:"))
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
    buttons = ['Word', 'Description', 'Example']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    logger.info(f'[{username}]: Transfer user to the data to change choice')
    await UpdateData.waiting_for_data_to_change.set()


async def ms_get_data_type_set_action_choose(message: types.Message, state: FSMContext):
    """
    1 action
        accept the response with the user data type ('Word', 'Description', 'Example')
        set the wait to set the desired action ('Change', 'Delete')
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    possible_answers = {'word', 'description', 'example'}

    logger.info(f'[{username}]: Catch data type: "{user_text}"')

    if user_text not in possible_answers:
        logger.info(f'[{username}] Incorrect data type "{user_text}"')
        answer = text(
            emojize(':police_car: Something is wrong here'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            italic('You can only work with your own words, descriptions and examples: '),
                                                            bold(f'{" | ".join(possible_answers)}\n'),
            '\n',
            r'Try it again\, just entering your answer below\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(user_data_type_to_change=user_text)

    answer = text(
        fr"Okay, now choose what you want to do with your {user_text}")
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
    # buttons = ['In order of addition', 'In alphabetical order', 'By importance']
    # keyboard.add(*buttons)
    # await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    # logger.info(f'[{username}]: Jump to order key input')
    # await SendData.waiting_for_order_key.set()


########################################################################################################################
def register_updating_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register updating handlers')
