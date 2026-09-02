"""What the server sends: the scenario's set-up and the files from the game box."""

import json
import re

import pytest

import app
from engine.board import MAXIMUM_TILT
from engine.hexagon import DEFAULT_MOVEMENT, MAP, Hex
from engine.piece import ALLIANCE, CATALOGUE, DARKNESS


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map, and leaves it deserted.

    The server's board survives from one request to the next: without this cleanup, the
    scenario's forty-eight units would stay under the next test's feet. Tests that want a
    populated board load "/" themselves.
    """


def read_hidden_field(page, identifier):
    """Returns the JSON carried by the hidden field `identifier`."""
    tag = re.search(rf'<input type="hidden" id="{identifier}" value="([^"]*)">', page)
    assert tag, f"hidden field \"{identifier}\" missing from the page"
    contents = (tag.group(1)
                .replace("&#34;", '"').replace("&lt;", "<").replace("&gt;", ">")
                .replace("&#39;", "'").replace("&amp;", "&"))
    return json.loads(contents)


def test_the_page_answers(client):
    answer = client.get("/")
    assert answer.status_code == 200


def test_the_page_carries_both_armies_of_the_scenario(client):
    """Scenario no. 4 puts 18 dwarves against 30 orcs: the page carries them all."""
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    assert len(pieces) == len(app.SCENARIO) == 48
    sides = [piece["side"] for piece in pieces]
    assert sides.count(ALLIANCE) == 18
    assert sides.count(DARKNESS) == 30


def test_the_page_places_each_piece_on_the_scenarios_square(client):
    """The server invents nothing: it serves the placement fixed in `scenarios/`."""
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    placed = {f"{piece['q']},{piece['r']},{piece['s']}": piece["key"] for piece in pieces}
    assert placed == app.SCENARIO.placement


def test_the_pieces_are_on_distinct_hexagons(client):
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    positions = {(piece["q"], piece["r"], piece["s"]) for piece in pieces}
    assert len(positions) == len(pieces)


def test_the_coordinates_are_cubic(client):
    """A grid hexagon satisfies q + r + s = 0 and appears on the map."""
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    for piece in pieces:
        assert piece["q"] + piece["r"] + piece["s"] == 0
        assert f"{piece['q']},{piece['r']},{piece['s']}" in MAP


def test_each_placed_piece_carries_its_movement(client):
    """The set-up says which piece is placed and how many points it has."""
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    for piece in pieces:
        assert piece["key"] in CATALOGUE
        assert piece["movement"] == CATALOGUE[piece["key"]].movement_points


def test_each_placed_piece_carries_its_side(client):
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    for piece in pieces:
        assert piece["side"] == CATALOGUE[piece["key"]].side


def test_each_placed_piece_carries_its_tilt(client):
    """The angle the counter lies at goes out with the piece: the browser does not draw one.

    It is the server that draws it, when placing, and that keeps it - without which the piece
    would lie down differently every time the page lays the scene out again.
    """
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    for piece in pieces:
        assert isinstance(piece["tilt"], float)
        assert abs(piece["tilt"]) <= MAXIMUM_TILT


def test_each_placed_piece_carries_its_counter_values(client):
    """The hover card is read from the hidden field: the whole counter must be in it.

    Values absent from the counter go out as `None` - it is the browser that renders them as a
    dash. `movement`, for its part, stays the movement budget, the one the engine uses, and not
    the raw value that `pions.json` sometimes leaves empty.
    """
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    for piece in pieces:
        placed = CATALOGUE[piece["key"]]
        assert piece["faction"] == placed.faction
        assert piece["symbol"] == placed.symbol
        assert piece["strength"] == placed.strength
        assert piece["fire"] == placed.fire
        assert piece["range"] == placed.range
        assert piece["flight_movement"] == placed.flight_movement
        assert piece["special_abilities"] == placed.special_abilities
        assert piece["remarks"] == placed.remarks
        assert piece["movement"] == placed.movement_points


def test_the_counter_values_are_those_read_off_the_photographs(client):
    """Two pieces from the scenario, recorded in `game_box/pions/pions.json`."""
    pieces = {piece["key"]: piece
              for piece in read_hidden_field(client.get("/").get_data(as_text=True), "pieces")}

    leaders = pieces["nains-05-2-leaders"]
    assert (leaders["strength"], leaders["fire"], leaders["range"]) == (25, 5, 10)
    assert leaders["symbol"] == "leader"

    infantry = pieces["orques-01-15-infanteries"]
    assert infantry["symbol"] == "infanterie"
    assert (infantry["fire"], infantry["range"], infantry["flight_movement"]) == (None, None, None)


def test_the_set_up_populates_the_servers_board(client):
    """The server keeps what it has placed: that is where the zones of control come from."""
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    assert len(app.BOARD) == len(pieces)
    for piece in pieces:
        placed = app.BOARD.piece_on(Hex(piece["q"], piece["r"], piece["s"]))
        assert placed is not None and placed.key == piece["key"]


def test_reloading_the_page_puts_the_pieces_back(client):
    """A moved piece returns to its starting square on reload: the set-up is fixed."""
    origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
    client.get("/")
    destination = app.BOARD.moves(origin)[0]
    assert app.BOARD.move(origin, destination)

    client.get("/")
    assert app.BOARD.piece_on(destination) is None
    assert app.BOARD.pieces.keys() == app.SCENARIO.placement.keys()


def test_the_catalogues_movements_are_those_of_the_counters():
    for piece in app.PIECE_CATALOGUE:
        assert piece["movement"] == CATALOGUE[piece["key"]].movement_points
    movements = {piece["key"]: piece["movement"] for piece in app.PIECE_CATALOGUE}
    assert movements["reissland-02-8-cavaleries"] == 8       # cavalry goes far
    assert movements["yzent-05-1-belier"] == 2               # the ram drags itself along
    assert movements["marqueurs-03-paralysie"] == 0          # a marker does not move


def test_the_piece_images_exist(client):
    pieces = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    for piece in pieces:
        assert client.get(f"/pieces/{piece['image']}").status_code == 200


def test_the_grid_alignment_is_transmitted(client):
    grid = read_hidden_field(client.get("/").get_data(as_text=True), "grid")
    assert grid["origin"] == app.GRID_ORIGIN
    assert grid["matrix"] == app.GRID_MATRIX
    assert grid["piece_size"] == app.PIECE_SIZE


def test_the_set_up_does_not_change_from_one_load_to_the_next(client):
    """A fixed scenario replays identically: that is what is asked of it.

    The tilt is set aside: it belongs not to the scenario but to the placing, and without
    persistence - the test configuration - every load of "/" rebuilds the set-up, hence drops the
    counters onto the map again. A saved game, for its part, finds them as it left them (see
    `test_persistence.py`).
    """
    first = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    second = read_hidden_field(client.get("/").get_data(as_text=True), "pieces")
    assert without_tilt(first) == without_tilt(second)


def without_tilt(pieces):
    """The pieces served, minus the placing angle."""
    return [{field: value for field, value in piece.items() if field != "tilt"}
            for piece in pieces]


def test_the_map_is_served(client):
    answer = client.get("/map.jpg")
    assert answer.status_code == 200
    assert answer.headers["Content-Type"] == "image/jpeg"


def test_the_overviews_are_not_served(client):
    """Whole sheets and record sheets are not pieces: neither served nor placed."""
    for path in ("21-vues-d-ensemble/vues-d-ensemble-01-planches-de-pions.jpg",
                 "19-magiciens/magiciens-02-pions-de-magiciens-et-clercs-vue-d-ensemble.jpg"):
        assert (app.PIECES / path).exists()
        assert client.get(f"/pieces/{path}").status_code == 404
        assert path not in [piece["path"] for piece in app.PIECE_CATALOGUE]


def test_the_catalogue_covers_the_pieces_of_the_box():
    """127 photographs in game_box/pions, minus the 4 sheets and the 2 record sheets."""
    assert len(app.PIECE_CATALOGUE) == 121
    assert all((app.PIECES / piece["path"]).exists() for piece in app.PIECE_CATALOGUE)


def test_the_piece_names_are_readable():
    names = {piece["path"]: piece["name"] for piece in app.PIECE_CATALOGUE}
    assert names["01-yzent/yzent-05-1-belier.jpg"] == "yzent · 1 belier"
    assert names["06-empire-de-lynn/empire-de-lynn-08-3-chars-legers.jpg"] == (
        "empire de lynn · 3 chars legers"
    )


def test_one_does_not_escape_the_pieces_directory(client):
    assert client.get("/pieces/../../CLAUDE.md").status_code == 404


# --- Moves ---------------------------------------------------------------------------------------

PLAIN = {"q": 1, "r": 26, "s": -27}
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}
DISTANT = {"q": 30, "r": 2, "s": -32}


SLOW = "yzent-05-1-belier"            # 2 points
FAST = "reissland-02-8-cavaleries"    # 8 points
MARKER = "marqueurs-03-paralysie"     # motionless


def test_the_moves_describe_the_origin(client):
    answer = client.get("/moves", query_string=PLAIN).json
    assert answer["origin"] == {**PLAIN, "terrain": "plaine"}
    assert answer["movement"] == DEFAULT_MOVEMENT == 5
    assert answer["piece"] is None


def test_the_moves_are_the_engines(client):
    """The route adds no rule: it exposes Hex.moves()."""
    expected = {(h.q, h.r, h.s) for h in Hex(**PLAIN).moves()}
    returned = {(h["q"], h["r"], h["s"])
                for h in client.get("/moves", query_string=PLAIN).json["hexagons"]}
    assert returned == expected and returned


def test_the_returned_hexagons_carry_their_terrain(client):
    for hexagon in client.get("/moves", query_string=PLAIN).json["hexagons"]:
        assert hexagon["q"] + hexagon["r"] + hexagon["s"] == 0
        assert hexagon["terrain"] == MAP[f"{hexagon['q']},{hexagon['r']},{hexagon['s']}"][0]


def test_the_origin_is_not_among_its_own_moves(client):
    hexagons = client.get("/moves", query_string=PLAIN).json["hexagons"]
    assert PLAIN not in [{"q": h["q"], "r": h["r"], "s": h["s"]} for h in hexagons]


def test_the_movement_is_that_of_the_piece(client):
    """The piece in hand gives the budget: the counter's, not the flat rate."""
    for key, expected in ((SLOW, 2), (FAST, 8), (MARKER, 0)):
        answer = client.get("/moves", query_string={**PLAIN, "piece": key}).json
        assert answer["piece"] == key
        assert answer["movement"] == expected
        assert len(answer["hexagons"]) == len(Hex(**PLAIN).moves(expected))


