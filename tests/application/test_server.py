"""What the server sends: the scenario's set-up and the files from the game box."""

import json
import re

import pytest

from tenebrae.application import current_game, pieces
from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.logs.battle_log import log_lines
from tenebrae.application.routes import combat as combat_routes
from tenebrae.engine.board import MAXIMUM_TILT
from tenebrae.engine.hexagon import DEFAULT_MOVEMENT, MAP, Hex
from tenebrae.engine.piece import ALLIANCE, CATALOGUE, DARKNESS


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map, and leaves it deserted.

    The server's board survives from one request to the next: without this cleanup, the
    scenario's forty-eight units would stay under the next test's feet. Tests that want a
    populated board call `the_board` themselves.
    """


def the_board(client):
    """Loads the board through "/game", the entry that needs no identifier.

    "/" is the list of saved games; "/game" is the last one played, laid out afresh where there is
    none, and it **redirects** to that game's own address - one game, one URL - which is why the
    redirect is followed here. Every test that wants a board on the server goes through this.
    """
    return client.get("/game", follow_redirects=True)


def read_hidden_field(page, identifier):
    """Returns the JSON carried by the hidden field `identifier`."""
    tag = re.search(rf'<input type="hidden" id="{identifier}" value="([^"]*)">', page)
    assert tag, f"hidden field \"{identifier}\" missing from the page"
    contents = (tag.group(1)
                .replace("&#34;", '"').replace("&lt;", "<").replace("&gt;", ">")
                .replace("&#39;", "'").replace("&amp;", "&"))
    return json.loads(contents)


def test_the_page_carries_both_armies_of_the_scenario(client):
    """Scenario no. 4 puts 18 dwarves against 30 orcs: the page carries them all."""
    pieces = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    assert len(pieces) == len(current_game.SCENARIO) == 48
    sides = [piece["side"] for piece in pieces]
    assert sides.count(ALLIANCE) == 18
    assert sides.count(DARKNESS) == 30


def test_the_page_places_each_piece_on_the_scenarios_square(client):
    """The server invents nothing: it serves the placement fixed in `tenebrae/scenarios/`.

    The equality carries more than the squares. A key names one and only one piece, so two units
    landing on the same hexagon would collapse the dict and the comparison would fail - which is
    why no separate test counts the distinct squares. That the squares exist at all is the
    scenario's business, and `tests/engine/test_scenario.py` checks it there; what belongs here is
    that the server decomposes each key into a **cube** triple, since it is that triple, and not
    the key, that the browser places.
    """
    pieces = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    placed = {f"{piece['q']},{piece['r']},{piece['s']}": piece["key"] for piece in pieces}
    assert placed == current_game.SCENARIO.placement
    for piece in pieces:
        assert piece["q"] + piece["r"] + piece["s"] == 0


def test_each_placed_piece_carries_its_tilt(client):
    """The angle the counter lies at goes out with the piece: the browser does not draw one.

    It is the server that draws it, when placing, and that keeps it - without which the piece
    would lie down differently every time the page lays the scene out again.
    """
    pieces = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    for piece in pieces:
        assert isinstance(piece["tilt"], float)
        assert abs(piece["tilt"]) <= MAXIMUM_TILT


def test_each_placed_piece_carries_its_counter_values(client):
    """The hover card is read from the hidden field: the whole counter must be in it.

    Values absent from the counter go out as `None` - it is the browser that renders them as a
    dash. `movement`, for its part, stays the movement budget, the one the engine uses, and not
    the raw value that `pions.json` sometimes leaves empty. The side is here too: it is read off
    the counter's faction like the rest, and has no reason to be walked over separately.
    """
    pieces = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    for piece in pieces:
        assert piece["key"] in CATALOGUE
        placed = CATALOGUE[piece["key"]]
        assert piece["side"] == placed.side
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
    """Two counters of the set-up, as `tenebrae/game_box/pions/pions.json` records them.

    Both must be **placed by scenario no. 4**: the page only carries what is on the board. The
    dwarf leaders would have been the telling case - they are the only counter of the box to carry
    a range of 10 - but the scenario leaves them in the box, along with the mage, since the engine
    gives them no effect (see `tenebrae/scenarios/README.md` and
    `tests/engine/test_scenario.py::test_neither_leader_nor_spellcaster_is_placed`). The heavy
    crossbowmen carry the firing pair instead, and the orc infantry carries none.
    """
    pieces = {piece["key"]: piece
              for piece in read_hidden_field(the_board(client).get_data(as_text=True), "pieces")}

    crossbowmen = pieces["nains-03-4-arbaletriers-lourds"]
    assert (crossbowmen["strength"], crossbowmen["fire"], crossbowmen["range"]) == (8, 5, 2)
    assert crossbowmen["symbol"] == "arbaletrier-lourd"

    infantry = pieces["orques-01-15-infanteries"]
    assert infantry["symbol"] == "infanterie"
    assert (infantry["fire"], infantry["range"], infantry["flight_movement"]) == (None, None, None)


def test_the_set_up_populates_the_servers_board(client):
    """The server keeps what it has placed: that is where the zones of control come from."""
    pieces = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    assert len(current_game.BOARD) == len(pieces)
    for piece in pieces:
        placed = current_game.BOARD.piece_on(Hex(piece["q"], piece["r"], piece["s"]))
        assert placed is not None and placed.key == piece["key"]


def test_reloading_the_page_puts_the_pieces_back(client):
    """A move the base never saw is undone by a reload: "/" resumes the saved game, not memory."""
    origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
    the_board(client)
    destination = current_game.BOARD.moves(origin)[0]
    assert current_game.BOARD.move(origin, destination)

    the_board(client)
    assert current_game.BOARD.piece_on(destination) is None
    assert current_game.BOARD.pieces.keys() == current_game.SCENARIO.placement.keys()


def test_the_catalogues_movements_are_those_of_the_counters():
    for piece in pieces.PIECE_CATALOGUE:
        assert piece["movement"] == CATALOGUE[piece["key"]].movement_points
    movements = {piece["key"]: piece["movement"] for piece in pieces.PIECE_CATALOGUE}
    assert movements["reissland-02-8-cavaleries"] == 8       # cavalry goes far
    assert movements["yzent-05-1-belier"] == 2               # the ram drags itself along
    assert movements["marqueurs-03-paralysie"] == 0          # a marker does not move


def test_the_piece_images_exist(client):
    pieces = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    for piece in pieces:
        assert client.get(f"/pieces/{piece['image']}").status_code == 200


def test_the_grid_alignment_is_transmitted(client):
    grid = read_hidden_field(the_board(client).get_data(as_text=True), "grid")
    assert grid["origin"] == GRID_ORIGIN
    assert grid["matrix"] == GRID_MATRIX
    assert grid["piece_size"] == PIECE_SIZE


def test_the_set_up_does_not_change_from_one_load_to_the_next(client):
    """A fixed scenario replays identically: that is what is asked of it.

    Tilts included: the second load resumes the game the first one saved, and finds the counters
    lying as it left them (see `test_persistence.py` for what happens across a restart).
    """
    first = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    second = read_hidden_field(the_board(client).get_data(as_text=True), "pieces")
    assert first == second


def test_the_map_is_served(client):
    answer = client.get("/map.jpg")
    assert answer.status_code == 200
    assert answer.headers["Content-Type"] == "image/jpeg"


def test_the_overviews_are_not_served(client):
    """Whole sheets and record sheets are not pieces: neither served nor placed."""
    for path in ("21-vues-d-ensemble/vues-d-ensemble-01-planches-de-pions.jpg",
                 "19-magiciens/magiciens-02-pions-de-magiciens-et-clercs-vue-d-ensemble.jpg"):
        assert (pieces.PIECES / path).exists()
        assert client.get(f"/pieces/{path}").status_code == 404
        assert path not in [piece["path"] for piece in pieces.PIECE_CATALOGUE]


def test_the_catalogue_covers_the_pieces_of_the_box():
    """127 photographs in game_box/pions, minus the 4 sheets and the 2 record sheets."""
    assert len(pieces.PIECE_CATALOGUE) == 121
    assert all((pieces.PIECES / piece["path"]).exists() for piece in pieces.PIECE_CATALOGUE)


def test_the_piece_names_are_readable():
    names = {piece["path"]: piece["name"] for piece in pieces.PIECE_CATALOGUE}
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
    """The route adds no rule: it exposes Hex.moves(), and adds to each square its terrain.

    The equality is the whole check. It says the route invents no square and forgets none - the
    origin's own absence among them included, which is the engine's rule and is exercised as such
    in `tests/engine/test_hexagon.py`.
    """
    expected = {(h.q, h.r, h.s) for h in Hex(**PLAIN).moves()}
    hexagons = client.get("/moves", query_string=PLAIN).json["hexagons"]
    assert {(h["q"], h["r"], h["s"]) for h in hexagons} == expected and expected
    for hexagon in hexagons:
        assert hexagon["q"] + hexagon["r"] + hexagon["s"] == 0
        assert hexagon["terrain"] == MAP[f"{hexagon['q']},{hexagon['r']},{hexagon['s']}"][0]


def test_the_movement_is_that_of_the_piece(client):
    """The piece in hand gives the budget: the counter's, not the flat rate."""
    for key, expected in ((SLOW, 2), (FAST, 8), (MARKER, 0)):
        answer = client.get("/moves", query_string={**PLAIN, "piece": key}).json
        assert answer["piece"] == key
        assert answer["movement"] == expected
        assert len(answer["hexagons"]) == len(Hex(**PLAIN).moves(expected))
    # The marker's case is the telling one: no budget, hence nowhere to go.
    assert client.get("/moves", query_string={**PLAIN, "piece": MARKER}).json["hexagons"] == []


