import datetime
import sys
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text, IDFilter
from aiogram.types import ParseMode
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram import Bot, Dispatcher, executor, types
import asyncio
from aiogram import Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.message import ContentType
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram.types import BotCommand
from aiogram.utils.helper import Helper, HelperMode, ListItem
import logging
from .. import db_worker    # if . only in current package


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
async def start_cmd(message: types.Message, state: FSMContext):
    logger.info(f'|{message.from_user.username}| Use start command')

    if not db_worker.is_user(str(message.from_user.id)):
        logger.info(f'|{message.from_user.username}| adding new user to "users" table...')
        await message.bot.send_chat_action(message.from_user.id, ChatActions.TYPING)
        now = str(datetime.date.today())
        db_worker.add_user(tg_id=str(message.from_user.id),
                           nickname=message.from_user.username,
                           lang_code=message.from_user.language_code,
                           shock_mode=0,
                           points=0,
                           is_blacklisted=False,
                           is_bot=bool(message.from_user.is_bot),
                           creation_time=now,
                           last_use_time=now,
                           current_use_time=now)
        logger.info(f'|{message.from_user.username}| New user added to "users" table')

    await state.reset_state(with_data=False)
    txt = text(r"Let's start\!", " I'm waiting from you commands\n\nMore about commands: /help")
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def cancel_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | Use cancel command')
    await state.reset_state(with_data=False)
    txt = text(r'Action canceled\.', '\n',
               r'Menu with available commands\: /help')
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def help_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | Use help command')
    await state.reset_state(with_data=False)
    txt = text(
        bold('Hi I\'m Teleword Bot'), emojize(' :robot_face:\n'),
        '\n',
        r'Here are the things that I can do\:', '\n',
        '\n',
        emojize(':gear: '), italic('Basic:'), '\n'
        r'/start \- start of acquaintance with me', '\n',
        r'/cancel /end /finish \- canceling any action', '\n'
        r'/help \- a place where everything that I can do is described', '\n'
        '\n',
        emojize(':blue_book: '), italic('Adding your words:'), '\n'
        r'/add \- begins the process of adding a new word', '\n',
        '\n',
        emojize(':lower_left_paintbrush: '), italic('Conduct a lesson:'), '\n'
        r'\(throws an error if you have less than 15 words\)', '\n',
        r'/lesson \- start classic lesson', '\n',
        '\n',
        emojize(':gem: '), italic('View admin commands:'), '\n',
        emojize(r'\(does not work if you are not an admin :man_genie:\)'), '\n',
        r'/admin \- shows the admin panel', '\n',
        sep=''
       )
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


#####################################################################
async def admin_panel_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | Show admin panel')
    await state.reset_state(with_data=False)

    txt = text(
                "/admin", italic(" >>> show admin panel"),
                "/admin_show_bl", italic(" >>> send current black list"),
    )
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=remove_keyboard)


async def admin_show_bl_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | Show black list')
    await state.reset_state(with_data=False)

    black_list = db_worker.users_bl_list()
    if not black_list:
        txt = text(
            'Black list is empty'
        )
    else:
        txt = text(
            f'{black_list}'
        )
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


########################################################################################################################
def register_handlers_common(dp: Dispatcher, admin_id: int):
    logger.info(f'| {dp, admin_id} | Register common handlers')
    dp.register_message_handler(start_cmd, commands=['start'], state='*')
    dp.register_message_handler(help_cmd, commands=['help'], state='*')
    dp.register_message_handler(cancel_cmd, commands=['cancel', 'end', 'finish'], state='*')
    dp.register_message_handler(admin_panel_cmd, IDFilter(user_id=admin_id), commands=['admin'], state='*')
