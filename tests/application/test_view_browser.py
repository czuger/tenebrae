"""Finding one's map view again on reload: what the browser reads and restores.

The map is 6173 x 5102 px and it is played zoomed in. Before, reloading the page brought one back
to the fit - the whole map in the window - and one had to redo one's zoom and find one's corner of
the front. These engine open the page, set the view, reload, and look at where one lands. What the
server makes of it is in `test_view.py`.

These engine require Chromium (`python3 -m playwright install chromium`).
"""

import time

import pytest

from tenebrae.application.discord_client import DEFAULT_IDENTITY

# The zoom is sent after half a second of quiet (`VIEW_DELAY` in `static/map.js`): these waits
# leave it some margin on a loaded machine.
PATIENCE = 5.0

# The views read either side of a reload are not pixel-exact: the point aimed at is bounded by the
# map's edge, and the scrollbars appear and disappear.
TOLERANCE = 2.0


@pytest.fixture
def views(application):
    """The view repository, emptied before and after: it lives as long as the application."""
    repository = application.extensions["view_repository"]
    repository.clear()
    yield repository
    repository.clear()


@pytest.fixture
def board(page, server, application, seat_the_player, views):
    """Opens the page logged in, and waits for the map to be laid out and the zoom mounted."""
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    wait_for_the_map(page)
    return page


def wait_for_the_map(page):
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")


def read_view(page):
    """The view the page is showing right now: its scale, its centre, its fitted state."""
    return page.evaluate(
        "() => ({ scale: view.scale(), ...view.viewedCentre(), fitted: view.followsWindow() })")


def wait_until(condition, seconds=PATIENCE):
    """Waits for a Python condition to become true - the view leaves after a period of quiet."""
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        value = condition()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("condition never met")


def stored_view(views):
    """The view the server keeps for the test player, or `None`."""
    return views.by_discord_id(DEFAULT_IDENTITY["discord_id"])


def wait_for_the_view(views, accept=None):
    """The stored view, once it is there and satisfies `accept`.

    The browser waits for a period of quiet before sending: nothing is stored yet at the moment of
    the click, and what is stored may date from the previous gesture.
    """
    def ready():
        view = stored_view(views)
        return view if view and (accept is None or accept(view)) else None
    return wait_until(ready)


def zoom_in(page, notches=3):
    """Zooms the map in by a few notches of the "+" button."""
    for _ in range(notches):
        page.locator("#zoom-in").click()


# --- What the browser stores ----------------------------------------------------------------------

def test_the_map_opens_fitted_when_nothing_is_stored(board):
    assert read_view(board)["fitted"] is True


def test_zooming_in_stores_the_view(board, views):
    """We wait for the view the **zoom** produced, and not simply for the first one stored.

    A player who has nothing stored yet opens on the fit, and that fit is a scroll like any other:
    it is sent after its half-second of quiet. Taking the first view that arrives would therefore
    read that one, still fitted, and the zoom would be tested by nothing - the same precaution as
    in `test_scrolling_stores_the_view` just below.
    """
    zoom_in(board)
    stored = wait_for_the_view(views, lambda view: not view["fitted"])
    shown = read_view(board)
    assert stored["fitted"] is False
    assert stored["scale"] == pytest.approx(shown["scale"])
    assert (stored["x"], stored["y"]) == pytest.approx((shown["x"], shown["y"]), abs=TOLERANCE)


def test_scrolling_stores_the_view(board, views):
    """Scrolling does not go through the zoom: it is watched separately."""
    zoom_in(board)
    first = wait_for_the_view(views)
    board.evaluate("() => document.getElementById('frame').scrollBy(600, 400)")
    moved = wait_for_the_view(views, lambda view: view["x"] != first["x"])
    assert (moved["x"], moved["y"]) == pytest.approx(
        (read_view(board)["x"], read_view(board)["y"]), abs=TOLERANCE)


def test_an_anonymous_visitor_stores_nothing(page, server, views):
    """The map is public, but a passing visitor has nowhere to store it."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/")
    wait_for_the_map(page)
    zoom_in(page)
    page.wait_for_timeout(int(PATIENCE * 200))
    assert stored_view(views) is None


# --- What a reload finds again --------------------------------------------------------------------

def test_the_zoom_and_the_position_survive_a_reload(board, server, views):
    """That is the requirement: reloading the map must no longer undo everything."""
    zoom_in(board)
    zoomed = wait_for_the_view(views, lambda view: not view["fitted"])
    # The scroll is awaited separately: without that, the stored view might be only the zoom's,
    # and the reload would land right without the scroll having anything to do with it.
    board.evaluate("() => document.getElementById('frame').scrollBy(500, 300)")
    before = wait_for_the_view(views, lambda view: view["x"] != zoomed["x"])

    board.goto(f"{server}/")
    wait_for_the_map(board)

    after = read_view(board)
    assert after["scale"] == pytest.approx(before["scale"])
    assert (after["x"], after["y"]) == pytest.approx((before["x"], before["y"]), abs=TOLERANCE)
    assert after["fitted"] is False


def test_a_fitted_view_is_found_fitted_again(board, server, views):
    """A map set to the window freezes no scale: the next window finds its own, instead of
    inheriting another screen's zoom."""
    zoom_in(board)
    wait_for_the_view(views, lambda view: not view["fitted"])
    board.locator("#fit").click()
    wait_for_the_view(views, lambda view: view["fitted"])

    board.set_viewport_size({"width": 900, "height": 700})
    board.goto(f"{server}/")
    wait_for_the_map(board)

    after = read_view(board)
    assert after["fitted"] is True
    fit = board.evaluate("""() => {
        const map = document.getElementById('map');
        return Math.min(window.innerWidth / map.naturalWidth,
                        window.innerHeight / map.naturalHeight);
    }""")
    assert after["scale"] == pytest.approx(fit)
