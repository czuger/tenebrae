"""The two faces of a pawn: the counter photographed, and the drawn icon that stands in for it.

The board opens on the counters. The second button of the bar puts an icon on the units that have
one - one drawing per kind of unit, tinted with the colour of its army - and puts the photographs
back; the choice is this browser's, and it survives the reload.

The set-up the server opens on is the war of the dwarves, where two counters out of eight have a
drawn face: the orc cavalry and the orc archers. That mixture is the point of several of these
tests - what has no icon must keep its counter rather than disappear. The counters the battle of
Reissland fields are named here by their photographs, and the page's own table is asked about them
directly.

These tests require Chromium (`make browser`).
"""

import json

import pytest

from tenebrae.application import current_game
from tenebrae.application.config import ROOT
from tenebrae.application.pieces import PIECE_CATALOGUE
from tenebrae.engine.piece import CATALOGUE

from tests.application.test_board_browser import (a_piece_that_can_move, piece_geometry,
                                                  show_the_ghosts)
from tests.application.test_scenarios import (plain_squares,  # noqa: F401
                                              scenarios_directory)
from tests.application.test_scenarios_browser import lay, open_the_page, wait_for_pieces

# The correspondences as the browser reads them, by photograph: these tests ask the file the same
# question the page asks it.
CORRESPONDENCES = dict(json.loads(
    (ROOT / "tenebrae" / "application" / "static" / "pawn_icons.json").read_text(encoding="utf-8")))

# The five counters the battle of Reissland fields and the icons they take, each named as the board
# names it - the faction's directory, then the photograph. Anything else keeps its photograph.
DRAWN_COUNTERS = [
    ("02-reissland/reissland-01-15-infanteries.jpg", "lorc/barbute"),
    ("01-yzent/yzent-02-6-infanteries-de-puissance-6.jpg", "lorc/visored-helm"),
    ("02-reissland/reissland-02-8-cavaleries.jpg", "delapouite/cavalry"),
    ("02-reissland/reissland-03-3-archers.jpg", "lorc/bowman"),
    ("01-yzent/yzent-04-3-catapultes.jpg", "heavenly-dog/catapult"),
]

# Counters no row draws: a ram, a phalanx, the populace, an infantry of the elves - and a name the
# box does not carry, which is the same nothing.
BLANK_COUNTERS = [
    "01-yzent/yzent-05-1-belier.jpg",
    "01-yzent/yzent-06-5-phalanges-de-puissance-5-renforts.jpg",
    "05-population/population-01-20-populaces.jpg",
    "09-elfes/elfes-01-5-infanteries.jpg",
    "11-orques/there-is-no-such-counter.jpg",
]

REISSLAND = "02-reissland"
YZENT = "01-yzent"

A_DRAWN_SOURCE = "data:image/svg+xml"

# The phase the orcs move at, and how many changes away it is: their movement, after the dwarves'
# movement and the dwarves' combat (magic is skipped).
ORC_MOVEMENT = "Phase de mouvement — Orques"
PHASES_TO_THE_ORCS = 2

# Two units of one faction, on either side of the correspondences: the cavalry's row names an
# icon, the infantry's row is blank, so it keeps its counter.
ORC_CAVALRY = "orques-02-5-cavaleries"
ORC_INFANTRY = "orques-01-15-infanteries"

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


def rgb(colour):
    """The three channels of a "#rrggbb" colour."""
    return tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))


def brightness(colour):
    """How light the colour reads, on the usual weighting of the three channels."""
    red, green, blue = rgb(colour)
    return 0.299 * red + 0.587 * green + 0.114 * blue


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

    assert kept, "every unit of the set-up took an icon: the mixture is no longer exercised"
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


def test_the_two_infantries_are_told_apart_by_their_photographs(board):
    """Both carry the symbol "infanterie", and they wear two different helmets: what separates
    them is the counter each was printed on."""
    helmets = ask_the_table(board, ["01-yzent/yzent-01-9-infanteries-de-puissance-4.jpg",
                                    "01-yzent/yzent-02-6-infanteries-de-puissance-6.jpg"])
    assert helmets == ["lorc/barbute", "lorc/visored-helm"]
    assert helmets[0] != helmets[1]


def test_a_counter_whose_row_is_blank_is_drawn_by_nothing(board):
    """A ram, a phalanx, the populace, an infantry of the elves - and a name the file does not
    carry: an empty icon, hence the counter."""
    assert ask_the_table(board, BLANK_COUNTERS) == [None] * len(BLANK_COUNTERS)


def test_the_table_answers_nothing_before_its_file_is_read(board):
    """It is a data file, and the fallback while it is in flight is the photograph - never a
    wrong icon."""
    assert board.evaluate(
        "() => pawnIconOf({ image: '02-reissland/reissland-02-8-cavaleries.jpg' })") is None


