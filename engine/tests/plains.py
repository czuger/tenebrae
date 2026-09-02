"""Terrain landmarks for the movement tests - no test here, only what it takes to write some.

The reference hexagons are not hard-coded: they are looked up on the game map, so that the tests
survive a terrain fix. What we want is a corner of plain wide enough that each step costs exactly
1 point, with no road or path to skew the arithmetic.
"""

from engine.hexagon import MAP, Hex

CORNER_RADIUS = 2                     # the centre, its ring, and the ring beyond
MAXIMUM_BUDGET = 8                    # beyond that, the route being looked for does not exist


def surroundings(hexagon, radius=CORNER_RADIUS):
    """The hexagons at `radius` squares or fewer, the hexagon itself included."""
    reached = {hexagon}
    edge = {hexagon}
    for _ in range(radius):
        edge = {neighbour for centre in edge for neighbour in centre.neighbours()} - reached
        reached |= edge
    return reached


def well_surrounded_plain(radius=CORNER_RADIUS):
    """A plain whose whole neighbourhood within `radius` squares is bare plain."""
    expected_squares = 1 + 3 * radius * (radius + 1)
    for key, elements in MAP.items():
        if elements != ("plaine",):
            continue
        hexagon = Hex.from_key(key)
        neighbourhood = surroundings(hexagon, radius)
        if (len(neighbourhood) == expected_squares
                and all(MAP.get(neighbour.key) == ("plaine",) for neighbour in neighbourhood)):
            return hexagon
    raise AssertionError("no corner of bare plain wide enough on the map")


def ring_of(centre):
    """Three consecutive squares of `centre`'s ring, and one square further out.

    This is the figure of the booklet's example: **C**, **X1** and **X2** follow one another around
    unit **A**, and "further out" is the first square outside its zone of control.
    """
    neighbours = centre.neighbours()
    c = neighbours[0]
    x1 = next(neighbour for neighbour in neighbours if neighbour.distance(c) == 1)
    x2 = next(neighbour for neighbour in neighbours
              if neighbour.distance(x1) == 1 and neighbour != c)
    further = next(neighbour for neighbour in c.neighbours() if neighbour.distance(centre) == 2)
    return c, x1, x2, further


def minimum_budget(origin, target, **rules):
    """The smallest movement putting `target` within `origin`'s reach, or None past the maximum."""
    for budget in range(1, MAXIMUM_BUDGET + 1):
        if target in origin.moves(budget, **rules):
            return budget
    return None
