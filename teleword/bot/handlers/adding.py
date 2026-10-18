import logging
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.keyboards import EXIT, Nav, keyboard
from teleword.bot.utils import drop_markup, reset_state, shorten
from teleword.config import Settings
from teleword.db.models import User
from teleword.services import vocabulary
from teleword.services.dictionary import lookup_category

router = Router(name="adding")
logger = logging.getLogger(__name__)

TEXT_INPUT = F.text & ~F.text.startswith("/")


class Adding(StatesGroup):
    example = State()
    word = State()
    description = State()


HINT = (
    "<b>A small clue:</b>\n\n"
    "<b>Example</b>: <i>We just imagine the arrows because we fear them.</i>\n"
    "<b>Word</b>: <i>arrow</i>\n"
    "<b>Description</b>: <i>A weapon consisting of a thin, straight stick with a sharp point, "
    "designed to be shot from a bow.</i>"
)


def entry_card(example: str, word: str, description: str) -> str:
    return (
        f"<b>Example</b>: <i>{escape(example)}</i>\n"
        f"<b>Word</b>: <i>{escape(word)}</i>\n"
        f"<b>Description</b>: <i>{escape(description)}</i>"
    )


async def ask_example(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer(HINT, reply_markup=ReplyKeyboardRemove())
    last_example = (await state.get_data()).get("last_example")
    markup = None
    if last_example:
        markup = keyboard(
            (f'Use my last example "{shorten(last_example, 20)}"', Nav(action="add_last_example")), width=1
        )
    await message.answer("🚀 Send me your example <i>(5 to 400 characters)</i>.", reply_markup=markup)
    await state.set_state(Adding.example)


async def ask_word(message: Message, state: FSMContext, intro: str) -> None:
    await message.answer(
        f"{intro}\nNow send the word <i>(1 to 135 characters)</i>.",
        reply_markup=keyboard(("🌊 Back", Nav(action="add_back_to_example")), EXIT),
    )
    await state.set_state(Adding.word)


@router.message(Command("add"))
async def add_cmd(message: Message, state: FSMContext) -> None:
    await ask_example(message, state)


@router.callback_query(Adding.example, Nav.filter(F.action == "add_last_example"))
async def use_last_example(callback: CallbackQuery, state: FSMContext) -> None:
    await drop_markup(callback)
    example = (await state.get_data()).get("last_example")
    if not example:
        await ask_example(callback.message, state)
        return
    await state.update_data(example=example)
    await ask_word(callback.message, state, f"Cool! Using your last example: <i>{escape(example)}</i>")


@router.message(Adding.example, TEXT_INPUT)
async def got_example(message: Message, state: FSMContext) -> None:
    try:
        example = vocabulary.validate("example", message.text)
    except vocabulary.ValidationError as exc:
        await message.answer(f"{exc} Try again.")
        return
    await state.update_data(example=example)
    await ask_word(message, state, "Cool!")


@router.callback_query(Adding.word, Nav.filter(F.action == "add_back_to_example"))
async def back_to_example(callback: CallbackQuery, state: FSMContext) -> None:
    await drop_markup(callback)
    await callback.message.answer("Let's go back to the example 🚶")
    await ask_example(callback.message, state)


@router.message(Adding.word, TEXT_INPUT)
async def got_word(message: Message, state: FSMContext) -> None:
    try:
        word = vocabulary.validate("word", message.text)
    except vocabulary.ValidationError as exc:
        await message.answer(f"{exc} Try again.")
        return
    await state.update_data(word=word)
    await message.answer(
        "Cool! Now send the description of the word <i>(1 to 400 characters)</i>.",
        reply_markup=keyboard(("🌊 Back", Nav(action="add_back_to_word")), EXIT),
    )
    await state.set_state(Adding.description)


@router.callback_query(Adding.description, Nav.filter(F.action == "add_back_to_word"))
async def back_to_word(callback: CallbackQuery, state: FSMContext) -> None:
    await drop_markup(callback)
    await ask_word(callback.message, state, "Let's go back to the word 🚶")


@router.message(Adding.description, TEXT_INPUT)
async def got_description(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    http: AsyncClient,
    settings: Settings,
) -> None:
    try:
        description = vocabulary.validate("description", message.text)
    except vocabulary.ValidationError as exc:
        await message.answer(f"{exc} Try again.")
        return

    data = await state.get_data()
    example, word = data["example"], data["word"]
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    category = await lookup_category(http, settings.dictionary_api_url, word)
    entry = await vocabulary.add_entry(session, user, example, word, description, category)
    await session.commit()
    logger.info("@%s added %r (%s) to example #%d", user.nickname, word, category or "-", entry.example_id)

    await state.set_data({"last_example": example})
    await state.set_state(None)
    await message.answer(
        f"<b>Saved!</b> 🎉\n\n{entry_card(example, word, description)}",
        reply_markup=keyboard(("🏄 Add another", Nav(action="add_again")), EXIT),
    )


@router.callback_query(Nav.filter(F.action == "add_again"))
async def add_again(callback: CallbackQuery, state: FSMContext) -> None:
    await drop_markup(callback)
    await ask_example(callback.message, state)
