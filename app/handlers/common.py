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


########################################################################################################################
logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s]:[%(levelname)s]:[%(filename)s]:[%(lineno)d]: %(message)s',
    )


########################################################################################################################
async def start_cmd(message: types.Message, state: FSMContext):
    logger.info(f'|{message.from_user.username}| use start command')
    await state.finish()
    txt = text("Hey, let's start\! I'm waiting for commands from you\n\nMore about commands: /help")
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


async def cancel_cmd(message: types.Message, state: FSMContext):
    logger.info(f'| {message.from_user.username} | use cancel command')
    await state.finish()
    txt = text("Action canceled")
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


#####################################################################
async def admin_panel_cmd(message: types.Message):
    logger.info(f'| {message.from_user.username} | show admin panel')
    txt = text(
                "/admin", italic(" >>> show admin panel"),
    )
    await message.answer(txt, parse_mode=ParseMode.MARKDOWN_V2)


########################################################################################################################
def register_handlers_common(dp: Dispatcher, admin_id: int):
    logger.info(f'| {dp, admin_id} | register common handlers')
    dp.register_message_handler(start_cmd, commands=['start'], state='*')
    dp.register_message_handler(cancel_cmd, commands=['cancel', 'end', 'finish'], state='*')
    dp.register_message_handler(admin_panel_cmd, IDFilter(user_id=admin_id), commands=['admin'], state='*')