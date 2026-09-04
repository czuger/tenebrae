"""The two faces of a pawn: the counter photographed, and the drawn icon that stands in for it.

The board opens on the counters. The second button of the bar puts an icon on the units that have
one - one drawing per kind of unit, tinted with the colour of its army - and puts the photographs
back; the choice is this browser's, and it survives the reload.

The set-up the server opens on is the war of the dwarves, where the orc cavalry and the orc archers
have a drawn face and the rest keep their counters. That mixture is the point of several of these
tests - what has no icon must keep its counter rather than disappear.

Which counter is drawn as what, and which army in what colours, are two data files edited by hand
row by row (`static/pawn_icons.json`, `static/faction_colours.json`). Nothing here writes down what
they hold: the counters and the armies these tests work on are taken from the files themselves, so
that giving one more unit a drawing breaks nothing. What is held is the mechanism - that the page
answers what the files say, and that a blank row leaves the counter and the cardboard alone.

These tests require Chromium (`make browser`).
"""

import json

import pytest

from tenebrae.application import current_game
from tenebrae.application.config import ROOT
from tenebrae.application.pieces import PIECE_CATALOGUE
from tenebrae.engine.piece import CATALOGUE
from tenebrae.engine.scenario import armies_of

from tests.application.test_faction_colours import READABLE, brightness

from tests.application.test_board_browser import (a_piece_that_can_move, piece_geometry,
                                                  show_the_ghosts)
from tests.application.test_scenarios import (plain_squares,  # noqa: F401
                                              scenarios_directory)
from tests.application.test_scenarios_browser import lay, open_the_page, wait_for_pieces

STATIC = ROOT / "tenebrae" / "application" / "static"


def read(name):
    """One of the two data files the page reads, as it reads it."""
    return json.loads((STATIC / name).read_text(encoding="utf-8"))


# The correspondences by photograph, and the colours by faction: these tests ask the files the same
# question the page asks them.
CORRESPONDENCES = dict(read("pawn_icons.json"))
ARMY_COLOURS = {faction: {"square": square, "drawing": drawing}
                for faction, square, drawing in read("faction_colours.json") if square}

# The counters painted apart from their army, by photograph. The file holds exceptions only, and
# may hold none at all.
PAWN_COLOURS = {photograph: {"square": square, "drawing": drawing}
                for photograph, square, drawing in read("pawn_colours.json") if square}

# Where each photograph lies, as the board names it: the faction's directory, then the file.
PHOTOGRAPHS = {str(piece["path"]).split("/")[1]: str(piece["path"])
               for piece in PIECE_CATALOGUE}

# Which army each counter belongs to, by photograph.
FACTIONS = {str(piece["path"]).split("/")[1]: str(piece["faction"]) for piece in PIECE_CATALOGUE}

# The symbol each counter carries, by photograph: two counters may share one and still be drawn
# apart, the row being found by the photograph.
SYMBOLS = {str(piece["path"]).split("/")[1]: piece["symbol"] for piece in PIECE_CATALOGUE}


def a_counter_per_icon():
    """One counter for each drawing the file gives, in the file's own order.

    What a test needs is a counter that has a drawing, never a particular drawing on a particular
    counter: the file is edited by hand, row by row, and it is not these tests' business to say
    what a hand should have put there.
    """
    chosen = {}
    for photograph, icon in CORRESPONDENCES.items():
        if icon:
            chosen.setdefault(icon, PHOTOGRAPHS[photograph])
    return [(path, icon) for icon, path in chosen.items()]


def counters_drawn_by_nothing(how_many):
    """That many counters whose row is blank, in the file's own order."""
    blank = [PHOTOGRAPHS[photograph] for photograph, icon in CORRESPONDENCES.items() if not icon]
    return blank[:how_many]


# One counter per drawing, and counters no row draws - the last of them a name the box does not
# carry at all, which is the same nothing.
DRAWN_COUNTERS = a_counter_per_icon()
BLANK_COUNTERS = counters_drawn_by_nothing(4) + ["11-orques/there-is-no-such-counter.jpg"]

# Two armies the colours file gives colours to, and one it leaves the cardboard: the tint is
# exercised on what the file holds, whatever it holds.
COLOURED_ARMIES = sorted(ARMY_COLOURS)
AN_ARMY = COLOURED_ARMIES[0]

# A counter the exceptions file paints apart, and the army it would otherwise be painted with.
PAINTED_APART = next(iter(PAWN_COLOURS), None)

needs_a_counter_painted_apart = pytest.mark.skipif(
    PAINTED_APART is None, reason="no counter is painted apart from its army")

# An army the colours file leaves blank, hence the tone of the cardboard - and a second one, to
# hold that they take the same.
CARDBOARD_ARMIES = sorted({str(piece["faction"]) for piece in PIECE_CATALOGUE}
                          - set(ARMY_COLOURS))

A_DRAWN_SOURCE = "data:image/svg+xml"