def test_the_slow_piece_goes_less_far_than_the_fast_one(client):
    slow = client.get("/moves", query_string={**PLAIN, "piece": SLOW}).json
    fast = client.get("/moves", query_string={**PLAIN, "piece": FAST}).json
    reached = {(h["q"], h["r"], h["s"]) for h in slow["hexagons"]}
    assert 0 < len(reached) < len(fast["hexagons"])
    assert reached < {(h["q"], h["r"], h["s"]) for h in fast["hexagons"]}


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
    current_game.BOARD.place(Hex(**hexagon), CATALOGUE[key])


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
    assert current_game.BOARD.piece_on(Hex(**PLAIN)) is None
    assert current_game.BOARD.piece_on(Hex(**NEIGHBOUR)).key == ELF


def test_a_move_returns_the_new_tilt(client):
    """Picked up, the piece lies down again - and it is the server that says how."""
    place(PLAIN, ELF)
    before = current_game.BOARD.tilt_on(Hex(**PLAIN))
    answer = client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json
    assert answer["allowed"] is True
    assert answer["tilt"] == current_game.BOARD.tilt_on(Hex(**NEIGHBOUR))
    assert answer["tilt"] != before


def test_a_move_does_not_lay_the_other_pieces_down_again(client):
    """Only the moved piece changes angle: the others have not been touched."""
    place(PLAIN, ELF)
    place(DISTANT, ELF)
    motionless = current_game.BOARD.tilt_on(Hex(**DISTANT))
    client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR})
    assert current_game.BOARD.tilt_on(Hex(**DISTANT)) == motionless


