"""The landing page in Chromium: the cards, the way into a game, and the form that opens one.

These tests require Chromium (`make browser`). Logging in unrolls the real flow - the fake Discord
client closes the authorization on our own return route - and it lands here, on the list, which is
where one now chooses what to play.

The last of them is the one that could not be written before: the server plays one game at a time
and several have an address, so a tab whose game has been opened elsewhere is watching a board that
is no longer its own. It is told, and it stops following.
"""

import pytest

from tenebrae.application import current_game
from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.engine.models.game import Game

ALLIANCE, DARKNESS = "alliance", "tenebres"
GRISHNAK = DEFAULT_IDENTITY | {"discord_id": "100000000000000002", "nickname": "Grishnak"}


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map and the first phase, and leaves them so."""


def open_the_list(page, server, logged_in=True):
    """Loads the list of games, logged in or not, and waits for it to have laid itself out."""
    page.set_viewport_size({"width": 1400, "height": 900})
    if logged_in:
        page.goto(f"{server}/login")  # the login lands on the list
    else:
        page.goto(server)
    page.wait_for_selector("#saved")
    return page


def open_a_game(page, server, side=ALLIANCE):
    """Fills the form and follows it to the board of the game it opens."""
    open_the_list(page, server)
    page.select_option("#new-side", side)
    page.click("#new-game-submit")
    page.wait_for_url(f"{server}/game/*")
    wait_for_the_board(page)
    return page


def wait_for_the_board(page):
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    page.wait_for_function("document.querySelectorAll('img.piece').length > 0")


def cards(page):
    """The cards on screen, by the identifier each one carries."""
    return {card.get_attribute("data-game"): card
            for card in page.locator("#game-list > *").all()}


# --- The account corner ---------------------------------------------------------------------------


def test_a_connected_player_is_never_asked_to_log_in_again(page, server):
    """The way out, and nothing offering the way in: the whole page has one connection control."""
    open_the_list(page, server)

    assert page.locator("#account-logout").is_visible()
    assert DEFAULT_IDENTITY["nickname"] in page.locator("#account").inner_text()
    assert page.locator("#new-game-login").is_hidden()
    assert page.locator("#no-account").is_hidden()


def test_the_way_in_takes_the_place_of_the_way_out(page, server):
    """One corner of the header, one control: `Se connecter` where `Se déconnecter` stands for a
    player, and never the two at once."""
    open_the_list(page, server, logged_in=False)

    assert page.locator("#account #new-game-login").is_visible()
    assert page.locator("#account-logout").is_hidden()
    # And in place of the form, the reason there is none.
    assert page.locator("#new-game").is_hidden()
    assert page.locator("#no-account").is_visible()


def test_logging_out_leaves_the_way_in_where_the_way_out_was(page, server):
    open_the_list(page, server)
    page.locator("#account-logout").click()

    page.wait_for_selector("#new-game-login:not([hidden])")
    assert page.locator("#account-logout").is_hidden()
    assert page.locator("#new-game").is_hidden()


def test_an_empty_base_says_so_rather_than_showing_nothing(page, server):
    open_the_list(page, server)
    assert page.locator("#no-game").is_visible()
    assert Game.objects.count() == 0


def test_the_saved_games_are_listed_with_their_scenario(page, server):
    open_a_game(page, server)
    open_the_list(page, server)

    card, = page.locator("#game-list > *").all()
    assert current_game.SCENARIO.name in card.inner_text()
    assert "Tour 1" in card.inner_text()
    assert current_game.TURN.army_of(ALLIANCE) in card.inner_text()


def test_a_card_opens_its_own_game(page, server):
    first = open_a_game(page, server).url.rsplit("/", 1)[1]
    open_a_game(page, server)
    open_the_list(page, server)

    cards(page)[first].click()
    page.wait_for_url(f"{server}/game/{first}")
    wait_for_the_board(page)
    assert current_game.GAME_ID == first


def test_only_the_games_one_holds_a_side_in_are_marked(page, server, application):
    mine = open_a_game(page, server).url.rsplit("/", 1)[1]
    someone_elses = open_a_game(page, server).url.rsplit("/", 1)[1]
    current_game.SEATS.restore({ALLIANCE: GRISHNAK["discord_id"]})
    with application.app_context():
        current_game.save_the_game()

    open_the_list(page, server)
    on_screen = cards(page)
    assert "mine" in on_screen[mine].get_attribute("class")
    assert "mine" not in on_screen[someone_elses].get_attribute("class")


def test_the_form_opens_a_game_and_seats_its_creator(page, server):
    open_a_game(page, server, side=DARKNESS)

    assert current_game.SEATS.occupant(DARKNESS) == DEFAULT_IDENTITY["discord_id"]
    assert current_game.SEATS.occupant(ALLIANCE) is None
    # And the board one lands on says which side that is.
    page.locator("#player").click()
    assert "(vous)" in page.locator(f"#table-seats .side[data-side='{DARKNESS}']").inner_text()


def test_the_board_carries_the_way_back_to_the_list(page, server):
    open_a_game(page, server)
    page.locator("#player").click()
    page.locator("#table-games").click()
    page.wait_for_url(f"{server}/")
    assert page.locator("#saved").is_visible()


def test_the_dialog_no_longer_opens_a_game(page, server):
    """The set-up and the machine are chosen on the list now: what is left in the dialog is what
    belongs to the game one is at."""
    open_a_game(page, server)
    page.locator("#player").click()
    assert page.locator("#table-scenario").count() == 0
    assert page.locator("#table-against-ai").count() == 0


def test_a_tab_whose_game_has_been_opened_elsewhere_is_told(page, context, server):
    """One process, one game, several addresses: the tab left behind must not go on showing a
    board that is somebody else's. It says so and stops following - it does not reload onto its
    own game, which would take the table back and have the two tabs pulling at it forever."""
    watching = open_a_game(page, server)
    watched = watching.url.rsplit("/", 1)[1]

    elsewhere = context.new_page()
    open_a_game(elsewhere, server, side=DARKNESS)
    assert current_game.GAME_ID != watched

    watching.wait_for_selector("#displaced:not([hidden])")
    assert "Une autre partie" in watching.locator("#displaced").inner_text()
