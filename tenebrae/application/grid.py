"""Alignment of the hexagon grid on `map.jpg`, as the JavaScript receives it.

Recorded in `game_box/map.md`:

    centre(q, r) = ORIGIN + MATRIX . (q, r)

The browser does the conversion from cube coordinates to pixels; the server only passes these
constants along, to the board as to the map-fixing page.
"""

GRID_ORIGIN = [76.355, 70.511]
GRID_MATRIX = [[107.5724, -0.3407], [62.8901, 125.6828]]

# Side of a piece, in pixels of map.jpg (a hexagon is about 143 px from vertex to vertex).
PIECE_SIZE = 104