def test_a_refused_move_leaves_the_board_in_place(client):
    place(PLAIN, ELF)
    assert client.post("/move",
                       json={"origin": PLAIN, "destination": DISTANT}).json["allowed"] is False
    assert current_game.BOARD.piece_on(Hex(**PLAIN)).key == ELF


def test_unreadable_coordinates_are_refused(client):
    assert client.get("/moves", query_string={"q": "a", "r": 0, "s": 0}).status_code == 400
    assert client.get("/moves", query_string={"q": 1, "r": 26}).status_code == 400
    assert client.get("/moves", query_string={"q": 1, "r": 26, "s": 0}).status_code == 400


def test_a_hexagon_off_the_map_cannot_be_found(client):
    assert client.get("/moves", query_string={"q": 99, "r": 0, "s": -99}).status_code == 404


def test_a_move_is_allowed_within_reach_and_nowhere_else(client):
    """The reach decides, and the square one stands on is not within it."""
    allowed = client.post("/move", json={"origin": PLAIN, "destination": NEIGHBOUR}).json
    assert allowed["allowed"] is True
    assert allowed["destination"] == {**NEIGHBOUR, "terrain": "plaine"}

    for destination in (DISTANT, PLAIN):
        refused = client.post("/move", json={"origin": PLAIN, "destination": destination}).json
        assert refused["allowed"] is False, destination


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
    phase = read_hidden_field(the_board(client).get_data(as_text=True), "phase")
    assert phase == {"side": ALLIANCE, "type": "mouvement", "army": "Nains",
                     "label": "Phase de mouvement — Nains", "number": 1,
                     "unavailable": {"attackers": [], "targets": []},
                     "over": False, "winner": None}


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
    assert current_game.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


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


