"""What the browser displays: the pieces placed, centred and tilted on the map.

These engine require Chromium (`python3 -m playwright install chromium`).
"""

import math

import pytest

from tenebrae.application import app
from tenebrae.engine.hexagon import MAP, Hex
from tenebrae.engine.piece import CATALOGUE, OPPONENTS


@pytest.fixture
def board(page, server, application, seat_the_player):
    """Opens the page **logged in** and waits for the map and the scenario's units to load.

    The first `goto` is the browser equivalent of `session_transaction`: rather than fabricate a
    cookie, we unroll the real login flow, which the fake Discord client closes on our own return
    route. The browser leaves from there for "/", and the game page is loaded and logged in in a
    single movement.
    """
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(app.SCENARIO)
    )
    page.wait_for_function(
        "[...document.querySelectorAll('img.piece'), document.getElementById('map')]"
        ".every((i) => i.complete && i.naturalWidth > 0)"
    )
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def expected_centre(q, r):
    """centre(q, r) = origin + matrix . (q, r), in pixels of map.jpg (game_box/map.md)."""
    origin, matrix = app.GRID_ORIGIN, app.GRID_MATRIX
    return (origin[0] + matrix[0][0] * q + matrix[0][1] * r,
            origin[1] + matrix[1][0] * q + matrix[1][1] * r)


def piece_geometry(page, selector="img.piece:not(.ghost)"):
    """Returns, for each image matching `selector`, its rendered position in map.jpg pixels."""
    return page.evaluate("""(selector) => {
        const map = document.getElementById('map');
        const mapBox = map.getBoundingClientRect();
        const scale = mapBox.width / map.naturalWidth;
        return [...document.querySelectorAll(selector)].map((piece) => {
            const box = piece.getBoundingClientRect();
            const matrix = new DOMMatrix(getComputedStyle(piece).transform);
            return {
                q: Number(piece.dataset.q),
                r: Number(piece.dataset.r),
                s: Number(piece.dataset.s),
                x: (box.x + box.width / 2 - mapBox.x) / scale,
                y: (box.y + box.height / 2 - mapBox.y) / scale,
                angle: Math.atan2(matrix.b, matrix.a) * 180 / Math.PI,
                width: piece.offsetWidth,
                scale: scale,
                opacity: Number(getComputedStyle(piece).opacity),
            };
        });
    }""", selector)


def test_the_map_is_displayed(board):
    game_map = board.evaluate(
        "() => { const m = document.getElementById('map');"
        " return {w: m.naturalWidth, h: m.naturalHeight}; }"
    )
    assert (game_map["w"], game_map["h"]) == (6173, 5102)


def test_the_scenarios_units_are_placed(board):
    assert board.locator("img.piece").count() == len(app.SCENARIO)


def test_the_piece_images_load(board):
    assert board.evaluate(
        "() => [...document.querySelectorAll('img.piece')].every((i) => i.naturalWidth > 0)"
    )


def test_each_piece_is_centred_on_its_hexagon(board):
    """The piece's rendered centre falls on the hexagon's centre, to within a pixel."""
    for piece in piece_geometry(board):
        x, y = expected_centre(piece["q"], piece["r"])
        assert math.isclose(piece["x"], x, abs_tol=1.0), piece
        assert math.isclose(piece["y"], y, abs_tol=1.0), piece


def test_each_piece_is_tilted_by_less_than_five_degrees(board):
    for piece in piece_geometry(board):
        assert abs(piece["angle"]) <= 5.0, piece


def test_the_tilts_are_drawn_at_random(board):
    """Pieces all at the same tilt would betray a frozen rotation.

    The tilts are written to two decimals (`toFixed(2)` in map.js): they take only a thousand and
    one values, and forty-eight draws give a handful of duplicates among them - a little over one
    on average, sometimes five. Demanding forty-eight distinct values, or nearly, therefore made
    the test fail once in a few dozen runs without anything being broken. What we want to catch is
    a frozen rotation, which would give only one value: half the values distinct leaves chance all
    its margin and leaves it no way out.
    """
    angles = [piece["angle"] for piece in piece_geometry(board)]
    assert len(set(angles)) > len(angles) / 2
    assert any(angle < 0 for angle in angles) and any(angle > 0 for angle in angles)


def angles_by_square(page):
    """Each placed piece's angle, by "q,r,s" square - read off the rendered rotation."""
    return {f"{piece['q']},{piece['r']},{piece['s']}": round(piece["angle"], 2)
            for piece in piece_geometry(page)}


def let_the_opponent_play(page, server):
    """Plays a move outside the page - as the other browser would - and waits for it to see it.

    The state is then laid out again in full: that is the moment when a tilt drawn by the page,
    and not by the server, would show. The phase label is what says the resumption has happened;
    it is refreshed just after the pieces.
    """
    assert page.request.post(f"{server}/phase/next").ok
    page.wait_for_function(
        "document.getElementById('phase-label').textContent === 'Phase de combat — Nains'")


def test_the_pieces_keep_their_tilt_when_the_scene_is_laid_out_again(board, server):
    """What used to be disturbing: the counters spun at every poll of the game state.

    The tilt is part of the game state - the server draws it when placing and keeps it (see
    `tenebrae/engine/board.py`) - so the page lays it out again as it is.
    """
    before = angles_by_square(board)
    let_the_opponent_play(board, server)
    assert angles_by_square(board) == before