def test_the_slow_piece_goes_less_far_than_the_fast_one(client):
    slow = client.get("/moves", query_string={**PLAIN, "piece": SLOW}).json
    fast = client.get("/moves", query_string={**PLAIN, "piece": FAST}).json
    reached = {(h["q"], h["r"], h["s"]) for h in slow["hexagons"]}
    assert 0 < len(reached) < len(fast["hexagons"])
    assert reached < {(h["q"], h["r"], h["s"]) for h in fast["hexagons"]}


def test_a_marker_goes_nowhere(client):
    answer = client.get("/moves", query_string={**PLAIN, "piece": MARKER}).json
    assert answer["hexagons"] == []


def test_an_unknown_piece_is_refused(client):
    """Movement comes from the catalogue: a piece that is not in it has no reach."""
    assert client.get("/moves",
                      query_string={**PLAIN, "piece": "invented-piece"}).status_code == 400
    assert client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR,
                                      "piece": "invented-piece"}).status_code == 400


def test_the_movement_cannot_be_asked_for(client):
    """The browser transmits only a key: a budget in the request has no effect."""
    answer = client.get("/moves",
                        query_string={**PLAIN, "piece": SLOW, "movement": 99}).json
    assert answer["movement"] == 2


# --- Zones of control ----------------------------------------------------------------------------