def coordinates(hexagon):
    """The three coordinates of a hexagon, as a request carries them - `to_dict` adds its
    terrain."""
    return {"q": hexagon.q, "r": hexagon.r, "s": hexagon.s}


def ratio_of(client, target, attackers):
    """Asks the server to weigh a combat being composed, as the browser does at every click."""
    return client.get("/combat/ratio", query_string={
        "cq": target["q"], "cr": target["r"], "cs": target["s"],
        "a": [f"{a['q']},{a['r']},{a['s']}" for a in attackers]}).json


def test_the_ratio_weighs_the_combat_being_composed(client):
    """What the toolbar shows while the attackers are being designated: the column, the points on
    either side, and what each face of the die would give."""
    place(PLAIN, DWARF)       # strength 12
    place(NEIGHBOUR, ORC)     # strength 8, on the plain: nothing multiplies it
    assert ratio_of(client, NEIGHBOUR, [PLAIN]) == {
        "ratio": [1, 1], "attack": 12, "defence": 8,
        "outcomes": ["DR", "DR", "DR", "AR", "AR", "AR"]}


def test_the_ratio_adds_the_attackers_up(client):
    second = {"q": 2, "r": 25, "s": -27}  # the target's other neighbour
    place(PLAIN, DWARF)
    place(second, DWARF)
    place(NEIGHBOUR, ORC)
    assert ratio_of(client, NEIGHBOUR, [PLAIN, second]) == {
        "ratio": [3, 1], "attack": 24, "defence": 8,
        "outcomes": ["DR", "DR", "DR", "DR", "DR", "AR"]}


def test_the_faces_announced_are_the_ones_the_ground_allows(client):
    """A hill adds 2 to the throw: the faces the list gives are those the die can really reach
    there, and not the table's row read as it stands."""
    hill = Hex.from_key(next(key for key, elements in MAP.items() if elements[0] == "colline"))
    attacker = next(square for square in hill.neighbours() if square.is_on_map)
    place(coordinates(hill), ORC)
    place(coordinates(attacker), DWARF)
    weighed = ratio_of(client, coordinates(hill), [coordinates(attacker)])
    assert weighed["outcomes"] == ["DR", "AR", "AR", "AR", "AR", "AR"]


def test_the_ratio_counts_the_defenders_terrain(client):
    """The reason the weighing is the server's: the terrain of a square is not in the page."""
    ruins = Hex.from_key(next(key for key, elements in MAP.items() if elements[0] == "ruines"))
    attacker = next(square for square in ruins.neighbours() if square.is_on_map)
    place(coordinates(ruins), ORC)
    place(coordinates(attacker), DWARF)
    weighed = ratio_of(client, coordinates(ruins), [coordinates(attacker)])
    assert (weighed["ratio"], weighed["attack"], weighed["defence"]) == ([1, 2], 12, 16)