# The phase the orcs move at, and how many changes away it is: their movement, after the dwarves'
# movement and the dwarves' combat (magic is skipped).
ORC_MOVEMENT = "Phase de mouvement — Orques"
PHASES_TO_THE_ORCS = 2

# The army the board's set-up has moving.
ORCS = "11-orques"

# The side that plays no turn: a scenario laid out with those alone has no army at all.
NEUTRAL = "neutre"


def counters_on_either_side_of_the_correspondences():
    """One counter the file draws and one it leaves blank, of one side where it can be.

    The scenario written below lays the two of them. They are taken from the file rather than
    named: as it fills up, the counter still blank moves from one army to the next, and there is
    no counter one can point at and call undrawn for good. A side of its own is preferred for each,
    two neutral pieces making a scenario with no army in it.

    Returns:
        The key of a drawn counter and the key of a blank one, `None` for either the file no
        longer offers.
    """
    drawn, blank = [], []
    for piece in PIECE_CATALOGUE:
        listed = drawn if CORRESPONDENCES[str(piece["path"]).split("/")[1]] else blank
        listed.append((str(piece["key"]), str(piece["side"])))
    if not drawn or not blank:
        return None, None

    kept, side = next((counter for counter in blank if counter[1] != NEUTRAL), blank[0])
    of_that_side = [key for key, other in drawn if other == side]
    with_a_side = [key for key, other in drawn if other != NEUTRAL]
    return next(iter(of_that_side + with_a_side + [drawn[0][0]])), kept


A_DRAWN_UNIT, AN_UNDRAWN_UNIT = counters_on_either_side_of_the_correspondences()

needs_a_drawn_unit = pytest.mark.skipif(
    A_DRAWN_UNIT is None, reason="the correspondences draw no counter at all")
# The scenario the edit page is opened on here, written into the diverted directory.
DRAWN_SCENARIO = 7
DRAWN_SCENARIO_FILE = f"scenario-{DRAWN_SCENARIO:02d}-deux-faces.json"

# The side of a palette thumbnail, in pixels (`.palette-piece img` in scenarios.css).
PALETTE_THUMBNAIL = 40


@pytest.fixture
def board(page, server, application, seat_the_player):
    """The board loaded and logged in, its counters on screen - the fixture of the board's tests.

    The storage is the browser's own and this button writes in it: the page is opened on a fresh
    context by the `page` fixture, so one test's choice is not the next one's opening state.
    """
    return open_the_board(page, server, application, seat_the_player)


def open_the_board(page, server, application, seat_the_player, query=""):
    """Opens the board logged in, on the address given, and waits for its counters."""
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    if query:
        page.goto(f"{server}/{query}")
    wait_for_the_counters(page)
    return page


def wait_for_the_counters(page):
    """Waits for the scenario's units, their images and the scale: the board is then complete."""
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(current_game.SCENARIO)
    )
    page.wait_for_function(
        "[...document.querySelectorAll('img.piece'), document.getElementById('map')]"
        ".every((i) => i.complete && i.naturalWidth > 0)"
    )
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")


