import httpx
from sqlalchemy import select

from teleword.db.models import ApiKey
from teleword.services import api_keys, users
from teleword.services.dictionary import lookup_category

URL = "https://dictionary.test/entries/en/"


async def test_key_lifecycle(session, user):
    await api_keys.request(session, user, "I want to build a flashcards app")
    assert await api_keys.rotate(session, user.id) is None, "a pending request cannot be rotated"

    key = await api_keys.approve(session, user.id)
    record = await session.scalar(select(ApiKey))
    assert record.is_active
    assert record.key_hash == api_keys.hash_key(key) != key, "only the hash is stored"
    assert (await api_keys.authenticate(session, key)).id == user.id
    assert await api_keys.authenticate(session, key + "x") is None

    new_key = await api_keys.rotate(session, user.id)
    assert await api_keys.authenticate(session, key) is None
    assert (await api_keys.authenticate(session, new_key)).id == user.id


async def test_blacklisted_users_cannot_authenticate(session, user):
    await api_keys.request(session, user, "I want to build a flashcards app")
    key = await api_keys.approve(session, user.id)
    await users.set_blacklisted(session, user.tg_id, True)
    assert await api_keys.authenticate(session, key) is None


async def test_reject_removes_the_request(session, user):
    await api_keys.request(session, user, "I want to build a flashcards app")
    assert await api_keys.reject(session, user.id)
    assert await api_keys.get(session, user.id) is None
    assert await api_keys.approve(session, user.id) is None


async def test_lookup_category(http):
    assert await lookup_category(http, URL, " Arrow ") == "Noun"
    assert await lookup_category(http, URL, "run") == "Verb"
    assert await lookup_category(http, URL, "qwertyuiop") is None


async def test_lookup_category_survives_api_failures():
    def broken(request: httpx.Request) -> httpx.Response:
        if "timeout" in request.url.path:
            raise httpx.ConnectTimeout("too slow")
        return httpx.Response(200, json={"unexpected": "shape"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as client:
        assert await lookup_category(client, URL, "timeout") is None
        assert await lookup_category(client, URL, "weird") is None
