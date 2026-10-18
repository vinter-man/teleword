import random
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from teleword.bot.handlers.adding import entry_card
from teleword.bot.keyboards import Answer, Nav, keyboard
from teleword.bot.utils import drop_markup, reset_state, shorten
from teleword.config import ASSETS_DIR, Settings
from teleword.db.models import User
from teleword.services import lessons, starter_words, vocabulary

router = Router(name="lessons")

PRAISE = ["Well done!", "Super!", "Cool!", "Excellent!", "Perfect!", "Great!", "Fabulous!", "Correct!"]
COMFORT = [
    "Mistakes teach!",
    "Mistakes are the best teacher!",
    "Don't be upset!",
    "Not quite.",
    "Now you will remember this!",
    "We learn from failure, not from success!",
]
EASTER_EGG = "a|b|c|d"
EXIT = ("🔚 Exit", Nav(action="cancel"))

INTRO = (
    "<b>Let's start the lesson</b>\n\n"
    "🧐 <b>How it works</b>\n"
    f"• {lessons.LESSON_SIZE} tasks built from your words; the ones you struggle with come first and last.\n"
    "• Finish in one go: any other command ends the lesson and its progress is lost.\n"
    "• Attempts are unlimited, but only first-try answers count towards your result.\n\n"
    "😎 <b>Tips</b>\n"
    "• Use the buttons, or type a/b/c/d (for word tasks you can type the word itself).\n"
    "• Try to recall the answer before looking at the options."
)


class Lesson(StatesGroup):
    active = State()


def task_text(task: dict, number: int) -> str:
    main = lessons.main_option(task)
    if task["kind"] == lessons.PICK_DESCRIPTION:
        question, prompt, field = "Choose the correct description of the word", main["word"], "description"
    else:
        question, prompt, field = "Choose the word that matches the description", main["description"], "word"
    options = "\n\n".join(
        f"<b>{key}.</b> <i>{escape(option[field])}</i>" for key, option in task["options"].items()
    )
    return f"<b>{number}/{lessons.LESSON_SIZE}.</b> {question}\n\n<b>{escape(prompt)}</b>\n\n{options}"


def answer_keyboard(index: int):
    builder = InlineKeyboardBuilder()
    for key in lessons.OPTION_KEYS:
        builder.button(text=key.upper(), callback_data=Answer(task=index, key=key))
    builder.button(text=EXIT[0], callback_data=EXIT[1])
    builder.adjust(len(lessons.OPTION_KEYS), 1)
    return builder.as_markup()


