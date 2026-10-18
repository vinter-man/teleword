import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message

from teleword.bot.utils import drop_markup

router = Router(name="fallback")
logger = logging.getLogger(__name__)


@router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("🤔 I don't know this command. All commands: /help")
    else:
        await message.answer("Please send a text message, or /cancel to stop.")


@router.callback_query()
async def stale_button(callback: CallbackQuery) -> None:
    """Buttons from a flow that has already ended or was replaced by another command."""
    await drop_markup(callback)
    await callback.message.answer("This button is no longer active. All commands: /help")


@router.error()
async def on_error(event: ErrorEvent) -> None:
    logger.exception("Error while handling update %s", event.update.update_id, exc_info=event.exception)
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message is None:
        return
    try:
        await message.answer("🚑 Something went wrong on my side. Please try again in a moment.")
    except Exception:
        logger.exception("Could not notify the user about the error")