def test_the_moved_piece_lies_down_once_and_keeps_its_angle(board, server):
    """The only moment when the angle changes, and it does not change again at the next update."""
    piece, origin, _ = a_piece_that_can_move(board)
    before = angles_by_square(board)
    show_the_ghosts(board, piece)
    ghost = board.locator("img.ghost").last
    destination = ghost.evaluate("g => `${g.dataset.q},${g.dataset.r},${g.dataset.s}`")
    ghost.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    after = angles_by_square(board)
    assert after[destination] != before[origin.key], "the piece lay down on the same side"
    # The others were not touched: they were not picked up.
    assert {square: angle for square, angle in after.items() if square != destination} \
        == {square: angle for square, angle in before.items() if square != origin.key}

    let_the_opponent_play(board, server)
    assert angles_by_square(board) == after


def test_the_pieces_have_the_expected_size(board):
    for piece in piece_geometry(board):
        assert piece["width"] == app.PIECE_SIZE


def test_the_board_fits_in_the_window(board):
    overflow = board.evaluate(
        "() => ({ w: document.documentElement.scrollWidth - window.innerWidth,"
        "         h: document.documentElement.scrollHeight - window.innerHeight })"
    )
    assert overflow["w"] <= 0 and overflow["h"] <= 0


def test_the_board_follows_resizing(board):
    """After a resize, the map stays scaled and the pieces in their places."""
    before = piece_geometry(board)[0]["scale"]
    board.set_viewport_size({"width": 900, "height": 600})
    board.wait_for_function("() => window.innerWidth === 900 && window.innerHeight === 600")
    board.evaluate("() => new Promise(requestAnimationFrame)")
    after = piece_geometry(board)
    assert after[0]["scale"] < before
    for piece in after:
        x, y = expected_centre(piece["q"], piece["r"])
        assert math.isclose(piece["x"], x, abs_tol=1.0), piece
        assert math.isclose(piece["y"], y, abs_tol=1.0), piece


# --- Zoom -------------------------------------------------------------------------------------


def rendered_scale(page):
    """The scale at which the map is rendered, read off the image itself."""
    return page.evaluate(
        "() => { const m = document.getElementById('map');"
        " return m.getBoundingClientRect().width / m.naturalWidth; }")


def zoom_in(page, notches=1):
    """Clicks "+" and waits for the displayed scale to change."""
    for _ in range(notches):
        before = page.locator("#scale").text_content()
        page.locator("#zoom-in").click()
        page.wait_for_function(
            "(start) => document.getElementById('scale').textContent !== start", arg=before)


def test_the_zoom_buttons_change_the_scale(board):
    fitted = rendered_scale(board)
    zoom_in(board)
    assert rendered_scale(board) > fitted

    board.locator("#fit").click()
    board.wait_for_function(
        "(fitted) => { const m = document.getElementById('map');"
        " return Math.abs(m.getBoundingClientRect().width / m.naturalWidth - fitted) < 1e-6; }",
        arg=fitted)


def test_the_wheel_zooms_the_map_in(board):
    """Zooming in with the wheel keeps under the pointer the map point it was designating."""
    x, y = expected_centre(28, 15)
    pointer = board.evaluate("""([x, y]) => {
        const map = document.getElementById('map');
        const box = map.getBoundingClientRect();
        const scale = box.width / map.naturalWidth;
        return [box.x + x * scale, box.y + y * scale];
    }""", [x, y])

    fitted = rendered_scale(board)
    board.mouse.move(*pointer)
    board.mouse.wheel(0, -300)
    board.wait_for_function(
        "(fitted) => { const m = document.getElementById('map');"
        " return m.getBoundingClientRect().width / m.naturalWidth > fitted; }", arg=fitted)

    # The point of map.jpg now under the pointer: to within a few screen pixels, the same one.
    aimed = board.evaluate("""([cx, cy]) => {
        const map = document.getElementById('map');
        const box = map.getBoundingClientRect();
        const scale = box.width / map.naturalWidth;
        return [(cx - box.x) / scale, (cy - box.y) / scale];
    }""", list(pointer))
    assert math.isclose(aimed[0], x, abs_tol=30), aimed
    assert math.isclose(aimed[1], y, abs_tol=30), aimed


def test_the_pieces_stay_on_their_hexagon_once_zoomed_in(board):
    """The zoom touches only the scale: the pieces are placed in map.jpg pixels."""
    zoom_in(board, notches=3)
    placed = piece_geometry(board)
    assert placed[0]["scale"] > 0

    for piece in placed:
        x, y = expected_centre(piece["q"], piece["r"])
        assert math.isclose(piece["x"], x, abs_tol=1.0), piece
        assert math.isclose(piece["y"], y, abs_tol=1.0), piece


def test_resizing_does_not_undo_the_zoom(board):
    """The map follows the window as long as one has not set the scale oneself."""
    zoom_in(board)
    zoomed = rendered_scale(board)

    board.set_viewport_size({"width": 900, "height": 600})
    board.wait_for_function("() => window.innerWidth === 900 && window.innerHeight === 600")
    board.evaluate("() => new Promise(requestAnimationFrame)")
    assert math.isclose(rendered_scale(board), zoomed, rel_tol=1e-6)


