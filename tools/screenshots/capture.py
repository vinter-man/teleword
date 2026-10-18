"""Records real bot conversations for the README screenshots.

Every scenario goes through the real dispatcher, middlewares, services and a SQLite database;
only the Telegram network layer is replaced. The script stores what the bot actually sent
(texts, buttons, the statistics chart, documents), the log lines it produced and `sqlite3`
output, and the Remotion project in this folder draws them.

    uv run python tools/screenshots/capture.py
"""

import asyncio
import json
import logging
import random
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendAudio, SendDocument, SendMessage, SendPhoto

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from teleword.config import Settings  # noqa: E402
from teleword.db import create_engine, create_sessionmaker, init_db  # noqa: E402
from teleword.services import lessons, users, vocabulary  # noqa: E402
from tests.telegram import BotHarness, FakeTelegramSession, build_dispatcher  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "public" / "data"
DB_PATH = HERE / ".cache" / "teleword.db"

BOT_ID = 8838584288  # @teleword_learning_bot
USER_ID, USERNAME = 517204883, "demo_learner"
ADMIN_ID, ADMIN_NAME = 341677011, "vindemure"

EXAMPLE = "Remember when, you were choking this morning."
WORD = "choke"
DESCRIPTION = (
    "(of a person or animal) have severe difficulty in breathing because of a constricted "
    "or obstructed throat or a lack of air."
)


class LogCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        for line in self.format(record).splitlines():
            self.lines.append(f"bot-1  | {line}")

    def take(self) -> list[str]:
        lines, self.lines = self.lines, []
        return lines


