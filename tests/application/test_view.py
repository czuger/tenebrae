"""The map view: what the server keeps of it, and what it returns at the next load.

The map is 6173 x 5102 px and it is played zoomed in: every reload brought the player back to the
fit, the whole map inside the window. The server therefore keeps, per player, the scale and the
point they had at the centre (`tenebrae/application/models/view.py`).

What happens in the browser - reading the view, restoring it - is in `test_view_browser.py`; what
MongoDB makes of it, in `test_persistence.py`.
"""

import pytest

from tenebrae.application import app

from tests.application.test_server import read_hidden_field

# A second account, to exercise that a view belongs to one pair of eyes only.
OTHER_IDENTITY = {"discord_id": "100000000000000002", "nickname": "Adversaire", "avatar": None,
                  "display_name": None, "email": None}

A_VIEW = {"scale": 0.42, "x": 1234.5, "y": 678.25, "fitted": False}


@pytest.fixture(autouse=True)
def empty_views(application):
    """The view repository lives as long as the application, which the suite builds only once:
    without this cleanup, every test would inherit the previous one's views."""
    application.extensions["view_repository"].clear()
    yield application.extensions["view_repository"]
    application.extensions["view_repository"].clear()


def page_view(client):
    return read_hidden_field(client.get("/").get_data(as_text=True), "view")


# --- What the page carries -----------------------------------------------------------------------

def test_the_page_has_no_view_to_return_to_whoever_stored_none(anonymous_client, client):
    """A passing visitor has nowhere to store one, and a player who has not moved has none: the
    map opens fitted in both cases."""
    assert page_view(anonymous_client) is None
    assert page_view(client) is None


def test_the_page_returns_the_adjusted_view(client):
    """The route hands it straight back too, so the browser knows what was kept."""
    answer = client.post("/view", json=A_VIEW)
    assert answer.status_code == 200
    assert answer.json == A_VIEW
    assert page_view(client) == A_VIEW


# --- What the route accepts ----------------------------------------------------------------------


def test_an_anonymous_visitor_can_store_nothing(anonymous_client):
    answer = anonymous_client.post("/view", json=A_VIEW)
    assert answer.status_code == 401
    assert answer.json["allowed"] is False


def test_a_seat_is_not_required(application, anonymous_client, seat_the_player):
    """We keep the view of a logged-in spectator as of a seated player."""
    seat_the_player(application, anonymous_client, sides=[])
    assert anonymous_client.post("/view", json=A_VIEW).status_code == 200


@pytest.mark.parametrize("body", [
    {},                                                  # nothing
    {"scale": 0.4, "x": 10},                             # a field is missing
    {"scale": "a lot", "x": 10, "y": 20},                # not a number
    {"scale": float("inf"), "x": 10, "y": 20},           # not a finite number
    {"scale": float("nan"), "x": 10, "y": 20},
    [1, 2, 3],                                           # not even an object
])
def test_an_unreadable_view_is_refused(client, body):
    """The body comes from outside: we take from it only what we expect."""
    assert client.post("/view", json=body).status_code == 400


def test_the_fitted_flag_is_a_boolean_and_needs_no_value(client):
    """Absent, it counts as "no": a view stored without saying so is not a fit."""
    assert client.post("/view", json={"scale": 0.4, "x": 10, "y": 20}).json["fitted"] is False
    assert client.post("/view", json={**A_VIEW, "fitted": 1}).json["fitted"] is True


def test_integers_are_admitted_and_stored_as_numbers(client):
    """The browser sometimes sends round integers: they must not be refused."""
    assert client.post("/view", json={"scale": 1, "x": 0, "y": 0}).json \
        == {"scale": 1.0, "x": 0.0, "y": 0.0, "fitted": False}


# --- Whom it belongs to --------------------------------------------------------------------------

def test_each_player_has_their_own(application, client, anonymous_client, seat_the_player):
    """Two players in front of the same game are not looking at the same corner of the map."""
    other = application.test_client()
    seat_the_player(application, other, identity=OTHER_IDENTITY, sides=[])
    client.post("/view", json=A_VIEW)
    other_view = {"scale": 1.0, "x": 10.0, "y": 20.0, "fitted": False}
    other.post("/view", json=other_view)
    assert page_view(client) == A_VIEW
    assert page_view(other) == other_view


def test_adjusting_twice_overwrites_the_previous_one(client):
    """No zoom history is kept: one document per player."""
    client.post("/view", json=A_VIEW)
    last = {"scale": 0.1, "x": 1.0, "y": 2.0, "fitted": True}
    client.post("/view", json=last)
    assert page_view(client) == last


# --- What it is not ------------------------------------------------------------------------------

def test_adjusting_ones_view_is_not_a_move_played(client):
    """Neither does the version rise, nor is anything pushed to the streams: one player's view must
    not make the other's map jump."""
    client.get("/")
    subscriber = app.BROADCASTER.subscribe()
    try:
        version = app.VERSION
        assert client.post("/view", json=A_VIEW).status_code == 200
        assert app.VERSION == version
        assert subscriber.wait(0) is None
    finally:
        app.BROADCASTER.unsubscribe(subscriber)


def test_the_view_does_not_travel_with_the_game(client):
    """`/game/state` says what **all** spectators have in common; the view is not part of it."""
    client.post("/view", json=A_VIEW)
    assert "view" not in client.get("/game/state").json
    assert "view" not in app.shared_snapshot()
