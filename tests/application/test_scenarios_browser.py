"""The scenario page in the browser: the palette, placing, moving, removing, saving, editing.

These tests require Chromium (`python3 -m playwright install chromium`). Like the client ones,
they divert the scenarios directory: nothing is written into `tenebrae/scenarios/`.
"""

import json

import pytest

from tenebrae.application.grid import PIECE_SIZE
from tenebrae.application.pieces import PIECE_CATALOGUE, PIECES_BY_KEY
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.scenario import BOOKLET_SCENARIOS

from tests.application.test_board_browser import (click_the_hexagon, expected_centre,
                                                  piece_geometry)
from tests.application.test_scenarios import (CROSSBOWMEN, FIRE_MARKER,  # noqa: F401
                                              FIXED_FILE, FIXED_NUMBER, INFANTRY,
                                              ORC_INFANTRY, a_lake, fixed_scenario,
                                              plain_squares, scenarios_directory)


def open_the_page(page, server, application, seat_the_player, path):
    """Opens a page of the scenario editor logged in, and waits for the map to be loaded and
    scaled."""
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(f"{server}{path}")
    page.wait_for_function(
        "() => { const m = document.getElementById('map');"
        " return m.complete && m.naturalWidth > 0; }")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


@pytest.fixture
def editor(page, server, application, seat_the_player, scenarios_directory):  # noqa: F811
    """/admin/scenarios: composing a new scenario."""
    return open_the_page(page, server, application, seat_the_player, "/admin/scenarios")


@pytest.fixture
def editing(page, server, application, seat_the_player, fixed_scenario):  # noqa: F811
    """/admin/scenarios/7/edit: the scenario `fixed_scenario` wrote, opened for editing."""
    return open_the_page(page, server, application, seat_the_player,
                         f"/admin/scenarios/{FIXED_NUMBER}/edit")


def take(page, key):
    """Takes a piece in hand from the palette."""
    page.locator(f"#palette button[data-key='{key}']").click()


def placed(page):
    """The pieces laid on the map: their square and their key."""
    return page.evaluate("""() => [...document.querySelectorAll('img.piece')].map((image) => ({
        square: `${image.dataset.q},${image.dataset.r},${image.dataset.s}`,
        key: image.dataset.key,
    }))""")


def wait_for_pieces(page, number):
    page.wait_for_function("(n) => document.querySelectorAll('img.piece').length === n",
                           arg=number)


def lay(page, key, square):
    """Takes a piece and lays it on a square."""
    before = len(placed(page))
    take(page, key)
    click_the_hexagon(page, Hex.from_key(square))
    wait_for_pieces(page, before + 1)


# --- The page ---


def test_the_palette_offers_every_piece_of_the_box(editor):
    buttons = editor.locator("#palette button.palette-piece")
    assert buttons.count() == len(PIECE_CATALOGUE)
    assert buttons.first.get_attribute("data-key") == PIECE_CATALOGUE[0]["key"]
    assert buttons.first.locator("img").get_attribute("src").endswith(PIECE_CATALOGUE[0]["path"])
    assert editor.locator("#palette .faction").count() == len(
        {piece["faction"] for piece in PIECE_CATALOGUE})


def test_the_map_fits_beside_the_palette(editor):
    """The palette hides nothing of the map: the fit is that of the frame, not of the window."""
    boxes = editor.evaluate("""() => ({
        map: document.getElementById('map').getBoundingClientRect().toJSON(),
        palette: document.getElementById('palette').getBoundingClientRect().toJSON(),
        natural: document.getElementById('map').naturalWidth,
    })""")
    assert boxes["map"]["right"] <= boxes["palette"]["left"] + 1
    assert boxes["map"]["height"] <= 900 + 1
    assert boxes["map"]["width"] < boxes["natural"]


def test_the_save_button_waits_for_a_piece(editor):
    assert editor.locator("#save").is_disabled()
    assert editor.locator("#counter").text_content() == "aucun pion"


# --- Placing ---


