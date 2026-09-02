"""The admin route that fixes the map's terrains, without a browser.

No test writes into `tenebrae/game_box/`: the `fixes` fixture diverts the path of the fixes file,
which belongs to the engine, to a temporary file.

The page works on the **transcribed** map - not on `MAP`, which the engine has already overlaid
with the fixes in force: that is what keeps the "original" terrain and its "Rétablir" button
correct after a restart.
"""

import json

import pytest

from tenebrae.application import app
from tenebrae.engine import hexagon as engine_hexagon
from tenebrae.engine.hexagon import TRANSCRIBED_MAP

from tests.application.test_server import read_hidden_field

# A plain hexagon, and the first woods that come along: enough to fix one into the other.
PLAIN = "1,26,-27"
OTHER_TERRAIN = "bois"


@pytest.fixture
def fixes(tmp_path, monkeypatch):
    """Diverts the fixes file, and returns its path."""
    path = tmp_path / "map_fix.json"
    monkeypatch.setattr(engine_hexagon, "FIXES_PATH", path)
    return path


def reread(path):
    """The contents of the fixes file; an empty dict if it does not exist."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fix(client, key, terrain):
    q, r, s = (int(value) for value in key.split(","))
    return client.post("/admin/map_fix", json={"q": q, "r": r, "s": s, "terrain": terrain})


# --- The page ---


def test_the_page_answers(client, fixes):
    assert client.get("/admin/map_fix").status_code == 200


def test_the_page_carries_the_whole_map(client, fixes):
    """The todo asks that the browser have everything: it must have nothing to ask to hover."""
    hexagons = read_hidden_field(client.get("/admin/map_fix").get_data(as_text=True), "hexagons")
    assert len(hexagons) == len(TRANSCRIBED_MAP)
    assert hexagons[PLAIN] == TRANSCRIBED_MAP[PLAIN][0]


def test_the_terrains_sent_are_those_of_the_map(client, fixes):
    hexagons = read_hidden_field(client.get("/admin/map_fix").get_data(as_text=True), "hexagons")
    assert set(hexagons.values()) <= set(app.TERRAINS)


def test_the_terrain_list_covers_the_map(client, fixes):
    """`TERRAINS` is the buttons' vocabulary: it must be exactly the map's."""
    terrains = read_hidden_field(client.get("/admin/map_fix").get_data(as_text=True), "terrains")
    assert set(terrains) == {elements[0] for elements in TRANSCRIBED_MAP.values()}
    assert len(terrains) == len(set(terrains))


def test_the_page_carries_the_grid_alignment(client, fixes):
    grid = read_hidden_field(client.get("/admin/map_fix").get_data(as_text=True), "grid")
    assert grid == {"origin": app.GRID_ORIGIN, "matrix": app.GRID_MATRIX}


def test_the_page_is_served_without_a_fixes_file(client, fixes):
    assert not fixes.exists()
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert read_hidden_field(page, "fixes") == {}


def test_the_page_recalls_the_fixes_already_made(client, fixes):
    fixes.write_text(json.dumps({PLAIN: OTHER_TERRAIN}), encoding="utf-8")
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert read_hidden_field(page, "fixes") == {PLAIN: OTHER_TERRAIN}


# --- The fix ---


def test_fixing_writes_the_file(client, fixes):
    answer = fix(client, PLAIN, OTHER_TERRAIN)
    assert answer.status_code == 200
    assert answer.get_json() == {"key": PLAIN, "terrain": OTHER_TERRAIN,
                                 "original": TRANSCRIBED_MAP[PLAIN][0], "fixed": True}
    assert reread(fixes) == {PLAIN: OTHER_TERRAIN}


def test_the_fixes_accumulate(client, fixes):
    fix(client, PLAIN, OTHER_TERRAIN)
    neighbour = "1,27,-28"
    fix(client, neighbour, "colline")
    assert reread(fixes) == {PLAIN: OTHER_TERRAIN, neighbour: "colline"}


def test_fixing_the_same_hexagon_twice_replaces(client, fixes):
    fix(client, PLAIN, OTHER_TERRAIN)
    fix(client, PLAIN, "colline")
    assert reread(fixes) == {PLAIN: "colline"}


def test_choosing_the_maps_terrain_removes_the_fix(client, fixes):
    fix(client, PLAIN, OTHER_TERRAIN)
    answer = fix(client, PLAIN, TRANSCRIBED_MAP[PLAIN][0])
    assert answer.get_json()["fixed"] is False
    assert reread(fixes) == {}


def test_the_transcribed_map_stays_intact(client, fixes):
    """The fixes file is separate: the transcription does not budge."""
    before = TRANSCRIBED_MAP[PLAIN]
    fix(client, PLAIN, OTHER_TERRAIN)
    assert TRANSCRIBED_MAP[PLAIN] == before


def test_the_page_shows_the_transcription_even_once_fixed(client, fixes):
    """What the page calls "the map" is the scan - otherwise nothing can be reset."""
    fix(client, PLAIN, OTHER_TERRAIN)
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert read_hidden_field(page, "hexagons")[PLAIN] == TRANSCRIBED_MAP[PLAIN][0]
    assert read_hidden_field(page, "fixes")[PLAIN] == OTHER_TERRAIN


def test_the_page_says_what_the_engine_has_already_applied(client, fixes, monkeypatch):
    """The "applied" field serves to know whether the server must be restarted."""
    monkeypatch.setattr(engine_hexagon, "APPLIED_FIXES", {PLAIN: OTHER_TERRAIN})
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert read_hidden_field(page, "applied") == {PLAIN: OTHER_TERRAIN}


def test_an_unknown_terrain_is_refused(client, fixes):
    assert fix(client, PLAIN, "marecage").status_code == 400
    assert not fixes.exists()


def test_a_missing_terrain_is_refused(client, fixes):
    assert client.post("/admin/map_fix", json={"q": 1, "r": 26, "s": -27}).status_code == 400


def test_unreadable_coordinates_are_refused(client, fixes):
    assert client.post("/admin/map_fix",
                       json={"q": 1, "r": 26, "s": 0, "terrain": "bois"}).status_code == 400
    assert client.post("/admin/map_fix", json={"terrain": "bois"}).status_code == 400


def test_a_hexagon_off_the_map_is_refused(client, fixes):
    assert fix(client, "-1,0,1", "bois").status_code == 404
