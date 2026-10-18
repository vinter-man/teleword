from datetime import datetime, time, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from teleword.bot.keyboards import Nav
from teleword.bot.utils import drop_markup, reset_state
from teleword.config import Settings

router = Router(name="common")

HELP = (
    "<b>Hi, I'm Teleword Bot</b> 🤖\n"
    "I help you remember new English words using the examples you found yourself.\n\n"
    "⚙️ <i>Basic</i> (any of these cancels the current action)\n"
    "/start – let's start\n"
    "/cancel – cancel the current action\n"
    "/help – what I can do\n\n"
    "📘 <i>Add your words</i>\n"
    "/add – add a new word with an example\n\n"
    "🖌 <i>Practice</i>\n"
    "/lesson – a 15-task quiz built from your words (needs at least 15 words)\n\n"
    "📊 <i>Progress</i>\n"
    "/statistic – your streak, points and the last 7 days\n\n"
    "📬 <i>Download your words</i>\n"
    "/data – get your words as Excel, JSON, XML or CSV\n\n"
    "🦋 <i>Edit or delete</i>\n"
    "/change – edit or delete a word, description or example\n\n"
    "🎣 <i>Developers</i>\n"
    "/api – request a personal REST API key\n\n"
    "⌚ <i>Bot time</i>\n"
    "/time – the bot's clock and time left until the day ends (streaks count by this clock)"
)


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer(
        "Let's start! 👋\n\n"
        "Add words you meet in films, books or conversations with /add, "
        "then practise them every day with /lesson.\n\n"
        "All commands: /help",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("help"))
async def help_cmd(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer(HELP, reply_markup=ReplyKeyboardRemove())


@router.message(Command("cancel", "end", "finish"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    await reset_state(state)
    await message.answer("Action cancelled.\nAll commands: /help", reply_markup=ReplyKeyboardRemove())


@router.callback_query(Nav.filter(F.action == "cancel"))
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await drop_markup(callback)
    await reset_state(state)
    await callback.message.answer("Main menu: /help", reply_markup=ReplyKeyboardRemove())


def time_until_midnight(now: datetime) -> timedelta:
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=now.tzinfo)
    return midnight - now


@router.message(Command("time", "clock", "now"))
async def time_cmd(message: Message, state: FSMContext, settings: Settings) -> None:
    await reset_state(state)
    now = settings.now()
    hours, rest = divmod(int(time_until_midnight(now).total_seconds()), 3600)
    await message.answer(
        f"⏱ Time: <b>{now:%a, %H:%M}</b> ({settings.timezone})\n\n"
        f"📅 Date: <b>{now:%d.%m.%Y}</b>\n\n"
        f"⌛ Until the end of the day: <b>{hours} h {rest // 60} min</b>"
    )
