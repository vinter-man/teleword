from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from teleword.api.schemas import ExampleIn, ExampleOut, Task, WordIn, WordOut, WordPatch
from teleword.config import Settings, get_settings
from teleword.db import create_engine, create_sessionmaker
from teleword.db.models import Example, User
from teleword.services import api_keys, lessons, vocabulary
from teleword.services.dictionary import lookup_category

DESCRIPTION = """
REST interface to your Teleword vocabulary.

Get a key from the bot with the `/api` command and send it in the `X-API-Key` header.
"""


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


Session = Annotated[AsyncSession, Depends(get_session)]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def current_user(session: Session, key: Annotated[str | None, Security(api_key_header)]) -> User:
    user = await api_keys.authenticate(session, key) if key else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def _not_found(what: str) -> HTTPException:
    # Other users' objects are reported as missing too, so ids do not leak.
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


async def _category(request: Request, word: str) -> str | None:
    return await lookup_category(request.app.state.http, request.app.state.settings.dictionary_api_url, word)


router = APIRouter()


@router.get("/health", tags=["service"])
async def health(session: Session) -> dict:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/api/words", tags=["words"])
async def list_words(session: Session, user: CurrentUser) -> list[WordOut]:
    return [WordOut.of(w) for w in await vocabulary.list_words(session, user.id)]


@router.post("/api/words", status_code=status.HTTP_201_CREATED, tags=["words"])
async def create_word(body: WordIn, request: Request, session: Session, user: CurrentUser) -> WordOut:
    example = await vocabulary.get_example(session, user.id, body.example_id)
    if example is None:
        raise _not_found("Example")
    word = await vocabulary.add_entry(
        session, user, example.text, body.word, body.description, await _category(request, body.word)
    )
    await session.commit()
    return WordOut.of(word)


@router.get("/api/words/{word_id}", tags=["words"])
async def get_word(word_id: int, session: Session, user: CurrentUser) -> WordOut:
    word = await vocabulary.get_word(session, user.id, word_id)
    if word is None:
        raise _not_found("Word")
    return WordOut.of(word)


@router.patch("/api/words/{word_id}", tags=["words"])
async def update_word(
    word_id: int, body: WordPatch, request: Request, session: Session, user: CurrentUser
) -> WordOut:
    word = await vocabulary.get_word(session, user.id, word_id)
    if word is None:
        raise _not_found("Word")
    if body.word is not None and body.word != word.word:
        word.word = body.word
        word.category = await _category(request, body.word)
    if body.description is not None:
        word.description = body.description
    await session.commit()
    return WordOut.of(word)


@router.delete("/api/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["words"])
async def delete_word(word_id: int, session: Session, user: CurrentUser) -> Response:
    word = await vocabulary.get_word(session, user.id, word_id)
    if word is None:
        raise _not_found("Word")
    await vocabulary.delete_word(session, word)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/examples", tags=["examples"])
async def list_examples(session: Session, user: CurrentUser) -> list[ExampleOut]:
    return [ExampleOut.of(e) for e in await vocabulary.list_examples(session, user.id)]


@router.post("/api/examples", status_code=status.HTTP_201_CREATED, tags=["examples"])
async def create_example(body: ExampleIn, session: Session, user: CurrentUser) -> ExampleOut:
    example = await vocabulary.find_example(session, user.id, body.text)
    if example is None:
        example = Example(user_id=user.id, text=body.text)
        session.add(example)
        await session.commit()
        example = await vocabulary.get_example(session, user.id, example.id)
    return ExampleOut.of(example)


@router.get("/api/examples/{example_id}", tags=["examples"])
async def get_example(example_id: int, session: Session, user: CurrentUser) -> ExampleOut:
    example = await vocabulary.get_example(session, user.id, example_id)
    if example is None:
        raise _not_found("Example")
    return ExampleOut.of(example)


@router.put("/api/examples/{example_id}", tags=["examples"])
async def update_example(example_id: int, body: ExampleIn, session: Session, user: CurrentUser) -> ExampleOut:
    example = await vocabulary.get_example(session, user.id, example_id)
    if example is None:
        raise _not_found("Example")
    try:
        await vocabulary.update_example(session, example, body.text)
    except vocabulary.ValidationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return ExampleOut.of(example)


@router.delete("/api/examples/{example_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["examples"])
async def delete_example(example_id: int, session: Session, user: CurrentUser) -> Response:
    example = await vocabulary.get_example(session, user.id, example_id)
    if example is None:
        raise _not_found("Example")
    await vocabulary.delete_example(session, example)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/lesson", tags=["lesson"])
async def lesson(session: Session, user: CurrentUser) -> list[Task]:
    try:
        return lessons.build_lesson(await lessons.load_cards(session, user.id))
    except lessons.NotEnoughWords as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def create_app(
    settings: Settings | None = None,
    sessionmaker: async_sessionmaker | None = None,
    http: httpx.AsyncClient | None = None,
) -> FastAPI:
    """Run with `uvicorn --factory teleword.api.app:create_app`. Arguments are for tests."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = None
        if sessionmaker is None:
            engine = create_engine(settings.database_url)
        app.state.sessionmaker = sessionmaker or create_sessionmaker(engine)
        async with httpx.AsyncClient() as own_client:
            app.state.http = http or own_client
            yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title="Teleword API", version="3.0.0", description=DESCRIPTION, lifespan=lifespan)
    app.state.settings = settings
    app.include_router(router)
    return app