def test_an_attacker_out_of_range_does_not_weigh(client):
    """The same filter `POST /combat` applies: what would not fight does not count."""
    place(DISTANT, DWARF)
    place(NEIGHBOUR, ORC)
    assert ratio_of(client, NEIGHBOUR, [DISTANT]) == {
        "ratio": None, "attack": 0, "defence": 0, "outcomes": []}


def test_an_empty_target_weighs_nothing(client):
    place(PLAIN, DWARF)
    assert ratio_of(client, NEIGHBOUR, [PLAIN]) == {
        "ratio": None, "attack": 0, "defence": 0, "outcomes": []}


def test_weighing_writes_nothing_in_the_players_column(client):
    """It is recomputed at every attacker taken or withdrawn: a line each time would bury the
    account of the game."""
    place(DISTANT, DWARF)
    place(NEIGHBOUR, ORC)
    before = len(log_lines())
    ratio_of(client, NEIGHBOUR, [DISTANT])   # refused, and silent
    assert len(log_lines()) == before


def test_the_ratio_announced_is_the_one_the_combat_reads(client, monkeypatch):
    """The forecast and the resolution are one weighing: the player is dealt what was shown."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")  # the Dwarves' combat phase
    announced = ratio_of(client, NEIGHBOUR, [PLAIN])

    resolved = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert resolved["ratio"] == announced["ratio"]
    # The die was fixed at 1: the outcome played is the one the first face announced.
    assert resolved["outcome"] == announced["outcomes"][0]


def test_an_unreadable_attacker_key_is_refused(client):
    place(NEIGHBOUR, ORC)
    assert client.get("/combat/ratio", query_string={
        "cq": NEIGHBOUR["q"], "cr": NEIGHBOUR["r"], "cs": NEIGHBOUR["s"],
        "a": "over-there"}).status_code == 400


def test_a_combat_outside_its_phase_is_refused(client):
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ARCHER)
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["resolved"] is False


def test_a_won_combat_removes_the_defender(client, monkeypatch):
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)       # strength 12
    place(NEIGHBOUR, ARCHER)  # strength 2, darkness -> ratio 6-1, die 1 -> DE
    client.post("/phase/next")  # the Dwarves' combat phase
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["resolved"] is True
    assert answer["outcome"] == "DE"
    assert answer["message"] == "Combat résolu : Défenseur Éliminé"
    assert answer["eliminated"] == [{**NEIGHBOUR, "terrain": "plaine"}]
    assert current_game.BOARD.piece_on(Hex(**NEIGHBOUR)) is None
    assert current_game.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


def test_a_retreat_falls_the_defender_back(client, monkeypatch):
    """`DR`: the target leaves its square, the attacker stays on its own, and the answer says
    where each unit went - the browser lays the scene out again from the stream, but the route
    tells it all the same."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)                       # strength 12
    place(NEIGHBOUR, ORC)                     # strength 8 -> ratio 1-1, die 1 -> DR
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json

    assert answer["outcome"] == "DR"
    assert answer["eliminated"] == []
    assert len(answer["retreats"]) == 1
    fall_back = answer["retreats"][0]
    assert {name: fall_back["from"][name] for name in ("q", "r", "s")} == NEIGHBOUR
    assert current_game.BOARD.piece_on(Hex(**NEIGHBOUR)) is None
    assert current_game.BOARD.piece_on(Hex(**{name: fall_back["to"][name]
                                              for name in ("q", "r", "s")})).key == ORC
    assert current_game.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