ELF = "elfes-01-5-infanteries"         # alliance, 4 points
ORC = "orques-01-15-infanteries"       # darkness, 4 points


def place(hexagon, key):
    """Places a piece on the server's board, as a layout would."""
    app.BOARD.place(Hex(**hexagon), CATALOGUE[key])


def test_the_placed_piece_prevails(client):
    """The occupied square decides: the piece named in the request does not replace it."""
    place(PLAIN, ELF)
    answer = client.get("/moves", query_string={**PLAIN, "piece": SLOW}).json
    assert (answer["piece"], answer["side"], answer["movement"]) == (ELF, ALLIANCE, 4)


def test_an_empty_square_lets_itself_be_queried(client):
    answer = client.get("/moves", query_string={**PLAIN, "piece": SLOW}).json
    assert (answer["piece"], answer["side"], answer["movement"]) == (SLOW, DARKNESS, 2)


def test_a_nearby_opponent_reduces_the_reach(client):
    place(PLAIN, ELF)
    alone = client.get("/moves", query_string=PLAIN).json["hexagons"]
    place(NEIGHBOUR, ORC)
    hindered = client.get("/moves", query_string=PLAIN).json["hexagons"]
    assert 0 < len(hindered) < len(alone)


def test_one_does_not_go_onto_an_opponents_square(client):
    place(PLAIN, ELF)
    place(NEIGHBOUR, ORC)
    hexagons = client.get("/moves", query_string=PLAIN).json["hexagons"]
    assert NEIGHBOUR not in [{"q": h["q"], "r": h["r"], "s": h["s"]} for h in hexagons]
    assert client.post("/move",
                       json={"origin": PLAIN, "destination": NEIGHBOUR}).json["allowed"] is False


