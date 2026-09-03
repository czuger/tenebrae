"""The player in the page: their button, the table, the greying, and the opponent's move.

These engine require Chromium (`make browser`). They log in by unrolling the real flow - the fake
Discord client closes the authorization on our own return route - so that the browser leaves with a
session cookie just as it would have one from Discord.
"""

import pytest

from tenebrae.application import current_game
from tenebrae.application.discord_client import DEFAULT_IDENTITY

ALLIANCE, DARKNESS = "alliance", "tenebres"

# A one-pixel PNG: an avatar that really loads, without leaving the machine.
PIXEL = ("data:image/png;base64,"
         "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5E"
         "rkJggg==")

WITH_AVATAR = dict(DEFAULT_IDENTITY, avatar=PIXEL)

ORC = {"discord_id": "100000000000000002", "nickname": "Grishnak",
       "display_name": None, "avatar": None, "email": None}


@pytest.fixture(autouse=True)
def empty_table(application):
    """Every test starts from a lifted table and a fake client reset to its original account."""
    current_game.SEATS.clear()
    application.extensions["discord"].served_identity = dict(DEFAULT_IDENTITY)
    yield
    current_game.SEATS.clear()
    application.extensions["discord"].served_identity = dict(DEFAULT_IDENTITY)


def open_the_board(page, server, logged_in=True):
    """Loads the board, logged in or not, and waits for the scene to be laid out."""
    page.set_viewport_size({"width": 1400, "height": 900})
    if logged_in:
        page.goto(f"{server}/login")
    page.goto(server)
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(current_game.SCENARIO))
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def toolbar_height(page):
    return page.evaluate(
        "() => document.getElementById('toolbar').getBoundingClientRect().height")


# --- The account button --------------------------------------------------------------------------


def test_an_anonymous_visitor_is_offered_to_log_in(page, server):
    open_the_board(page, server, logged_in=False)
    assert page.locator("#player").inner_text().strip() == "Se connecter"


def test_the_button_shows_the_nickname_after_logging_in(page, server):
    open_the_board(page, server)
    assert DEFAULT_IDENTITY["nickname"] in page.locator("#player").inner_text()


def test_the_player_button_does_not_make_the_bar_grow(page, server, application):
    """The toolbar's reference size is a documented constraint (map.css).

    The account button must fit in it without lengthening it by a pixel, avatar included. It is
    this test that made the avatar be sized in `em`: at 16 px it exceeded the line height by a
    fraction of a pixel, and the whole bar gained a pixel by it.
    """
    open_the_board(page, server, logged_in=False)
    anonymous = toolbar_height(page)

    application.extensions["discord"].served_identity = dict(WITH_AVATAR)
    open_the_board(page, server)
    page.wait_for_function("document.querySelector('#player img')?.complete === true")

    assert toolbar_height(page) == anonymous


def test_a_very_long_nickname_does_not_push_the_buttons_out_of_sight(page, server, application):
    application.extensions["discord"].served_identity = dict(
        DEFAULT_IDENTITY, nickname="Vorgtd fils de Vorgtd, seigneur des salles profondes")
    open_the_board(page, server)

    bar = page.locator("#toolbar").bounding_box()
    button = page.locator("#player").bounding_box()

    assert button["x"] + button["width"] <= bar["x"] + bar["width"] + 1


# --- Taking a seat -------------------------------------------------------------------------------


def test_the_table_shows_both_armies(page, server):
    open_the_board(page, server)
    page.locator("#player").click()
    lines = page.locator("#table-seats .side")
    assert lines.count() == 2
    assert "Nains" in lines.first.inner_text() and "Orques" in lines.last.inner_text()


def test_taking_a_side_closes_the_dialog_and_hands_play_over(page, server):
    """Sitting down returns to the game: the dialog has nothing more to say, and it is our turn."""
    open_the_board(page, server)
    page.locator("#player").click()
    page.locator(f'#table-seats .side[data-side="{ALLIANCE}"] button').click()

    page.wait_for_function("() => !document.getElementById('table-dialog').open")
    page.wait_for_function("() => !document.getElementById('next-phase').disabled")
    assert current_game.SEATS.occupant(ALLIANCE) == DEFAULT_IDENTITY["discord_id"]


def test_the_side_held_reads_in_the_table(page, server):
    open_the_board(page, server)
    page.locator("#player").click()
    page.locator(f'#table-seats .side[data-side="{ALLIANCE}"] button').click()
    page.wait_for_function("() => !document.getElementById('table-dialog').open")

    page.locator("#player").click()

    line = page.locator(f'#table-seats .side[data-side="{ALLIANCE}"]')
    assert "mine" in line.get_attribute("class")
    assert "vous" in line.inner_text()


