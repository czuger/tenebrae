"""The exceptions file: the counters painted apart from their army.

`static/pawn_colours.json` holds one row per counter that is painted in colours of its own rather
than its army's - a named character among the rank and file, and nothing else. It is a list of
triples, `[photograph, square, drawing]`, and it is **short on purpose**: a counter absent from it,
which is nearly all of them, takes the colours of its faction (`faction_colours.json`).

What is checked here is what a hand editing that file can get wrong: a photograph the box does not
carry, the same counter named twice, half a pair, a colour that is not a colour, a drawing that
would not read on its own square, and a row that says nothing - the army's own colours written out
again, which is an exception that excepts nothing.
"""

import json
from pathlib import Path

import pytest

from tenebrae.application.config import ROOT
from tenebrae.application.pieces import PIECE_CATALOGUE

from tests.application.test_faction_colours import HEXADECIMAL, READABLE, brightness

PAWN_COLOURS = ROOT / "tenebrae" / "application" / "static" / "pawn_colours.json"
FACTION_COLOURS = ROOT / "tenebrae" / "application" / "static" / "faction_colours.json"
CORRESPONDENCES = ROOT / "tenebrae" / "application" / "static" / "pawn_icons.json"

COLUMNS = 3


@pytest.fixture(scope="module")
def rows():
    """The file as it is read by the browser."""
    return json.loads(PAWN_COLOURS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def factions():
    """Which army each counter belongs to, by the name of its photograph."""
    return {str(piece["path"]).split("/")[1]: piece["faction"] for piece in PIECE_CATALOGUE}


@pytest.fixture(scope="module")
def army_colours():
    """The colours each army is painted in, the armies left the cardboard apart."""
    return {faction: (square, drawing)
            for faction, square, drawing in json.loads(
                FACTION_COLOURS.read_text(encoding="utf-8")) if square}


def test_it_is_a_list_of_triples(rows):
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, list) and len(row) == COLUMNS, row


def test_the_columns_are_the_photograph_and_its_two_colours(rows):
    for photograph, square, drawing in rows:
        assert isinstance(photograph, str) and photograph.endswith(".jpg"), photograph
        assert isinstance(square, str) and isinstance(drawing, str), photograph


def test_no_row_names_a_photograph_the_box_does_not_carry(rows, factions):
    """A misspelt name would sit there painting nothing, and say nothing about it."""
    assert {row[0] for row in rows} - set(factions) == set()


def test_no_counter_is_named_twice(rows):
    names = [row[0] for row in rows]
    assert len(names) == len(set(names)), [name for name in names if names.count(name) > 1]


def test_a_row_carries_both_colours(rows):
    """Half a pair would leave the icon with one fill of the set's own - black on the counter's
    square, or its ink on white."""
    for photograph, square, drawing in rows:
        assert bool(square) == bool(drawing), photograph
        assert square, f"{photograph}: a row that paints nothing is a row to delete"


def test_the_colours_are_written_as_the_browser_reads_them(rows):
    """`tintTheIcon` writes them into the SVG as they are: "#rrggbb", lower case."""
    for photograph, square, drawing in rows:
        assert HEXADECIMAL.match(square), f"{photograph}: {square}"
        assert HEXADECIMAL.match(drawing), f"{photograph}: {drawing}"


def test_the_drawing_reads_on_the_square_of_every_counter(rows):
    """As for the armies: a counter of one tone would show nothing at a counter's size."""
    for photograph, square, drawing in rows:
        assert abs(brightness(square) - brightness(drawing)) > READABLE, photograph


def test_a_counter_painted_apart_is_painted_apart(rows, factions, army_colours):
    """A row repeating the army's own colours excepts nothing, and hides that it excepts nothing:
    the counter would look exactly as it looks without the row."""
    for photograph, square, drawing in rows:
        army = army_colours.get(factions[photograph])
        assert (square, drawing) != army, f"{photograph}: its army's own colours"


def test_a_counter_painted_apart_is_drawn_at_all(rows):
    """Colours paint an icon: a counter whose correspondence is blank keeps its photograph, and
    the row would say something nothing shows."""
    icons = dict(json.loads(CORRESPONDENCES.read_text(encoding="utf-8")))
    for photograph, _, _ in rows:
        assert icons[photograph], f"{photograph}: no icon to paint"


def test_the_file_is_where_the_browser_fetches_it(rows):
    """`static/`, beside the other two, so that the page reads it without a route."""
    assert PAWN_COLOURS.is_file()
    assert PAWN_COLOURS.parent == Path(ROOT, "tenebrae", "application", "static")
