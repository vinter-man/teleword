"""Part-of-speech lookup through the free dictionaryapi.dev API."""

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


async def lookup_category(client: httpx.AsyncClient, base_url: str, word: str) -> str | None:
    """Returns the part of speech ("Noun", "Verb", ...) or None when the word is unknown or the API fails."""
    try:
        response = await client.get(base_url + quote(word.strip().lower()), timeout=5)
        if response.status_code != 200:
            return None
        part = response.json()[0]["meanings"][0]["partOfSpeech"]
    except (httpx.HTTPError, ValueError, LookupError, TypeError) as exc:
        logger.warning("Dictionary lookup failed for %r: %s", word, exc)
        return None
    return str(part).capitalize()[:20]
