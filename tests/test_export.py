import csv
import io
import json
from xml.etree import ElementTree

import pytest
from openpyxl import load_workbook

from teleword.services import export, vocabulary
from teleword.services.export import Format, Order, Selection


@pytest.fixture
async def words(session, user):
    created = [
        await vocabulary.add_entry(session, user, "Bananas are yellow.", "banana", "a fruit", None),
        await vocabulary.add_entry(session, user, "Apples & <pears>", "Apple", "another fruit", None),
        await vocabulary.add_entry(session, user, "Cherries are red.", "cherry", "small fruit", None),
    ]
    created[0].rating, created[1].rating, created[2].rating = 5, -2, 2
    await session.flush()
    return created


async def test_orders(session, user, words):
    by = {o: [r.word for r in await export.fetch_rows(session, user.id, Selection.ALL, o)] for o in Order}
    assert by[Order.ADDED] == ["banana", "Apple", "cherry"]
    assert by[Order.ALPHABET] == ["Apple", "banana", "cherry"]
    assert by[Order.IMPORTANCE] == ["banana", "cherry", "Apple"]


async def test_important_means_above_the_users_average(session, user, words):
    rows = await export.fetch_rows(session, user.id, Selection.IMPORTANT, Order.ADDED)
    assert [r.word for r in rows] == ["banana", "cherry"]  # average rating is 1.67


async def test_rendered_files_round_trip(session, user, words):
    rows = await export.fetch_rows(session, user.id, Selection.ALL, Order.ADDED)

    as_json = json.loads(export.render(rows, Format.JSON))
    assert as_json[1]["example"] == "Apples & <pears>"
    assert set(as_json[0]) == set(export.COLUMNS)

    as_csv = list(csv.reader(io.StringIO(export.render(rows, Format.CSV).decode("utf-8-sig"))))
    assert as_csv[0] == list(export.COLUMNS)
    assert as_csv[2][1] == "Apple"

    as_xml = ElementTree.fromstring(export.render(rows, Format.XML))
    assert [w.findtext("word") for w in as_xml] == ["banana", "Apple", "cherry"]

    sheet = load_workbook(io.BytesIO(export.render(rows, Format.XLSX)))["words"]
    assert sheet["B2"].value == "word id"
    assert sheet["C4"].value == "Apple"
    assert sheet["F4"].value == "Apples & <pears>"


def test_filename():
    assert export.filename(Format.XLSX) == "teleword_words.xlsx"