def test_a_friend_does_not_reduce_the_reach(client):
    """Two pieces of the same side do not hinder each other: only their square is taken."""
    place(PLAIN, ELF)
    alone = client.get("/moves", query_string=PLAIN).json["hexagons"]
    place(NEIGHBOUR, "nains-01-5-infanteries")
    with_the_friend = client.get("/moves", query_string=PLAIN).json["hexagons"]
    assert len(with_the_friend) == len(alone) - 1


def test_an_accepted_move_changes_the_board(client):
    """The piece really leaves its square: the next move's zones take account of it."""
    place(PLAIN, ELF)
    assert client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json["allowed"]
    assert app.BOARD.piece_on(Hex(**PLAIN)) is None
    assert app.BOARD.piece_on(Hex(**NEIGHBOUR)).key == ELF


def test_a_move_returns_the_new_tilt(client):
    """Picked up, the piece lies down again - and it is the server that says how."""
    place(PLAIN, ELF)
    before = app.BOARD.tilt_on(Hex(**PLAIN))
    answer = client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json
    assert answer["allowed"] is True
    assert answer["tilt"] == app.BOARD.tilt_on(Hex(**NEIGHBOUR))
    assert answer["tilt"] != before


def test_a_move_does_not_lay_the_other_pieces_down_again(client):
    """Only the moved piece changes angle: the others have not been touched."""
    place(PLAIN, ELF)
    place(DISTANT, ELF)
    motionless = app.BOARD.tilt_on(Hex(**DISTANT))
    client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR})
    assert app.BOARD.tilt_on(Hex(**DISTANT)) == motionless


def test_a_refused_move_leaves_the_board_in_place(client):
    place(PLAIN, ELF)
    assert client.post("/move",
                       json={"origin": PLAIN, "destination": DISTANT}).json["allowed"] is False
    assert app.BOARD.piece_on(Hex(**PLAIN)).key == ELF


def test_unreadable_coordinates_are_refused(client):
    assert client.get("/moves", query_string={"q": "a", "r": 0, "s": 0}).status_code == 400
    assert client.get("/moves", query_string={"q": 1, "r": 26}).status_code == 400
    assert client.get("/moves", query_string={"q": 1, "r": 26, "s": 0}).status_code == 400


def test_a_hexagon_off_the_map_cannot_be_found(client):
    assert client.get("/moves", query_string={"q": 99, "r": 0, "s": -99}).status_code == 404


def test_a_move_within_reach_is_allowed(client):
    answer = client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json
    assert answer["allowed"] is True
    assert answer["destination"] == {**NEIGHBOUR, "terrain": "plaine"}


def test_a_move_out_of_reach_is_refused(client):
    answer = client.post("/move", json={"origin": PLAIN, "destination": DISTANT}).json
    assert answer["allowed"] is False


def test_one_does_not_move_on_the_spot(client):
    assert client.post("/move",
                       json={"origin": PLAIN, "destination": PLAIN}).json["allowed"] is False


def test_a_move_out_of_the_pieces_reach_is_refused(client):
    """A square reached by the flat rate is no longer reached if the piece in hand is slower."""
    far = next(hexagon for hexagon in Hex(**PLAIN).moves(5)
               if hexagon not in Hex(**PLAIN).moves(2))
    destination = {"q": far.q, "r": far.r, "s": far.s}

    assert client.post("/move", json={"origin": PLAIN, "destination": destination}).json["allowed"]
    refused = client.post("/move",
                          json={"origin": PLAIN, "destination": destination,
                                "piece": SLOW}).json
    assert refused["allowed"] is False
    assert (refused["piece"], refused["movement"]) == (SLOW, 2)