def test_the_attacker_can_take_the_square_the_defender_leaves(client, monkeypatch):
    """"Attaquer et avancer": the decision the booklet has announced immediately after the combat
    travels with the request, and the answer says where the counter went."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)       # 12
    place(NEIGHBOUR, ORC)     # 8 -> 1-1, die 1 -> DR
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN],
                                          "advance": True}).json

    assert answer["outcome"] == "DR"
    assert {name: answer["advance"]["from"][name] for name in ("q", "r", "s")} == PLAIN
    assert {name: answer["advance"]["to"][name] for name in ("q", "r", "s")} == NEIGHBOUR
    assert answer["advance"]["tilt"] is not None
    assert current_game.BOARD.piece_on(Hex(**NEIGHBOUR)).key == DWARF
    assert current_game.BOARD.piece_on(Hex(**PLAIN)) is None


def test_an_attack_without_the_advance_stays_where_it_is(client, monkeypatch):
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json

    assert answer["advance"] is None
    assert current_game.BOARD.piece_on(Hex(**PLAIN)).key == DWARF


def test_the_advance_is_told_in_the_log(client, monkeypatch):
    """Under the fall-back it follows, above the outcome that allowed it - the column reads the
    most recent line first, so it comes out the other way round."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")
    client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN], "advance": True})

    written = [line["text"] for line in log_lines()]
    assert f"Avance : {Hex(**PLAIN).key} → {Hex(**NEIGHBOUR).key}" in written


def test_the_unit_that_advanced_is_engaged_on_its_new_square(client, monkeypatch):
    """The register counts it where it now stands: marked on the square it left, it could attack
    again from the one it took."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN],
                                          "advance": True}).json

    engaged = [{name: square[name] for name in ("q", "r", "s")}
               for square in answer["unavailable"]["attackers"]]
    assert engaged == [NEIGHBOUR]


def test_a_retreat_is_told_in_the_log(client, monkeypatch):
    """One line per unit that gave ground, under the outcome it comes from."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json

    destination = answer["retreats"][0]["to"]
    lines = [line["text"] for line in log_lines()]
    assert f"Recul : {Hex(**NEIGHBOUR).key} → " \
           f"{Hex(destination['q'], destination['r'], destination['s']).key}" in lines


def test_a_unit_that_cannot_fall_back_is_eliminated(client, monkeypatch):
    """Ringed by the enemy, the target has nowhere to go: it leaves the board, and the browser is
    told to clear its square like any other elimination."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    target = Hex(**NEIGHBOUR)
    place(NEIGHBOUR, ORC)
    for square in target.neighbours():
        current_game.BOARD.place(square, CATALOGUE[DWARF])
    client.post("/phase/next")
    attacker = {"q": PLAIN["q"], "r": PLAIN["r"], "s": PLAIN["s"]}
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [attacker]}).json

    assert answer["outcome"] == "DR"
    assert answer["eliminated"] == [{**NEIGHBOUR, "terrain": "plaine"}]
    assert answer["retreats"] == []
    assert current_game.BOARD.piece_on(target) is None
    lines = [line["text"] for line in log_lines()]
    assert f"Recul impossible : unité éliminée en {target.key}" in lines


def test_an_eliminated_unit_is_kept_for_the_end_of_the_game(client, monkeypatch):
    """"Eliminated units are kept by the player who eliminated them, to establish their total of
    points at the end of the game." """
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)       # strength 12
    place(NEIGHBOUR, ARCHER)  # strength 2 -> ratio 6-1, die 1 -> DE
    client.post("/phase/next")
    client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})

    assert [loss["piece"] for loss in current_game.CASUALTIES.taken_by(ALLIANCE)] == [ARCHER]
    assert current_game.CASUALTIES.points_taken_by(ALLIANCE) == 2
    assert current_game.CASUALTIES.points_lost_by(DARKNESS) == 2


def test_an_attacker_out_of_range_does_not_resolve_the_combat(client):
    place(DISTANT, DWARF)
    place(NEIGHBOUR, ORC)
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [DISTANT]}).json
    assert answer["resolved"] is False
    assert current_game.BOARD.piece_on(Hex(**NEIGHBOUR)).key == ORC


def test_the_target_must_be_an_opponent(client):
    place(PLAIN, DWARF)
    place(NEIGHBOUR, "nains-01-5-infanteries")
    client.post("/phase/next")
    answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert answer["resolved"] is False


# --- One combat per unit and per phase ------------------------------------------------------------

