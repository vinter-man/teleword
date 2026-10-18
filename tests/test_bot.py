"""End-to-end bot scenarios: fake updates go through the real dispatcher, middlewares and database."""

from aiogram.methods import SendAudio, SendDocument, SendMessage, SendPhoto

from teleword.bot.handlers.lessons import Lesson
from teleword.services import api_keys, users, vocabulary
from teleword.services.starter_words import add_starter_words
from tests.conftest import ADMIN_ID, make_user
from tests.telegram import buttons, joined, of_type

ALICE = 1


async def word_count(sessionmaker, tg_id: int = ALICE) -> int:
    async with sessionmaker() as session:
        user = await users.get_by_tg_id(session, tg_id)
        return await vocabulary.count_words(session, user.id)


async def test_start_registers_the_user(bot, sessionmaker):
    calls = await bot.send("/start", username=None)
    assert "Let's start" in joined(calls)
    async with sessionmaker() as session:
        user = await users.get_by_tg_id(session, ALICE)
        assert user.nickname == f"user{ALICE}"


async def test_any_first_message_registers_the_user(bot, sessionmaker):
    """The old bot crashed for users who skipped /start."""
    await bot.send("/statistic")
    async with sessionmaker() as session:
        assert await users.get_by_tg_id(session, ALICE) is not None


async def test_help_and_unknown_input(bot):
    assert "/lesson" in joined(await bot.send("/help"))
    assert "don't know this command" in joined(await bot.send("hello?"))
    assert "Until the end of the day" in joined(await bot.send("/time"))


async def test_add_word_flow(bot, sessionmaker):
    calls = await bot.send("/add")
    assert "Send me your example" in joined(calls)

    assert "5-400 characters" in joined(await bot.send("tiny"))
    await bot.send("Fire the <arrow> & run!")
    await bot.send("arrow")
    calls = await bot.send("A thin stick shot from a bow")

    text = joined(calls)
    assert "Saved!" in text
    assert "Fire the &lt;arrow&gt; &amp; run!" in text, "user input is HTML-escaped"
    async with sessionmaker() as session:
        user = await users.get_by_tg_id(session, ALICE)
        [word] = await vocabulary.list_words(session, user.id)
        assert (word.word, word.category, word.example.text) == ("arrow", "Noun", "Fire the <arrow> & run!")

    # The next /add offers to reuse the example.
    calls = await bot.click(buttons(calls)["🏄 Add another"])
    reuse = buttons(calls)
    assert any("Use my last example" in b for b in reuse)
    await bot.click(next(v for k, v in reuse.items() if "Use my last example" in k))
    await bot.send("run")
    await bot.send("to move fast")
    assert await word_count(sessionmaker) == 2


async def test_back_buttons_and_commands_inside_a_flow(bot):
    await bot.send("/add")
    calls = await bot.send("A perfectly fine example")
    calls = await bot.click(buttons(calls)["🌊 Back"])
    assert "Send me your example" in joined(calls)

    # A command in the middle of a flow is handled as a command, not as the example text.
    assert "Action cancelled" in joined(await bot.send("/cancel"))
    assert await bot.state() is None


async def finish_lesson_by_buttons(bot, mistakes_on_first_task: int = 0) -> list:
    data = await bot.state_data()
    for index, task in enumerate(data["tasks"]):
        await bot.click("nav:lesson_next")
        wrong = [k for k, o in task["options"].items() if not o["is_correct"]]
        correct = next(k for k, o in task["options"].items() if o["is_correct"])
        if index == 0:
            for key in wrong[:mistakes_on_first_task]:
                assert "Try again" in str(buttons(await bot.click(f"ans:{index}:{key}")))
                await bot.click("nav:lesson_next")
        await bot.click(f"ans:{index}:{correct}")
    return await bot.click("nav:lesson_next")


async def test_lesson_needs_words_and_offers_starter_words(bot, sessionmaker):
    calls = await bot.send("/lesson")
    assert "you have <b>0</b>" in joined(calls)

    calls = await bot.click(buttons(calls)["🧞 Add starter words"])
    assert "you now have <b>15</b> words" in joined(calls)
    assert await word_count(sessionmaker) == 15


