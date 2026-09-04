"""The scenario chooser in the table dialog, in Chromium: what it offers, and what it opens.

These tests require Chromium (`make browser`). The chooser is filled when the dialog opens, from
`/game/scenarios` rather than from the page: that is what lets a scenario disabled in its file
leave the list without a reload, and it is exercised here on a diverted directory - nothing writes
into `tenebrae/scenarios/`.
"""

import json
import shutil

import pytest

from tenebrae.application import current_game
from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.scenario import scenario

ALLIANCE = "alliance"
WAR_OF_THE_DWARVES = 4
REISSLAND = 6


@pytest.fixture(autouse=True)
def empty_table(application):
    """Every test starts from a lifted table; the board lays itself out again at every load."""
    current_game.SEATS.clear()
    yield
    current_game.SEATS.clear()


@pytest.fixture
def scenarios_directory(tmp_path, monkeypatch):
    """Diverts the scenarios directory to a copy of the real one, and returns it."""
    for path in engine_scenario.SCENARIOS.glob("scenario-*.json"):
        shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(engine_scenario, "SCENARIOS", tmp_path)
    return tmp_path


def disable(directory, number):
    """Writes `"enabled": false` into a scenario's file, as an administrator would by hand."""
    path = next(directory.glob(f"scenario-{number:02d}-*.json"))
    values = json.loads(path.read_text(encoding="utf-8"))
    values["enabled"] = False
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def open_the_board(page, server):
    """Loads the board logged in, and waits for the scene to be laid out."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(server)
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(current_game.SCENARIO))
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def sit_down_at_the_alliance(page):
    """Takes the Alliance seat through the dialog, as a player would, and closes it."""
    page.locator("#player").click()
    page.locator(f"#table-seats .side[data-side='{ALLIANCE}'] button").click()
    page.wait_for_function("!document.getElementById('table-dialog').open")


def open_the_chooser(page):
    """Reopens the table and waits for the chooser to have been filled from the server."""
    page.locator("#player").click()
    page.wait_for_function(
        "!document.getElementById('table-scenario').hidden"
        " && document.getElementById('table-scenario-choice').options.length > 0")
    return page.locator("#table-scenario-choice")


def test_the_chooser_offers_the_scenarios_on_file(page, server, scenarios_directory):
    open_the_board(page, server)
    sit_down_at_the_alliance(page)
    chooser = open_the_chooser(page)

    assert chooser.evaluate("select => [...select.options].map((option) => Number(option.value))") \
        == [WAR_OF_THE_DWARVES, REISSLAND]
    # The set-up being played is the proposal.
    assert chooser.input_value() == str(WAR_OF_THE_DWARVES)


def test_a_player_without_a_seat_has_no_chooser(page, server, scenarios_directory):
    """Nothing can be started from the dialog without a seat: the row stays out of it."""
    open_the_board(page, server)
    page.locator("#player").click()
    assert page.locator("#table-scenario").is_hidden()


def test_a_scenario_disabled_in_its_file_leaves_the_chooser(page, server, scenarios_directory):
    """No reload: the list is fetched at every opening of the dialog."""
    open_the_board(page, server)
    sit_down_at_the_alliance(page)
    assert open_the_chooser(page).locator("option").count() == 2

    page.locator("#table-close").click()
    disable(scenarios_directory, REISSLAND)

    chooser = open_the_chooser(page)
    assert chooser.locator("option").count() == 1
    assert chooser.input_value() == str(WAR_OF_THE_DWARVES)


def test_the_choice_survives_the_dialog_being_rebuilt(page, server, scenarios_directory):
    """A move played while the dialog is open must not put the chooser back on the current one."""
    open_the_board(page, server)
    sit_down_at_the_alliance(page)
    open_the_chooser(page).select_option(str(REISSLAND))

    # What a move arriving through the stream does: the table comes back as it stands, and the
    # dialog is rebuilt around it. The refill is asynchronous - it goes to the server - so the
    # assertion waits for the options to have been written again rather than firing at once.
    page.evaluate("""
        window.refilled = false;
        new MutationObserver(() => { window.refilled = true; }).observe(
          document.getElementById('table-scenario-choice'), { childList: true });
        updateTheTable(table);
    """)
    page.wait_for_function("window.refilled")
    assert page.locator("#table-scenario-choice").input_value() == str(REISSLAND)


def test_the_chosen_scenario_is_the_one_laid_out(page, server, scenarios_directory):
    open_the_board(page, server)
    sit_down_at_the_alliance(page)
    open_the_chooser(page).select_option(str(REISSLAND))

    page.locator("#table-against-ai").click()
    page.wait_for_function("!document.getElementById('table-dialog').open")

    assert current_game.SCENARIO_NUMBER == REISSLAND
    page.wait_for_function("document.querySelectorAll('img.piece').length > 0")
    assert set(current_game.BOARD.to_dict()) <= set(scenario(REISSLAND).placement)