def test_a_side_already_held_is_not_offered(page, server, application, seat_the_player):
    seat_the_player(application, identity=ORC, sides=[ALLIANCE])
    open_the_board(page, server)
    page.locator("#player").click()

    line = page.locator(f'#table-seats .side[data-side="{ALLIANCE}"]')
    assert line.locator("button").count() == 0


# --- The greying ---------------------------------------------------------------------------------


def test_the_action_buttons_are_off_when_it_is_not_ones_turn(page, server):
    """The Darkness player opens the game: the first phase is the Alliance's."""
    current_game.SEATS.seat(DARKNESS, DEFAULT_IDENTITY["discord_id"])
    open_the_board(page, server)
    assert page.locator("#next-phase").is_disabled()


def test_the_action_buttons_are_on_at_ones_turn(page, server):
    current_game.SEATS.seat(ALLIANCE, DEFAULT_IDENTITY["discord_id"])
    open_the_board(page, server)
    assert page.locator("#next-phase").is_enabled()


def test_a_visitor_without_a_seat_cannot_pass_the_phase(page, server):
    open_the_board(page, server)
    assert page.locator("#next-phase").is_disabled()


def test_a_refused_move_says_so_to_the_player(page, server, deserted_map):
    """The greying covers the ordinary case; the message covers what it cannot cover.

    Here the player holds the Alliance, but play passed to the Darkness while they were thinking:
    the page does not know it yet, and their click goes out all the same.
    """
    current_game.SEATS.seat(ALLIANCE, DEFAULT_IDENTITY["discord_id"])
    open_the_board(page, server)
    current_game.TURN.advance()  # the server moves to the other side, without the page knowing
    current_game.TURN.advance()

    page.evaluate("() => document.getElementById('next-phase').disabled = false")
    page.locator("#next-phase").click()

    page.wait_for_selector("#message:not([hidden])")
    assert "de jouer" in page.locator("#message").inner_text()


# --- Following the opponent ----------------------------------------------------------------------


def test_the_opponents_move_appears_without_reloading(browser, server, application):
    """Two browsers, two sides: the one waiting sees the game advance without doing anything.

    That is what periodic polling promises, and the only way to exercise it really is to open two
    windows.
    """
    alliance = browser.new_context()
    darkness = browser.new_context()
    try:
        alliance_page = open_the_board(alliance.new_page(), server)
        alliance_page.locator("#player").click()
        alliance_page.locator(f'#table-seats .side[data-side="{ALLIANCE}"] button').click()
        # The dialog closes by itself once the seat is taken; we wait for it to be gone, without
        # which its modal backdrop would swallow the next click.
        alliance_page.wait_for_function(
            "() => !document.getElementById('table-dialog').open"
            " && !document.getElementById('next-phase').disabled")

        application.extensions["discord"].served_identity = dict(ORC)
        darkness_page = open_the_board(darkness.new_page(), server)
        label_before = darkness_page.locator("#phase-label").inner_text()

        alliance_page.locator("#next-phase").click()

        # Nothing to click on this side: the page updates by itself.
        darkness_page.wait_for_function(
            "(before) => document.getElementById('phase-label').textContent !== before",
            arg=label_before, timeout=15000)
        assert darkness_page.locator("#phase-label").inner_text() != label_before
    finally:
        alliance.close()
        darkness.close()


def test_the_seat_taken_by_the_opponent_appears_without_reloading(browser, server, application):
    dwarf = browser.new_context()
    orc = browser.new_context()
    try:
        dwarf_page = open_the_board(dwarf.new_page(), server)
        dwarf_page.locator("#player").click()
        dwarf_page.locator(f'#table-seats .side[data-side="{ALLIANCE}"] button').click()
        dwarf_page.wait_for_function(
            "() => !document.getElementById('next-phase').disabled")
        # We reopen the table: that is where the opposite seat must appear by itself.
        dwarf_page.locator("#player").click()

        application.extensions["discord"].served_identity = dict(ORC)
        orc_page = open_the_board(orc.new_page(), server)
        orc_page.locator("#player").click()
        orc_page.locator(f'#table-seats .side[data-side="{DARKNESS}"] button').click()

        # The Dwarves' page learns, all by itself, that somebody has sat down opposite.
        dwarf_page.wait_for_function(
            "() => document.querySelector('#table-seats .side[data-side=\\'tenebres\\']')"
            "?.innerText.includes('Grishnak')", timeout=15000)
    finally:
        dwarf.close()
        orc.close()


# --- Logging out ---------------------------------------------------------------------------------


def test_logging_out_brings_back_the_login_button(page, server):
    open_the_board(page, server)
    page.locator("#player").click()
    page.locator("#table-logout").click()
    page.wait_for_function(
        "() => document.getElementById('player').innerText.trim() === 'Se connecter'")