# Two more adjacent squares: a second darkness unit within reach of the one on PLAIN, and a second
# alliance unit within reach of the one on NEIGHBOUR. Enough to exercise the two rules separately.
CONTACT = {"q": 1, "r": 27, "s": -28}
SUPPORT = {"q": 2, "r": 27, "s": -29}

# These tests want a combat that **leaves the board exactly as it was**: the register is what is
# being looked at, and a unit that moved would no longer be where the test placed it. Since the
# retreats are played, one case alone answers that - the booklet's "a unit firing missiles can in
# no case suffer a retreat or exchange result". Missile troops on both sides, and a die that reads
# `AR` in both directions:
#
#     crossbowmen 6 against orc archers 4 -> 1-1, die 4 -> AR
#     orc archers 4 against crossbowmen 6 -> 1-2, die 4 -> AR
#
# In both, it is the attacker that should fall back, and in both it fires: nobody moves, and the
# combat counts all the same.
SHOOTER = "nains-02-4-arbaletriers"       # alliance, strength 6, fire 4, range 2
ORC_SHOOTER = "orques-03-5-archers"       # darkness, strength 4, fire 8, range 3
A_STILL_RETREAT = 4


@pytest.fixture
def combat_phase(client, monkeypatch):
    """Moves to the Dwarves' combat phase, the die fixed on a retreat nobody suffers."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: A_STILL_RETREAT)
    client.post("/phase/next")
    return client


def test_an_attacker_cannot_attack_twice(combat_phase):
    """Even without effect - a retreat - the combat took place: the attacker has had its turn."""
    place(PLAIN, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
    place(CONTACT, ORC_SHOOTER)
    first = combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
    assert first["resolved"] is True
    assert first["outcome"] in ("AR", "DR")

    second = combat_phase.post("/combat", json={"target": CONTACT, "attackers": [PLAIN]}).json
    assert second["resolved"] is False
    assert combat_routes.ALREADY_ATTACKED in second["messages"]
    assert current_game.BOARD.piece_on(Hex(**CONTACT)).key == ORC_SHOOTER


def test_a_target_cannot_be_attacked_twice(combat_phase):
    """Even by another attacker: it is the target that is consumed, not the pairing."""
    place(PLAIN, SHOOTER)
    place(SUPPORT, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
    assert combat_phase.post("/combat",
                             json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]

    second = combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [SUPPORT]}).json
    assert second["resolved"] is False
    assert second["message"] == combat_routes.ALREADY_TARGETED


def test_the_whole_group_of_attackers_is_marked(combat_phase):
    """Attacking in pairs engages both, not only the one designated first."""
    place(PLAIN, SHOOTER)
    place(SUPPORT, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
    place(CONTACT, ORC_SHOOTER)
    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN, SUPPORT]})

    for origin in (PLAIN, SUPPORT):
        refusal = combat_phase.post("/combat",
                                    json={"target": CONTACT, "attackers": [origin]}).json
        assert refusal["resolved"] is False, origin


def test_two_units_of_the_same_counter_are_tracked_apart(combat_phase):
    """One counter stands for several units - `orques-01-15-infanteries` is placed fifteen times in
    scenario no. 4. Attacking one of the two orcs must therefore not consume the other."""
    place(PLAIN, SHOOTER)
    place(SUPPORT, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
    place(CONTACT, ORC_SHOOTER)
    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})

    other = combat_phase.post("/combat", json={"target": CONTACT, "attackers": [SUPPORT]}).json
    assert other["resolved"] is True


def test_the_next_phase_frees_the_units(client, monkeypatch):
    """Each combat phase starts again with all its units - the other side's, and the next turn."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: A_STILL_RETREAT)
    place(PLAIN, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
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
    place(PLAIN, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
    place(CONTACT, ORC_SHOOTER)
    query = {"cq": CONTACT["q"], "cr": CONTACT["r"], "cs": CONTACT["s"],
             "aq": PLAIN["q"], "ar": PLAIN["r"], "as": PLAIN["s"]}
    before = combat_phase.get("/combat/range", query_string=query).json
    assert before == {"in_range": True, "available": True, "message": None}

    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})
    after = combat_phase.get("/combat/range", query_string=query).json
    assert after["available"] is False
    assert after["message"] == combat_routes.ALREADY_ATTACKED


