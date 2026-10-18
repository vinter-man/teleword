import asyncio
import logging
from html import escape

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.middlewares import IsAdmin
from teleword.bot.utils import reset_state
from teleword.services import users

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())

PANEL = (
    "<b>Admin panel</b>\n\n"
    "/admin – this panel\n"
    "/admin_blacklist – show blacklisted users\n"
    "/admin_ban <code>tg_id</code> – blacklist a user\n"
    "/admin_unban <code>tg_id</code> – remove a user from the blacklist\n"
    "/admin_broadcast <code>text</code> – send a message to every user"
)
# Telegram allows about 30 messages per second for bots.
BROADCAST_DELAY = 0.05


@router.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer(PANEL)


@router.message(Command("admin_blacklist", "admin_show_bl", "adminshowbl"))
async def blacklist_cmd(message: Message, session: AsyncSession) -> None:
    blacklisted = await users.list_blacklisted(session)
    if not blacklisted:
        await message.answer("The blacklist is empty.")
        return
    lines = "\n".join(f"• @{escape(u.nickname)} (<code>{u.tg_id}</code>)" for u in blacklisted)
    await message.answer(f"<b>Blacklist</b>\n{lines}")


async def _set_blacklisted(
    message: Message, command: CommandObject, session: AsyncSession, value: bool
) -> None:
    if not command.args or not command.args.strip().lstrip("-").isdigit():
        await message.answer(f"Usage: /{command.command} <code>tg_id</code>")
        return
    user = await users.set_blacklisted(session, int(command.args.strip()), value)
    if user is None:
        await message.answer("No user with this id.")
        return
    await session.commit()
    await message.answer(f"@{escape(user.nickname)} is {'now' if value else 'no longer'} blacklisted.")


@router.message(Command("admin_ban"))
async def ban_cmd(message: Message, command: CommandObject, session: AsyncSession) -> None:
    await _set_blacklisted(message, command, session, True)


@router.message(Command("admin_unban"))
async def unban_cmd(message: Message, command: CommandObject, session: AsyncSession) -> None:
    await _set_blacklisted(message, command, session, False)


@router.message(Command("admin_broadcast", "admintell"))
async def broadcast_cmd(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    text = (command.args or "").strip()
    if not text:
        await message.answer(f"Usage: /{command.command} <code>your message to all users</code>")
        return

    recipients = await users.list_active_tg_ids(session)
    delivered = 0
    for tg_id in recipients:
        try:
            await bot.send_message(tg_id, text, parse_mode=None)
            delivered += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(tg_id, text, parse_mode=None)
                delivered += 1
            except TelegramAPIError as retry_exc:
                logger.warning("Broadcast to %s failed: %s", tg_id, retry_exc)
        except TelegramAPIError as exc:  # blocked the bot, deleted account, ...
            logger.warning("Broadcast to %s failed: %s", tg_id, exc)
        await asyncio.sleep(BROADCAST_DELAY)

    await message.answer(f"📣 Delivered to {delivered} of {len(recipients)} users.")