# --- Ghosts and moving --------------------------------------------------------------------------


def pieces_that_can_move(page, suits=lambda piece: True):
    """The page's pieces that have squares to go to, and that `suits` accepts.

    The reach is the one the **server's board** computes: the counter's movement, minus what the
    opponents placed around it forbid. The test server runs in this process, so its board can be
    read directly.
    """
    for index in range(len(app.SCENARIO)):
        piece = page.locator("img.piece:not(.ghost)").nth(index)
        position = piece.evaluate(
            "p => [Number(p.dataset.q), Number(p.dataset.r), Number(p.dataset.s)]")
        origin = Hex(*position)
        reachable = app.BOARD.moves(origin)
        if reachable and suits(app.BOARD.piece_on(origin)):
            yield piece, origin, reachable


def a_piece_that_can_move(page, suits=lambda piece: True):
    """The first piece of the page that has squares to go to."""
    for candidate in pieces_that_can_move(page, suits):
        return candidate
    raise AssertionError("no unit of the scenario can move")


def ghosts(page):
    return piece_geometry(page, "img.ghost")


def show_the_ghosts(page, piece):
    """Clicks the piece and waits for its ghosts."""
    piece.click()
    page.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    return ghosts(page)


def test_clicking_a_piece_shows_its_moves(board):
    piece, origin, reachable = a_piece_that_can_move(board)
    placed = show_the_ghosts(board, piece)

    assert len(placed) == len(reachable)
    assert {(g["q"], g["r"], g["s"]) for g in placed} == {(h.q, h.r, h.s) for h in reachable}
    assert (origin.q, origin.r, origin.s) not in {(g["q"], g["r"], g["s"]) for g in placed}


def test_the_ghosts_follow_the_counters_movement(board):
    """The number of ghosts is that of the piece's movement, not of a common flat rate."""
    piece, origin, _ = a_piece_that_can_move(board)
    movement = app.BOARD.piece_on(origin).movement_points
    placed = show_the_ghosts(board, piece)

    assert len(placed) == len(app.BOARD.moves(origin))
    assert len(placed) <= len(origin.moves(movement))


def contact_with_an_opponent(page):
    """Places an opponent adjacent to a piece of the page, and returns the figure obtained.

    The enemy is placed on the server's board with no image on the map: what we want to exercise is
    the chain from click to rule, not the display of that piece. We look for a figure where
    something is left to show - a cornered piece would have no ghost, and there would be nothing to
    compare. A unit caught in the middle of its army has no free neighbouring square: it will not
    do either, and we move on to the next.
    """
    for piece, origin, alone in pieces_that_can_move(page, engaged):
        neighbour = next((n for n in origin.neighbours() if n in alone), None)
        if neighbour is None:
            continue
        app.BOARD.place(neighbour, opponent_of(app.BOARD.piece_on(origin)))
        in_contact = app.BOARD.moves(origin)
        if 0 < len(in_contact) < len(alone):
            return piece, origin, alone, neighbour
        app.BOARD.remove(neighbour)
    pytest.skip("no unit of the scenario has a neighbour to place an opponent on")


def test_the_ghosts_stop_in_front_of_the_opponent(board):
    """An opponent placed in contact reduces what the click displays."""
    piece, _, alone, neighbour = contact_with_an_opponent(board)

    placed = show_the_ghosts(board, piece)
    assert len(placed) < len(alone)
    assert (neighbour.q, neighbour.r, neighbour.s) not in {(g["q"], g["r"], g["s"])
                                                           for g in placed}


def engaged(piece):
    """Says whether the piece belongs to a side: a neutral has no opponent to oppose it."""
    return piece.side in OPPONENTS


def opponent_of(piece):
    """A piece of the opposing side, taken from the catalogue."""
    return next(other for other in CATALOGUE.values()
                if other.side == OPPONENTS[piece.side] and other.is_a_unit)


# --- The hovered unit's card ---------------------------------------------------------------------


def read_card(page):
    """What the card is showing right now: its state, its texts and its values."""
    return page.evaluate("""() => {
        const pairs = [...document.getElementById('card-values').children];
        const values = {};
        for (let i = 0; i < pairs.length; i += 2) {
            values[pairs[i].textContent] = pairs[i + 1].textContent;
        }
        const image = document.getElementById('card-image');
        const remarks = document.getElementById('card-remarks');
        return {
            hidden: document.getElementById('card').hidden,
            name: document.getElementById('card-name').textContent,
            extra: document.getElementById('card-extra').textContent,
            symbol: document.getElementById('card-symbol').textContent,
            values: values,
            remarks: remarks.hidden ? null : remarks.textContent,
            source: image.src,
            loaded: image.complete && image.naturalWidth > 0,
        };
    }""")


def hover(page, piece):
    """Hovers the piece and waits for its card to appear; returns what it shows."""
    piece.hover()
    page.wait_for_function("() => !document.getElementById('card').hidden")
    return read_card(page)


def leave_the_piece(page):
    """Moves the pointer away from any piece, and waits for the card to close."""
    page.mouse.move(1, 1)
    page.wait_for_function("() => document.getElementById('card').hidden")


def as_written_on_the_card(value):
    """The value as the card writes it: what the counter does not carry becomes a dash."""
    return "—" if value is None else str(value)


