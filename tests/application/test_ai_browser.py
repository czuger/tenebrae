"""The game against the AI, seen from the browser: the dialog button, the "IA" seat, the opening.

These engine require Chromium (`make browser`). As everywhere, logging in unrolls the real flow: the
fake Discord client closes the authorization on our own return route.
"""

import pytest

import app
from discord_client import DEFAULT_IDENTITY
from tenebrae.engine import ai

ALLIANCE, DARKNESS = "alliance", "tenebres"


@pytest.fixture(autouse=True)
def empty_table(application):
    """Every test starts from a lifted table; the board lays itself out again at every load."""
    app.SEATS.clear()
    yield
    app.SEATS.clear()


def open_the_board(page, server, logged_in=True):
    """Loads the board, logged in or not, and waits for the scene to be laid out."""
    page.set_viewport_size({"width": 1400, "height": 900})
    if logged_in:
        page.goto(f"{server}/login")
    page.goto(server)
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(app.SCENARIO))
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def click_the_against_ai_button(page):
    """Opens the table, clicks "Nouvelle partie contre l'IA", waits for the dialog to close.

    The dialog only closes on the server's answer: waiting for it closed means waiting for the
    fresh game - and the AI's possible opening turn - to have been played.
    """
    page.locator("#player").click()
    page.locator("#table-against-ai").click()
    page.wait_for_function("!document.getElementById('table-dialog').open")


def test_a_player_without_a_seat_does_not_see_the_button(page, server):
    open_the_board(page, server)
    page.locator("#player").click()
    assert page.locator("#table-against-ai").is_hidden()


def test_the_button_entrusts_the_opposing_side_to_the_ai(page, server):
    open_the_board(page, server)
    # Sit down at the Alliance through the dialog, as a player would.
    page.locator("#player").click()
    page.locator(f"#table-seats .side[data-side='{ALLIANCE}'] button").click()
    page.wait_for_function("!document.getElementById('table-dialog').open")

    click_the_against_ai_button(page)

    assert app.SEATS.occupant(DARKNESS) == ai.AI_PLAYER
    # The table reopened shows the seat occupied by "IA".
    page.locator("#player").click()
    assert ai.AI_NAME in page.locator(f"#table-seats .side[data-side='{DARKNESS}']").inner_text()


def test_the_ai_opens_the_scenario_when_it_holds_the_alliance(page, server):
    app.SEATS.seat(DARKNESS, DEFAULT_IDENTITY["discord_id"])
    open_the_board(page, server)

    click_the_against_ai_button(page)

    # The AI got the Alliance, played its opening turn, and handed play back to the Darkness.
    assert app.SEATS.occupant(ALLIANCE) == ai.AI_PLAYER
    assert (app.TURN.active_side, app.TURN.phase_type) == (DARKNESS, "mouvement")
    assert app.BOARD.to_dict() != app.SCENARIO.placement
    # And the page shows it: the phase displayed is the human player's.
    assert "Orques" in page.locator("#phase-label").inner_text()
