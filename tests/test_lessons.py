import random
from collections import Counter

import pytest

from teleword.services import lessons
from teleword.services.lessons import PICK_DESCRIPTION, PICK_WORD, Card, build_lesson, resolve_answer


def make_cards(n: int, category: str | None = "Noun", start: int = 1) -> list[Card]:
    return [
        Card(i, f"word{i}", f"description {i}", f"example {i}", category, rating=0)
        for i in range(start, start + n)
    ]


def test_needs_at_least_fifteen_words():
    with pytest.raises(lessons.NotEnoughWords) as exc:
        build_lesson(make_cards(14))
    assert exc.value.have == 14


def test_lesson_shape():
    tasks = build_lesson(make_cards(40), random.Random(1))

    assert len(tasks) == lessons.LESSON_SIZE
    assert len({t["word_id"] for t in tasks}) == lessons.LESSON_SIZE, "every task asks about a different word"
    for number, task in enumerate(tasks):
        assert task["kind"] == (PICK_DESCRIPTION if number % 2 == 0 else PICK_WORD)
        options = task["options"]
        assert list(options) == ["a", "b", "c", "d"]
        assert len({o["id"] for o in options.values()}) == 4
        assert [o["id"] for o in options.values() if o["is_correct"]] == [task["word_id"]]


def test_hardest_words_open_and_close_the_lesson():
    cards = make_cards(30)
    hard = [Card(c.id, c.word, c.description, c.example, c.category, rating=10) for c in cards[:5]]
    cards = hard + cards[5:]

    tasks = build_lesson(cards, random.Random(7))
    hard_ids = {c.id for c in hard}
    positions = [i for i, t in enumerate(tasks) if t["word_id"] in hard_ids]
    assert positions == [0, 1, 2, 13, 14]


def test_wrong_answers_prefer_the_same_part_of_speech():
    cards = make_cards(5, "Noun") + make_cards(20, "Verb", start=100)
    for task in build_lesson(cards, random.Random(3)):
        main = lessons.main_option(task)
        categories = Counter(o["category"] for o in task["options"].values())
        assert categories[main["category"]] == 4


def test_same_word_with_another_example_is_not_a_distractor():
    cards = make_cards(15)
    twin = Card(99, cards[0].word.upper(), "another meaning", "another example", "Noun", rating=0)
    for task in build_lesson([*cards, twin], random.Random(5)):
        assert sum(o["is_correct"] for o in task["options"].values()) == 1


def test_duplicates_count_as_correct_when_nothing_else_is_left():
    # 15 cards but only two distinct words: duplicates must be used and both count as correct.
    cards = [Card(i, "same" if i % 2 else "other", f"d{i}", f"e{i}", None, 0) for i in range(1, 16)]
    for task in build_lesson(cards, random.Random(2)):
        main = lessons.main_option(task)
        for option in task["options"].values():
            assert option["is_correct"] == (option["word"] == main["word"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("a", "a"), (" B ", "b"), ("3", "c"), ("4", "d"), ("5", None), ("e", None), ("", None)],
)
def test_resolve_letters_and_numbers(raw, expected):
    task = build_lesson(make_cards(15), random.Random(0))[0]
    assert resolve_answer(task, raw) == expected


def test_resolve_word_text_only_for_word_tasks():
    tasks = build_lesson(make_cards(15), random.Random(0))
    word_task = tasks[1]
    key, option = next(iter(word_task["options"].items()))
    assert resolve_answer(word_task, option["word"].upper()) == key

    description_task = tasks[0]
    option = next(iter(description_task["options"].values()))
    assert resolve_answer(description_task, option["word"]) is None
