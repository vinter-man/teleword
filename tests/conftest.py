from datetime import date

import httpx
import pytest
from aiogram.fsm.storage.memory import MemoryStorage

from teleword.config import Settings
from teleword.db import create_engine, create_sessionmaker, init_db
from teleword.services import users
from tests.telegram import BotHarness, FakeTelegramSession, build_dispatcher

ADMIN_ID = 1000
TODAY = date(2026, 10, 18)


def dictionary_handler(request: httpx.Request) -> httpx.Response:
    """Fake dictionaryapi.dev: knows a couple of words, 404 for everything else."""
    known = {"arrow": "noun", "run": "verb", "happy": "adjective"}
    word = request.url.path.rsplit("/", 1)[-1]
    if word not in known:
        return httpx.Response(404, json={"title": "No Definitions Found"})
    return httpx.Response(200, json=[{"word": word, "meanings": [{"partOfSpeech": known[word]}]}])


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        bot_token="42:TEST",
        admin_id=ADMIN_ID,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        dictionary_api_url="https://dictionary.test/entries/en/",
        api_public_url="https://teleword.test",
        timezone="UTC",
    )


@pytest.fixture
async def engine(settings):
    engine = create_engine(settings.database_url)
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessionmaker(engine):
    return create_sessionmaker(engine)


@pytest.fixture
async def session(sessionmaker):
    async with sessionmaker() as session:
        yield session


async def make_user(session, tg_id: int = 1, username: str = "alice"):
    user, _ = await users.get_or_create(
        session, tg_id=tg_id, username=username, lang_code="en", is_bot=False, today=TODAY
    )
    await session.commit()
    return user


@pytest.fixture
async def user(session):
    return await make_user(session)


@pytest.fixture
async def http():
    async with httpx.AsyncClient(transport=httpx.MockTransport(dictionary_handler)) as client:
        yield client


@pytest.fixture(scope="session")
def dispatcher():
    # Routers are module-level singletons, so one dispatcher serves the whole test session.
    return build_dispatcher()


@pytest.fixture
async def bot(dispatcher, settings, sessionmaker, http):
    dispatcher.fsm.storage = MemoryStorage()
    harness = BotHarness(
        dispatcher, FakeTelegramSession(), settings=settings, sessionmaker=sessionmaker, http=http
    )
    yield harness
    await harness.close()
