import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.handlers.adding import TEXT_INPUT, entry_card
from teleword.bot.keyboards import EXIT, EditChoice, Nav, keyboard
from teleword.bot.utils import drop_markup, reset_state
from teleword.config import Settings
from teleword.db.models import Example, User, Word
from teleword.services import vocabulary
from teleword.services.dictionary import lookup_category

router = Router(name="editing")
logger = logging.getLogger(__name__)

FIELDS = ("word", "description", "example")
NEXT_STEP = keyboard(("🚣 Continue", Nav(action="change_again")), EXIT)


class Editing(StatesGroup):
    target = State()
    value = State()
    confirm_delete = State()


def example_card(example: Example) -> str:
    words = ", ".join(w.word for w in example.words) or "—"
    return f"<b>Example</b>: <i>{escape(example.text)}</i>\n<b>Words</b>: <i>{escape(words)}</i>"


def word_card(word: Word) -> str:
    return entry_card(word.example.text, word.word, word.description)


async def find_target(session: AsyncSession, user: User, field: str, query: str) -> Word | Example | None:
    """Looks the target up by id first, then by its exact text (case-insensitive)."""
    if field == "example":
        found = await vocabulary.get_example(session, user.id, int(query)) if query.isdigit() else None
        return found or await vocabulary.find_example(session, user.id, query)
    found = await vocabulary.get_word(session, user.id, int(query)) if query.isdigit() else None
    return found or await vocabulary.find_word(session, user.id, **{field: query})


async def load_target(session: AsyncSession, user: User, field: str, target_id: int) -> Word | Example | None:
    if field == "example":
        return await vocabulary.get_example(session, user.id, target_id)
    return await vocabulary.get_word(session, user.id, target_id)


@router.message(Command("change"))
async def change_cmd(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer(
        "<b>Small reminder</b>\n"
        "<i>Use /data first to look up the ids of your words and examples.</i>\n\n"
        "<b>1.</b> Choose what to change or delete\n"
        "<b>2.</b> Choose the action\n"
        "<b>3.</b> Send the id (or the exact text) and then the new value",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "What are we changing? 👀",
        reply_markup=keyboard(*((f.capitalize(), EditChoice(field=f)) for f in FIELDS), width=3),
    )


@router.callback_query(EditChoice.filter((F.field != "") & (F.action == "")))
async def choose_action(callback: CallbackQuery, callback_data: EditChoice) -> None:
    await drop_markup(callback)
    field = callback_data.field
    buttons = [("✏️ Edit", EditChoice(field=field, action="edit"))]
    if field != "description":  # a description cannot exist without its word
        buttons.append(("🗑 Delete", EditChoice(field=field, action="delete")))
    await callback.message.answer(
        f"Okay, what do you want to do with your {field}?", reply_markup=keyboard(*buttons)
    )


@router.callback_query(EditChoice.filter(F.action != ""))
async def ask_target(callback: CallbackQuery, callback_data: EditChoice, state: FSMContext) -> None:
    await drop_markup(callback)
    await state.update_data(edit_field=callback_data.field, edit_action=callback_data.action)
    owner = "example" if callback_data.field == "example" else "word"
    await callback.message.answer(
        f"Now send the id of the {owner} to {callback_data.action} it "
        f"(or its exact {callback_data.field} text)."
    )
    await state.set_state(Editing.target)


@router.message(Editing.target, TEXT_INPUT)
async def got_target(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    field, action = data["edit_field"], data["edit_action"]
    target = await find_target(session, user, field, message.text.strip())
    if target is None:
        await message.answer(f"🕵️ I couldn't find that {field}. Check the id in /data and try again.")
        return

    await state.update_data(target_id=target.id)
    if isinstance(target, Example):
        await message.answer(f"<b>Here's what I found</b> 🚁\n\n{example_card(target)}")
    else:
        await message.answer(f"<b>Here's what I found</b> 🚁\n\n{word_card(target)}")

    if action == "delete":
        warning = (
            "This deletes the example <b>and all its words</b>."
            if isinstance(target, Example)
            else "The example is deleted too if no other words use it."
        )
        await message.answer(
            f"Are you sure you want to <b>delete</b> it? 🧨\n{warning}",
            reply_markup=keyboard(("💥 Yes", Nav(action="edit_delete_yes")), ("🕊 No", Nav(action="cancel"))),
        )
        await state.set_state(Editing.confirm_delete)
    else:
        await message.answer(f"Send me the new {field} 🖍")
        await state.set_state(Editing.value)


@router.message(Editing.value, TEXT_INPUT)
async def got_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    http: AsyncClient,
    settings: Settings,
) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    target = await load_target(session, user, field, data["target_id"])
    if target is None:
        await reset_state(state)
        await message.answer("🕵️ It seems this was deleted in the meantime.", reply_markup=NEXT_STEP)
        return

    try:
        value = vocabulary.validate(field, message.text)
        if isinstance(target, Example):
            await vocabulary.update_example(session, target, value)
        elif field == "word":
            target.word = value
            target.category = await lookup_category(http, settings.dictionary_api_url, value)
        else:
            target.description = value
    except vocabulary.ValidationError as exc:
        await message.answer(f"{exc} Try again.")
        return
    await session.commit()
    logger.info("@%s edited %s #%d", user.nickname, field, target.id)

    await reset_state(state)
    card = example_card(target) if isinstance(target, Example) else word_card(target)
    await message.answer(f"<b>Updated!</b> ✅\n\n{card}", reply_markup=NEXT_STEP)


@router.callback_query(Editing.confirm_delete, Nav.filter(F.action == "edit_delete_yes"))
async def confirm_delete(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await drop_markup(callback)
    data = await state.get_data()
    await reset_state(state)
    target = await load_target(session, user, data["edit_field"], data["target_id"])
    if isinstance(target, Example):
        await vocabulary.delete_example(session, target)
    elif target is not None:
        await vocabulary.delete_word(session, target)
    await session.commit()
    logger.info("@%s deleted %s #%d", user.nickname, data["edit_field"], data["target_id"])
    await callback.message.answer("Deleted 🧹", reply_markup=NEXT_STEP)


@router.callback_query(Nav.filter(F.action == "change_again"))
async def change_again(callback: CallbackQuery, state: FSMContext) -> None:
    await drop_markup(callback)
    await change_cmd(callback.message, state)