async def test_full_lesson(bot, sessionmaker, session):
    user = await make_user(session)
    await add_starter_words(session, user)
    await session.commit()

    calls = await bot.send("/lesson")
    assert "Let's start the lesson" in joined(calls)
    assert await bot.state() == Lesson.active.state

    calls = await finish_lesson_by_buttons(bot, mistakes_on_first_task=2)

    text = joined(calls)
    assert "End of the lesson" in text
    assert "93%" in text and "Mistakes: <b>2</b>" in text and "Streak: <b>1</b> day" in text
    assert await bot.state() is None
    async with sessionmaker() as check:
        stored = await users.get_by_tg_id(check, ALICE)
        assert (stored.points, stored.streak) == (15, 1)


async def test_lesson_text_answers_and_guards(bot, session):
    user = await make_user(session)
    await add_starter_words(session, user)
    await session.commit()
    await bot.send("/lesson")

    assert "Press the button above" in joined(await bot.send("a")), "answers before the task is shown"
    await bot.click("nav:lesson_next")
    assert "a | b | c | d" in joined(await bot.send("banana"))

    task = (await bot.state_data())["tasks"][0]
    correct = next(k for k, o in task["options"].items() if o["is_correct"])
    calls = await bot.send(str("abcd".index(correct) + 1))
    assert "Next" in str(buttons(calls))

    # A stale button of the already answered task does nothing.
    calls = await bot.click(f"ans:0:{correct}")
    assert of_type(calls, SendMessage) == []
    assert (await bot.state_data())["index"] == 1

    calls = await bot.send("A|B|C|D")
    assert of_type(calls, SendPhoto) and of_type(calls, SendAudio), "the easter egg still works"


async def test_lesson_word_ratings_change(bot, sessionmaker, session):
    user = await make_user(session)
    await add_starter_words(session, user)
    await session.commit()
    await bot.send("/lesson")
    first_word = (await bot.state_data())["tasks"][0]["word_id"]

    await finish_lesson_by_buttons(bot, mistakes_on_first_task=3)

    async with sessionmaker() as check:
        word = await vocabulary.get_word(check, user.id, first_word)
        assert word.rating == 2


async def test_statistic(bot, session):
    await make_user(session)
    calls = await bot.send("/statistic")
    [photo] = of_type(calls, SendPhoto)
    assert "Streak: <b>0</b>" in photo.caption
    assert "Total words: <b>0</b>" in photo.caption


async def test_export(bot, session):
    user = await make_user(session)
    await add_starter_words(session, user)
    await session.commit()

    calls = await bot.send("/data")
    calls = await bot.click(buttons(calls)["Most important words"])
    calls = await bot.click(buttons(calls)["Alphabetically"])
    assert "No words match" in joined(await bot.click(buttons(calls)["Excel"])), "all ratings are equal"

    calls = await bot.send("/data")
    calls = await bot.click(buttons(calls)["All my words"])
    calls = await bot.click(buttons(calls)["By importance"])
    calls = await bot.click(buttons(calls)["All formats"])
    documents = of_type(calls, SendDocument)
    assert sorted(d.document.filename for d in documents) == [
        "teleword_words.csv",
        "teleword_words.json",
        "teleword_words.xlsx",
        "teleword_words.xml",
    ]


async def test_edit_word_keeps_the_case(bot, sessionmaker, session):
    user = await make_user(session)
    word = await vocabulary.add_entry(session, user, "I went to Paris.", "paris", "a city", None)
    await session.commit()

    calls = await bot.send("/change")
    calls = await bot.click(buttons(calls)["Word"])
    calls = await bot.click(buttons(calls)["✏️ Edit"])
    assert "not found" not in joined(await bot.send(str(word.id)))
    calls = await bot.send("Paris")
    assert "Updated!" in joined(calls)

    async with sessionmaker() as check:
        assert (await vocabulary.get_word(check, user.id, word.id)).word == "Paris"