def test_the_card_is_hidden_until_a_piece_is_hovered_and_again_after(board):
    assert read_card(board)["hidden"]
    piece = board.locator("img.piece:not(.ghost)").first
    assert not hover(board, piece)["hidden"]
    leave_the_piece(board)
    assert read_card(board)["hidden"]


def test_hovering_a_piece_shows_its_counters_values(board):
    """Every placed unit shows, on hover, what its counter carries - and nothing invented.

    The remarks line is part of it: it appears exactly when the counter has a remark, which is why
    `seen` counts both cases and the walk refuses to pass if the scenario offers only one.
    """
    seen = {True: 0, False: 0}
    for index in range(len(app.SCENARIO)):
        piece = board.locator("img.piece:not(.ghost)").nth(index)
        key = piece.evaluate("p => p.piece.key")
        placed = CATALOGUE[key]

        card = hover(board, piece)
        assert card["values"] == {
            "Force": as_written_on_the_card(placed.strength),
            "Mouvement": str(placed.movement_points),
            "Tir": as_written_on_the_card(placed.fire),
            "Portée": as_written_on_the_card(placed.range),
            "Vol": as_written_on_the_card(placed.flight_movement),
            "Facultés": as_written_on_the_card(placed.special_abilities),
        }, key
        assert card["symbol"] == as_written_on_the_card(placed.symbol), key
        # A remark is what the photograph leaves open: no remark, no line.
        assert card["remarks"] == placed.remarks, key
        seen[placed.remarks is None] += 1
        leave_the_piece(board)

    assert seen[True] and seen[False], (
        "the scenario must carry pieces with and without a remark for the walk to be worth it")


def test_the_card_states_the_piece_and_shows_its_photograph(board):
    """Name, side and square in words - and the counter itself, which is where it is really read:
    the fitted map shows only a dozen pixels of it."""
    piece = board.locator("img.piece:not(.ghost)").first
    key, square, source = piece.evaluate(
        "p => [p.piece.key, `${p.dataset.q},${p.dataset.r},${p.dataset.s}`, p.src]")

    card = hover(board, piece)
    assert card["name"] == app.PIECES_BY_KEY[key]["name"]
    assert card["extra"] == f"{CATALOGUE[key].side} — {square}"
    assert card["source"] == source
    assert card["loaded"]


def test_hovering_a_ghost_shows_no_card(board):
    """A ghost repeats the selected unit: its card would teach nothing."""
    piece, _, _ = a_piece_that_can_move(board)
    show_the_ghosts(board, piece)
    leave_the_piece(board)

    board.locator("img.ghost").last.hover()
    assert read_card(board)["hidden"]


def test_the_card_states_the_square_the_piece_has_just_reached(board):
    """Once the piece has moved, its card must give its new square, not the scenario's."""
    piece, origin, _ = a_piece_that_can_move(board)
    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    board.locator("img.ghost").last.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    square = piece.evaluate("p => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`")
    assert square != origin.key
    assert hover(board, piece)["extra"].endswith(f"— {square}")


def test_the_card_sits_under_the_bar_of_zoom_buttons(board):
    """The card is not a box placed anywhere on the map: it is under the bar.

    It used to be in the bar, following the buttons; for that it had to stay tiny on pain of
    lengthening it. Moved down a notch, it has room to be read, and the panel still keeps it in the
    corner the bar already occupies.
    """
    assert board.locator("#panel > #toolbar").count() == 1
    assert board.locator("#panel > #card").count() == 1

    piece = board.locator("img.piece:not(.ghost)").first
    hover(board, piece)
    places = board.evaluate("""() => {
        const box = (id) => document.getElementById(id).getBoundingClientRect();
        const toolbar = box('toolbar');
        const card = box('card');
        return { bar: [toolbar.bottom, toolbar.left], card: [card.top, card.left] };
    }""")
    assert places["card"][0] >= places["bar"][0], places  # under the bar
    assert places["card"][1] == places["bar"][1], places  # aligned on its left edge


def test_the_card_reads_at_the_size_of_the_bar(board):
    """The box takes the toolbar's font size: both read to the same eye.

    This is the correction of the 0.1875rem - three pixels - the card had been reduced to in order
    to fit in the bar without enlarging it.
    """
    hover(board, board.locator("img.piece:not(.ghost)").first)
    sizes = board.evaluate("""() => ['toolbar', 'card'].map(
        (id) => getComputedStyle(document.getElementById(id)).fontSize)""")
    assert sizes[0] == sizes[1], sizes
    assert float(sizes[1].removesuffix("px")) >= 12, sizes


def test_the_card_does_not_move_from_one_piece_to_another(board):
    """The bar is fixed in place: hovering another unit does not displace it."""
    corners = set()
    for index in range(len(app.SCENARIO)):
        piece = board.locator("img.piece:not(.ghost)").nth(index)
        hover(board, piece)
        corners.add(tuple(board.evaluate(
            "() => { const c = document.getElementById('toolbar').getBoundingClientRect();"
            "        return [Math.round(c.x), Math.round(c.y)]; }")))
    assert len(corners) == 1, corners


