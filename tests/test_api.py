import httpx
import pytest

from teleword.api.app import create_app
from teleword.services import api_keys
from teleword.services.starter_words import add_starter_words
from tests.conftest import make_user


@pytest.fixture
async def app(settings, sessionmaker, http):
    app = create_app(settings, sessionmaker, http)
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def issue_key(session, user) -> dict:
    await api_keys.request(session, user, "Testing the API from a script")
    key = await api_keys.approve(session, user.id)
    await session.commit()
    return {"X-API-Key": key}


@pytest.fixture
async def auth(session, user):
    return await issue_key(session, user)


async def test_health(client):
    response = await client.get("/health")
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "nope"}])
async def test_requires_a_valid_key(client, headers):
    assert (await client.get("/api/words", headers=headers)).status_code == 401


async def test_crud(client, auth):
    example = await client.post("/api/examples", json={"text": "  The arrow flew.  "}, headers=auth)
    assert example.status_code == 201
    example = example.json()
    assert example["text"] == "The arrow flew."

    word = await client.post(
        "/api/words",
        json={"word": "arrow", "description": "shot from a bow", "example_id": example["id"]},
        headers=auth,
    )
    assert word.status_code == 201
    word = word.json()
    assert word["category"] == "Noun"
    assert word["example"] == "The arrow flew."

    patched = await client.patch(f"/api/words/{word['id']}", json={"word": "Run"}, headers=auth)
    assert patched.json()["word"] == "Run"
    assert patched.json()["category"] == "Verb", "the part of speech is looked up again"
    assert patched.json()["description"] == "shot from a bow"

    listed = (await client.get("/api/words", headers=auth)).json()
    assert [w["id"] for w in listed] == [word["id"]]
    assert (await client.get(f"/api/examples/{example['id']}", headers=auth)).json()["word_ids"] == [
        word["id"]
    ]

    updated = await client.put(
        f"/api/examples/{example['id']}", json={"text": "The arrow flew far."}, headers=auth
    )
    assert updated.json()["text"] == "The arrow flew far."

    assert (await client.delete(f"/api/words/{word['id']}", headers=auth)).status_code == 204
    assert (await client.get(f"/api/words/{word['id']}", headers=auth)).status_code == 404
    assert (await client.get(f"/api/examples/{example['id']}", headers=auth)).status_code == 404, (
        "orphan removed"
    )


async def test_example_delete_cascades(client, auth):
    example = (await client.post("/api/examples", json={"text": "Cats and dogs."}, headers=auth)).json()
    for word in ("cat", "dog"):
        await client.post(
            "/api/words", json={"word": word, "description": "pet", "example_id": example["id"]}, headers=auth
        )
    assert (await client.delete(f"/api/examples/{example['id']}", headers=auth)).status_code == 204
    assert (await client.get("/api/words", headers=auth)).json() == []


async def test_duplicate_example_text_conflicts(client, auth):
    first = (await client.post("/api/examples", json={"text": "First one."}, headers=auth)).json()
    second = (await client.post("/api/examples", json={"text": "Second one."}, headers=auth)).json()
    again = (await client.post("/api/examples", json={"text": "first ONE."}, headers=auth)).json()
    assert again["id"] == first["id"]

    response = await client.put(f"/api/examples/{second['id']}", json={"text": "First one."}, headers=auth)
    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"text": "tiny"},
        {"text": "x" * 401},
        {"text": "Valid example", "extra": 1},
    ],
)
async def test_example_validation(client, auth, body):
    assert (await client.post("/api/examples", json=body, headers=auth)).status_code == 422


async def test_other_users_data_is_invisible(client, auth, session):
    example = (await client.post("/api/examples", json={"text": "Private stuff."}, headers=auth)).json()
    word = (
        await client.post(
            "/api/words",
            json={"word": "secret", "description": "hidden", "example_id": example["id"]},
            headers=auth,
        )
    ).json()

    intruder = await issue_key(session, await make_user(session, tg_id=2, username="mallory"))
    assert (await client.get(f"/api/words/{word['id']}", headers=intruder)).status_code == 404
    assert (await client.delete(f"/api/examples/{example['id']}", headers=intruder)).status_code == 404
    response = await client.post(
        "/api/words", json={"word": "hack", "description": "x", "example_id": example["id"]}, headers=intruder
    )
    assert response.status_code == 404
    assert (await client.get("/api/words", headers=intruder)).json() == []


async def test_lesson(client, auth, session, user):
    response = await client.get("/api/lesson", headers=auth)
    assert response.status_code == 409

    await add_starter_words(session, user)
    await session.commit()
    tasks = (await client.get("/api/lesson", headers=auth)).json()
    assert len(tasks) == 15
    assert set(tasks[0]["options"]) == {"a", "b", "c", "d"}
