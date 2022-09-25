import logging
import sys

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, italic
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, ChatActions
from aiogram.dispatcher.filters import Text
from config.config import URL_OXF

from .. import db_worker


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
    waiting_for_next_move = State()


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
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(answer1, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)

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
    await call.message.delete_reply_markup()
    username = call.from_user.username
    user_data = await state.get_data()
    user_example = user_data.get('last_example')
    example_length = len(user_example)
    logger.info(f'{username} Send call with example({example_length}) \n\n >>> {user_example}\n\n')

    # everything is fine. Write current data example, answer the user, set next step state
    await state.update_data(current_example=user_example)   # it will be switched with the last_example
    answer = text(
           rf'Cool\! We used your last example:', r'"', italic(f'{user_example[:5]}...'), r'"\.',
           '\nNow write your word ', italic(r'(from 1 to 135 characters long).'))

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':ocean: Back  ')), callback_data='call_back_to_add'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')
    ]
    inl_keyboard.add(*inl_buttons)

    await call.bot.send_message(call.from_user.id,
                                text=answer,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                reply_markup=inl_keyboard
                                )
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

    # wrong length
    if example_length > 400 or example_length < 5:
        answer = text(
               rf'The length of your example is {example_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # everything is fine. Write current data example, answer the user, set next step state
    await state.update_data(current_example=user_example)   # it will be switched with last_example
    answer = text(
           r'Cool\! Now enter your word', italic('(from 1 to 135 characters long).'))

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':ocean: Back  ')), callback_data='call_back_to_add'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')
    ]
    inl_keyboard.add(*inl_buttons)

    await message.reply(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
    await AddingData.waiting_for_word.set()


async def cb_get_word_back_to_add(call: types.CallbackQuery, state: FSMContext):
    """
    2 action
        The user changed his mind about entering a word
        and decided to return to entering an example
    """
    logger.info(f'| {call.from_user.username} | Use back to add call')
    await call.message.delete_reply_markup()

    txt = text(emojize("Let's take a step back to introduce an example :walking:"))
    await call.message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)

    await call.answer(show_alert=False)
    await add_cmd(message=call.message, state=state)


async def ms_get_word_set_description_input(message: types.Message, state: FSMContext):
    """
    2 action
        get word from user input
    """
    username = message.from_user.username
    user_word = message.text
    word_length = len(user_word)
    logger.info(f'{username} Send message with word({word_length}) >>> {user_word}')

    # wrong length
    if word_length > 135 or word_length < 1:
        answer = text(
               rf'The length of your word is  {word_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # everything is fine. Write current data example, reply the user, set next step state
    await state.update_data(current_word=user_word)
    answer = text(
           r'Cool\! Now write your description of the word', italic('(from 1 to 400 characters long).'))

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':ocean: Back  ')), callback_data='call_back_to_word'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')
    ]
    inl_keyboard.add(*inl_buttons)

    await message.reply(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
    await AddingData.waiting_for_description.set()


async def cb_get_description_back_to_word(call: types.CallbackQuery):
    """
    3 action
        The user changed his mind about entering a description
        and decided to return to entering an word
    """
    logger.info(f'| {call.from_user.username} | Use back to word call')
    await call.message.delete_reply_markup()

    # successfully accepted the command
    txt = text(emojize("Let's take a step back to introduce an word :walking:"))
    await call.message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)

    # clone the response from ms_get_example_set_word_input
    answer = text(
           r'Cool\! Now enter your word', italic('(from 1 to 135 characters long).'))

    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':ocean: Back  ')), callback_data='call_back_to_add'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')
    ]
    inl_keyboard.add(*inl_buttons)

    await call.message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)

    # set the correct state (text from 2 steps back, state from previous(1 step) back)
    await call.answer(show_alert=False)
    await AddingData.waiting_for_word.set()