def test_a_piece_taken_from_the_palette_is_laid_on_the_clicked_square(
        editor, plain_squares):  # noqa: F811
    first, second, _ = plain_squares
    take(editor, INFANTRY)
    assert editor.locator(f"#palette button[data-key='{INFANTRY}']").get_attribute(
        "class") == "palette-piece selected"
    assert PIECES_BY_KEY[INFANTRY]["name"] in editor.locator("#in-hand").text_content()

    click_the_hexagon(editor, Hex.from_key(first))
    wait_for_pieces(editor, 1)
    assert placed(editor) == [{"square": first, "key": INFANTRY}]
    assert editor.locator("#counter").text_content() == "1 pion"
    assert editor.locator("#save").is_enabled()

    # The piece stays in hand: the next click lays another one.
    click_the_hexagon(editor, Hex.from_key(second))
    wait_for_pieces(editor, 2)
    assert editor.locator("#counter").text_content() == "2 pions"


def test_the_laid_piece_is_centred_on_its_hexagon_at_the_boards_size(
        editor, plain_squares):  # noqa: F811
    first, _, _ = plain_squares
    lay(editor, INFANTRY, first)
    [piece] = piece_geometry(editor, "img.piece")
    x, y = expected_centre(piece["q"], piece["r"])
    assert abs(piece["x"] - x) < 1 and abs(piece["y"] - y) < 1
    assert piece["width"] == PIECE_SIZE
    assert abs(piece["angle"]) <= 5


def test_a_square_no_unit_can_occupy_refuses_the_piece(editor):
    take(editor, INFANTRY)
    click_the_hexagon(editor, Hex.from_key(a_lake()))
    message = editor.locator("#message")
    message.wait_for(state="visible")
    assert "lac" in message.text_content()
    assert placed(editor) == []


# --- Moving and removing ---


def test_clicking_a_placed_piece_takes_it_in_hand_and_retirer_removes_it(
        editor, plain_squares):  # noqa: F811
    first, _, _ = plain_squares
    lay(editor, INFANTRY, first)
    remove = editor.locator("#remove")
    assert remove.is_hidden()

    click_the_hexagon(editor, Hex.from_key(first))
    remove.wait_for(state="visible")
    assert editor.locator("img.piece.selected").count() == 1
    # The palette piece is no longer in hand: the placed one is.
    assert editor.locator("#palette button.selected").count() == 0
    assert first in editor.locator("#in-hand").text_content()

    remove.click()
    wait_for_pieces(editor, 0)
    assert editor.locator("#counter").text_content() == "aucun pion"
    assert editor.locator("#save").is_disabled()
    assert remove.is_hidden()


def test_the_piece_in_hand_moves_to_the_clicked_square(editor, plain_squares):  # noqa: F811
    first, second, _ = plain_squares
    lay(editor, INFANTRY, first)
    click_the_hexagon(editor, Hex.from_key(first))
    editor.locator("#remove").wait_for(state="visible")

    click_the_hexagon(editor, Hex.from_key(second))
    editor.wait_for_function(
        "(square) => document.querySelector('img.piece').dataset.q === square.split(',')[0]"
        " && document.querySelector('img.piece').dataset.r === square.split(',')[1]",
        arg=second)
    assert placed(editor) == [{"square": second, "key": INFANTRY}]


def test_the_delete_key_removes_the_piece_in_hand(editor, plain_squares):  # noqa: F811
    first, _, _ = plain_squares
    lay(editor, INFANTRY, first)
    click_the_hexagon(editor, Hex.from_key(first))
    editor.locator("#remove").wait_for(state="visible")
    editor.keyboard.press("Delete")
    wait_for_pieces(editor, 0)


# --- Saving ---


def open_the_dialog(page):
    page.locator("#save").click()
    page.locator("#save-dialog[open]").wait_for()


def test_saving_asks_for_the_title_and_the_turns_then_writes_the_file(
        editor, scenarios_directory, plain_squares):  # noqa: F811
    first, second, _ = plain_squares
    lay(editor, INFANTRY, first)
    lay(editor, ORC_INFANTRY, second)

    open_the_dialog(editor)
    editor.locator("#save-name").fill("Essai en Chromium")
    editor.locator("#save-turns").fill("12")
    editor.locator("#save-confirm").click()

    status = editor.locator("#status")
    status.wait_for(state="visible")
    filename = f"scenario-{BOOKLET_SCENARIOS + 1:02d}-essai-en-chromium.json"
    assert f"n° {BOOKLET_SCENARIOS + 1}" in status.text_content()
    assert filename in status.text_content()
    assert editor.locator("#save-dialog[open]").count() == 0

    values = json.loads((scenarios_directory / filename).read_text(encoding="utf-8"))
    assert values["nom"] == "Essai en Chromium"
    assert values["nombre_de_tours"] == 12
    assert values["placement"] == {first: INFANTRY, second: ORC_INFANTRY}