async def test_edit_description_by_text_and_unknown_id(bot, sessionmaker, session):
    user = await make_user(session)
    word = await vocabulary.add_entry(session, user, "I went to Paris.", "Paris", "a city", None)
    await session.commit()

    calls = await bot.send("/change")
    calls = await bot.click(buttons(calls)["Description"])
    assert "🗑 Delete" not in buttons(calls)
    await bot.click(buttons(calls)["✏️ Edit"])
    assert "couldn't find" in joined(await bot.send("99999"))
    await bot.send("A CITY")
    await bot.send("The capital of France")

    async with sessionmaker() as check:
        assert (await vocabulary.get_word(check, user.id, word.id)).description == "The capital of France"


async def test_delete_example(bot, sessionmaker, session):
    user = await make_user(session)
    word = await vocabulary.add_entry(session, user, "Cats and dogs.", "cat", "meow", None)
    await vocabulary.add_entry(session, user, "Cats and dogs.", "dog", "woof", None)
    await session.commit()

    calls = await bot.send("/change")
    calls = await bot.click(buttons(calls)["Example"])
    calls = await bot.click(buttons(calls)["🗑 Delete"])
    calls = await bot.send(str(word.example_id))
    assert "all its words" in joined(calls)
    assert "Deleted" in joined(await bot.click(buttons(calls)["💥 Yes"]))
    assert await word_count(sessionmaker) == 0


async def test_api_key_request_and_approval(bot, sessionmaker):
    await bot.send("/api")
    assert "20-1000 characters" in joined(await bot.send("for fun"))
    calls = await bot.send("I want to sync my words with Anki every night")

    [to_admin] = [c for c in of_type(calls, SendMessage) if c.chat_id == ADMIN_ID]
    assert "API key request" in to_admin.text
    approve = buttons([to_admin])["✅ Approve"]

    assert "waiting for the admin" in joined(await bot.send("/api"))
    calls = await bot.click(approve, user_id=777, username="random")
    assert "Only the admin" in str([c.text for c in calls if hasattr(c, "text")])

    calls = await bot.click(approve, user_id=ADMIN_ID, username="admin")
    [to_user] = [c for c in of_type(calls, SendMessage) if c.chat_id == ALICE]
    key = to_user.text.split("<code>")[1].split("</code>")[0]
    async with sessionmaker() as session:
        assert (await api_keys.authenticate(session, key)).tg_id == ALICE

    calls = await bot.send("/api")
    calls = await bot.click(buttons(calls)["🔄 New key"])
    new_key = joined(calls).split("<code>")[1].split("</code>")[0]
    async with sessionmaker() as session:
        assert await api_keys.authenticate(session, key) is None
        assert await api_keys.authenticate(session, new_key) is not None


async def test_admin_commands(bot, session):
    await make_user(session, tg_id=ALICE)
    await make_user(session, tg_id=ADMIN_ID, username="admin")

    assert "don't know this command" in joined(await bot.send("/admin")), "hidden from regular users"
    assert "Admin panel" in joined(await bot.send("/admin", user_id=ADMIN_ID, username="admin"))

    assert "now blacklisted" in joined(await bot.send(f"/admin_ban {ALICE}", user_id=ADMIN_ID))
    assert await bot.send("/help") == [], "blacklisted users are ignored"
    assert "alice" in joined(await bot.send("/admin_blacklist", user_id=ADMIN_ID))

    calls = await bot.send("/admin_broadcast Hello <everyone>", user_id=ADMIN_ID)
    assert "Delivered to 1 of 1" in joined(calls), "blacklisted users get no broadcasts"
    assert any(c.text == "Hello <everyone>" and c.parse_mode is None for c in of_type(calls, SendMessage))

    assert "no longer blacklisted" in joined(await bot.send(f"/admin_unban {ALICE}", user_id=ADMIN_ID))
    assert await bot.send("/help") != []
    assert "Usage" in joined(await bot.send("/admin_ban abc", user_id=ADMIN_ID))


async def test_stale_button(bot):
    calls = await bot.click("nav:lesson_next")
    assert "no longer active" in joined(calls)


async def test_errors_are_reported_to_the_user(bot, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("database is on fire")

    monkeypatch.setattr(vocabulary, "count_words", boom)
    calls = await bot.send("/statistic", allow_error=True)
    assert "Something went wrong" in joined(calls)