async def ms_get_description_write_data_to_sql(message: types.Message, state: FSMContext):
    """
    3 action
        get description from user input
        write current data in mysql tables
        switch current_ to last_examples
        send a proposal to add new data
    """
    username = message.from_user.username
    user_description = message.text
    description_length = len(user_description)
    logger.info(f'{username} Send message with description({description_length}) \n\n >>> {user_description}\n\n')

    # wrong length
    if description_length > 400 or description_length < 1:
        answer = text(
               rf'The length of your description is  {description_length}\. Try again')
        await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # everything is fine. Save current data description, reply user
    await state.update_data(current_description=user_description)
    answer = text(
           r'Cool\!')
    await message.reply(answer, parse_mode=ParseMode.MARKDOWN_V2)
    answer = text(
        r'Writing your data to the database \- this may take some time', emojize(':hourglass_flowing_sand:'))
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2)
    await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)  # comfortable waiting for the user

    data = await state.get_data()
    example = data.get('current_example')
    word = data.get('current_word')
    description = data.get('current_description')

    db_worker.pending_rollback(username=message.from_user.username)

    category = db_worker.get_word_category(
        word=word,
        default='-',
        url=URL_OXF
    )
    # work with sql tables 'examples' -> 'words'
    user_example = db_worker.add_example(
        example_text=example,
        user_tg_id=str(message.from_user.id)
    )
    user_word = db_worker.add_word(
        word=word,
        description=description,
        category=category,
        rating=0,
        example=user_example,
    )

    # finish, but saving data (we need last_example in the future)
    await state.update_data(last_example=example,     # told you about the switching
                            current_example=None,
                            current_word=None,
                            current_description=None,
                            with_data=False)

    # answer with buttons, set next step state
    answer = text(
           bold('Congratulate'), r'your data have been successfully written\!', '\n',
           bold('\n\tExample'), ' : ', italic(rf'"{example}"'),
           bold('\n\tWord'), ' : ', italic(fr'{word}'),
           bold('\n\tDescription'), ' : ', italic(fr'{description}'))
    inl_keyboard = types.InlineKeyboardMarkup()
    inl_buttons = [
        types.InlineKeyboardButton(text=text(emojize(':man_surfing: Continue ')), callback_data='call_add'),
        types.InlineKeyboardButton(text=text(emojize(':desert_island: Exit ')), callback_data='call_cancel')]
    inl_keyboard.add(*inl_buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)
    await AddingData.waiting_for_next_move.set()


async def cb_delegate_add(call: types.CallbackQuery, state: FSMContext):
    """
    4 action
        delegate work in add_cmd coroutine
    """
    username = call.from_user.username
    logger.info(f'{username} Send call with /add command')

    await call.message.delete_reply_markup()
    await call.answer(show_alert=False)
    await add_cmd(message=call.message, state=state)


async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    """
    independent action
        exit call works as a /cancel
    """
    logger.info(f'| {call.from_user.username} | Use cancel call')

    await call.message.delete_reply_markup()
    txt = text(r'Main menu with available commands\: /help')
    remove_keyboard = types.ReplyKeyboardRemove()
    await call.message.answer(
        txt,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=remove_keyboard
    )
    await call.answer(show_alert=False)
    await state.reset_state(with_data=False)


########################################################################################################################
def register_adding_handlers(dp: Dispatcher):
    logger.info(f'| {dp} | Register adding handlers')

    dp.register_message_handler(add_cmd, commands=['add'])

    dp.register_callback_query_handler(
        cb_get_example_set_word_input,
        Text(equals='call_last_exx'),
        state=AddingData.waiting_for_example
    )    # first
    dp.register_message_handler(ms_get_example_set_word_input,
                                state=AddingData.waiting_for_example)

    dp.register_callback_query_handler(
        cb_get_word_back_to_add,
        Text(equals='call_back_to_add'),
        state=AddingData.waiting_for_word
    )
    dp.register_message_handler(ms_get_word_set_description_input,
                                state=AddingData.waiting_for_word)

    dp.register_callback_query_handler(
        cb_get_description_back_to_word,
        Text(equals='call_back_to_word'),
        state=AddingData.waiting_for_description
    )
    dp.register_message_handler(ms_get_description_write_data_to_sql,
                                state=AddingData.waiting_for_description)

    dp.register_callback_query_handler(
        cb_cancel,
        Text(equals='call_cancel'),
        state='*'
    )
    dp.register_callback_query_handler(
        cb_delegate_add,
        Text(equals='call_add'),
        state=AddingData.waiting_for_next_move
    )
