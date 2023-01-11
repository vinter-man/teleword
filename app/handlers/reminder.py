import logging
import sys
import datetime

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import text, bold, italic
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, ChatActions
from aiogram.dispatcher.filters import Text
from config.config import URL_OXF, REMINDERS_PAGE_SIZE
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.utils.callback_data import CallbackData

from typing import Collection


from .. import db_worker


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )



########################################################################################################################
# class InlineMenu(StatesGroup):
#     """
#     Stateful class for menu traveling logic
#     """
#     step = State()


########################################################################################################################
class Pagination:
    def __init__(self,
                 buttons: Collection[InlineKeyboardButton], buttons_on_page: int,
                 button_back: types.InlineKeyboardButton, button_next: types.InlineKeyboardButton,
                 button_previous_page: types.InlineKeyboardButton, button_exit: types.InlineKeyboardButton
                 ):
        self.buttons = buttons
        self.buttons_on_page = buttons_on_page
        self.current_page = 0
        self.button_back = button_back
        self.button_next = button_next
        self.button_previous_page = button_previous_page
        self.button_exit = button_exit

    async def update_keyboard(self) -> InlineKeyboardMarkup:
        inl_keyboard = InlineKeyboardMarkup()
        start = self.current_page * self.buttons_on_page
        end = (self.current_page + 1) * self.buttons_on_page

        for button in self.buttons[start:end]:
            inl_keyboard.row(button)    # add the row

        if start <= 0:            # we do not need back button
            inl_keyboard.row(self.button_next)
        elif end >= len(self.buttons):   # we do not need next button
            inl_keyboard.row(self.button_back)
        else:
            inl_keyboard.row(self.button_back, self.button_next)   # we need both

        inl_keyboard.row(self.button_previous_page, self.button_exit)

        return inl_keyboard

    async def next(self) -> None:
        self.current_page += 1

    async def back(self) -> None:
        self.current_page -= 1

    # TODO: serialize() | deserialize()


########################################################################################################################
# TODO: inline crud to redis
# TODO: independent while which use dict of {type:all/only_if_i_have_no_completed_lesson user_id: 111 time: 22:30}
#  from redis
async def reminder_cmd(message: types.Message, state: FSMContext):
    """
    0 action
        send instruction to user
    """
    username = message.from_user.username
    logger.info(f'[{username}]: Start /reminder cmd')

    current_time = datetime.datetime.today().strftime("%a, %H:%M")
    current_date = datetime.datetime.today().strftime('%d.%m.%Y')
    answer = text(
        emojize(':stopwatch:'), r'Bot time\: ', bold(f'{current_time}'), '\n',
        emojize(':calendar:'), r'Bot date\: ', bold(f'{current_date}'), '\n',
        emojize(':open_file_folder:'), bold('Reminder menu'), '\n'
    )
    inl_keyboard = types.InlineKeyboardMarkup(row_width=2)
    inl_buttons = [
        types.InlineKeyboardButton(text=text('My reminders'), callback_data='call_get_reminders'),
        types.InlineKeyboardButton(text=text('Add new reminder'), callback_data='call_add_reminder'),
        types.InlineKeyboardButton(text=text('Exit'), callback_data='call_cancel')
    ]
    inl_keyboard.add(*inl_buttons)
    await message.answer(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=inl_keyboard)


async def cb_get_reminders(call: types.CallbackQuery, state: FSMContext):
    """
    independent action
        show all user reminders like pages
    """
    username = call.from_user.username
    user_data = await state.get_data()

    user_reminders: list | None = user_data.get('reminders')
    #user_reminders = ['19:00', '19:01', '19:02', '19:03', '19:04', '19:05', '19:06', '19:07']
    if not user_reminders:
        await state.update_data(reminders=[])
        user_reminders: list = (await state.get_data()).get('reminders')

    logger.info(f'[{username}]: Call get reminders ({len(user_reminders)})')

    if len(user_reminders) < 1:    # we have not any reminders
        answer = text('You don\'t have any reminders yet')
        await call.answer(
            text=answer,
            show_alert=True
        )
        return
    else:     # we have reminders, but need to paginate it
        buttons = [
            types.InlineKeyboardButton(text=text(f'{reminder_time}'), callback_data=f'user_{reminder_time}')
            for reminder_time in user_reminders
        ]
        pagination = Pagination(
            buttons=buttons,
            buttons_on_page=REMINDERS_PAGE_SIZE,
            button_back=types.InlineKeyboardButton(
                text=text(emojize(':arrow_left:')),
                callback_data='user_reminders_back'
            ),
            button_next=types.InlineKeyboardButton(
                text=text(emojize(':arrow_right:')),
                callback_data='user_reminders_back'
            ),
            button_previous_page=types.InlineKeyboardButton(
                text=text('Back to menu'),
                callback_data='user_reminders_previous_page'
            ),
            button_exit=types.InlineKeyboardButton(
                text=text('Exit'),
                callback_data='call_cancel'
            )
        )
        new_inl_keyboard = await pagination.update_keyboard()
        current_time = datetime.datetime.today().strftime("%a, %H:%M")
        current_date = datetime.datetime.today().strftime('%d.%m.%Y')
        answer = text(
            emojize(':stopwatch:'), r'Bot time\: ', bold(f'{current_time}'), '\n',
            emojize(':calendar:'), r'Bot date\: ', bold(f'{current_date}'), '\n',
            emojize(':calendar:'), r'Your reminders\: ', '\n',
        )
        await call.message.edit_text(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=new_inl_keyboard)


