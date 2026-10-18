import asyncio

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.keyboards import ExportChoice, keyboard
from teleword.bot.utils import drop_markup, reset_state
from teleword.db.models import User
from teleword.services import export
from teleword.services.export import Format, Order, Selection

router = Router(name="export")

ALL_FORMATS = "all"
FORMAT_LABELS = {Format.XLSX: "Excel", Format.JSON: "JSON", Format.XML: "XML", Format.CSV: "CSV"}


@router.message(Command("data"))
async def data_cmd(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer("Soon I'll send you a file with your words 🚢", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "First, which words?",
        reply_markup=keyboard(
            ("All my words", ExportChoice(selection=Selection.ALL)),
            ("Most important words", ExportChoice(selection=Selection.IMPORTANT)),
            width=1,
        ),
    )


@router.callback_query(ExportChoice.filter((F.selection != "") & (F.order == "")))
async def choose_order(callback: CallbackQuery, callback_data: ExportChoice) -> None:
    await drop_markup(callback)
    selection = callback_data.selection
    await callback.message.answer(
        "Great, how should I sort them?",
        reply_markup=keyboard(
            ("In order of addition", ExportChoice(selection=selection, order=Order.ADDED)),
            ("Alphabetically", ExportChoice(selection=selection, order=Order.ALPHABET)),
            ("By importance", ExportChoice(selection=selection, order=Order.IMPORTANCE)),
            width=1,
        ),
    )


@router.callback_query(ExportChoice.filter((F.order != "") & (F.fmt == "")))
async def choose_format(callback: CallbackQuery, callback_data: ExportChoice) -> None:
    await drop_markup(callback)
    base = {"selection": callback_data.selection, "order": callback_data.order}
    await callback.message.answer(
        "Excellent, and the last question: which format?",
        reply_markup=keyboard(
            *((label, ExportChoice(**base, fmt=fmt)) for fmt, label in FORMAT_LABELS.items()),
            ("All formats", ExportChoice(**base, fmt=ALL_FORMATS)),
        ),
    )


@router.callback_query(ExportChoice.filter(F.fmt != ""))
async def send_files(
    callback: CallbackQuery, callback_data: ExportChoice, session: AsyncSession, user: User
) -> None:
    await drop_markup(callback)
    rows = await export.fetch_rows(
        session, user.id, Selection(callback_data.selection), Order(callback_data.order)
    )
    if not rows:
        await callback.message.answer("🤷 No words match this choice yet. Add some with /add.")
        return

    formats = list(Format) if callback_data.fmt == ALL_FORMATS else [Format(callback_data.fmt)]
    for fmt in formats:
        await callback.message.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_DOCUMENT)
        content = await asyncio.to_thread(export.render, rows, fmt)
        await callback.message.answer_document(
            BufferedInputFile(content, filename=export.filename(fmt)),
            caption=f"Done, here are your {len(rows)} words, enjoy 🍰",
        )
