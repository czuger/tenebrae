"""The game against the AI, seen from the browser: the landing form, the "IA" seat, the opening.

These tests require Chromium (`make browser`). As everywhere, logging in unrolls the real flow: the
fake Discord client closes the authorization on our own return route - and lands on the list of
games, which is where a game against the machine is now opened.

It used to be opened from the board's own table dialog, by a player already seated, and the button
was hidden from anyone who held no side. There is no such button any more and no such seat: one
picks the set-up, the side one takes and "contre l'IA" on the list, before the game exists.
"""

import pytest

from tenebrae.application import current_game
from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.engine import ai

ALLIANCE, DARKNESS = "alliance", "tenebres"


@pytest.fixture(autouse=True)
def empty_table(application):
    """Every test starts from a lifted table; the board lays itself out again at every load."""
    current_game.SEATS.clear()
    yield
    current_game.SEATS.clear()


def open_the_list(page, server, logged_in=True):
    """Loads the list of games, logged in or not, and waits for the page to have laid itself out."""
    page.set_viewport_size({"width": 1400, "height": 900})
    if logged_in:
        page.goto(f"{server}/login")  # the login lands on the list
    else:
        page.goto(server)
    page.wait_for_selector("#saved")
    return page


def open_a_game_against_the_ai(page, server, side):
    """Fills the landing form and follows it to the board of the game it opens.

    Waiting for the board is waiting for the whole request: the AI's opening turn, when it holds
    the side that starts, is played inside it.
    """
    open_the_list(page, server)
    page.select_option("#new-side", side)
    page.check("#new-against-ai")
    page.click("#new-game-submit")
    page.wait_for_url(f"{server}/game/*")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def test_the_form_seats_the_machine_at_the_side_left_over(page, server):
    open_a_game_against_the_ai(page, server, ALLIANCE)

    assert current_game.SEATS.occupant(ALLIANCE) == DEFAULT_IDENTITY["discord_id"]
    assert current_game.SEATS.occupant(DARKNESS) == ai.AI_PLAYER
    # And the table of the board one lands on shows that seat held by "IA".
    page.locator("#player").click()
    assert ai.AI_NAME in page.locator(f"#table-seats .side[data-side='{DARKNESS}']").inner_text()


def test_the_ai_opens_the_scenario_when_it_holds_the_alliance(page, server):
    open_a_game_against_the_ai(page, server, DARKNESS)

    # The AI got the Alliance, played its opening turn, and handed play back to the Darkness.
    assert current_game.SEATS.occupant(ALLIANCE) == ai.AI_PLAYER
    assert (current_game.TURN.active_side, current_game.TURN.phase_type) == (DARKNESS, "mouvement")
    assert current_game.BOARD.to_dict() != current_game.SCENARIO.placement
    # And the page shows it: the phase displayed is the human player's.
    darkness = next(army["armee"] for army in current_game.SCENARIO.armies
                    if army["camp"] == DARKNESS)
    assert darkness in page.locator("#phase-label").inner_text()


def test_an_anonymous_visitor_is_offered_the_way_in_and_not_the_form(page, server):
    """The list is public; opening a game is not, and a form whose every control would be refused
    is worse than a single button."""
    open_the_list(page, server, logged_in=False)

    assert page.locator("#new-game").is_hidden()
    assert page.locator("#new-game-login").is_visible()