def test_a_marker_does_not_move(client):
    answer = client.post("/move",
                         json={"origin": PLAIN, "destination": NEIGHBOUR, "piece": MARKER}).json
    assert answer["allowed"] is False


def test_an_incomplete_move_request_is_refused(client):
    assert client.post("/move", json={"origin": PLAIN}).status_code == 400
    assert client.post("/move", json={}).status_code == 400
    assert client.post("/move", data="not json").status_code == 400


# --- Game phases ---------------------------------------------------------------------------------

DWARF = "nains-01-5-infanteries"       # alliance, strength 12
ARCHER = "yzent-03-8-archers"          # darkness, strength 2, fire 4, range 3


def test_the_page_carries_the_current_phase(client):
    phase = read_hidden_field(client.get("/").get_data(as_text=True), "phase")
    assert phase == {"side": ALLIANCE, "type": "mouvement", "army": "Nains",
                     "label": "Phase de mouvement — Nains", "number": 1,
                     "unavailable": {"attackers": [], "targets": []}}


def test_next_phase_skips_magic_and_alternates_the_players(client):
    sequence = [client.post("/phase/next").json for _ in range(4)]
    assert [(p["army"], p["type"]) for p in sequence] == [
        ("Nains", "combat"), ("Orques", "mouvement"), ("Orques", "combat"), ("Nains", "mouvement")]
    assert sequence[-1]["number"] == 2


def test_movement_is_blocked_outside_its_phase(client):
    place(PLAIN, DWARF)
    client.post("/phase/next")  # the Dwarves' combat phase
    refused = client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json
    assert refused["allowed"] is False
    assert app.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


def test_movement_is_blocked_for_the_inactive_side(client):
    place(PLAIN, ARCHER)  # a Darkness unit, while it is the Dwarves' turn
    refused = client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json
    assert refused["allowed"] is False


# --- Combat resolution ---------------------------------------------------------------------------

def test_the_combat_range_follows_the_distance(client):
    place(PLAIN, ARCHER)
    answer = client.get("/combat/range", query_string={
        "cq": NEIGHBOUR["q"], "cr": NEIGHBOUR["r"], "cs": NEIGHBOUR["s"],
        "aq": PLAIN["q"], "ar": PLAIN["r"], "as": PLAIN["s"]}).json
    assert answer["in_range"] is True
    far = client.get("/combat/range", query_string={
        "cq": DISTANT["q"], "cr": DISTANT["r"], "cs": DISTANT["s"],
        "aq": PLAIN["q"], "ar": PLAIN["r"], "as": PLAIN["s"]}).json
    assert far["in_range"] is False
    assert far["message"] == "Cette unité n'est pas à portée de la cible"


def test_a_combat_outside_its_phase_is_refused(client):
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ARCHER)
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["resolved"] is False


def test_a_won_combat_removes_the_defender(client, monkeypatch):
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)       # strength 12
    place(NEIGHBOUR, ARCHER)  # strength 2, darkness -> ratio 6-1, die 1 -> DE
    client.post("/phase/next")  # the Dwarves' combat phase
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["resolved"] is True
    assert answer["outcome"] == "DE"
    assert answer["message"] == "Combat résolu : Défenseur Éliminé"
    assert answer["eliminated"] == [{**NEIGHBOUR, "terrain": "plaine"}]
    assert app.BOARD.piece_on(Hex(**NEIGHBOUR)) is None
    assert app.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


def test_a_retreat_changes_nothing_on_the_board(client, monkeypatch):
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)                       # strength 12
    place(NEIGHBOUR, ORC)                     # strength 8 -> ratio 1-1, die 1 -> DR
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["outcome"] in ("AR", "DR")
    assert app.BOARD.piece_on(Hex(**NEIGHBOUR)).key == ORC
    assert app.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


def test_an_attacker_out_of_range_does_not_resolve_the_combat(client):
    place(DISTANT, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [DISTANT]}).json
    assert answer["resolved"] is False
    assert app.BOARD.piece_on(Hex(**NEIGHBOUR)).key == ORC


def test_the_target_must_be_an_opponent(client):
    place(PLAIN, DWARF)
    place(NEIGHBOUR, "nains-01-5-infanteries")
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["resolved"] is False


# --- One combat per unit and per phase ------------------------------------------------------------

# Two more adjacent squares: a second orc within reach of the dwarf on PLAIN, and a second dwarf
# within reach of the orc on NEIGHBOUR. Enough to exercise the two rules separately.
CONTACT = {"q": 1, "r": 27, "s": -28}
SUPPORT = {"q": 2, "r": 27, "s": -29}

