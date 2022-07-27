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

    waiting_for_data_type = State()
    waiting_for_action = State()
    waiting_for_data_id = State()
    waiting_for_new_data = State()
    waiting_for_deleting = State()
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
        bold('1.'), r'Choose what you want to change or delete', '\n',
        bold('2.'), r'Then choose an action \(delete \| change\)', '\n',
        bold('3.'), r'And then enter the new word\, description\, or example', '\n',
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
    await UpdateData.waiting_for_data_type.set()


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
        logger.info(f'[{username}]: Incorrect data type "{user_text}"')
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

    await state.update_data(user_data_type=user_text)

    answer = text(
        fr"Okay, now choose what you want to do with your {user_text}")
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
    if user_text in 'word example'.split():
        buttons = ['Edit', 'Delete']
    else:           # description
        buttons = ['Edit']
    keyboard.add(*buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    logger.info(f'[{username}]: Jump to action input')
    await UpdateData.waiting_for_action.set()


async def ms_get_action_set_enter_data(message: types.Message, state: FSMContext):
    """
    2 action
        accept the response with the user action ('Edit', 'Delete')
        set the wait to data id ('word_id', 'example-id')
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    possible_answers = {'edit', 'delete'}

    logger.info(f'[{username}]: Catch action: "{user_text}"')

    if user_text not in possible_answers:
        logger.info(f'[{username}]: Incorrect action "{user_text}"')
        answer = text(
            emojize(':police_car: Something is wrong here'), italic(
                f'"{message.text if len(message.text) <= 12 else message.text[:13] + "..."}"\n'),
            '\n',
            italic('You can only edit or delete your data: '),
                                                            bold(f'{" | ".join(possible_answers)}\n'),
            '\n',
            r'Try it again\, just entering your answer below\.', '\n',
            '\n'
        )
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(user_data_action=user_text)
    data = await state.get_data()
    user_data_type = data.get("user_data_type")

    if user_data_type == 'example':
        answer = text(
            fr"Now all we need is the id of your example to {user_text} it")
    else:        # word description
        answer = text(
            fr"Now all we need is the id of your word to {user_text} it")

    keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)

    logger.info(f'[{username}]: Jump to id input')
    await UpdateData.waiting_for_data_id.set()


async def ms_get_id_set_action(message: types.Message, state: FSMContext):
    """
    3 action
        accept the response with the user data to change (id | data)
        set the action (delete from sql, new data to edit)
    """
    username = message.from_user.username
    user_text = message.text.lower().strip()
    data = await state.get_data()
    user_data_type = data.get("user_data_type")
    user_data_action = data.get("user_data_action")
    logger.info(f'[{username}]: Catch id | data: "{user_text}"')

    # example
    if user_data_type == 'example':
        example_obj = None
        try:
            flag = 'example_id'
            user = db_worker.get_user(tg_id=message.from_user.id)
            if user_text.isdigit():
                example_obj = db_worker.get_example(user=user, example_id=int(user_text))
            if not example_obj:     # the specified numbers are not correct id or the user has entered text
                flag = 'example_text'
                word_obj = db_worker.get_example(user=user, example=user_text)
        except Exception as e:
            logger.error(f'[{username}]: Houston, we have got a unknown sql problem {e}')
            answer = text(
                emojize(":oncoming_police_car:"), fr"There was a big trouble when searching your {user_data_type}\, "
                                                  r"please write to the administrator\.")
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return
        if not example_obj:
            logger.info(f'[{username}]: Incorrect id | data "{user_text}"')
            answer = text(
                emojize(":man_detective:"),
                  rf"We couldn\'t find the right {user_data_type}\, make sure you entered the correct example id", '\n',
                r'Try it again\, just entering your answer below\.', '\n',
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return

        example = example_obj.example
        words = [w.word for w in example_obj.words]
        await state.update_data(user_example_id=example_obj.ex_id)   # need for next step (deleting | editing)

        answer = text(
            bold(r"Here\'s what we found"), emojize(r':helicopter:'), '\n',
            '\n',
            bold(r" Example : "), italic(f'{example}'), '\n',
            bold(rf" With word{'s' if len(words) > 1 else ''} : "), italic(f'{", ".join(words)}'), '\n',
            '\n')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

        if user_data_action == 'delete':
            answer = text(
                r"Are you sure you want to", bold("delete"), rf"an example", italic(f'{example}'),
                r'\, this will result in the deletion of all these words:', italic(f'{", ".join(words)}'),
                emojize(r':firecracker:'), '\n',
                '\n',)
            inl_keyboard = types.InlineKeyboardMarkup()
            inl_buttons = [
                types.InlineKeyboardButton(text=text(emojize(':boom: Yes')), callback_data='call_delete_example'),
                types.InlineKeyboardButton(text=text(emojize(':dove_of_peace: No')), callback_data='call_cancel')]
            inl_keyboard.add(*inl_buttons)
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
            logger.info(f'[{username}]: Jump to deleting example')
            await UpdateData.waiting_for_deleting.set()
        else:    # edit
            answer = text(
                r"Enter what you want to ", bold("change"), rf"the example", italic(f'"{example}"'),
                    emojize(r'to :lower_left_crayon:'), '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f'[{username}]: Jump to new {user_data_type} input')
            await UpdateData.waiting_for_new_data.set()

    # word | description
    else:
        word_obj = None
        try:
            flag = 'word_id'
            user = db_worker.get_user(tg_id=message.from_user.id)
            if user_text.isdigit():
                word_obj = db_worker.get_user_word(user=user, word_id=int(user_text))
            if not word_obj:     # the specified numbers are not correct id or the user has entered text
                if user_data_type == 'description':
                    flag = 'desc_text'
                    word_obj = db_worker.get_user_word(user=user, description=user_text)
                else:
                    flag = 'word_text'
                    word_obj = db_worker.get_user_word(user=user, word=user_text)
        except Exception as e:
            logger.error(f'[{username}]: Houston, we have got a unknown sql problem {e}')
            answer = text(
                emojize(":oncoming_police_car:"), fr"There was a big trouble when searching your {user_data_type}\, "
                                                  r"please write to the administrator\.")
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return
        if not word_obj:
            logger.info(f'[{username}]: Incorrect id | data "{user_text}"')
            answer = text(
                emojize(":man_detective:"),
                    rf"We couldn\'t find the right {user_data_type}\, make sure you entered the correct word id", '\n',
                r'Try it again\, just entering your answer below\.', '\n',
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            return

        word = word_obj.word
        description = word_obj.description
        example_obj = db_worker.get_example(user=user, example_id=word_obj.example_id)
        example = example_obj.example
        await state.update_data(user_word_id=word_obj.word_id)     # need for next step (deleting | editing)

        answer = text(
            bold(r"Here\'s what we found"), f'({"first match with your input" if flag != "word_id" else ""})',
                emojize(r':helicopter:'), '\n',
            '\n',
            bold(r" Example : "), italic(f'{example}'), '\n',
            bold(r" Word : "), italic(f'{word}'), '\n',
            bold(r" Description : "), italic(f'{example_obj}'), '\n',
            '\n')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

        if user_data_action == 'delete':
            answer = text(
                r"Are you sure you want to", bold("delete"),
                    rf"the word {'with this description' if user_data_type == 'description' else ''}\? ",
                        emojize(r':firecracker:'), '\n',
                '\n',)
            inl_keyboard = types.InlineKeyboardMarkup()
            inl_buttons = [
                types.InlineKeyboardButton(text=text(emojize(':boom: Yes')), callback_data='call_delete_word'),
                types.InlineKeyboardButton(text=text(emojize(':dove_of_peace: No')), callback_data='call_cancel')]
            inl_keyboard.add(*inl_buttons)
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
            logger.info(f'[{username}]: Jump to deleting word')
            await UpdateData.waiting_for_deleting.set()
        else:    # edit
            answer = text(
                r"Enter what you want to ", bold("change"),
                    rf"the {'word' if user_data_type == 'word' else 'description'}",
                        italic(f'"{word if user_data_type == "word" else description}"'),
                            emojize(r'to :lower_left_crayon:'),
                '\n')
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f'[{username}]: Jump to new {user_data_type} input')
            await UpdateData.waiting_for_new_data.set()


########################################################################################################################
def register_updating_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register updating handlers')
