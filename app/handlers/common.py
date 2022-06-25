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

    if not db_worker.is_user(message.from_user.id):
        now = str(datetime.date.today())
        db_worker.add_user(tg_id=message.from_user.id,
                           nickname=message.from_user.username,
                           lang_code=message.from_user.language_code,
                           shock_mode=0,
                           is_blacklisted=False,
                           is_bot=bool(message.from_user.is_bot),
                           creation_time=now,
                           last_use_time=now,
                           current_use_time=now)
        logger.info(f'|{message.from_user.username}| New user added to "users" table')

    await state.reset_state(with_data=False)
    txt = text(r"Hey, let's start\!", " I'm waiting for commands from you\n\nMore about commands: /help")
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


async def cancel_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | Use cancel command')
    await state.reset_state(with_data=False)
    txt = text("Action canceled")
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


#####################################################################
async def admin_panel_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | Show admin panel')
    await state.reset_state(with_data=False)

    txt = text(
                "/admin", italic(" >>> show admin panel"),
                "/admin_show_bl", italic(" >>> send current black list"),
    )
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


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
    dp.register_message_handler(cancel_cmd, commands=['cancel', 'end', 'finish'], state='*')
    dp.register_message_handler(admin_panel_cmd, IDFilter(user_id=admin_id), commands=['admin'], state='*')
