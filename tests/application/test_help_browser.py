"""The help page in Chromium: the ways to it, and the way back.

These tests require Chromium (`make browser`). The page itself is text and is held by
`test_help.py`; what needs a browser is that the two buttons that lead to it lead to it - the link
in the list's header, and the button in the board's table dialog - and that the page leads back
to the list.
"""

import pytest

from tests.application.test_games_browser import open_a_game, open_the_list


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map and the first phase, and leaves them so."""


def test_the_list_leads_to_the_help(page, server):
    open_the_list(page, server, logged_in=False)
    page.locator("#help-link").click()
    page.wait_for_url(f"{server}/aide")
    assert "aide" in page.locator("h1").inner_text()
    assert page.locator("#credits").is_visible()


def test_the_table_dialog_leads_to_the_help(page, server):
    open_a_game(page, server)
    page.locator("#player").click()
    page.locator("#table-help").click()
    page.wait_for_url(f"{server}/aide")
    assert page.locator("#start").is_visible()


def test_the_help_leads_back_to_the_list(page, server):
    page.goto(f"{server}/aide")
    page.locator("#ways a", has_text="Les parties").click()
    page.wait_for_url(f"{server}/")
    assert page.locator("#saved").is_visible()