def test_the_cards_elements_are_stacked(board):
    """One element per line, from the name to the remarks: each begins under the previous one.

    The thumbnail, for its part, stays beside the stack - the counter is recognised at a glance
    while its values are read.
    """
    piece = board.locator("img.piece:not(.ghost)").first
    hover(board, piece)

    places = board.evaluate("""() => {
        const box = (id) => {
            const c = document.getElementById(id).getBoundingClientRect();
            return { top: c.top, left: c.left, bottom: c.bottom, right: c.right };
        };
        return {
            stacked: ['card-name', 'card-extra', 'card-symbol', 'card-values'].map(box),
            thumbnail: box('card-image'),
            text: box('card-text'),
        };
    }""")

    for previous, following in zip(places["stacked"], places["stacked"][1:]):
        assert following["top"] >= previous["bottom"], places["stacked"]
        assert following["left"] == previous["left"], places["stacked"]

    assert places["thumbnail"]["right"] <= places["text"]["left"]


def toolbar_height(page):
    return page.evaluate(
        "() => Math.round(document.getElementById('toolbar').getBoundingClientRect().height)")


def test_the_bar_keeps_its_size_when_the_card_appears(board):
    """The toolbar keeps the reference size map.css documents: the same height, card open or not,
    and at any window width.

    That is what the todo asked to preserve. The card is now under the bar rather than inside it,
    so it can no longer lengthen it; the fact remains that the bar still does not wrap - wrapping
    would double its height - it lets itself be clipped on the right. Hovering is simulated here
    rather than played with the mouse: once the window is narrowed, the piece aimed at may end up
    under the bar, out of the pointer's reach, and what is exercised is the layout, not the
    pointing.
    """
    # The piece with the longest label: it is the one that lengthens the bar most.
    index = board.evaluate("""() => {
        const pieces = [...document.querySelectorAll('img.piece:not(.ghost)')];
        const widest = pieces.slice().sort((a, b) =>
            (b.piece.name + (b.piece.remarks ?? '')).length
            - (a.piece.name + (a.piece.remarks ?? '')).length)[0];
        return pieces.indexOf(widest);
    }""")
    hovering = """([index, event]) => {
        const piece = document.querySelectorAll('img.piece:not(.ghost)')[index];
        piece.dispatchEvent(new MouseEvent(event, { bubbles: true }));
    }"""

    for width in (1400, 800):
        board.set_viewport_size({"width": width, "height": 900})
        board.wait_for_function("(w) => window.innerWidth === w", arg=width)
        board.evaluate(hovering, [index, "mouseout"])
        bare = toolbar_height(board)

        board.evaluate(hovering, [index, "mouseover"])
        assert not read_card(board)["hidden"]
        assert toolbar_height(board) == bare, width


def test_the_panel_does_not_overflow_the_window(board):
    """At any width, the panel fits in the window and the page does not scroll sideways.

    Moving the card down under the bar gave it back some room, but it now takes room in height as
    well as in width: it must nonetheless neither leave the screen nor push the map.
    """
    index = board.evaluate("""() => {
        const pieces = [...document.querySelectorAll('img.piece:not(.ghost)')];
        const widest = pieces.slice().sort((a, b) =>
            (b.piece.name + (b.piece.remarks ?? '')).length
            - (a.piece.name + (a.piece.remarks ?? '')).length)[0];
        return pieces.indexOf(widest);
    }""")
    hovering = """(index) => {
        const piece = document.querySelectorAll('img.piece:not(.ghost)')[index];
        piece.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    }"""

    for width in (1400, 800, 480):
        board.set_viewport_size({"width": width, "height": 900})
        board.wait_for_function("(w) => window.innerWidth === w", arg=width)
        board.evaluate(hovering, index)
        assert not read_card(board)["hidden"]

        measurements = board.evaluate("""() => {
            const panel = document.getElementById('panel').getBoundingClientRect();
            return { right: panel.right, bottom: panel.bottom,
                     width: window.innerWidth, height: window.innerHeight,
                     scrolls: document.documentElement.scrollWidth > window.innerWidth };
        }""")
        assert measurements["right"] <= measurements["width"], (width, measurements)
        assert measurements["bottom"] <= measurements["height"], (width, measurements)
        assert not measurements["scrolls"], (width, measurements)


def test_the_map_stays_whole_under_the_panel(board):
    """The panel sits on top of the map; it neither shrinks nor displaces it.

    It is fixed in place, out of the flow: the map occupies the window as if it did not exist,
    card open or not.
    """
    box = "() => { const c = document.getElementById('map').getBoundingClientRect();"\
          "        return [Math.round(c.x), Math.round(c.y),"\
          "                Math.round(c.width), Math.round(c.height)]; }"
    bare = board.evaluate(box)
    hover(board, board.locator("img.piece:not(.ghost)").first)
    assert board.evaluate(box) == bare


def test_the_card_does_not_capture_clicks(board):
    """The bar carries buttons, but the card lets the click through to the map: without which it
    would make the strip of map it covers unplayable."""
    piece = board.locator("img.piece:not(.ghost)").first
    hover(board, piece)
    assert board.evaluate("""() => {
        const card = document.getElementById('card');
        const box = card.getBoundingClientRect();
        const aimed = document.elementFromPoint(box.x + box.width / 2,
                                                box.y + box.height / 2);
        return aimed === null || !card.contains(aimed);
    }""")


