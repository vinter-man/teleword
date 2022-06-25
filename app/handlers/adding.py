"""
ADD WORDS TO USER DB (all skills with redis, algorithmic, aiogram, restapi)
1 Example adding (inl.button - use last) - check for min len
2 Word adding - check for min len
3 Description adding - check for min len
4 Try to category by api | parsing

back button
reset button
"""
import asyncio
import logging
import sys
import time


from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram.dispatcher.filters import Text


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
class AddingData(StatesGroup):

    waiting_for_example = State()
    waiting_for_word = State()
    waiting_for_description = State()


########################################################################################################################
async def add_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        instruction
    """
    username = message.from_user.username
    user_data = await state.get_data()
    last_example = user_data.get('last_example')
    last_example_length = 0
    if last_example:
        last_example_length = len(last_example)
    logger.info(f'{username} Start adding new data. Last user example len - {last_example_length}')

    answer1 = text(
            bold('A small clue:\n'),
            bold('\n\tExample'), ' : ', italic(r'"We just imagine the arrows because we fear them.";'),
            bold('\n\tWord'), ' : ', italic(r'Arrow;'),
            bold('\n\tDescription'), ' : ', italic(r'A weapon consisting of a thin, straight stick '
                                                   r'with a sharp point, designed to be shot from a bow.'))
    await message.answer(answer1, parse_mode=ParseMode.MARKDOWN_V2)

    answer2 = text(
            emojize(r":rocket: Let's start\! Send me your example"), italic('(from 5 to 400 characters).'))
    if last_example:
        inl_keyboard = types.InlineKeyboardMarkup()
        inl_button = types.InlineKeyboardButton(text=f'Use my last example "{last_example[0:5]}..."',
                                                callback_data='call_last_exx')
        inl_keyboard.add(inl_button)
        await message.answer(answer2, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
    else:
        await message.answer(answer2, parse_mode=ParseMode.MARKDOWN_V2)

    logger.info(f'{username} Jump to word input')
    await AddingData.waiting_for_example.set()


async def cb_get_example_set_word_input(call: types.CallbackQuery, state: FSMContext):
    """
    1 action
        get example from redis data
    """

    username = call.from_user.username
    user_data = await state.get_data()
    user_example = user_data.get('last_example')
    example_length = len(user_example)
    logger.info(f'{username} Send call with example({example_length}) \n\n >>> {user_example}\n\n')

    # * write correct text
    # All is ok. Write current data example, reply user, set next step state
    await state.update_data(current_example=user_example)   # it will be switched with last_example
    answer = text(
           rf'Cool\! We have used your last exx: "{user_example[:5]}\.\.\."\.',
           '\nNow write your word ', italic(r'(from 1 to 135 characters).'))
    await call.bot.send_message(call.from_user.id, text=answer, parse_mode=ParseMode.MARKDOWN_V2)
    await call.message.delete_reply_markup()
    await call.answer(show_alert=False)
    await AddingData.waiting_for_word.set()


async def ms_get_example_set_word_input(message: types.Message, state: FSMContext):
    """
    1 action
        get example from user input
    """
    username = message.from_user.username
    user_example = message.text
    example_length = len(user_example)
    logger.info(f'{username} Send message with example({example_length}) \n\n >>> {user_example}\n\n')

    # * write correct text
    # Wrong length
    if example_length > 400 or example_length < 5:
        answer = text(
               rf'You example length is {example_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # * write correct text
    # All is ok. Write current data example, reply user, set next step state
    await state.update_data(current_example=user_example)   # it will be switched with last_example
    answer = text(
           r'Cool\! Now write your word', italic('(from 1 to 135 characters).'))
    await message.reply(answer, parse_mode=ParseMode.MARKDOWN_V2)
    await AddingData.waiting_for_word.set()


async def ms_get_word_set_description_input(message: types.Message, state: FSMContext):
    """
    2 action
        get word from user input
    """
    username = message.from_user.username
    user_word = message.text
    word_length = len(user_word)
    logger.info(f'{username} Send message with word({word_length}) >>> {user_word}')

    # * write correct text
    # Wrong length
    if word_length > 135 or word_length < 1:
        answer = text(
               rf'You word length is {word_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # * write correct text
    # All is ok. Write current data example, reply user, set next step state
    await state.update_data(current_word=user_word)
    answer = text(
           r'Cool\! Now write your word description', italic('(from 1 to 400 characters).'))
    await message.reply(answer, parse_mode=ParseMode.MARKDOWN_V2)
    await AddingData.waiting_for_description.set()


async def ms_get_description_write_data_to_sql(message: types.Message, state: FSMContext):
    """
    3 action
        get description from user input
        write current data to mysql tables
        switch current to last examples
        send suggestion to add new data
    """
    username = message.from_user.username
    user_description = message.text
    description_length = len(user_description)
    logger.info(f'{username} Send message with description({description_length}) \n\n >>> {user_description}\n\n')

    # * write correct text
    # Wrong length
    if description_length > 400 or description_length < 1:
        answer = text(
               rf'You description length is {description_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # * write correct text
    # All is ok. Write current data description, reply user
    await state.update_data(current_description=user_description)
    answer = text(
           r'Cool\!')
    await message.reply(answer, parse_mode=ParseMode.MARKDOWN_V2)

    data = await state.get_data()
    example = data.get('current_example')
    word = data.get('current_word')
    description = data.get('current_description')

    # * write sql func

    answer = text(
           bold('Congratulate'), r'your data have been successfully written\!', '\n',
           bold('\n\tExample'), ' : ', italic(rf'"{example}"'),
           bold('\n\tWord'), ' : ', italic(fr'{word}'),
           bold('\n\tDescription'), ' : ', italic(fr'{description}'))
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)

    # finish, but with saving data (we need last_example in the future)
    await state.update_data(last_example=example,     # told you about switching, dude
                            current_example=None,
                            current_word=None,
                            current_description=None,
                            with_data=False)

    # * write inline button add more| / |exit|ok|nice

    await state.reset_state(with_data=False)


########################################################################################################################
def register_adding_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register adding handlers')
    dp.register_message_handler(add_cmd, commands=['add'])
    dp.register_callback_query_handler(cb_get_example_set_word_input, Text(equals='call_last_exx'),
                                       state=AddingData.waiting_for_example)    # first
    dp.register_message_handler(ms_get_example_set_word_input, state=AddingData.waiting_for_example)
    dp.register_message_handler(ms_get_word_set_description_input, state=AddingData.waiting_for_word)
    dp.register_message_handler(ms_get_description_write_data_to_sql, state=AddingData.waiting_for_description)