def test_the_five_icons_are_read_from_the_server(board):
    """Each of the five files is where the table says it is: they are fetched and tinted here."""
    units = [{"image": photograph, "faction": REISSLAND} for photograph, _ in DRAWN_COUNTERS]
    drawn = board.evaluate("""async (units) => {
        await loadThePawnIcons(units);
        return units.map((unit) => pawnIconSource(unit));
    }""", units)

    assert len(drawn) == len(DRAWN_COUNTERS)
    assert all(source and source.startswith(A_DRAWN_SOURCE) for source in drawn), drawn
    assert len(set(drawn)) == len(drawn), "two counters are drawn the same"


# --- The colours of the armies ---

def test_the_two_armies_of_reissland_are_told_apart_by_their_blue(board):
    """Reissland's blue is the clear one, Yzent's the deep one, and both are blue."""
    colours = board.evaluate("""() => ({
        reissland: armyColoursOf({ faction: '02-reissland' }),
        yzent: armyColoursOf({ faction: '01-yzent' }),
    })""")
    reissland, yzent = colours["reissland"]["square"], colours["yzent"]["square"]

    for blue in (reissland, yzent):
        red, green, channel = rgb(blue)
        assert channel > red and channel > green, blue
    assert brightness(reissland) > brightness(yzent)


def test_the_drawing_reads_on_the_square_of_both_armies(board):
    """Dark on the clear blue, pale on the deep one: an icon of one tone would show nothing."""
    colours = board.evaluate("""() => [
        armyColoursOf({ faction: '02-reissland' }),
        armyColoursOf({ faction: '01-yzent' }),
        armyColoursOf({ faction: '11-orques' }),
    ]""")
    for army in colours:
        assert abs(brightness(army["square"]) - brightness(army["drawing"])) > 100, army


def test_an_army_the_table_does_not_colour_takes_neither_blue(board):
    """The two blues were given for the two armies of the battle; the others keep out of them."""
    colours = board.evaluate("""() => ({
        orcs: armyColoursOf({ faction: '11-orques' }),
        dwarves: armyColoursOf({ faction: '10-nains' }),
        reissland: armyColoursOf({ faction: '02-reissland' }),
        yzent: armyColoursOf({ faction: '01-yzent' }),
    })""")
    blues = {colours["reissland"]["square"], colours["yzent"]["square"]}

    assert colours["orcs"] == colours["dwarves"]
    assert colours["orcs"]["square"] not in blues


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
    piece, _, _ = a_piece_that_can_move(board, lambda unit: has_an_icon(unit.key))
    show_the_ghosts(board, piece)

    ghosts = pawn_faces(board, "img.ghost")
    assert ghosts
    assert all(ghost["icon"] and ghost["drawn"] for ghost in ghosts)


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

    The orc cavalry's row names an icon; the orc infantry's row is blank, so it keeps its
    photograph. One file therefore exercises both answers of the edit page.
    """
    drawn, kept, _ = plain_squares
    values = {
        "numero": DRAWN_SCENARIO, "nom": "Deux faces", "source": "les tests",
        "nombre_de_tours": 10,
        "armees": [
            {"joueur": 1, "camp": "tenebres", "armee": "Orques", "consigne": None,
             "ancre": drawn, "unites": 2, "magie": None, "jeteur_de_sorts": None}],
        "placement": {drawn: ORC_CAVALRY, kept: ORC_INFANTRY}}
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
    assert faces[ORC_CAVALRY]["drawn"], drawn
    assert faces[ORC_INFANTRY]["photograph"], kept


def test_the_edit_page_keeps_the_counters_without_the_parameter(
        page, server, application, seat_the_player, a_scenario_with_a_drawn_unit):
    """The photographs are what the page has always shown: the icons are asked for, never given."""
    editing = open_the_page(page, server, application, seat_the_player,
                            f"/admin/scenarios/{DRAWN_SCENARIO}/edit")
    wait_for_pieces(editing, 2)

    assert all(pawn["photograph"] and not pawn["icon"]
               for pawn in pawn_faces(editing, "img.piece"))


def test_a_piece_laid_from_the_palette_wears_the_face(
        page, server, application, seat_the_player, scenarios_directory,  # noqa: F811
        plain_squares):  # noqa: F811
    """It is placed long after the page opened: the whole box is tinted at start-up so that it is
    drawn the moment it lands, and not a photograph first."""
    first, _, _ = plain_squares
    editor = open_the_page(page, server, application, seat_the_player,
                           "/admin/scenarios?icons=1")
    lay(editor, ORC_CAVALRY, first)
    wait_for_pieces(editor, 1)
    wait_for_the_drawn_face(editor, 1)

    [pawn] = pawn_faces(editor, "img.piece")
    assert pawn["drawn"] and pawn["icon"]


def test_a_piece_laid_without_the_parameter_keeps_its_photograph(
        page, server, application, seat_the_player, scenarios_directory,  # noqa: F811
        plain_squares):  # noqa: F811
    first, _, _ = plain_squares
    editor = open_the_page(page, server, application, seat_the_player, "/admin/scenarios")
    lay(editor, ORC_CAVALRY, first)
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