def test_a_ghost_is_the_piece_itself_shown_half_transparent_on_a_reachable_square(board):
    """The unit's own image, at half opacity, centred and tilted on the hexagon it could reach:
    one selection says all of it, and laying the scene out again for each facet would say no
    more."""
    piece, _, _ = a_piece_that_can_move(board)
    source = piece.evaluate("p => p.src")
    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")

    assert board.evaluate(
        "(src) => [...document.querySelectorAll('img.ghost')].every((g) => g.src === src)", source
    )
    for ghost in ghosts(board):
        assert ghost["opacity"] == 0.5
        x, y = expected_centre(ghost["q"], ghost["r"])
        assert math.isclose(ghost["x"], x, abs_tol=1.0), ghost
        assert math.isclose(ghost["y"], y, abs_tol=1.0), ghost
        assert abs(ghost["angle"]) <= 5.0, ghost


def test_clicking_a_zoomed_in_piece_shows_its_moves(board):
    """The click aims at the right hexagon whatever the scale."""
    piece, _, reachable = a_piece_that_can_move(board)
    zoom_in(board, notches=2)
    piece.scroll_into_view_if_needed()

    placed = show_the_ghosts(board, piece)
    assert {(g["q"], g["r"], g["s"]) for g in placed} == {(h.q, h.r, h.s) for h in reachable}


def test_clicking_a_ghost_moves_the_piece(board):
    piece, origin, _ = a_piece_that_can_move(board)
    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")

    target = board.locator("img.ghost").last
    destination = target.evaluate(
        "g => [Number(g.dataset.q), Number(g.dataset.r), Number(g.dataset.s)]")
    target.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    # The unit is found at its square, and no longer at the one it came from. We look for it on the
    # board rather than keeping hold of its image: the move played comes straight back through the
    # stream (see `test_stream_browser.py`), and the scene laid out again recreates every image.
    # The `piece` from before the click then no longer designates the same unit - which the old
    # poll's three seconds used to hide.
    squares = {(p["q"], p["r"], p["s"]) for p in piece_geometry(board)}
    assert tuple(destination) in squares
    assert (origin.q, origin.r, origin.s) not in squares
    assert destination != [origin.q, origin.r, origin.s]

    placed = next(p for p in piece_geometry(board)
                  if [p["q"], p["r"], p["s"]] == destination)
    x, y = expected_centre(*destination[:2])
    assert math.isclose(placed["x"], x, abs_tol=1.0) and math.isclose(placed["y"], y, abs_tol=1.0)
    assert abs(placed["angle"]) <= 5.0

    # A move moves: it neither loses a counter nor draws a second one.
    assert board.locator("img.piece:not(.ghost)").count() == len(app.SCENARIO)