async def start_lesson(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await reset_state(state)
    await message.answer("🧘 Preparing your lesson…", reply_markup=ReplyKeyboardRemove())
    try:
        tasks = lessons.build_lesson(await lessons.load_cards(session, user.id))
    except lessons.NotEnoughWords as exc:
        await message.answer(
            f"👮 A lesson needs at least <b>{lessons.LESSON_SIZE}</b> words, you have <b>{exc.have}</b>.\n\n"
            "🤔 I can add 15 starter words for you; delete them later with /change "
            "once you have enough of your own.",
            reply_markup=keyboard(
                ("🧞 Add starter words", Nav(action="starter_words")),
                ("🙅 No, thanks", Nav(action="cancel")),
            ),
        )
        return

    await state.set_data(
        {
            **await state.get_data(),
            "tasks": tasks,
            "index": 0,
            "attempts": 0,
            "mistakes": 0,
            "results": [],
            "awaiting_answer": False,
        }
    )
    await state.set_state(Lesson.active)
    await message.answer(INTRO, reply_markup=keyboard(("🏂 Start", Nav(action="lesson_next")), EXIT))


@router.message(Command("lesson"))
async def lesson_cmd(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await start_lesson(message, state, session, user)


@router.callback_query(Nav.filter(F.action == "lesson_again"))
async def lesson_again(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await drop_markup(callback)
    await start_lesson(callback.message, state, session, user)


@router.callback_query(Lesson.active, Nav.filter(F.action == "lesson_next"))
async def next_task(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, settings: Settings
) -> None:
    await drop_markup(callback)
    data = await state.get_data()
    index = data["index"]
    if index >= len(data["tasks"]):
        await finish(callback.message, state, session, user, settings)
        return
    await state.update_data(awaiting_answer=True)
    await callback.message.answer(
        task_text(data["tasks"][index], index + 1), reply_markup=answer_keyboard(index)
    )


@router.callback_query(Lesson.active, Answer.filter())
async def answer_button(callback: CallbackQuery, callback_data: Answer, state: FSMContext) -> None:
    data = await state.get_data()
    if callback_data.task != data["index"] or not data["awaiting_answer"]:
        await callback.answer("This task is already answered.")
        return
    await drop_markup(callback)
    await check_answer(callback.message, state, data, callback_data.key)


@router.message(Lesson.active, F.text.lower() == EASTER_EGG)
async def easter_egg(message: Message) -> None:
    await message.answer_photo(
        FSInputFile(ASSETS_DIR / "easter_egg" / "photo.png"),
        caption=(
            "<b>Congratulations, you found an Easter egg!</b> 🥚\n\n"
            "I dedicate it to the first person who found it as a bug.\n\n"
            "Toha, brother, thank you for always helping me and never turning away. "
            "I hope we meet many more times, somewhere warm like Bora-Bora "
            "and not in this cold and hopelessness 🏖"
        ),
    )
    await message.answer_audio(FSInputFile(ASSETS_DIR / "easter_egg" / "song.mp3"))


@router.message(Lesson.active, F.text & ~F.text.startswith("/"))
async def answer_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data["awaiting_answer"]:
        await message.answer("Press the button above to continue 👆")
        return
    key = lessons.resolve_answer(data["tasks"][data["index"]], message.text)
    if key is None:
        await message.answer(
            f"🚓 Something is wrong here: <i>{escape(shorten(message.text))}</i>\n\n"
            "Answer with a letter: <b>a | b | c | d</b>, or use the buttons."
        )
        return
    await check_answer(message, state, data, key)


async def check_answer(message: Message, state: FSMContext, data: dict, key: str) -> None:
    task = data["tasks"][data["index"]]
    option = task["options"][key]
    attempts = data["attempts"] + 1
    card = entry_card(option["example"], option["word"], option["description"])

    if option["is_correct"]:
        result = {"word_id": task["word_id"], "attempts": attempts, "mistakes": data["mistakes"]}
        await state.update_data(
            index=data["index"] + 1,
            attempts=0,
            mistakes=0,
            results=[*data["results"], result],
            awaiting_answer=False,
        )
        text, button = f"<b>{random.choice(PRAISE)}</b>", ("✔️ Next", Nav(action="lesson_next"))
    else:
        await state.update_data(attempts=attempts, mistakes=data["mistakes"] + 1, awaiting_answer=False)
        text, button = f"<b>{random.choice(COMFORT)}</b>", ("🔙 Try again", Nav(action="lesson_next"))

    await message.answer(f"{text}\n\n{card}", reply_markup=keyboard(button, EXIT))


async def finish(
    message: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings
) -> None:
    results = (await state.get_data())["results"]
    await reset_state(state)
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    summary = await lessons.finish_lesson(session, user, results, settings.today())
    await session.commit()

    await message.answer(
        "<b>End of the lesson</b> 🎉\n\n"
        f"⚡ Result: <b>{summary.success_percent}%</b> on the first try\n"
        f"❌ Mistakes: <b>{summary.mistakes}</b>\n"
        f"💎 Points: <b>+{summary.points}</b>\n"
        f"🔥 Streak: <b>{summary.streak}</b> day{'s' if summary.streak != 1 else ''}",
        reply_markup=keyboard(
            ("🧗 Once again", Nav(action="lesson_again")), ("⛰ Exit", Nav(action="cancel"))
        ),
    )


@router.callback_query(Nav.filter(F.action == "starter_words"))
async def add_starter_words(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await drop_markup(callback)
    await reset_state(state)
    await starter_words.add_starter_words(session, user)
    total = await vocabulary.count_words(session, user.id)
    await session.commit()
    await callback.message.answer(
        f"⛷ Done, you now have <b>{total}</b> words.",
        reply_markup=keyboard(("🏂 Start a lesson", Nav(action="lesson_again")), EXIT),
    )