class Chat:
    """One Telegram chat as seen by a single user. Message times are the real capture times."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    @staticmethod
    def now() -> str:
        return datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%H:%M")


class Recorder:
    def __init__(self, harness: BotHarness) -> None:
        self.harness = harness
        self.chats: dict[int, Chat] = {}

    def chat(self, chat_id: int) -> Chat:
        return self.chats.setdefault(chat_id, Chat())

    def reset(self, chat_id: int) -> Chat:
        self.chats[chat_id] = Chat()
        return self.chats[chat_id]

    def _store(self, calls: list) -> None:
        for call in calls:
            if not isinstance(call, SendMessage | SendPhoto | SendDocument | SendAudio):
                continue
            chat = self.chat(call.chat_id)
            message: dict = {"from": "bot", "time": chat.now()}
            markup = getattr(call, "reply_markup", None)
            if markup is not None and hasattr(markup, "inline_keyboard"):
                message["buttons"] = [[b.text for b in row] for row in markup.inline_keyboard]
            if isinstance(call, SendMessage):
                message["html"] = call.text
            elif isinstance(call, SendPhoto):
                name = f"photo-{len(list(OUT.glob('photo-*')))}.png"
                (OUT / name).write_bytes(call.photo.data)
                message.update(photo=f"data/{name}", html=call.caption or "")
            elif isinstance(call, SendDocument):
                message.update(
                    document={"name": call.document.filename, "size": _size(len(call.document.data))},
                    html=call.caption or "",
                )
            else:
                continue
            chat.messages.append(message)

    async def say(self, text: str, user_id: int = USER_ID, username: str = USERNAME) -> None:
        chat = self.chat(user_id)
        chat.messages.append({"from": "user", "text": text, "time": chat.now()})
        self._store(await self.harness.send(text, user_id=user_id, username=username))

    async def press(self, label: str, user_id: int = USER_ID, username: str = USERNAME) -> None:
        """Presses an inline button of the latest message that has it; the bot removes that keyboard."""
        chat = self.chat(user_id)
        for message in reversed(chat.messages):
            for row in message.get("buttons", []):
                if label in row:
                    data = self._callback_data(user_id, label)
                    del message["buttons"]
                    self._store(await self.harness.click(data, user_id=user_id, username=username))
                    return
        raise LookupError(label)

    def _callback_data(self, user_id: int, label: str) -> str:
        for call in reversed(self.harness.session.calls):
            markup = getattr(call, "reply_markup", None)
            if getattr(call, "chat_id", None) == user_id and hasattr(markup, "inline_keyboard"):
                for row in markup.inline_keyboard:
                    for button in row:
                        if button.text == label:
                            return button.callback_data
        raise LookupError(label)


def _size(n: int) -> str:
    return f"{n} B" if n < 1024 else f"{n / 1024:.1f} KB"


async def simulate_history(session, user, today) -> None:
    """Lessons on the previous six days (with a day off), through the same service the bot uses."""
    rng = random.Random(18)
    for days_ago in (6, 5, 3, 2, 1):
        for _ in range(rng.choice([1, 1, 2, 3])):
            tasks = lessons.build_lesson(await lessons.load_cards(session, user.id), rng)
            mistakes = [rng.choice([0, 0, 0, 0, 1, 2]) for _ in tasks]
            results = [
                {"word_id": t["word_id"], "attempts": 1 + m, "mistakes": m}
                for t, m in zip(tasks, mistakes, strict=True)
            ]
            await lessons.finish_lesson(session, user, results, today - timedelta(days=days_ago))


def save_chat(name: str, chat: Chat, **extra) -> None:
    (OUT / f"{name}.json").write_text(json.dumps({"messages": chat.messages, **extra}, indent=2))


def save_terminal(name: str, lines: list[str], title: str) -> None:
    (OUT / f"{name}.json").write_text(json.dumps({"title": title, "lines": lines}, indent=2))


def sql(queries: list[str]) -> list[str]:
    lines = []
    for query in queries:
        lines.append(f"sqlite> {query}")
        result = subprocess.run(
            ["sqlite3", "-table", str(DB_PATH), query], capture_output=True, text=True, check=True
        )
        lines.extend(result.stdout.rstrip("\n").splitlines())
        lines.append("")
    lines.append("sqlite> ")
    return lines


async def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)

    collector = LogCollector()
    logging.basicConfig(level=logging.INFO, handlers=[collector])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sql_log = logging.getLogger("sqlalchemy.engine")

    settings = Settings(
        bot_token=f"{BOT_ID}:capture",
        admin_id=ADMIN_ID,
        database_url=f"sqlite+aiosqlite:///{DB_PATH}",
        api_public_url="http://localhost:8790",
        timezone="Europe/Kyiv",
    )
    engine = create_engine(settings.database_url)
    await init_db(engine)
    sessionmaker = create_sessionmaker(engine)

    async with httpx.AsyncClient() as http:
        dispatcher = build_dispatcher()
        dispatcher.fsm.storage = MemoryStorage()
        harness = BotHarness(
            dispatcher, FakeTelegramSession(), settings=settings, sessionmaker=sessionmaker, http=http
        )
        harness.bot = Bot(
            settings.bot_token.get_secret_value(),
            session=harness.session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        rec = Recorder(harness)

        # First steps: /start registers the user, /help shows the menu.
        rec.reset(USER_ID)
        collector.take()
        sql_log.setLevel(logging.INFO)
        await rec.say("/start")
        sql_log.setLevel(logging.WARNING)
        await rec.say("/help")
        save_terminal("first-steps-back", collector.take(), "docker compose logs -f bot")
        save_chat("first-steps-front", rec.chats[USER_ID], date="October 18")
        save_terminal(
            "first-steps-back2",
            sql(["SELECT * FROM users;"]),
            "sqlite3 /app/data/teleword.db",
        )

        # Adding a word; SQL echo on, as in the original "under the hood" screenshots.
        rec.reset(USER_ID)
        await rec.say("/add")
        collector.take()
        sql_log.setLevel(logging.INFO)
        await rec.say(EXAMPLE)
        await rec.say(WORD)
        await rec.say(DESCRIPTION)
        sql_log.setLevel(logging.WARNING)
        save_terminal("addlogs", collector.take(), "docker compose logs -f bot")
        save_terminal(
            "addsql",
            sql(
                [
                    "SELECT * FROM examples ORDER BY id DESC LIMIT 1;",
                    "SELECT * FROM words ORDER BY id DESC LIMIT 1;",
                ]
            ),
            "sqlite3 /app/data/teleword.db",
        )

        # Enough words for lessons, and six days of history for the chart.
        await rec.say("/lesson")
        await rec.press("🧞 Add starter words")
        async with sessionmaker() as session:
            user = await users.get_by_tg_id(session, USER_ID)
            await simulate_history(session, user, settings.today())
            choke = await vocabulary.find_word(session, user.id, word=WORD)
            choke.rating = 3  # a hard one, so it opens the lesson
            await session.commit()

        # Lesson: start until the first task asks about "choke", answer it correctly.
        for _ in range(50):
            rec.reset(USER_ID)
            await rec.say("/lesson")
            first = (await harness.state_data(USER_ID))["tasks"][0]
            if lessons.main_option(first)["word"] == WORD:
                break
        await rec.press("🏂 Start")
        save_chat("lesson1", rec.chats[USER_ID])
        correct = next(k for k, o in first["options"].items() if o["is_correct"])
        rec.reset(USER_ID)
        await rec.say(correct)
        save_chat("lesson2", rec.chats[USER_ID])

        # Finish the lesson (one mistake on the fourth task) so today shows up on the chart.
        data = await harness.state_data(USER_ID)
        for index in range(1, len(data["tasks"])):
            await rec.press("✔️ Next")
            options = data["tasks"][index]["options"]
            if index == 3:
                wrong = next(k for k, o in options.items() if not o["is_correct"])
                await rec.say(wrong)
                await rec.press("🔙 Try again")
            await rec.say(next(k for k, o in options.items() if o["is_correct"]))
        await rec.press("✔️ Next")

        # Statistics.
        rec.reset(USER_ID)
        collector.take()
        sql_log.setLevel(logging.INFO)
        await rec.say("/statistic")
        sql_log.setLevel(logging.WARNING)
        save_terminal("statistic-back", collector.take(), "docker compose logs -f bot")
        save_chat("statistic-front", rec.chats[USER_ID])

        # Export.
        rec.reset(USER_ID)
        await rec.say("/data")
        await rec.press("All my words")
        await rec.press("In order of addition")
        await rec.press("All formats")
        save_chat("data-cmd", rec.chats[USER_ID])

        # Change / delete.
        rec.reset(USER_ID)
        await rec.say("/change")
        await rec.press("Word")
        await rec.press("🗑 Delete")
        await rec.say(WORD)
        save_chat("change-cmd", rec.chats[USER_ID])
        await rec.press("🕊 No")

        # API key: request, admin approval, the key with instructions.
        rec.reset(USER_ID)
        rec.reset(ADMIN_ID)
        await rec.say("/api")
        await rec.say(
            "Hello, I would like to write a solid README.md file for GitHub, "
            "so that the user can understand what's what with a live example."
        )
        save_chat("api-request", rec.chats[USER_ID], date="October 18")
        save_chat("api-admin", rec.chats[ADMIN_ID])
        rec.reset(USER_ID)
        await rec.press("✅ Approve", user_id=ADMIN_ID, username=ADMIN_NAME)
        save_chat("api-doc", rec.chats[USER_ID])

        await harness.close()
    await engine.dispose()

    with sqlite3.connect(DB_PATH) as db:
        print("words:", db.execute("SELECT count(*) FROM words").fetchone()[0])
    print("captured:", ", ".join(sorted(p.stem for p in OUT.glob("*.json"))))


if __name__ == "__main__":
    asyncio.run(main())