def test_giving_up_a_selection_erases_the_ghosts(board):
    """Two ways of changing one's mind: clicking the unit again, or clicking a square with neither
    piece nor ghost on it."""
    piece, origin, reachable = a_piece_that_can_move(board)
    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")

    occupied = set(board.evaluate(
        "() => [...document.querySelectorAll('img.piece:not(.ghost)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))
    forbidden = {hexagon.key for hexagon in reachable} | {origin.key} | occupied
    click_the_hexagon(board, an_uncovered_hexagon(board, forbidden))
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")


def point_of_the_hexagon(page, hexagon):
    """The hexagon's centre in screen pixels, at the scale the map is rendered."""
    x, y = expected_centre(hexagon.q, hexagon.r)
    return page.evaluate("""([x, y]) => {
        const map = document.getElementById('map');
        const box = map.getBoundingClientRect();
        const scale = box.width / map.naturalWidth;
        return [box.x + x * scale, box.y + y * scale];
    }""", [x, y])


def click_the_hexagon(page, hexagon):
    """Clicks at the centre of the hexagon, in screen pixels."""
    page.mouse.click(*point_of_the_hexagon(page, hexagon))


def an_uncovered_hexagon(page, forbidden):
    """The first hexagon outside `forbidden` that a click really reaches.

    The toolbar sits over the top-left corner of the map, and the window shows only part of it once
    zoomed in: a click landing there would never reach the board.
    """
    for key in MAP:
        if key in forbidden:
            continue
        hexagon = Hex.from_key(key)
        x, y = point_of_the_hexagon(page, hexagon)
        if page.evaluate("([x, y]) => document.getElementById('board')"
                         ".contains(document.elementFromPoint(x, y))", [x, y]):
            return hexagon
    raise AssertionError("no free hexagon is clickable")


# --- Locating the last clicked piece
# ---------------------------------------------------------------


def a_centrable_piece(page):
    """The scenario's piece furthest from the map's right edge.

    Scenario 4 puts all its units in the east of the map: zoomed in, the one nearest the edge
    cannot come to the middle of the window - the scroll stops first. This one can, at the scales
    these engine work at.
    """
    index = page.evaluate("""() => {
        const placed = [...document.querySelectorAll('img.piece:not(.ghost)')];
        const x = (piece) => parseFloat(piece.style.left);
        return placed.indexOf(placed.reduce((a, b) => (x(a) <= x(b) ? a : b)));
    }""")
    return page.locator("img.piece:not(.ghost)").nth(index)


def offset_from_the_centre(piece):
    """By how many screen pixels the piece misses the middle of the frame, in x and in y."""
    return piece.evaluate("""(piece) => {
        const frame = document.getElementById('frame');
        const placed = piece.getBoundingClientRect();
        return [Math.abs(placed.x + placed.width / 2 - frame.clientWidth / 2),
                Math.abs(placed.y + placed.height / 2 - frame.clientHeight / 2)];
    }""")


def can_come_to_the_centre(piece):
    """Says whether half a window of map is left on each side of the piece.

    Without that the scroll stops before having brought the piece to the middle, and the map does
    not have to uncover empty space to offer it: the button then does what it can, not what is
    measured here.
    """
    return piece.evaluate("""(piece) => {
        const frame = document.getElementById('frame');
        const map = document.getElementById('map');
        const rendered = map.getBoundingClientRect();
        const scale = rendered.width / map.naturalWidth;
        const x = parseFloat(piece.style.left) * scale;
        const y = parseFloat(piece.style.top) * scale;
        return x >= frame.clientWidth / 2 && x <= rendered.width - frame.clientWidth / 2
            && y >= frame.clientHeight / 2 && y <= rendered.height - frame.clientHeight / 2;
    }""")


def zoom_in_until_it_can_be_centred(page, piece):
    """Zooms in notch by notch until the piece can come to the middle of the window.

    Scenario 4 puts its units near the eastern edge of the map: one has to zoom in a fair way
    before half a window fits between them and the edge.
    """
    while not can_come_to_the_centre(piece):
        if page.locator("#scale").text_content() == "100 %":
            pytest.skip("no scale brings this piece to the centre: it is too close to the edge")
        zoom_in(page, notches=1)


def test_the_locate_button_is_off_while_no_piece_has_been_clicked(board):
    assert board.locator("#locate").is_disabled()


def test_the_locate_button_fits_in_the_bar(board):
    """The bar is `overflow: hidden`: one button too many would be clipped there silently."""
    overflow = board.evaluate("""() => {
        const toolbar = document.getElementById('toolbar').getBoundingClientRect();
        const button = document.getElementById('locate').getBoundingClientRect();
        return toolbar.right - button.right;
    }""")
    assert overflow >= 0, overflow


def test_clicking_a_piece_turns_the_locate_button_on(board):
    a_centrable_piece(board).click()
    assert board.locator("#locate").is_enabled()


def test_locate_brings_the_last_clicked_piece_back_to_the_centre(board):
    """Zooming into the map drives away the unit one is manoeuvring; the button recalls it."""
    piece = a_centrable_piece(board)
    piece.click()
    zoom_in_until_it_can_be_centred(board, piece)
    # The buttons' zoom keeps the centre of the window: the piece, placed east, is far from it.
    assert max(offset_from_the_centre(piece)) > 50

    board.locator("#locate").click()
    offset = offset_from_the_centre(piece)
    assert offset[0] <= 2 and offset[1] <= 2, offset


def a_movable_piece_that_can_be_centred(page):
    """Among the units that have somewhere to go, the one furthest from the map's right edge.

    The counterpart of `a_centrable_piece` for a unit that is going to move: scenario 4 places all
    its units in the east, and the button can only bring to the middle of the window a piece with
    half a window of map left on each side of it.

    A **Dwarf**: the map opens on their movement phase, and clicking a unit of the other side
    would show no ghost at all.
    """
    candidates = list(pieces_that_can_move(page, lambda piece: piece.side == "alliance"))
    assert candidates, "no Dwarf of the scenario can move"
    return min(candidates, key=lambda candidate: expected_centre(candidate[1].q, candidate[1].r)[0])


def test_locate_follows_the_piece_that_has_moved(board):
    """The button keeps the counter, not the square: once moved, it is where it is that we find
    it.

    The unit is looked up **by its square** once the move is played, and not through the rank it
    held before: the move comes straight back through the stream, the scene is laid out again and
    every image recreated, so the locator from before the click no longer designates the same unit
    (the same precaution as in `test_clicking_a_ghost_moves_the_piece`).
    """
    piece, origin, reachable = a_movable_piece_that_can_be_centred(board)
    piece.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")

    # Westernmost of the squares it can reach: scenario 4 crowds the east of the map, and a unit
    # that ends its move against the edge could not be brought to the middle of the window - the
    # scroll would stop first, and the test would measure the scroll's limit, not the button.
    west = min(reachable, key=lambda hexagon: expected_centre(hexagon.q, hexagon.r)[0])
    destination = [west.q, west.r, west.s]
    ghost = board.locator(
        f'img.ghost[data-q="{west.q}"][data-r="{west.r}"][data-s="{west.s}"]')
    ghost.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")
    assert destination != [origin.q, origin.r, origin.s]

    q, r, s = destination
    moved = board.locator(
        f'img.piece:not(.ghost)[data-q="{q}"][data-r="{r}"][data-s="{s}"]')
    moved.wait_for()

    zoom_in_until_it_can_be_centred(board, moved)
    board.locator("#locate").click()
    offset = offset_from_the_centre(moved)
    assert offset[0] <= 2 and offset[1] <= 2, offset


# --- Game phases and combat ----------------------------------------------------------------------


def read_phase(page):
    return page.locator("#phase-label").inner_text()


def move_to_the_combat_phase(page):
    """Clicks "Phase suivante" and waits for the Dwarves' combat phase (magic is skipped)."""
    page.locator("#next-phase").click()
    page.wait_for_function(
        "document.getElementById('phase-label').textContent === 'Phase de combat — Nains'")


def test_the_label_announces_the_phase(board):
    assert read_phase(board) == "Phase de mouvement — Nains"


def test_next_phase_skips_magic(board):
    move_to_the_combat_phase(board)
    assert read_phase(board) == "Phase de combat — Nains"


def test_in_the_combat_phase_movement_no_longer_answers(board):
    piece, _, _ = a_piece_that_can_move(board, lambda p: p.side == "alliance")
    move_to_the_combat_phase(board)
    piece.click()
    board.wait_for_timeout(150)
    assert board.locator("img.ghost").count() == 0


def test_clicking_an_opposing_unit_highlights_it_in_red(board):
    move_to_the_combat_phase(board)
    orc = Hex.from_key(next(key for key, p in app.BOARD.pieces.items()
                            if p.side == "tenebres"))
    click_the_hexagon(board, orc)
    board.wait_for_selector("img.piece.target")
    assert board.locator("img.piece.target").count() == 1


def a_pair_for_combat(page):
    """A Dwarf that can come into contact with an Orc, the contact square, and the Orc."""
    contacts = {neighbour.key: orc
                for key, p in app.BOARD.pieces.items() if p.side == "tenebres"
                for orc in [Hex.from_key(key)] for neighbour in orc.neighbours()}
    for piece, _, reachable in pieces_that_can_move(page, lambda p: p.side == "alliance"):
        for destination in reachable:
            if destination.key in contacts:
                return piece, destination, contacts[destination.key]
    pytest.skip("no Dwarf can come into contact with an Orc")


def test_the_combat_cycle_highlights_the_units_then_frees_them(board, monkeypatch):
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    dwarf, contact, orc = a_pair_for_combat(board)

    dwarf.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    click_the_hexagon(board, contact)
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    move_to_the_combat_phase(board)

    click_the_hexagon(board, orc)
    board.wait_for_selector("img.piece.target")
    click_the_hexagon(board, contact)
    board.wait_for_selector("img.piece.attacker")
    board.wait_for_selector("#attack", state="visible")

    board.locator("#attack").click()
    board.wait_for_function(
        "!document.querySelector('img.piece.target')"
        " && !document.querySelector('img.piece.attacker')")
    board.wait_for_selector("#attack", state="hidden")


def test_the_units_that_have_fought_are_greyed_and_refuse_the_click(board, monkeypatch):
    """A unit fights only once per phase: the map shows it, and the click refuses it.

    The combat's result is not known in advance - the die is fixed, not the pair of units the
    set-up offers - so we query the server's register to find out who must be greyed out, rather
    than bet on an outcome.
    """
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    dwarf, contact, orc = a_pair_for_combat(board)

    dwarf.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    click_the_hexagon(board, contact)
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    move_to_the_combat_phase(board)
    click_the_hexagon(board, orc)
    board.wait_for_selector("img.piece.target")
    click_the_hexagon(board, contact)
    board.wait_for_selector("img.piece.attacker")
    board.locator("#attack").click()
    board.wait_for_selector("#attack", state="hidden")

    # What the server entered, minus the squares the combat cleared: that is what gets greyed out.
    engaged_squares = {key for key in app.REGISTER.engaged_attackers | app.REGISTER.engaged_targets
                       if key in app.BOARD.pieces}
    assert engaged_squares, "the combat engaged nobody"
    board.wait_for_function(
        "(n) => document.querySelectorAll('img.piece.unavailable').length === n",
        arg=len(engaged_squares))
    greyed = set(board.evaluate(
        "() => [...document.querySelectorAll('img.piece.unavailable')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))
    assert greyed == engaged_squares

    # And the click does not take them up again: nothing highlights afresh, in red or in gold.
    for key in engaged_squares:
        click_the_hexagon(board, Hex.from_key(key))
    board.wait_for_timeout(200)
    assert board.locator("img.piece.target").count() == 0
    assert board.locator("img.piece.attacker").count() == 0


def test_the_next_phase_erases_the_greying(board, monkeypatch):
    """Each combat phase starts again with all its units: nothing is greyed out any more."""
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    dwarf, contact, orc = a_pair_for_combat(board)

    dwarf.click()
    board.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    click_the_hexagon(board, contact)
    board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    move_to_the_combat_phase(board)
    click_the_hexagon(board, orc)
    board.wait_for_selector("img.piece.target")
    click_the_hexagon(board, contact)
    board.wait_for_selector("img.piece.attacker")
    board.locator("#attack").click()
    board.wait_for_selector("img.piece.unavailable")

    board.locator("#next-phase").click()  # the Orcs' movement
    board.wait_for_function("!document.querySelector('img.piece.unavailable')")


def test_cancel_removes_the_combat_highlights(board):
    move_to_the_combat_phase(board)
    orc = Hex.from_key(next(key for key, p in app.BOARD.pieces.items()
                            if p.side == "tenebres"))
    click_the_hexagon(board, orc)
    board.wait_for_selector("img.piece.target")
    board.locator("#cancel-combat").click()
    board.wait_for_function("!document.querySelector('img.piece.target')")
