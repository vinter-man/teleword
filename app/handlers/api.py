import asyncio
import copy
import logging
import sys
import time
import collections
import random
import os
import phonenumbers
import re

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram.dispatcher.filters import Text
from config.config import APP_KEY_OXF, APP_ID_OXF, URL_OXF, ADMIN_ID_TG

from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class ApiKeyRequest(StatesGroup):

    waiting_for_purpose = State()
    waiting_for_phone = State()


########################################################################################################################
async def api_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(fr'[{username}]: Start /api command')
    await state.reset_state(with_data=False)

    try:
        sql_user = db_worker.get_user(tg_id=message.from_user.id)
        is_api = db_worker.is_api_keys(
            user=sql_user
        )
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
            emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                       r"please write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    if is_api:     # user is already has an api_keys
        answer = text(
            r'If you still do not have a private api key \- contact the administrator'
        )
        remove_keyboard = types.ReplyKeyboardRemove()
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    else:          # register new keys
        answer = text(
            emojize(r'There are only a couple of steps left to your private api key :key:')
        )
        remove_keyboard = types.ReplyKeyboardRemove()
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)
        answer = text(
            emojize(r'Tell us what you would like to use the bot API for \(feel free to describe\)')
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await state.update_data(
        purpose=None,
        phone=None,
    )

    logger.info(f'[{username}]: Jump to purpose input')
    await ApiKeyRequest.waiting_for_purpose.set()


async def ms_get_purpose_set_phone_input(message: types.Message, state: FSMContext):
    """
    1 action
        accept the response with the purpose
        set the wait to a phone number
    """
    username = message.from_user.username
    user_text = message.text

    logger.info(f'[{username}]: Catch user api`s purpose: "{user_text}"')

    if len(user_text) < 40:
        logger.info(f'[{username}] Incorrect purpose - too small "{user_text}"')
        answer = text(
            emojize(':police_car: Be bold'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            r'please describe what you would like to use the bot API for in more detail\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        r"Great\, now enter your phone number where you will receive your private api key")
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    await state.update_data(
        purpose=user_text,
    )

    logger.info(f'[{username}]: Jump to phone number input')
    await ApiKeyRequest.waiting_for_phone.set()


async def ms_get_phone_sql_admin_send(message: types.Message, state: FSMContext):
    """
    2 action
        accept the response with the phone number
        make sql func
        send admin req
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    pattern = re.compile(r'\(?([0-9]{3})\)?([ .-]?)([0-9]{3})\2([0-9]{4})')

    logger.info(f'[{username}]: Catch user phone number: "{user_text}"')

    if not pattern.findall(user_text):
        logger.info(f'[{username}] Incorrect phone number "{user_text}"')
        answer = text(
            emojize(r':police_car: Either our number filter is wrong\, or you have entered an invalid number '), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            r'Please try again', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)

    await state.update_data(
        phone=user_text,
    )

    data = await state.get_data()
    phone_number = data.get('phone')
    purpose = data.get('purpose')

    try:
        sql_user = db_worker.get_user(tg_id=message.from_user.id)
        db_worker.generate_api_keys(
            user=sql_user
        )
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
            emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                       r"please write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        answer = text(
            bold('API private key request'), '\n',
            r'Phone\:', code(f' {phone_number}'), '\n',
            r'Purpose\:', italic(f' {purpose}'), '\n',
            r'Key to send\:', code(f' {db_worker.get_user_api_key(user=sql_user)}'), '\n',
        )
        await message.bot.send_message(ADMIN_ID_TG, answer, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f'[{username}]: Houston, we have got a problem {e}')
        answer = text(
            emojize(":man_mechanic:"), r"There was a big trouble when searching for you in the database\, "
                                       r"please write to the administrator\.")
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        r"Cool\, now all you have to do is wait for the admin to give you a private token")
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    logger.info(f'[{username}]: Finish /api command')

    await state.reset_state(with_data=False)


########################################################################################################################
def register_api_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register api handlers')

    dp.register_message_handler(api_cmd, commands=['api'], state='*')
    dp.register_message_handler(ms_get_purpose_set_phone_input, state=ApiKeyRequest.waiting_for_purpose)
    dp.register_message_handler(ms_get_phone_sql_admin_send, state=ApiKeyRequest.waiting_for_phone)