def test_the_target_check_refuses_an_already_attacked_unit(combat_phase):
    place(PLAIN, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
    query = {"cq": NEIGHBOUR["q"], "cr": NEIGHBOUR["r"], "cs": NEIGHBOUR["s"]}
    assert combat_phase.get("/combat/target",
                            query_string=query).json["available"] is True

    combat_phase.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})
    after = combat_phase.get("/combat/target", query_string=query).json
    assert after["available"] is False
    assert after["message"] == combat_routes.ALREADY_TARGETED


def test_the_unavailable_are_told_to_the_browser(combat_phase):
    """The map's greying is set from these two lists, given as squares."""
    place(PLAIN, SHOOTER)
    place(NEIGHBOUR, ORC_SHOOTER)
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
    the_board(client)
    answer = client.get("/game/state").json
    assert answer["changed"] is True
    assert len(answer["pieces"]) == len(current_game.SCENARIO)
    assert answer["phase"]["side"] == current_game.TURN.active_side


def test_the_state_returns_only_the_number_while_nothing_moves(client):
    """And the game it is the state of: the version counts the moves of the process, not of one
    game, so a tab whose game was swapped out under it would otherwise read "nothing has moved"."""
    the_board(client)
    version = client.get("/game/state").json["version"]
    answer = client.get("/game/state", query_string={"version": version}).json
    assert answer == {"game": current_game.GAME_ID, "version": version, "changed": False}


def test_a_move_played_raises_the_version(client):
    the_board(client)
    version = client.get("/game/state").json["version"]
    client.post("/phase/next")
    assert client.get("/game/state").json["version"] > version


def test_the_state_tells_the_phase_the_opponent_reached(client):
    """The use case: the other has passed their phase, and the page learns it without reloading."""
    the_board(client)
    version = client.get("/game/state").json["version"]
    client.post("/phase/next")

    answer = client.get("/game/state", query_string={"version": version}).json

    assert answer["changed"] is True
    assert answer["phase"]["label"] == current_game.TURN.label


def test_a_move_shows_in_the_state(client, deserted_map):
    the_board(client)
    origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
    destination = current_game.BOARD.moves(origin)[0]
    version = client.get("/game/state").json["version"]
    client.post("/move", json={"origin": origin.to_dict(), "destination": destination.to_dict(),
                               "piece": current_game.BOARD.piece_on(origin).key})

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
    the_board(client)
    first = client.get("/game/state").json["pieces"]
    client.post("/phase/next")
    second = client.get("/game/state").json["pieces"]
    assert [piece["tilt"] for piece in first] == [piece["tilt"] for piece in second]


def test_only_the_moved_piece_changes_tilt_in_the_state(client):
    the_board(client)
    origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
    destination = current_game.BOARD.moves(origin)[0]
    before = {(piece["q"], piece["r"], piece["s"]): piece["tilt"]
              for piece in client.get("/game/state").json["pieces"]}

    client.post("/move", json={"origin": origin.to_dict(), "destination": destination.to_dict(),
                               "piece": current_game.BOARD.piece_on(origin).key})

    after = {(piece["q"], piece["r"], piece["s"]): piece["tilt"]
             for piece in client.get("/game/state").json["pieces"]}
    del before[(origin.q, origin.r, origin.s)]
    del after[(destination.q, destination.r, destination.s)]
    assert after == before


def test_the_state_is_public(anonymous_client):
    """A passing visitor follows the game as they see the map."""
    assert anonymous_client.get("/game/state").status_code == 200


def test_the_state_says_who_holds_which_side(client):
    the_board(client)
    table = client.get("/game/state").json["table"]
    assert table["seats"] == {side: "Joueuse d'essai" for side in current_game.SCENARIO.sides}
