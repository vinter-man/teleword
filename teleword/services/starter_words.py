"""Fifteen starter words, so a new user can try a lesson right away and delete them later."""

from sqlalchemy.ext.asyncio import AsyncSession

from teleword.db.models import User
from teleword.services import vocabulary

STARTER_WORDS = [
    {
        "example": "We just imagine the arrows because we fear them.",
        "word": "arrow",
        "description": "A weapon consisting of a thin, straight stick with a sharp point, "
        "designed to be shot from a bow.",
        "category": "Noun",
    },
    {
        "example": "She was reluctant to admit that she had been wrong.",
        "word": "reluctant",
        "description": "Unwilling and hesitant; not wanting to do something.",
        "category": "Adjective",
    },
    {
        "example": "Some plants thrive in the shade, while others need full sun.",
        "word": "thrive",
        "description": "To grow or develop well; to prosper or flourish.",
        "category": "Verb",
    },
    {
        "example": "Dad is always grumpy before his first cup of coffee.",
        "word": "grumpy",
        "description": "Bad-tempered and irritable.",
        "category": "Adjective",
    },
    {
        "example": "I stumbled upon this song while looking for something else.",
        "word": "stumble",
        "description": "To find or meet by chance; also, to trip and almost fall.",
        "category": "Verb",
    },
    {
        "example": "There was an awkward silence after he told the joke.",
        "word": "awkward",
        "description": "Causing or feeling embarrassment or difficulty.",
        "category": "Adjective",
    },
    {
        "example": "At half the usual price, the jacket was a real bargain.",
        "word": "bargain",
        "description": "A thing bought or offered for sale more cheaply than is usual.",
        "category": "Noun",
    },
    {
        "example": "The amount of homework began to overwhelm the students.",
        "word": "overwhelm",
        "description": "To be too much for someone to deal with; to have a very strong emotional effect on.",
        "category": "Verb",
    },
    {
        "example": "The puppy was eager to go outside and play.",
        "word": "eager",
        "description": "Wanting to do or have something very much.",
        "category": "Adjective",
    },
    {
        "example": "The detective found a clue hidden under the carpet.",
        "word": "clue",
        "description": "A piece of evidence or information that helps to solve a problem or mystery.",
        "category": "Noun",
    },
    {
        "example": "The kids tried to sneak into the kitchen to grab some cookies.",
        "word": "sneak",
        "description": "To move or go somewhere quietly and secretly.",
        "category": "Verb",
    },
    {
        "example": "Renewing my passport turned out to be a real hassle.",
        "word": "hassle",
        "description": "An annoying inconvenience; something that is troublesome to do.",
        "category": "Noun",
    },
    {
        "example": "I reckon it's going to rain later today.",
        "word": "reckon",
        "description": "To think or believe; to have an opinion (informal).",
        "category": "Verb",
    },
    {
        "example": "She has vivid memories of her first day at school.",
        "word": "vivid",
        "description": "Producing very clear, powerful and detailed images in the mind; bright and intense.",
        "category": "Adjective",
    },
    {
        "example": "The task was difficult; nevertheless, they finished it on time.",
        "word": "nevertheless",
        "description": "In spite of that; however.",
        "category": "Adverb",
    },
]


async def add_starter_words(session: AsyncSession, user: User) -> None:
    """Idempotent: words the user already has are not duplicated."""
    for entry in STARTER_WORDS:
        await vocabulary.add_entry(session, user, **entry)