def announced_face(page):
    """What the button says it is showing: "true" for the icons, "false" for the counters."""
    return page.evaluate(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed')")


def swap_the_face(page):
    """Clicks the button and waits for the board to have finished changing face.

    The button announces the new face only once it is on the counters - the icons are read from the
    server before anything is dressed - so what is waited for is `aria-pressed`, not the click.
    """
    before = announced_face(page)
    page.locator("#pawn-style").click()
    page.wait_for_function(
        "(before) => document.getElementById('pawn-style').getAttribute('aria-pressed') !== before",
        arg=before)
    return announced_face(page)


def pawn_faces(page, selector="img.piece:not(.ghost)"):
    """For each counter on the board: the unit it carries, and the face it is wearing."""
    return page.evaluate("""(selector) => [...document.querySelectorAll(selector)].map(
        (image) => ({
            key: image.piece.key,
            faction: image.piece.faction,
            icon: image.classList.contains('icon'),
            drawn: image.src.startsWith('data:image/svg+xml'),
            photograph: image.src.includes('/pieces/'),
            shown: image.complete && image.naturalWidth > 0,
        }))""", selector)


def has_an_icon(key):
    """Whether that counter's row names an icon, read from the file the page reads."""
    return bool(CORRESPONDENCES[CATALOGUE[key].image.split("/")[-1]])


def move_to_the_orcs_movement(page):
    """Advances the phases until the orcs move.

    On this set-up the units that carry an icon are theirs, and a unit of the side that is not
    playing has no moves to show: their phase is where a selection can be exercised. Two clicks
    away - the dwarves' movement, their combat, magic being skipped - and each phase change lays
    the scene out again, which the counters go through wearing the face in use.
    """
    for _ in range(PHASES_TO_THE_ORCS + 1):
        shown = page.locator("#phase-label").text_content().strip()
        if shown == ORC_MOVEMENT:
            return
        page.locator("#next-phase").click()
        page.wait_for_function(
            "(shown) => document.getElementById('phase-label').textContent.trim() !== shown",
            arg=shown)
    raise AssertionError(f"the orcs never came to move: {shown}")


# --- The button ---

def test_the_bar_carries_the_button_and_it_fits(board):
    """The bar is `overflow: hidden`: one button too many would be clipped there silently."""
    room = board.evaluate("""() => {
        const toolbar = document.getElementById('toolbar').getBoundingClientRect();
        const player = document.getElementById('player').getBoundingClientRect();
        return toolbar.right - player.right;
    }""")
    assert board.locator("#pawn-style").is_visible()
    assert room >= 0, room


def test_the_button_takes_its_own_click(board):
    """It sits in the bar, the one box of the panel that keeps the pointer."""
    found = board.evaluate("""() => {
        const box = document.getElementById('pawn-style').getBoundingClientRect();
        return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2).id;
    }""")
    assert found == "pawn-style", found


def test_the_bar_keeps_its_height_whichever_face_is_showing(board):
    """The button keeps its sign rather than swapping it, so the bar cannot change size under it."""
    height = board.evaluate(
        "() => Math.round(document.getElementById('toolbar').getBoundingClientRect().height)")
    swap_the_face(board)
    assert board.evaluate(
        "() => Math.round(document.getElementById('toolbar').getBoundingClientRect().height)"
    ) == height


def test_the_button_says_which_face_is_showing(board):
    """Pressed for the icons, and its tooltip offers the way back."""
    assert announced_face(board) == "false"
    assert "icônes" in board.locator("#pawn-style").get_attribute("title")

    assert swap_the_face(board) == "true"
    assert "photograph" in board.locator("#pawn-style").get_attribute("title")


# --- The two faces ---

def test_the_board_opens_on_the_counters(board):
    """The photographs are the game's own object: nothing is drawn until it is asked for."""
    assert all(pawn["photograph"] and not pawn["icon"] for pawn in pawn_faces(board))


def test_the_button_draws_the_units_that_have_an_icon(board):
    """The orc cavalry and the orc archers, on the set-up the server opens on."""
    swap_the_face(board)
    faces = pawn_faces(board)
    drawn = [pawn for pawn in faces if pawn["icon"]]

    assert drawn, "no unit of the set-up took an icon"
    assert all(pawn["drawn"] for pawn in drawn)
    assert ({pawn["key"] for pawn in drawn}
            == {pawn["key"] for pawn in faces if has_an_icon(pawn["key"])})


def test_a_unit_with_no_icon_keeps_its_photograph(board):
    """The board shows both faces at once rather than empty the squares it cannot draw."""
    swap_the_face(board)
    kept = [pawn for pawn in pawn_faces(board) if not pawn["icon"]]
    if not kept:
        pytest.skip("the correspondences now draw every counter of the set-up")

    assert all(pawn["photograph"] for pawn in kept)
    assert not any(has_an_icon(pawn["key"]) for pawn in kept)


def test_every_pawn_is_shown_whichever_face_it_wears(board):
    """An icon that did not arrive would leave a hole on the map: they are all on screen."""
    swap_the_face(board)
    assert all(pawn["shown"] for pawn in pawn_faces(board))


def test_the_button_puts_the_photographs_back(board):
    swap_the_face(board)
    assert any(pawn["icon"] for pawn in pawn_faces(board))

    assert swap_the_face(board) == "false"
    assert all(pawn["photograph"] and not pawn["icon"] for pawn in pawn_faces(board))


def test_the_whole_board_changes_face_at_once(board):
    """No unit is left on the other face: what is on the board is dressed, not what is hovered."""
    swap_the_face(board)
    faces = pawn_faces(board)
    assert len(faces) == len(current_game.SCENARIO)
    assert all(pawn["drawn"] is has_an_icon(pawn["key"]) for pawn in faces)


# --- What each unit is drawn as ---

def ask_the_table(page, photographs):
    """What the correspondences give those counters, the file read first.

    The table is a data file (`static/pawn_icons.json`), not a list in the script: it answers
    nothing until it has been read, and reading it is what `loadThePawnIcons` begins with.
    """
    return page.evaluate("""async (photographs) => {
        await loadThePawnIcons([]);
        return photographs.map((image) => pawnIconOf({ image }));
    }""", photographs)


def test_each_counter_takes_the_icon_it_was_given(board):
    """The file itself, asked by the names it is written with."""
    photographs = [photograph for photograph, _ in DRAWN_COUNTERS]
    assert ask_the_table(board, photographs) == [icon for _, icon in DRAWN_COUNTERS]


def two_counters_of_one_symbol_drawn_apart():
    """Two counters carrying the same symbol whose rows do not say the same thing, or nothing.

    The symbol is what the old table was keyed by, and it does not tell every counter apart: the
    box holds several infantries, and the file is free to draw them differently - or to draw one
    and leave the other its photograph.
    """
    seen = {}
    for photograph, icon in CORRESPONDENCES.items():
        symbol = SYMBOLS[photograph]
        if symbol is None:
            continue
        if symbol in seen and seen[symbol][1] != icon:
            return [seen[symbol], (PHOTOGRAPHS[photograph], icon)]
        seen.setdefault(symbol, (PHOTOGRAPHS[photograph], icon))
    return None


def test_two_counters_of_one_symbol_are_told_apart_by_their_photographs(board):
    """The symbol alone would not: several counters of the box carry the same one, and the file
    answers each of them on its own."""
    apart = two_counters_of_one_symbol_drawn_apart()
    if apart is None:
        pytest.skip("the file draws every counter of a symbol the same way")

    given = ask_the_table(board, [photograph for photograph, _ in apart])
    assert given == [icon or None for _, icon in apart]
    assert given[0] != given[1]


def test_a_counter_whose_row_is_blank_is_drawn_by_nothing(board):
    """The counters the file leaves blank - and a name it does not carry at all: an empty icon,
    hence the photograph."""
    assert ask_the_table(board, BLANK_COUNTERS) == [None] * len(BLANK_COUNTERS)


def test_the_table_answers_nothing_before_its_file_is_read(board):
    """It is a data file, and the fallback while it is in flight is the photograph - never a
    wrong icon."""
    assert board.evaluate("(photograph) => pawnIconOf({ image: photograph })",
                          DRAWN_COUNTERS[0][0]) is None


def test_every_icon_named_is_read_from_the_server(board):
    """Each file is where the table says it is: they are fetched and tinted here."""
    units = [{"image": photograph, "faction": AN_ARMY} for photograph, _ in DRAWN_COUNTERS]
    drawn = board.evaluate("""async (units) => {
        await loadThePawnIcons(units);
        return units.map((unit) => pawnIconSource(unit));
    }""", units)

    assert len(drawn) == len(DRAWN_COUNTERS)
    assert all(source and source.startswith(A_DRAWN_SOURCE) for source in drawn), drawn
    assert len(set(drawn)) == len(drawn), "two counters are drawn the same"


# --- The colours of the armies ---

def ask_the_colours(page, factions):
    """What the page gives those armies, the colours file read first.

    They are a data file too (`static/faction_colours.json`), read where the correspondences are
    read: `loadThePawnIcons` is what fetches both.
    """
    return page.evaluate("""async (factions) => {
        await loadThePawnIcons([]);
        return factions.map((faction) => armyColoursOf({ faction }));
    }""", factions)


def test_every_coloured_army_takes_the_colours_of_its_row(board):
    """The file itself, army by army: what the page paints with is what a hand wrote there."""
    given = ask_the_colours(board, COLOURED_ARMIES)
    assert given == [ARMY_COLOURS[faction] for faction in COLOURED_ARMIES]


def test_the_drawing_reads_on_the_square_of_every_army(board):
    """The cardboard included: an army of one tone would show nothing at a counter's size."""
    for army in ask_the_colours(board, COLOURED_ARMIES + CARDBOARD_ARMIES):
        assert abs(brightness(army["square"]) - brightness(army["drawing"])) > READABLE, army


def test_an_army_whose_row_is_blank_takes_the_tone_of_the_cardboard(board):
    """They take it together, and none of the coloured armies claims it: a colour is given to an
    army, never inherited by the ones nobody has coloured."""
    cardboard = ask_the_colours(board, CARDBOARD_ARMIES)
    coloured = ask_the_colours(board, COLOURED_ARMIES)

    assert cardboard, "the colours file leaves no army the cardboard"
    assert all(army == cardboard[0] for army in cardboard)
    assert cardboard[0] not in coloured


# --- A counter painted apart from its army ---

def ask_the_pawn_colours(page, photographs):
    """What the page paints those counters in, the files read first."""
    return page.evaluate("""async (photographs) => {
        await loadThePawnIcons([]);
        return photographs.map(([image, faction]) => pawnColoursOf({ image, faction }));
    }""", photographs)


@needs_a_counter_painted_apart
def test_a_counter_of_its_own_row_is_painted_by_that_row(board):
    """The exception is the counter's, not its army's: the row wins over the faction."""
    faction = FACTIONS[PAINTED_APART]
    [given] = ask_the_pawn_colours(board, [[PHOTOGRAPHS[PAINTED_APART], faction]])

    assert given == PAWN_COLOURS[PAINTED_APART]
    assert given != ARMY_COLOURS.get(faction, board.evaluate("() => ANY_OTHER_ARMY"))


@needs_a_counter_painted_apart
def test_the_rest_of_that_army_is_painted_as_before(board):
    """One counter told apart tells no other: its army is left exactly as it was."""
    faction = FACTIONS[PAINTED_APART]
    others = [PHOTOGRAPHS[photograph] for photograph, army in FACTIONS.items()
              if army == faction and photograph not in PAWN_COLOURS]
    if not others:
        pytest.skip("that army has no other counter")

    given = ask_the_pawn_colours(board, [[photograph, faction] for photograph in others])
    expected = ARMY_COLOURS.get(faction, board.evaluate("() => ANY_OTHER_ARMY"))
    assert given == [expected] * len(others)


@needs_a_counter_painted_apart
def test_the_icon_of_a_counter_painted_apart_carries_its_own_colours(board):
    """What an <img> takes is tinted with the row's two colours, and with neither of the set's."""
    unit = {"image": PHOTOGRAPHS[PAINTED_APART], "faction": FACTIONS[PAINTED_APART]}
    drawn = board.evaluate("""async (unit) => {
        await loadThePawnIcons([unit]);
        return decodeURIComponent(pawnIconSource(unit));
    }""", unit)

    colours = PAWN_COLOURS[PAINTED_APART]
    assert f'fill="{colours["square"]}"' in drawn
    assert f'fill="{colours["drawing"]}"' in drawn
    assert 'fill="#fff"' not in drawn and 'fill="#000"' not in drawn


@needs_a_counter_painted_apart
def test_the_counter_painted_apart_answers_its_army_before_the_file_is_read(board):
    """It is a data file like the other two, and the fallback while it is in flight is the army's
    own colours - never a colour claimed for a counter that has none."""
    unit = [PHOTOGRAPHS[PAINTED_APART], FACTIONS[PAINTED_APART]]
    before = board.evaluate("([image, faction]) => pawnColoursOf({ image, faction })", unit)

    assert before == board.evaluate("() => ANY_OTHER_ARMY")
    assert ask_the_pawn_colours(board, [unit]) == [PAWN_COLOURS[PAINTED_APART]]


def test_the_colours_answer_the_cardboard_before_their_file_is_read(board):
    """It is a data file, and the fallback while it is in flight is the tone of the cardboard -
    never a colour claimed for an army that has none."""
    before = board.evaluate("(faction) => armyColoursOf({ faction })", COLOURED_ARMIES[0])
    assert before == board.evaluate("() => ANY_OTHER_ARMY")
    assert ask_the_colours(board, [COLOURED_ARMIES[0]]) != [before]


def test_the_icon_carries_the_colours_of_its_army(board):
    """The file is black on white on disk: what an <img> takes carries the army's two colours and
    neither of the set's."""
    drawn = board.evaluate("""async () => {
        const cavalry = { image: '02-reissland/reissland-02-8-cavaleries.jpg',
                          faction: '02-reissland' };
        const yzent = { image: '01-yzent/yzent-03-8-archers.jpg', faction: '01-yzent' };
        await loadThePawnIcons([cavalry, yzent]);
        return {
            reissland: decodeURIComponent(pawnIconSource(cavalry)),
            yzent: decodeURIComponent(pawnIconSource(yzent)),
            colours: {
                reissland: armyColoursOf(cavalry),
                yzent: armyColoursOf(yzent),
            },
        };
    }""")

    for army in ("reissland", "yzent"):
        svg, colours = drawn[army], drawn["colours"][army]
        assert f'fill="{colours["square"]}"' in svg
        assert f'fill="{colours["drawing"]}"' in svg
        assert 'fill="#fff"' not in svg and 'fill="#000"' not in svg


def test_the_same_icon_of_two_armies_is_drawn_in_two_colours(board):
    """One drawing, two tints: the icon says what the unit is, the colour says whose it is."""
    drawn = board.evaluate("""async () => {
        const armies = ['02-reissland', '01-yzent'].map((faction) =>
            ({ image: '02-reissland/reissland-03-3-archers.jpg', faction }));
        await loadThePawnIcons(armies);
        return armies.map((unit) => pawnIconSource(unit));
    }""")
    assert drawn[0] != drawn[1]
    assert all(source.startswith(A_DRAWN_SOURCE) for source in drawn)


# --- What the face does not change ---

def test_the_icons_stay_on_the_counters_squares_and_size(board):
    """The face is the source of an <img> and nothing else: the geometry is the counters' own."""
    counters = {(p["q"], p["r"], p["s"]): p for p in piece_geometry(board)}
    swap_the_face(board)

    for icon in piece_geometry(board):
        counter = counters[(icon["q"], icon["r"], icon["s"])]
        assert icon["width"] == counter["width"]
        assert abs(icon["x"] - counter["x"]) < 1
        assert abs(icon["y"] - counter["y"]) < 1


def test_the_scene_laid_out_again_keeps_the_face(board):
    """A phase change re-lays every counter: they come back drawn, and nothing has to say so."""
    swap_the_face(board)
    move_to_the_orcs_movement(board)

    faces = pawn_faces(board)
    assert len(faces) == len(current_game.SCENARIO)
    assert all(pawn["drawn"] is has_an_icon(pawn["key"]) for pawn in faces)


def test_the_ghosts_wear_the_face_in_use(board):
    """They are born under the selection, after the choice: the layer dresses them as it lays
    them."""
    swap_the_face(board)
    move_to_the_orcs_movement(board)
    piece, _, _ = a_piece_that_can_move(
        board, lambda unit: unit.faction == ORCS and has_an_icon(unit.key))
    show_the_ghosts(board, piece)

    ghosts = pawn_faces(board, "img.ghost")
    assert ghosts
    assert all(ghost["icon"] and ghost["drawn"] for ghost in ghosts)


# --- The drawn pawns lie on the map, they are not printed on it ---

def shadow_of(page, selector):
    """The box-shadow each of those images computes to."""
    return page.evaluate("""(selector) => [...document.querySelectorAll(selector)].map(
        (image) => getComputedStyle(image).boxShadow)""", selector)


def test_a_drawn_pawn_casts_a_shadow_of_its_own(board):
    """A photograph is a scan of cardboard and carries the shading of the thing photographed; the
    drawn face is a flat square, and what puts it on top of the map rather than in it is the
    shadow under it - two layers, where the counter touches and what it casts."""
    photographs = set(shadow_of(board, "img.piece:not(.ghost)"))
    swap_the_face(board)
    drawn = shadow_of(board, "img.piece.icon:not(.ghost)")

    assert drawn, "no unit of the set-up took an icon"
    assert all(shadow not in photographs for shadow in drawn), drawn
    assert all(shadow.count("rgba") == 2 for shadow in drawn), drawn


def test_a_drawn_ghost_casts_nothing(board):
    """A ghost marks a square a unit could go to, not a counter lying on one. Its rule has to name
    the piece as well as the ghost to say so: the drawn face's shadow is worn by two classes."""
    swap_the_face(board)
    move_to_the_orcs_movement(board)
    piece, _, _ = a_piece_that_can_move(
        board, lambda unit: unit.faction == ORCS and has_an_icon(unit.key))
    show_the_ghosts(board, piece)

    ghosts = shadow_of(board, "img.ghost")
    assert ghosts
    assert all(shadow == "none" for shadow in ghosts)


def test_the_drawn_pawn_in_hand_is_still_ringed_in_gold(board):
    """The shadow gives way to what the board has to say about the counter: the piece in hand
    keeps its glow, drawn face or not."""
    swap_the_face(board)
    move_to_the_orcs_movement(board)
    piece, _, _ = a_piece_that_can_move(
        board, lambda unit: unit.faction == ORCS and has_an_icon(unit.key))
    show_the_ghosts(board, piece)

    [selected] = shadow_of(board, "img.piece.selected")
    assert "246, 231, 193" in selected, selected


def test_the_card_keeps_the_photograph_of_the_hovered_unit(board):
    """The icon is a reading aid on the map; the card is where the counter itself is read."""
    swap_the_face(board)
    board.locator("img.piece:not(.ghost)").first.hover()
    board.wait_for_function("() => !document.getElementById('card').classList.contains('empty')")

    assert "/pieces/" in board.locator("#card-image").get_attribute("src")


# --- The choice is the browser's ---

def test_the_chosen_face_survives_a_reload(board):
    """It belongs to this browser, as the panel's edge does: not to the player, not to the game."""
    assert swap_the_face(board) == "true"

    board.reload()
    wait_for_the_counters(board)
    board.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")
    assert any(pawn["drawn"] for pawn in pawn_faces(board))


def test_the_counters_come_back_after_a_reload_too(board):
    """The way back is stored like the way there: a swap and a swap back leave nothing behind."""
    swap_the_face(board)
    assert swap_the_face(board) == "false"

    board.reload()
    wait_for_the_counters(board)
    assert announced_face(board) == "false"
    assert all(pawn["photograph"] for pawn in pawn_faces(board))


# --- The face asked for in the address ---

def test_the_address_opens_the_board_on_the_icons(page, server, application, seat_the_player):
    """"?icons=1" - the parameter the scenario page is opened on, understood here too."""
    board = open_the_board(page, server, application, seat_the_player, "?icons=1")
    board.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")
    assert any(pawn["drawn"] for pawn in pawn_faces(board))


def test_the_address_is_remembered_like_the_button(page, server, application, seat_the_player):
    """It is kept as "?debug=1" is kept: one opens the board on a face, and it is still that face
    on the next load."""
    board = open_the_board(page, server, application, seat_the_player, "?icons=1")
    board.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")

    board.goto(server)
    wait_for_the_counters(board)
    board.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")


def test_the_address_puts_the_counters_back(page, server, application, seat_the_player):
    """"?icons=0" says the other thing, and says it over what was stored."""
    board = open_the_board(page, server, application, seat_the_player, "?icons=1")
    board.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")

    board.goto(f"{server}/?icons=0")
    wait_for_the_counters(board)
    assert announced_face(board) == "false"
    assert all(pawn["photograph"] for pawn in pawn_faces(board))


def test_an_address_that_says_nothing_leaves_the_stored_choice(board, server):
    """The parameter decides when it is there, and only then."""
    swap_the_face(board)

    board.goto(server)
    wait_for_the_counters(board)
    board.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")


# --- The scenario page ---
#
# It composes on the same map, and a counter is the same small grey square there. It has no button:
# the face is asked for in the address, which is what "?icons=1" is for.

def wait_for_the_drawn_face(page, number):
    """Waits for that many counters to be wearing an icon: the set is read after they are laid."""
    page.wait_for_function("(n) => document.querySelectorAll('img.piece.icon').length === n",
                           arg=number)


@pytest.fixture
def a_scenario_with_a_drawn_unit(scenarios_directory, plain_squares):  # noqa: F811
    """Writes a scenario no. 7 with one unit that has an icon and one that has none.

    The two are taken from either side of the correspondences, so that one file exercises both
    answers of the edit page. The armies are derived from the placement, as the edit page itself
    derives them.
    """
    if A_DRAWN_UNIT is None or AN_UNDRAWN_UNIT is None:
        pytest.skip("the correspondences leave no counter undrawn")
    drawn, kept, _ = plain_squares
    values = {
        "numero": DRAWN_SCENARIO, "nom": "Deux faces", "source": "les tests",
        "nombre_de_tours": 10,
        "armees": armies_of({drawn: A_DRAWN_UNIT, kept: AN_UNDRAWN_UNIT}),
        "placement": {drawn: A_DRAWN_UNIT, kept: AN_UNDRAWN_UNIT}}
    (scenarios_directory / DRAWN_SCENARIO_FILE).write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return drawn, kept


def test_the_edit_page_lays_the_scenarios_units_drawn(
        page, server, application, seat_the_player, a_scenario_with_a_drawn_unit):
    """What the address was asked for: `/admin/scenarios/<n>/edit?icons=1`."""
    drawn, kept = a_scenario_with_a_drawn_unit
    editing = open_the_page(page, server, application, seat_the_player,
                            f"/admin/scenarios/{DRAWN_SCENARIO}/edit?icons=1")
    wait_for_pieces(editing, 2)
    wait_for_the_drawn_face(editing, 1)

    faces = {pawn["key"]: pawn for pawn in pawn_faces(editing, "img.piece")}
    assert faces[A_DRAWN_UNIT]["drawn"], drawn
    assert faces[AN_UNDRAWN_UNIT]["photograph"], kept


def test_the_edit_page_keeps_the_counters_without_the_parameter(
        page, server, application, seat_the_player, a_scenario_with_a_drawn_unit):
    """The photographs are what the page has always shown: the icons are asked for, never given."""
    editing = open_the_page(page, server, application, seat_the_player,
                            f"/admin/scenarios/{DRAWN_SCENARIO}/edit")
    wait_for_pieces(editing, 2)

    assert all(pawn["photograph"] and not pawn["icon"]
               for pawn in pawn_faces(editing, "img.piece"))


@needs_a_drawn_unit
def test_a_piece_laid_from_the_palette_wears_the_face(
        page, server, application, seat_the_player, scenarios_directory,  # noqa: F811
        plain_squares):  # noqa: F811
    """It is placed long after the page opened: the whole box is tinted at start-up so that it is
    drawn the moment it lands, and not a photograph first."""
    first, _, _ = plain_squares
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    lay(editor, A_DRAWN_UNIT, first)
    wait_for_pieces(editor, 1)
    wait_for_the_drawn_face(editor, 1)

    [pawn] = pawn_faces(editor, "img.piece")
    assert pawn["drawn"] and pawn["icon"]


@needs_a_drawn_unit
def test_a_piece_laid_without_the_parameter_keeps_its_photograph(
        page, server, application, seat_the_player, scenarios_directory,  # noqa: F811
        plain_squares):  # noqa: F811
    first, _, _ = plain_squares
    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    lay(editor, A_DRAWN_UNIT, first)
    wait_for_pieces(editor, 1)

    [pawn] = pawn_faces(editor, "img.piece")
    assert pawn["photograph"] and not pawn["icon"]


def palette_faces(page):
    """Each thumbnail of the palette: the unit it stands for, and the face it is wearing."""
    return page.evaluate("""() => [...document.querySelectorAll('#palette img')].map(
        (image) => ({
            key: image.piece.key,
            icon: image.classList.contains('icon'),
            drawn: image.src.startsWith('data:image/svg+xml'),
            photograph: image.src.includes('/pieces/'),
        }))""")


def test_the_palette_wears_the_face_too(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """One picks there what one lays on the map: a list of photographs beside a map of drawings
    would have to be read twice."""
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    editor.wait_for_function("() => document.querySelectorAll('#palette img.icon').length > 0")

    faces = palette_faces(editor)
    assert len(faces) == len(PIECE_CATALOGUE)
    assert all(entry["drawn"] is has_an_icon(entry["key"]) for entry in faces)


# --- The same button on the scenario page ---

def swap_the_face_on_the_editor(page):
    """Clicks the editor's button and waits for it to announce the new face."""
    before = page.evaluate(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed')")
    page.locator("#pawn-style").click()
    page.wait_for_function(
        "(before) => document.getElementById('pawn-style').getAttribute('aria-pressed') !== before",
        arg=before)
    return page.evaluate(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed')")


def test_the_editors_bar_carries_the_button_and_it_fits(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """That bar is `overflow: hidden` too, and narrower than the board's - the palette takes the
    right of the window: one button too many would be clipped there silently."""
    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    room = editor.evaluate("""() => {
        const toolbar = document.getElementById('toolbar').getBoundingClientRect();
        const save = document.getElementById('save').getBoundingClientRect();
        return toolbar.right - save.right;
    }""")

    assert editor.locator("#pawn-style").is_visible()
    assert room >= 0, room


def test_the_editors_button_draws_the_map_and_the_palette(
        page, server, application, seat_the_player, scenarios_directory,  # noqa: F811
        plain_squares):  # noqa: F811
    """The same button the board carries, and the same two faces behind it."""
    first, *_ = plain_squares
    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    lay(editor, A_DRAWN_UNIT, first)
    wait_for_pieces(editor, 1)
    assert all(pawn["photograph"] for pawn in pawn_faces(editor, "img.piece"))

    assert swap_the_face_on_the_editor(editor) == "true"
    wait_for_the_drawn_face(editor, 1)

    [pawn] = pawn_faces(editor, "img.piece")
    assert pawn["drawn"] and pawn["icon"]
    assert any(entry["drawn"] for entry in palette_faces(editor))


def test_the_editors_button_puts_the_photographs_back(
        page, server, application, seat_the_player, scenarios_directory,  # noqa: F811
        plain_squares):  # noqa: F811
    """A swap and a swap back leave the page as it was found."""
    first, *_ = plain_squares
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    lay(editor, A_DRAWN_UNIT, first)
    wait_for_the_drawn_face(editor, 1)

    assert swap_the_face_on_the_editor(editor) == "false"

    assert all(pawn["photograph"] and not pawn["icon"]
               for pawn in pawn_faces(editor, "img.piece"))
    assert all(entry["photograph"] for entry in palette_faces(editor))


def test_the_face_chosen_on_the_editor_survives_a_reload(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """It is kept where the board keeps it: one key, this browser's, for the two pages."""
    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    assert swap_the_face_on_the_editor(editor) == "true"

    editor.reload()
    editor.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")


def test_the_face_chosen_on_the_board_is_the_one_the_editor_opens_on(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """One choice for the two pages: a counter does not change appearance because one walked from
    the game to the composing."""
    board = open_the_board(page, server, application, seat_the_player)
    assert swap_the_face(board) == "true"

    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    editor.wait_for_function(
        "() => document.getElementById('pawn-style').getAttribute('aria-pressed') === 'true'")
    # The whole box is read before anything is dressed: the button announces the face at once, the
    # palette wears it when the set has arrived.
    editor.wait_for_function("() => document.querySelectorAll('#palette img.icon').length > 0")

    assert any(entry["drawn"] for entry in palette_faces(editor))


def test_the_palette_keeps_the_counter_where_there_is_no_icon(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """The same answer as the map's: a unit the file leaves blank stays its photograph."""
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    editor.wait_for_function("() => document.querySelectorAll('#palette img.icon').length > 0")

    kept = [entry for entry in palette_faces(editor) if not entry["icon"]]
    assert kept
    assert all(entry["photograph"] and not has_an_icon(entry["key"]) for entry in kept)


def test_the_palette_keeps_its_photographs_without_the_parameter(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    assert all(entry["photograph"] and not entry["icon"] for entry in palette_faces(editor))


def test_the_palette_thumbnails_keep_their_size(
        page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """The drawn face must not move a row of the list: the hairline eats inwards."""
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    editor.wait_for_function("() => document.querySelectorAll('#palette img.icon').length > 0")

    sizes = editor.evaluate("""() => [...document.querySelectorAll('#palette img')].map(
        (image) => [image.offsetWidth, image.offsetHeight])""")
    assert set(map(tuple, sizes)) == {(PALETTE_THUMBNAIL, PALETTE_THUMBNAIL)}


def test_the_chooser_carries_the_face_to_the_next_scenario(
        page, server, application, seat_the_player, a_scenario_with_a_drawn_unit):
    """Going from one scenario to the next must not put the photographs back unasked."""
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    editor.select_option("#chooser", str(DRAWN_SCENARIO))
    editor.wait_for_url(f"**/admin/scenarios/{DRAWN_SCENARIO}/edit?icons=1")
    wait_for_pieces(editor, 2)
    wait_for_the_drawn_face(editor, 1)
