import asyncio
import logging
import time

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.charts import render_stats_chart
from teleword.bot.utils import reset_state
from teleword.config import Settings
from teleword.db.models import User
from teleword.services import stats, vocabulary
from teleword.services.streak import current_streak

router = Router(name="statistic")
logger = logging.getLogger(__name__)


@router.message(Command("statistic", "stats"))
async def statistic_cmd(
    message: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings
) -> None:
    await reset_state(state)
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

    today = settings.today()
    streak = current_streak(user.streak, user.last_lesson_date, today)
    words = await vocabulary.count_words(session, user.id)
    series = await stats.recent_stats(session, user.id, today)
    caption = (
        f"🔥 Streak: <b>{streak}</b> day{'s' if streak != 1 else ''}\n"
        f"🛬 First use: <b>{user.created_at:%d.%m.%Y}</b>\n"
        f"💎 Total points: <b>{user.points}</b>\n"
        f"📘 Total words: <b>{words}</b>"
    )

    try:
        started = time.perf_counter()
        chart = await asyncio.to_thread(render_stats_chart, series)
        logger.info("Chart for @%s rendered in %d ms", user.nickname, (time.perf_counter() - started) * 1000)
    except Exception:
        logger.exception("Failed to render the chart for %s", user.tg_id)
        await message.answer(caption, reply_markup=ReplyKeyboardRemove())
        return
    await message.answer_photo(
        BufferedInputFile(chart, filename="statistic.png"),
        caption=caption,
        reply_markup=ReplyKeyboardRemove(),
    )
