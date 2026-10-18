from pydantic import BaseModel, ConfigDict, Field

from teleword.db.models import Example, Word
from teleword.services.vocabulary import LIMITS


def _text(field: str, **kwargs):
    low, high = LIMITS[field]
    return Field(min_length=low, max_length=high, **kwargs)


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ExampleIn(Input):
    text: str = _text("example")


class WordIn(Input):
    word: str = _text("word")
    description: str = _text("description")
    example_id: int


class WordPatch(Input):
    word: str | None = _text("word", default=None)
    description: str | None = _text("description", default=None)


class WordOut(BaseModel):
    id: int
    word: str
    description: str
    category: str | None
    rating: int
    example_id: int
    example: str

    @classmethod
    def of(cls, word: Word) -> "WordOut":
        return cls(
            id=word.id,
            word=word.word,
            description=word.description,
            category=word.category,
            rating=word.rating,
            example_id=word.example_id,
            example=word.example.text,
        )


class ExampleOut(BaseModel):
    id: int
    text: str
    word_ids: list[int]

    @classmethod
    def of(cls, example: Example) -> "ExampleOut":
        return cls(id=example.id, text=example.text, word_ids=[w.id for w in example.words])


class Option(BaseModel):
    id: int
    word: str
    description: str
    example: str
    category: str | None
    rating: int
    is_correct: bool


class Task(BaseModel):
    word_id: int
    kind: str = Field(
        description="pick_description: choose the description of the word; pick_word: the reverse"
    )
    options: dict[str, Option]
