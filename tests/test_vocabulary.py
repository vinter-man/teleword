import pytest
from sqlalchemy import func, select

from teleword.db.models import Example, Word
from teleword.services import vocabulary
from tests.conftest import make_user


async def test_add_entry_reuses_the_example(session, user):
    first = await vocabulary.add_entry(session, user, "Run, Forrest, run!", "run", "move fast", "Verb")
    second = await vocabulary.add_entry(session, user, "run, forrest, RUN!", "Forrest", "a name", None)
    assert first.example_id == second.example_id
    assert await session.scalar(select(func.count(Example.id))) == 1


async def test_add_entry_is_idempotent(session, user):
    first = await vocabulary.add_entry(session, user, "An example here", "word", "meaning", None)
    again = await vocabulary.add_entry(session, user, "An example here", "word", "meaning", None)
    assert first.id == again.id
    assert await vocabulary.count_words(session, user.id) == 1


@pytest.mark.parametrize(
    ("field", "value", "ok"),
    [
        ("example", "four", False),
        ("example", "  five!  ", True),
        ("example", "x" * 401, False),
        ("word", "", False),
        ("word", "   ", False),
        ("word", "a", True),
        ("word", "x" * 136, False),
        ("description", "x" * 400, True),
    ],
)
def test_validate(field, value, ok):
    if ok:
        assert vocabulary.validate(field, value) == value.strip()
    else:
        with pytest.raises(vocabulary.ValidationError):
            vocabulary.validate(field, value)


async def test_users_cannot_see_each_other(session, user):
    word = await vocabulary.add_entry(session, user, "Mine, all mine.", "mine", "belongs to me", None)
    other = await make_user(session, tg_id=2, username="bob")

    assert await vocabulary.get_word(session, other.id, word.id) is None
    assert await vocabulary.get_example(session, other.id, word.example_id) is None
    assert await vocabulary.find_word(session, other.id, word="mine") is None
    assert await vocabulary.count_words(session, other.id) == 0


async def test_find_is_case_insensitive(session, user):
    word = await vocabulary.add_entry(session, user, "Hello there, friend", "Hello", "a greeting", None)
    assert (await vocabulary.find_word(session, user.id, word=" hello ")).id == word.id
    assert (await vocabulary.find_word(session, user.id, description="A GREETING")).id == word.id
    assert (await vocabulary.find_example(session, user.id, "HELLO THERE, FRIEND")).id == word.example_id


async def test_delete_word_removes_orphan_example_only(session, user):
    a = await vocabulary.add_entry(session, user, "Cats and dogs.", "cat", "meow", None)
    b = await vocabulary.add_entry(session, user, "Cats and dogs.", "dog", "woof", None)

    await vocabulary.delete_word(session, a)
    assert await vocabulary.get_example(session, user.id, b.example_id) is not None

    await vocabulary.delete_word(session, b)
    assert await vocabulary.get_example(session, user.id, b.example_id) is None


async def test_delete_example_cascades_to_words(session, user):
    word = await vocabulary.add_entry(session, user, "Cats and dogs.", "cat", "meow", None)
    await vocabulary.add_entry(session, user, "Cats and dogs.", "dog", "woof", None)
    example = await vocabulary.get_example(session, user.id, word.example_id)

    await vocabulary.delete_example(session, example)
    await session.commit()
    assert await session.scalar(select(func.count(Word.id))) == 0


async def test_update_example_rejects_duplicates(session, user):
    a = await vocabulary.add_entry(session, user, "First example", "first", "1st", None)
    b = await vocabulary.add_entry(session, user, "Second example", "second", "2nd", None)
    example_b = await vocabulary.get_example(session, user.id, b.example_id)

    with pytest.raises(vocabulary.ValidationError):
        await vocabulary.update_example(session, example_b, "first EXAMPLE")

    await vocabulary.update_example(session, example_b, "Second example, edited")
    assert example_b.text == "Second example, edited"
    assert a.example.text == "First example"