def test_the_servers_refusal_is_read_in_the_dialog(
        editor, scenarios_directory, plain_squares):  # noqa: F811
    """Markers alone make no scenario: the server says so, and the dialog stays open."""
    first, _, _ = plain_squares
    lay(editor, FIRE_MARKER, first)

    open_the_dialog(editor)
    editor.locator("#save-name").fill("Sans armée")
    editor.locator("#save-confirm").click()

    error = editor.locator("#save-error")
    error.wait_for(state="visible")
    assert "Alliance" in error.text_content()
    assert editor.locator("#save-dialog[open]").count() == 1
    assert list(scenarios_directory.glob("*.json")) == []


def test_cancelling_writes_nothing(editor, scenarios_directory, plain_squares):  # noqa: F811
    first, _, _ = plain_squares
    lay(editor, INFANTRY, first)
    open_the_dialog(editor)
    editor.locator("#save-cancel").click()
    editor.wait_for_function("!document.getElementById('save-dialog').open")
    assert list(scenarios_directory.glob("*.json")) == []


# --- Editing ---


def test_the_edit_page_lays_the_scenarios_pieces(editing, fixed_scenario):  # noqa: F811
    wait_for_pieces(editing, 2)
    assert sorted(placed(editing), key=lambda entry: entry["square"]) == sorted(
        ({"square": square, "key": key} for square, key in fixed_scenario["placement"].items()),
        key=lambda entry: entry["square"])
    assert editing.locator("#counter").text_content() == "2 pions"
    assert editing.locator("#save").is_enabled()
    assert editing.locator("#chooser").input_value() == str(FIXED_NUMBER)
    assert f"n° {FIXED_NUMBER}" in editing.title()


def test_the_dialog_is_filled_and_saving_rewrites_the_file(
        editing, fixed_scenario, scenarios_directory, plain_squares):  # noqa: F811
    _, _, third = plain_squares
    wait_for_pieces(editing, 2)
    lay(editing, CROSSBOWMEN, third)

    open_the_dialog(editing)
    assert editing.locator("#save-name").input_value() == "La guerre des nains"
    assert editing.locator("#save-turns").input_value() == "10"
    assert f"n° {FIXED_NUMBER}" in editing.locator("#save-title").text_content()
    editing.locator("#save-turns").fill("20")
    editing.locator("#save-confirm").click()

    status = editing.locator("#status")
    status.wait_for(state="visible")
    assert f"n° {FIXED_NUMBER} modifié" in status.text_content()
    assert FIXED_FILE in status.text_content()

    assert sorted(path.name for path in scenarios_directory.glob("*.json")) == [FIXED_FILE]
    values = json.loads((scenarios_directory / FIXED_FILE).read_text(encoding="utf-8"))
    assert values["numero"] == FIXED_NUMBER
    assert values["nombre_de_tours"] == 20
    assert len(values["placement"]) == 3
    assert values["placement"][third] == CROSSBOWMEN
    assert values["armees"][0]["consigne"] == "Au sud du volcan."


def test_the_chooser_goes_from_one_scenario_to_another(
        fixed_scenario, editor):  # noqa: F811
    """From the new scenario to no. 7 and back: the chooser lists the files and navigates."""
    chooser = editor.locator("#chooser")
    assert chooser.input_value() == ""
    assert chooser.locator("option").all_text_contents() == [
        "nouveau scénario", f"n° {FIXED_NUMBER} — La guerre des nains"]

    chooser.select_option(str(FIXED_NUMBER))
    editor.wait_for_url(f"**/admin/scenarios/{FIXED_NUMBER}/edit")
    wait_for_pieces(editor, 2)

    editor.locator("#chooser").select_option("")
    editor.wait_for_url("**/admin/scenarios")
    editor.wait_for_function("document.getElementById('scale').textContent !== '—'")
    assert placed(editor) == []