async def cb_add_reminder(call: types.CallbackQuery, state: FSMContext):
    """
    independent action
        start an adding process
    """
    username = call.from_user.username
    user_data = await state.get_data()

    user_reminders: list | None = user_data.get('reminders')

    available_reminders = []
    for i in range(0, 24):           # [00:00, 01:00, ...,  23:00]
        if i < 12:
            i = f'0{i}'
        available_reminders.append(f'{i}:00')

    for i in available_reminders:    # delete user`s reminder
        if i in user_reminders:
            available_reminders.remove(i)

    logger.info(f'[{username}]: Call add reminder')

    buttons = [
        types.InlineKeyboardButton(text=text(f'{reminder_time}'), callback_data=f'add_{reminder_time}')
        for reminder_time in available_reminders
    ]
    pagination = Pagination(
        buttons=buttons,
        buttons_on_page=REMINDERS_PAGE_SIZE
    )
    new_inl_keyboard = await pagination.update_keyboard()
    current_time = datetime.datetime.today().strftime("%a, %H:%M")
    current_date = datetime.datetime.today().strftime('%d.%m.%Y')
    answer = text(
        emojize(':stopwatch:'), r'Bot time\: ', bold(f'{current_time}'), '\n',
        emojize(':calendar:'), r'Bot date\: ', bold(f'{current_date}'), '\n',
        emojize(':calendar:'), r'Click to add new reminder\: ', '\n',
    )
    await call.message.edit_text(answer, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=new_inl_keyboard)


########################################################################################################################
# @dp.message_handler(commands=["start"])
# async def on_start(message: Message) -> None:
#     await message.answer("MENU", reply_markup=await pagination.update_kb())
#
#
# async def cb_keyboard_next_page(query: CallbackQuery) -> None:
#     await pagination.on_next()
#     await query.message.edit_text("MENU", reply_markup=await pagination.update_kb())


#
#
# @dp.callback_query_handler(navigation.filter(action="navigate", direction="previous"))
# async def prev_(query: CallbackQuery) -> None:
#     await pagination.on_prev()
#     await query.message.edit_text("MENU", reply_markup=await pagination.update_kb())
#
#
# if __name__ == '__main__':
#     executor.start_polling(dp, skip_updates=True)
########################################################################################################################
def register_reminder_handlers(dp: Dispatcher):
    """
    The function serves as a register of all the module coroutines in the correct sequence
     (used instead of decorators to create a more readable structure)
    """
    logger.info(f'[{dp}]: Register reminder handlers')

    dp.register_message_handler(reminder_cmd, commands=['reminder'], state='*')

    dp.register_callback_query_handler(
        cb_get_reminders,
        Text(equals='call_get_reminders'),
        state='*'
    )

    dp.register_callback_query_handler(
        cb_add_reminder,
        Text(equals='call_add_reminder'),
        state='*'
    )
    #
    # dp.register_callback_query_handler(
    #     cb_keyboard_next_page,
    #     Text(equals='call_add_reminder'),
    # )
    # dp.register_message_handler(ms_get_example_set_word_input,
    #                             state=AddingData.waiting_for_example)
    #
    # dp.register_callback_query_handler(
    #     cb_get_word_back_to_add,
    #     Text(equals='call_back_to_add'),
    #     state=AddingData.waiting_for_word
    # )
    # dp.register_message_handler(ms_get_word_set_description_input,
    #                             state=AddingData.waiting_for_word)
    #
    # dp.register_callback_query_handler(
    #     cb_get_description_back_to_word,
    #     Text(equals='call_back_to_word'),
    #     state=AddingData.waiting_for_description
    # )
    # dp.register_callback_query_handler(
    #     cb_get_description_await_ms_get_description_write_data_to_sql,
    #     Text(equals='call_use_description'),
    #     state=AddingData.waiting_for_description
    # )
    # dp.register_message_handler(ms_get_description_write_data_to_sql,
    #                             state=AddingData.waiting_for_description)
    #
    # dp.register_callback_query_handler(
    #     cb_cancel,
    #     Text(equals='call_cancel'),
    #     state='*'
    # )
    # dp.register_callback_query_handler(
    #     cb_delegate_add,
    #     Text(equals='call_add'),
    #     state=AddingData.waiting_for_next_move
    # )