# A die of 1 on DWARF 12 against ORC 8 gives a 1-1 ratio: a retreat, which the engine leaves
# without effect. Both units therefore survive the combat - and must nonetheless stay marked by it.
A_RETREAT = 1


@pytest.fixture
def combat_phase(client, monkeypatch):
    """Moves to the Dwarves' combat phase, the die fixed on a retreat: nobody is eliminated."""
    monkeypatch.setattr(app, "roll_the_die", lambda: A_RETREAT)
    client.post("/phase/next")
    return client


def test_an_attacker_cannot_attack_twice(combat_phase):
    """Even without effect - a retreat - the combat took place: the attacker has had its turn."""
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    place(CONTACT, ORC)
    first = combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert first["resolved"] is True
    assert first["outcome"] in ("AR", "DR")

    second = combat_phase.post("/combat", json={"target": CONTACT, "attackers": [PLAIN]}).json
    assert second["resolved"] is False
    assert app.ALREADY_ATTACKED in second["messages"]
    assert app.BOARD.piece_on(Hex(**CONTACT)).key == ORC


def test_a_target_cannot_be_attacked_twice(combat_phase):
    """Even by another attacker: it is the target that is consumed, not the pairing."""
    place(PLAIN, DWARF)
    place(SUPPORT, DWARF)
    place(NEIGHBOUR, ORC)
    assert combat_phase.post("/combat",
                             json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]

    second = combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [SUPPORT]}).json
    assert second["resolved"] is False
    assert second["message"] == app.ALREADY_TARGETED


def test_the_whole_group_of_attackers_is_marked(combat_phase):
    """Attacking in pairs engages both, not only the one designated first."""
    place(PLAIN, DWARF)
    place(SUPPORT, DWARF)
    place(NEIGHBOUR, ORC)
    place(CONTACT, ORC)
    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN, SUPPORT]})

    for origin in (PLAIN, SUPPORT):
        refusal = combat_phase.post("/combat",
                                    json={"target": CONTACT, "attackers": [origin]}).json
        assert refusal["resolved"] is False, origin


def test_two_units_of_the_same_counter_are_tracked_apart(combat_phase):
    """One counter stands for several units - `orques-01-15-infanteries` is placed fifteen times in
    scenario no. 4. Attacking one of the two orcs must therefore not consume the other."""
    place(PLAIN, DWARF)
    place(SUPPORT, DWARF)
    place(NEIGHBOUR, ORC)
    place(CONTACT, ORC)
    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})

    other = combat_phase.post("/combat", json={"target": CONTACT, "attackers": [SUPPORT]}).json
    assert other["resolved"] is True


def test_the_next_phase_frees_the_units(client, monkeypatch):
    """Each combat phase starts again with all its units - the other side's, and the next turn."""
    monkeypatch.setattr(app, "roll_the_die", lambda: A_RETREAT)
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")  # the Dwarves' combat
    assert client.post("/combat",
                       json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]

    client.post("/phase/next")  # the Orcs' movement
    client.post("/phase/next")  # the Orcs' combat: the orc attacks in its turn
    assert client.post("/combat",
                       json={"target": PLAIN, "attackers": [NEIGHBOUR]}).json["resolved"]

    client.post("/phase/next")  # the Dwarves' movement, turn 2
    client.post("/phase/next")  # the Dwarves' combat, turn 2
    assert client.post("/combat",
                       json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]


def test_the_range_check_refuses_an_already_engaged_attacker(combat_phase):
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    place(CONTACT, ORC)
    query = {"cq": CONTACT["q"], "cr": CONTACT["r"], "cs": CONTACT["s"],
             "aq": PLAIN["q"], "ar": PLAIN["r"], "as": PLAIN["s"]}
    before = combat_phase.get("/combat/range", query_string=query).json
    assert before == {"in_range": True, "available": True, "message": None}

    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})
    after = combat_phase.get("/combat/range", query_string=query).json
    assert after["available"] is False
    assert after["message"] == app.ALREADY_ATTACKED


def test_the_target_check_refuses_an_already_attacked_unit(combat_phase):
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    query = {"cq": NEIGHBOUR["q"], "cr": NEIGHBOUR["r"], "cs": NEIGHBOUR["s"]}
    assert combat_phase.get("/combat/target",
                            query_string=query).json["available"] is True

    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})
    after = combat_phase.get("/combat/target", query_string=query).json
    assert after["available"] is False
    assert after["message"] == app.ALREADY_TARGETED


