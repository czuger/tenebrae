"""Choosing the set-up on the landing page, in Chromium: what it offers, and what it opens.

These tests require Chromium (`make browser`). The chooser used to sit in the board's table dialog
and be fetched from `/game/scenarios` at every opening: the dialog could be hours old, and a set-up
disabled meanwhile had to leave it without a reload. It is on the list of games now, and that page
was served a moment ago - so the list is laid **in the page**, and the guard against a stale choice
is the one that always did the work: `POST /game/new` reads the files again and refuses. What the
browser has to show is that refusal.

Everything runs on a diverted directory: nothing writes into `tenebrae/scenarios/`.
"""

import json
import shutil

import pytest

from tenebrae.application import current_game
from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.scenario import scenario

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
    """Diverts the scenarios directory to a copy of the real one, every scenario offered.

    The copies start offered whatever their originals say - no. 4 is withdrawn in the repository as
    it stands - so that the chooser these tests read holds the list they have themselves composed.
    """
    for path in engine_scenario.SCENARIOS.glob("scenario-*.json"):
        copy = tmp_path / path.name
        shutil.copy(path, copy)
        write_the_field(copy, True)
    monkeypatch.setattr(engine_scenario, "SCENARIOS", tmp_path)
    return tmp_path


def disable(directory, number):
    """Writes `"enabled": false` into a scenario's file, as an administrator would by hand."""
    write_the_field(next(directory.glob(f"scenario-{number:02d}-*.json")), False)


def write_the_field(path, enabled):
    """Sets the `enabled` field of a scenario file, leaving the rest of it as it was."""
    values = json.loads(path.read_text(encoding="utf-8"))
    values["enabled"] = enabled
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def on_file(directory, *withdrawn):
    """The numbers of the scenarios in that directory, in order, less those named.

    Read from the directory rather than named here: composing a scenario on `/admin/scenarios`
    writes one more file, and a list written down would have to be edited every time somebody laid
    a set-up out.
    """
    return [int(path.name.split("-")[1]) for path in sorted(directory.glob("scenario-*.json"))
            if int(path.name.split("-")[1]) not in withdrawn]


def open_the_list(page, server):
    """Loads the list of games logged in, and waits for the form to have been filled."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")  # the login lands on the list
    page.wait_for_function("document.getElementById('new-scenario').options.length > 0")
    return page


def chosen_numbers(page):
    """The scenario numbers the form offers, in the order it offers them."""
    return page.locator("#new-scenario").evaluate(
        "select => [...select.options].map((option) => Number(option.value))")


def test_the_form_offers_the_scenarios_on_file(page, server, scenarios_directory):
    open_the_list(page, server)

    assert chosen_numbers(page) == on_file(scenarios_directory)
    # The first on file is the proposal: there is no set-up "being played" on a page that plays
    # nothing.
    assert page.locator("#new-scenario").input_value() == str(WAR_OF_THE_DWARVES)


def test_a_scenario_disabled_in_its_file_leaves_the_form(page, server, scenarios_directory):
    """The page is served with the list, so a file changed since is honoured at the next load."""
    open_the_list(page, server)
    assert REISSLAND in chosen_numbers(page)

    disable(scenarios_directory, REISSLAND)
    open_the_list(page, server)

    assert chosen_numbers(page) == on_file(scenarios_directory, REISSLAND)


def test_a_scenario_disabled_since_the_page_was_served_is_refused(page, server,
                                                                  scenarios_directory):
    """The page holds a list that has just gone stale; the server reads the files again and says
    so, and the player is told rather than left before an unchanged list."""
    open_the_list(page, server)
    page.select_option("#new-scenario", str(REISSLAND))

    disable(scenarios_directory, REISSLAND)
    page.click("#new-game-submit")

    page.wait_for_selector("#new-game-error:not([hidden])")
    assert f"n° {REISSLAND}" in page.locator("#new-game-error").inner_text()


def test_the_sides_offered_are_the_chosen_scenarios(page, server, scenarios_directory):
    """Another set-up is another pair of armies: a side kept from the one before would be a side
    the game has not."""
    open_the_list(page, server)
    page.select_option("#new-scenario", str(REISSLAND))

    armies = {army["camp"]: army["armee"] for army in scenario(REISSLAND).armies}
    sides = page.locator("#new-side")
    assert sides.evaluate(
        "select => [...select.options].map((option) => option.value)") == list(armies)
    assert sides.evaluate(
        "select => [...select.options].map((option) => option.textContent)") \
        == list(armies.values())


def test_the_chosen_scenario_is_the_one_laid_out(page, server, scenarios_directory):
    open_the_list(page, server)
    page.select_option("#new-scenario", str(REISSLAND))

    page.click("#new-game-submit")
    page.wait_for_url(f"{server}/game/*")

    assert current_game.SCENARIO_NUMBER == REISSLAND
    page.wait_for_function("document.querySelectorAll('img.piece').length > 0")
    assert set(current_game.BOARD.to_dict()) <= set(scenario(REISSLAND).placement)
