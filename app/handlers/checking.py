"""
CHECK DB AND SEND IT TO USER (all mysql skills)
1 default check (ordering by date, all results, examples - words with descriptions, exel)
2 custom check
    2.1 SUB-QUERIES >>> SELECT word FROM words WHERE rating > (SELECT AVG(rating) FROM words) ORDER BY Salary DESC;
"""

import asyncio
import copy
import logging
import sys
import time
import collections
import random
import os

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
class SendData(StatesGroup):

    waiting_for_filter = State()
    waiting_for_order_key = State()
    waiting_for_file_type = State()


########################################################################################################################
async def data_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    logger.info(fr'[{username}]: Start /data command')
    await state.reset_state(with_data=False)

    answer1 = text(
        emojize(r'Soon we will send you a file with your words :ship:'))
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer1, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    answer2 = text(
        r"First of all\, let\'s decide on the quantity")
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
    buttons = ['All my words', 'Most important words']
    keyboard.add(*buttons)
    await message.answer(answer2, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    await state.update_data(
        filter_key=None,
        sort_key=None,
    )

    logger.info(f'[{username}]: Jump to filter input')
    await SendData.waiting_for_filter.set()


async def ms_get_filter_set_order_key_choose(message: types.Message, state: FSMContext):
    """
    1 action
        accept the response with the desired data filtering
        set the wait to set the desired order key
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    possible_answers = {'all my words', 'most important words'}

    logger.info(f'[{username}]: Catch filter: "{user_text}"')

    if user_text not in possible_answers:
        logger.info(f'[{username}] Incorrect filter "{user_text}"')
        answer = text(
            emojize(':police_car: Something is wrong here'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            italic('So far we have only the following answers: '), bold(f'{" | ".join(possible_answers)}\n'),
            '\n',
            r'Try it again\, just entering your answer below\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        r"Great\, now tell me by which parameter I should sort your words")
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
    buttons = ['In order of addition', 'In alphabetical order', 'By importance']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    await state.update_data(
        filter_key=user_text,
    )

    logger.info(f'[{username}]: Jump to order key input')
    await SendData.waiting_for_order_key.set()


async def ms_get_order_key_set_file_type_choose(message: types.Message, state: FSMContext):
    """
    2 action
        accept the response with the order key
        set the wait to set the desired file type
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    possible_answers = {'in order of addition', 'in alphabetical order', 'by importance'}

    logger.info(f'[{username}]: Catch order key: "{user_text}"')

    if user_text not in possible_answers:
        logger.info(f'[{username}] Incorrect order key "{user_text}"')
        answer = text(
            emojize(r":police_car: There\'s something wrong here"), italic(
                f'"{message.text if len(message.text) <= 20 else message.text[:12] + "..."}"\n'),
            '\n',
            italic('The following sort keys are available: '), bold(f'{" | ".join(possible_answers)}\n'),
            '\n',
            r'Try it again\, just entering your answer below\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    answer = text(
        r"Excellent\, now the last question in which formats would you most conveniently get your words\:", '\n',
        bold('1. exel\n'),
        bold('2. json\n'),
        bold('3. xml\n'),
        bold('4. csv\n'),
        '\n')
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = ['1', '2', '3', '4']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    await state.update_data(
        sort_key=user_text,
    )

    logger.info(f'[{username}]: Jump to file type input')
    await SendData.waiting_for_file_type.set()


async def ms_get_file_type_send_data(message: types.Message, state: FSMContext):
    """
    3 action
        accepts file types list
        form data from sql
        send file
    """
    username = message.from_user.username
    answers = message.text.lower().strip().split()
    possible_answers = {'1': 'xlsx', '2': 'json', '3': 'xml', '4': 'csv'}
    data = await state.get_data()
    filter_key = data['filter_key']
    sort_key = data['sort_key']

    logger.info(f'[{username}]: Catch file types: "{answers}"')

    answer = text(
        emojize(r'Starting to process your request \- this may take some time :man_cook:'))
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

    for file_type_answer in answers:
        await message.bot.send_chat_action(message.from_user.id, ChatActions.UPLOAD_DOCUMENT)
        if file_type_answer not in possible_answers:
            logger.info(f'[{username}] Incorrect file type "{file_type_answer}"')
            answer = text(
                emojize(r":police_car: There\'s not right here"), italic(
                    f'"{file_type_answer if len(file_type_answer) <= 12 else file_type_answer[:12] + "..."}"\n'),
                '\n',
                italic('You can choose one of the numbers'), bold(f'{" | ".join(possible_answers)}\n'),
                italic(' or write the desired numbers separated by a space.'),
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            file_type = possible_answers[file_type_answer]
            logger.info(f'[{username}]: Start working on a file with user data {file_type, filter_key, sort_key}')
            try:
                document = db_worker.create_file_with_user_words(
                    user_tg_id=str(message.from_user.id),
                    file_path='temporary',
                    file_type=file_type,
                    sql_filter_key=filter_key,
                    sql_sort_key=sort_key
                )
            except Exception as e:
                logger.error(f'[{username}]: Houston, we have got a problem {e, file_type, filter_key, sort_key}')
                answer = text(
                    emojize(":man_mechanic:"), r"There was a big trouble when compiling your document\, "
                                                                        r"please write to the administrator\.")
                await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                try:
                    answer = text(
                        r"Done\, here are your words\, enjoy", emojize(":cake:"))
                    await message.answer_document(
                        document=types.InputFile(document),
                        caption=answer,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                except Exception as e:
                    logger.error(f'[{username}]: Houston, we have got a problem {e, document}')
                    answer = text(
                        emojize(":man_mechanic:"), r"There was a big trouble when sending your document\, "
                                                                       r"please write to the administrator\.")
                    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
                finally:
                    os.remove(document)

    logger.info(f'[{username}]: Finish data files sending')
    await state.reset_state(with_data=False)


########################################################################################################################
def register_checking_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register checking handlers')

    dp.register_message_handler(data_cmd, commands=['data'], state='*')
    dp.register_message_handler(ms_get_filter_set_order_key_choose, state=SendData.waiting_for_filter)
    dp.register_message_handler(ms_get_order_key_set_file_type_choose, state=SendData.waiting_for_order_key)
    dp.register_message_handler(ms_get_file_type_send_data, state=SendData.waiting_for_file_type)



