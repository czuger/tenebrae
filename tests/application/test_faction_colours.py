"""The colours file: which army the icons are drawn in.

`static/faction_colours.json` is what one edits to give an army its two colours, and nothing else -
the browser reads it, and `static/pawns.js` holds no table of its own. It is a list of triples,
`[faction, square, drawing]`, one row per faction the pages can lay, two empty strings where the
army is left the tone of the cardboard it is printed on.

What is checked here is what a hand editing that file can get wrong: a faction the box does not
carry, a faction of the box with no row at all, a colour that is not a colour, half a pair, and
above all a drawing that would not read on its own square - the one mistake the browser shows as a
counter gone blank rather than as an error.
"""

import json
import re
from pathlib import Path

import pytest

from tenebrae.application.config import ROOT
from tenebrae.application.pieces import PIECE_CATALOGUE

COLOURS = ROOT / "tenebrae" / "application" / "static" / "faction_colours.json"

COLUMNS = 3

# A colour as the file writes it, and as `tintTheIcon` puts it into the SVG.
HEXADECIMAL = re.compile(r"^#[0-9a-f]{6}$")

# How far apart the square and the drawing must read for the icon to be seen at all, on the usual
# weighting of the three channels. The counters are some fifteen pixels wide: less than this and
# the drawing dissolves into its own square.
READABLE = 100


def rgb(colour):
    """The three channels of a "#rrggbb" colour."""
    return tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))


def brightness(colour):
    """How light the colour reads, on the usual weighting of the three channels."""
    red, green, blue = rgb(colour)
    return 0.299 * red + 0.587 * green + 0.114 * blue


@pytest.fixture(scope="module")
def rows():
    """The file as it is read by the browser."""
    return json.loads(COLOURS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def factions_of_the_box():
    """Every army the pages lay a counter of, as `pions/` numbers it."""
    return {piece["faction"] for piece in PIECE_CATALOGUE}


def test_it_is_a_list_of_triples(rows):
    assert isinstance(rows, list) and rows
    for row in rows:
        assert isinstance(row, list) and len(row) == COLUMNS, row


def test_the_columns_are_the_faction_and_its_two_colours(rows):
    for faction, square, drawing in rows:
        assert isinstance(faction, str) and faction, faction
        assert isinstance(square, str) and isinstance(drawing, str), faction


def test_every_faction_of_the_box_has_a_row(rows, factions_of_the_box):
    """Giving an army its colours is filling a blank in, never working out where a row should go."""
    assert factions_of_the_box - {row[0] for row in rows} == set()


def test_no_row_names_a_faction_the_box_does_not_carry(rows, factions_of_the_box):
    """A misspelt faction would sit there colouring nothing, and say nothing about it."""
    assert {row[0] for row in rows} - factions_of_the_box == set()


def test_no_faction_is_named_twice(rows):
    names = [row[0] for row in rows]
    assert len(names) == len(set(names)), [name for name in names if names.count(name) > 1]


def test_the_rows_follow_the_box(rows):
    """In the order `pions/` numbers the armies, the file being read by a hand looking for one."""
    ordered = sorted({piece["faction"] for piece in PIECE_CATALOGUE})
    assert [row[0] for row in rows] == ordered


def test_a_coloured_army_carries_both_colours(rows):
    """Half a pair would leave the icon with one fill of the set's own - black on the army's
    square, or the army's ink on white."""
    for faction, square, drawing in rows:
        assert bool(square) == bool(drawing), faction


def test_the_colours_are_written_as_the_browser_reads_them(rows):
    """`tintTheIcon` writes them into the SVG as they are: "#rrggbb", lower case."""
    for faction, square, drawing in rows:
        if not square:
            continue
        assert HEXADECIMAL.match(square), f"{faction}: {square}"
        assert HEXADECIMAL.match(drawing), f"{faction}: {drawing}"


def test_the_drawing_reads_on_the_square_of_every_army(rows):
    """Dark on a pale square, pale on a deep one: an army of one tone would show nothing."""
    for faction, square, drawing in rows:
        if not square:
            continue
        assert abs(brightness(square) - brightness(drawing)) > READABLE, faction


def test_some_armies_are_coloured_and_some_are_left_the_cardboard(rows):
    """Both answers are meant to be exercised: a file coloured throughout would say every army has
    a colour of its own, which the box does not."""
    coloured = [row[0] for row in rows if row[1]]
    assert coloured
    assert len(coloured) < len(rows)


def test_the_file_is_where_the_browser_fetches_it(rows):
    """`static/`, beside the correspondences, so that the page reads it without a route."""
    assert COLOURS.is_file()
    assert COLOURS.parent == Path(ROOT, "tenebrae", "application", "static")