def test_the_unavailable_are_told_to_the_browser(combat_phase):
    """The map's greying is set from these two lists, given as squares."""
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    answer = combat_phase.post("/combat",
                               json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json

    def squares(entries):
        return [{"q": c["q"], "r": c["r"], "s": c["s"]} for c in entries]

    assert squares(answer["unavailable"]["attackers"]) == [PLAIN]
    assert squares(answer["unavailable"]["targets"]) == [NEIGHBOUR]

    # The next phase frees them, and the page sees it in the same place.
    following = combat_phase.post("/phase/next").json
    assert following["unavailable"] == {"attackers": [], "targets": []}


# --- Following the game ---------------------------------------------------------------------------
#
# The route the browser used to query every three seconds to watch the opponent play. It only
# returns the board when it has changed: that is the whole point of the version number.


def test_the_state_returns_the_game_to_whoever_knows_no_version(client):
    client.get("/")
    answer = client.get("/game/state").json
    assert answer["changed"] is True
    assert len(answer["pieces"]) == len(app.SCENARIO)
    assert answer["phase"]["side"] == app.TURN.active_side


def test_the_state_returns_only_the_number_while_nothing_moves(client):
    client.get("/")
    version = client.get("/game/state").json["version"]
    answer = client.get("/game/state", query_string={"version": version}).json
    assert answer == {"version": version, "changed": False}


def test_a_move_played_raises_the_version(client):
    client.get("/")
    version = client.get("/game/state").json["version"]
    client.post("/phase/next")
    assert client.get("/game/state").json["version"] > version


def test_the_state_tells_the_phase_the_opponent_reached(client):
    """The use case: the other has passed their phase, and the page learns it without reloading."""
    client.get("/")
    version = client.get("/game/state").json["version"]
    client.post("/phase/next")

    answer = client.get("/game/state", query_string={"version": version}).json

    assert answer["changed"] is True
    assert answer["phase"]["label"] == app.TURN.label


def test_a_move_shows_in_the_state(client, deserted_map):
    client.get("/")
    origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
    destination = app.BOARD.moves(origin)[0]
    version = client.get("/game/state").json["version"]
    client.post("/move", json={"origin": origin.to_dict(), "destination": destination.to_dict(),
                               "piece": app.BOARD.piece_on(origin).key})

    squares = {(piece["q"], piece["r"], piece["s"])
               for piece in client.get("/game/state",
                                       query_string={"version": version}).json["pieces"]}

    assert (destination.q, destination.r, destination.s) in squares
    assert (origin.q, origin.r, origin.s) not in squares


def test_the_state_returns_the_same_tilts_every_time(client):
    """The heart of the matter: polling the game does not lay the pieces down again.

    The browser lays the scene out again at every version change; if the angle were redrawn at
    every send, every counter would spin under the player's eyes at each move played opposite.
    """
    client.get("/")
    first = client.get("/game/state").json["pieces"]
    client.post("/phase/next")
    second = client.get("/game/state").json["pieces"]
    assert [piece["tilt"] for piece in first] == [piece["tilt"] for piece in second]


def test_only_the_moved_piece_changes_tilt_in_the_state(client):
    client.get("/")
    origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
    destination = app.BOARD.moves(origin)[0]
    before = {(piece["q"], piece["r"], piece["s"]): piece["tilt"]
              for piece in client.get("/game/state").json["pieces"]}

    client.post("/move", json={"origin": origin.to_dict(), "destination": destination.to_dict(),
                               "piece": app.BOARD.piece_on(origin).key})

    after = {(piece["q"], piece["r"], piece["s"]): piece["tilt"]
             for piece in client.get("/game/state").json["pieces"]}
    del before[(origin.q, origin.r, origin.s)]
    del after[(destination.q, destination.r, destination.s)]
    assert after == before


def test_the_state_is_public(anonymous_client):
    """A passing visitor follows the game as they see the map."""
    assert anonymous_client.get("/game/state").status_code == 200


def test_the_state_says_who_holds_which_side(client):
    client.get("/")
    table = client.get("/game/state").json["table"]
    assert table["seats"] == {side: "Joueuse d'essai" for side in app.SCENARIO.sides}
