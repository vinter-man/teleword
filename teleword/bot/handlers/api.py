from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.handlers.adding import TEXT_INPUT
from teleword.bot.keyboards import ApiDecision, Nav, keyboard
from teleword.bot.utils import drop_markup, reset_state
from teleword.config import Settings
from teleword.db.models import User
from teleword.services import api_keys

router = Router(name="api")


class ApiRequest(StatesGroup):
    purpose = State()


def instructions(base_url: str) -> str:
    return (
        "<b>How to use the API</b>\n\n"
        "Send your key in the <code>X-API-Key</code> header:\n"
        f"<code>curl -H 'X-API-Key: YOUR_KEY' {base_url}/api/words</code>\n\n"
        "<b>GET</b> <code>/api/words</code> – all your words\n"
        "<b>GET</b> <code>/api/lesson</code> – a freshly built lesson\n"
        "<b>GET | PATCH | DELETE</b> <code>/api/words/{id}</code>\n"
        '<b>POST</b> <code>/api/words</code> – <code>{"word", "description", "example_id"}</code>\n'
        "<b>GET</b> <code>/api/examples</code>\n"
        "<b>GET | PUT | DELETE</b> <code>/api/examples/{id}</code>\n"
        '<b>POST</b> <code>/api/examples</code> – <code>{"text"}</code>\n\n'
        f"Interactive docs: {base_url}/docs"
    )


def key_message(key: str, base_url: str) -> str:
    return (
        "🔑 <b>Your API key</b>\n"
        f"<code>{key}</code>\n\n"
        "Keep it secret: anyone with this key can read and change your words. "
        "If it leaks, generate a new one in /api.\n\n" + instructions(base_url)
    )


@router.message(Command("api"))
async def api_cmd(
    message: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings
) -> None:
    await reset_state(state)
    record = await api_keys.get(session, user.id)
    if record is not None and record.is_active:
        await message.answer(
            "You already have an API key. Lost it? Generate a new one; the old key stops working.\n\n"
            + instructions(settings.api_public_url),
            reply_markup=keyboard(("🔄 New key", Nav(action="api_rotate")), width=1),
        )
        return
    if record is not None:
        await message.answer("⏳ Your request is waiting for the admin's approval.")
        return

    await message.answer(
        "A couple of steps to your private API key 🔑\n\n"
        "Tell me what you'd like to use the API for (feel free to describe).",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(ApiRequest.purpose)


@router.message(ApiRequest.purpose, TEXT_INPUT)
async def got_purpose(
    message: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings
) -> None:
    purpose = message.text.strip()
    low, high = api_keys.PURPOSE_LIMITS
    if not low <= len(purpose) <= high:
        await message.answer(f"🚓 Please describe it in {low}-{high} characters.")
        return

    await api_keys.request(session, user, purpose)
    await session.commit()
    await reset_state(state)

    await message.bot.send_message(
        settings.admin_id,
        "<b>API key request</b>\n"
        f"User: @{escape(user.nickname)} (<code>{user.tg_id}</code>)\n"
        f"Purpose: <i>{escape(purpose)}</i>",
        reply_markup=keyboard(
            ("✅ Approve", ApiDecision(action="approve", user_id=user.id)),
            ("❌ Reject", ApiDecision(action="reject", user_id=user.id)),
        ),
    )
    await message.answer("Cool! The admin will review your request, and the key will arrive right here.")


@router.callback_query(ApiDecision.filter())
async def admin_decision(
    callback: CallbackQuery, callback_data: ApiDecision, session: AsyncSession, bot: Bot, settings: Settings
) -> None:
    if callback.from_user.id != settings.admin_id:
        await callback.answer("Only the admin can do this.", show_alert=True)
        return
    await drop_markup(callback)

    requester = await session.get(User, callback_data.user_id)
    if requester is None:
        await callback.message.answer("The user no longer exists.")
        return

    if callback_data.action == "approve":
        key = await api_keys.approve(session, requester.id)
        await session.commit()
        if key is None:
            await callback.message.answer("The request was withdrawn.")
            return
        await bot.send_message(requester.tg_id, key_message(key, settings.api_public_url))
        await callback.message.answer(f"✅ Key sent to @{escape(requester.nickname)}.")
    else:
        await api_keys.reject(session, requester.id)
        await session.commit()
        await bot.send_message(requester.tg_id, "Sorry, your API key request was declined.")
        await callback.message.answer(f"❌ Request from @{escape(requester.nickname)} declined.")


@router.callback_query(Nav.filter(F.action == "api_rotate"))
async def rotate_key(callback: CallbackQuery, session: AsyncSession, user: User, settings: Settings) -> None:
    await drop_markup(callback)
    key = await api_keys.rotate(session, user.id)
    await session.commit()
    if key is None:
        await callback.message.answer("You don't have an active key. Request one with /api.")
        return
    await callback.message.answer(key_message(key, settings.api_public_url))
