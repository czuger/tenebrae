"""The map-fixing page in the browser: hovering, dialog, zoom.

These engine require Chromium (`python3 -m playwright install chromium`). Like the client ones, they
divert the path of the fixes file: nothing is written into `tenebrae/game_box/`.
"""

import json

import pytest

from tenebrae.application import app
from tenebrae.engine import hexagon as engine_hexagon
from tenebrae.engine.hexagon import TRANSCRIBED_MAP, Hex

from tests.application.test_board_browser import click_the_hexagon, point_of_the_hexagon
from tests.application.test_map_fix import fixes, reread  # noqa: F401  (fixture reused)

# A plain hexagon, far from the edges, and the terrain it will be given.
PLAIN = Hex.from_key("10,20,-30")
FIX = "colline"


@pytest.fixture
def fixing_page(page, server, fixes, monkeypatch, application,
                seat_the_player):  # noqa: F811
    """Opens /admin/map_fix and waits for the map to be loaded and scaled.

    The engine is presented as having started with no fixes, so as to start from a consistent page:
    no fix recorded, and none in force.
    """
    monkeypatch.setattr(engine_hexagon, "APPLIED_FIXES", {})
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    # The admin page is reserved to declared accounts: we log in first.
    page.goto(f"{server}/login")
    page.goto(f"{server}/admin/map_fix")
    page.wait_for_function(
        "() => { const m = document.getElementById('map');"
        " return m.complete && m.naturalWidth > 0; }")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def hover(page, hexagon):
    """Brings the pointer to the centre of the hexagon."""
    page.mouse.move(*point_of_the_hexagon(page, hexagon))


def test_the_map_fits_in_the_window(fixing_page):
    measurements = fixing_page.evaluate("""() => {
        const map = document.getElementById('map');
        return { width: map.getBoundingClientRect().width,
                 natural: map.naturalWidth,
                 height: map.getBoundingClientRect().height };
    }""")
    assert measurements["width"] <= 1400 + 1
    assert measurements["height"] <= 900 + 1
    assert measurements["width"] < measurements["natural"]


def test_hovering_states_the_terrain(fixing_page):
    hover(fixing_page, PLAIN)
    tooltip = fixing_page.locator("#tooltip")
    tooltip.wait_for(state="visible")
    assert tooltip.text_content() == f"{PLAIN.key} — {TRANSCRIBED_MAP[PLAIN.key][0]}"


def test_hovering_highlights_the_hexagon(fixing_page):
    hover(fixing_page, PLAIN)
    fixing_page.wait_for_function(
        "document.querySelectorAll('#highlight .aimed').length === 1")


def test_clicking_opens_the_dialog(fixing_page):
    click_the_hexagon(fixing_page, PLAIN)
    fixing_page.locator("#choice[open]").wait_for()
    assert fixing_page.locator("#choice-title").text_content() == f"Hexagone {PLAIN.key}"
    assert TRANSCRIBED_MAP[PLAIN.key][0] in fixing_page.locator("#choice-state").text_content()
    assert fixing_page.locator("#choice-terrains button").count() == len(app.TERRAINS)


def test_choosing_a_terrain_records_the_fix(fixing_page, fixes):  # noqa: F811
    click_the_hexagon(fixing_page, PLAIN)
    fixing_page.locator("#choice[open]").wait_for()
    fixing_page.locator(f"#choice-terrains button:text-is('{FIX}')").click()

    fixing_page.wait_for_function(
        "document.getElementById('counter').textContent === '1 correction'")
    assert reread(fixes) == {PLAIN.key: FIX}
    assert fixing_page.locator("#highlight .fixed").count() == 1


def test_resetting_erases_the_fix(fixing_page, fixes):  # noqa: F811
    click_the_hexagon(fixing_page, PLAIN)
    fixing_page.locator("#choice[open]").wait_for()
    fixing_page.locator(f"#choice-terrains button:text-is('{FIX}')").click()
    fixing_page.wait_for_function(
        "document.getElementById('counter').textContent === '1 correction'")

    click_the_hexagon(fixing_page, PLAIN)
    fixing_page.locator("#choice[open]").wait_for()
    fixing_page.locator("#choice-reset").click()

    fixing_page.wait_for_function(
        "document.getElementById('counter').textContent === 'aucune correction'")
    assert reread(fixes) == {}


def test_the_fix_survives_a_reload(fixing_page, fixes):  # noqa: F811
    fixes.write_text(json.dumps({PLAIN.key: FIX}), encoding="utf-8")
    fixing_page.reload()
    fixing_page.wait_for_function(
        "document.getElementById('counter').textContent === '1 correction'")
    assert fixing_page.locator("#highlight .fixed").count() == 1


def test_the_zoom_buttons_change_the_scale(fixing_page):
    scale = fixing_page.locator("#scale")
    fitted = scale.text_content()
    fixing_page.locator("#zoom-in").click()
    fixing_page.wait_for_function(
        "(start) => document.getElementById('scale').textContent !== start", arg=fitted)
    fixing_page.locator("#fit").click()
    fixing_page.wait_for_function(
        "(start) => document.getElementById('scale').textContent === start", arg=fitted)


def test_the_restart_is_announced_after_a_fix(fixing_page):
    """The engine only rereads map_fix.json at start-up: the page must say so."""
    restart = fixing_page.locator("#restart")
    assert restart.is_hidden()

    click_the_hexagon(fixing_page, PLAIN)
    fixing_page.locator("#choice[open]").wait_for()
    fixing_page.locator(f"#choice-terrains button:text-is('{FIX}')").click()
    restart.wait_for(state="visible")

    # Going back to the transcribed terrain brings the page back in step with the engine.
    click_the_hexagon(fixing_page, PLAIN)
    fixing_page.locator("#choice[open]").wait_for()
    fixing_page.locator("#choice-reset").click()
    restart.wait_for(state="hidden")
