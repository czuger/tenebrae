"""The correspondence file: which counter is drawn as which icon.

`static/pawn_icons.json` is what one edits to give a counter a drawn face, and nothing else - the
browser reads it, and `static/pawns.js` holds no table of its own. It is a list of pairs,
`[photograph, icon]`, one row per counter the pages can lay, an empty icon where the counter has no
drawing.

What is checked here is what a hand editing that file can get wrong: a photograph the box does not
carry, a counter of the box with no row at all, the same photograph named twice, and above all an
icon named where no file lies. None of that needs a browser.
"""

import json
from pathlib import Path

import pytest

from tenebrae.application.config import ROOT
from tenebrae.application.pieces import PIECE_CATALOGUE

CORRESPONDENCES = ROOT / "tenebrae" / "application" / "static" / "pawn_icons.json"
ICONS = ROOT / "tenebrae" / "application" / "static" / "icons" / "000000" / "ffffff" / "1x1"

COLUMNS = 2


@pytest.fixture(scope="module")
def rows():
    """The file as it is read by the browser."""
    return json.loads(CORRESPONDENCES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def photographs_of_the_box():
    """Every counter the pages lay, by the name of its photograph - the overview sheets apart."""
    return {piece["path"].split("/")[1] for piece in PIECE_CATALOGUE}


def test_it_is_a_list_of_pairs(rows):
    assert isinstance(rows, list) and rows
    for row in rows:
        assert isinstance(row, list) and len(row) == COLUMNS, row


def test_the_columns_are_the_photograph_and_the_icon(rows):
    for photograph, icon in rows:
        assert isinstance(photograph, str) and photograph.endswith(".jpg"), photograph
        assert isinstance(icon, str), photograph


def test_every_counter_of_the_box_has_a_row(rows, photographs_of_the_box):
    """Adding a correspondence is filling a blank in, never working out where a row should go."""
    listed = {row[0] for row in rows}
    assert photographs_of_the_box - listed == set()


def test_no_row_names_a_photograph_the_box_does_not_carry(rows, photographs_of_the_box):
    """A misspelt name would sit there drawing nothing, and say nothing about it."""
    assert {row[0] for row in rows} - photographs_of_the_box == set()


def test_no_photograph_is_named_twice(rows):
    """Two rows for one counter: the second is read by nothing, and the hand that wrote it thinks
    it drew something."""
    names = [row[0] for row in rows]
    assert len(names) == len(set(names)), [name for name in names if names.count(name) > 1]


def test_the_rows_follow_the_box(rows):
    """Faction by faction and rank by rank, as `pions/` numbers them: the file is read by a hand
    looking for its counter."""
    assert [row[0] for row in rows] == [piece["path"].split("/")[1] for piece in PIECE_CATALOGUE]


def test_every_icon_named_lies_where_it_is_named(rows):
    """The one mistake a browser would hide: the fetch fails, the counters simply stay."""
    for photograph, icon in rows:
        if not icon:
            continue
        assert (ICONS / f"{icon}.svg").is_file(), f"{photograph}: {icon}"


def test_the_icons_are_the_black_on_white_variant(rows):
    """The colour is put on in the browser, from those two fills: a file built otherwise would come
    out untinted."""
    for _, icon in rows:
        if not icon:
            continue
        drawing = (ICONS / f"{icon}.svg").read_text(encoding="utf-8")
        assert 'fill="#fff"' in drawing and 'fill="#000"' in drawing, icon


def test_a_unit_of_the_reissland_battle_is_drawn(rows):
    """The counters that battle fields are the reason the file exists: none is blank."""
    drawn = dict(rows)
    assert drawn["reissland-01-15-infanteries.jpg"] == "lorc/barbute"
    assert drawn["reissland-02-8-cavaleries.jpg"] == "delapouite/cavalry"
    assert drawn["reissland-03-3-archers.jpg"] == "lorc/bowman"
    assert drawn["yzent-02-6-infanteries-de-puissance-6.jpg"] == "lorc/visored-helm"
    assert drawn["yzent-04-3-catapultes.jpg"] == "heavenly-dog/catapult"


def test_the_file_is_where_the_browser_fetches_it(rows):
    """`static/`, so that the page reads it without a route of its own."""
    assert CORRESPONDENCES.is_file()
    assert CORRESPONDENCES.parent == Path(ROOT, "tenebrae", "application", "static")
