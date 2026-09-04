// The geometry of the grid, shared by the pages that display the map.
//
// The alignment recorded in tenebrae/game_box/map.md fits into an origin and a 2 x 2 matrix:
//
//     centre(q, r) = origin + matrix . (q, r)
//
// The pixels obtained are those of map.jpg (6173 x 5102), hence the frame of reference of #board,
// which carries the image at its natural size and is only scaled afterwards. Nothing here knows
// the game's rules nor the page's DOM: only numbers and the map image.
//
// The debug log (debug.js, silent unless turned on) says here what the alignment was built with,
// and what a pointer resolves to. `invert`, `centre`, `key` and `vertices` stay mute: they are
// pure arithmetic, called in loops over hundreds of hexagons, and a line each would bury the log
// under numbers nobody reads.

const geometryTrace = debugScope("geometry.js");

function invert([[a, b], [c, d]]) {
  const determinant = a * d - b * c;
  return [[d / determinant, -b / determinant], [-c / determinant, a / determinant]];
}

function alignment(grid) {
  const [origin, matrix] = [grid.origin, grid.matrix];
  const inverseMatrix = invert(matrix);
  geometryTrace.info("alignment built", { origin, matrix, inverseMatrix });

  // Half-width and half-height of a hexagon: the matrix carries the grid's step, from which the
  // flat-top tiling factors (1.5 in x, sqrt(3) in y) are removed.
  // See tenebrae/game_box/extract_map.py.
  const halfWidth = matrix[0][0] / 1.5;
  const halfHeight = matrix[1][1] / Math.sqrt(3);

  function centre(q, r) {
    return {
      x: origin[0] + matrix[0][0] * q + matrix[0][1] * r,
      y: origin[1] + matrix[1][0] * q + matrix[1][1] * r,
    };
  }

  function hexagonOfPixel(x, y) {
    // The inverted alignment gives fractional coordinates; cube rounding brings them back to the
    // nearest hexagon by correcting whichever of the three drifted most.
    const dx = x - origin[0];
    const dy = y - origin[1];
    const q = inverseMatrix[0][0] * dx + inverseMatrix[0][1] * dy;
    const r = inverseMatrix[1][0] * dx + inverseMatrix[1][1] * dy;
    const s = -q - r;

    let [rq, rr, rs] = [Math.round(q), Math.round(r), Math.round(s)];
    const [driftQ, driftR, driftS] = [Math.abs(rq - q), Math.abs(rr - r), Math.abs(rs - s)];
    if (driftQ > driftR && driftQ > driftS) rq = -rr - rs;
    else if (driftR > driftS) rr = -rq - rs;
    else rs = -rq - rr;
    const hexagon = { q: rq, r: rr, s: rs };
    geometryTrace.trace("hexagonOfPixel", { x, y, fractional: { q, r, s }, hexagon });
    return hexagon;
  }

  function vertices(q, r) {
    // The six corners of a flat-top hexagon, the first due east. Used to highlight it.
    const { x, y } = centre(q, r);
    return Array.from({ length: 6 }, (_, k) => ({
      x: x + halfWidth * Math.cos((Math.PI / 3) * k),
      y: y + halfHeight * Math.sin((Math.PI / 3) * k),
    }));
  }

  return { centre, hexagonOfPixel, vertices };
}

function key(hexagon) {
  return `${hexagon.q},${hexagon.r},${hexagon.s}`;
}

function pixelOfPointer(event, map) {
  // From the screen to map.jpg pixels: the map may be scaled down, and is not at the screen's
  // corner.
  const mapBox = map.getBoundingClientRect();
  const scale = mapBox.width / map.naturalWidth;
  const point = {
    x: (event.clientX - mapBox.x) / scale,
    y: (event.clientY - mapBox.y) / scale,
  };
  geometryTrace.trace("pixelOfPointer",
                      { client: { x: event.clientX, y: event.clientY }, scale, point });
  return point;
}
