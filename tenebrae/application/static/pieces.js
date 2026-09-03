// The counters laid on the map, shared by the pages that place them: the board, and the scenario
// page.
//
// A piece is an <img> in #board, at the hexagon's centre in map.jpg pixels, then tilted by a few
// degrees so that the board does not look laid out with a ruler. On the board the angle comes from
// the server - it is part of the game state, drawn when the piece is placed and saved with it (see
// tenebrae/engine/board.py). A piece arriving without one gets a random one here: that is the case
// of the ghosts, which are placed nowhere, and of the scenario page, whose pieces are not yet in a
// game. Nothing here knows the rules: only the grid alignment and the size of a counter.

const MAXIMUM_ROTATION = 5; // degrees, forwards or backwards

function pieceLayer({ board, centre, pieceSize }) {
  function place(image, hexagon, tilt) {
    const point = centre(hexagon.q, hexagon.r);
    const angle = tilt ?? (Math.random() * 2 - 1) * MAXIMUM_ROTATION;
    image.dataset.q = hexagon.q;
    image.dataset.r = hexagon.r;
    image.dataset.s = hexagon.s;
    image.style.left = `${point.x}px`;
    image.style.top = `${point.y}px`;
    // The half-offset centres the piece on the hexagon; the rotation comes after.
    image.style.transform = `translate(-50%, -50%) rotate(${angle.toFixed(2)}deg)`;
  }

  function createImage(piece, hexagon, className, tilt) {
    const image = document.createElement("img");
    image.className = className;
    image.src = `/pieces/${piece.image}`;
    image.alt = piece.name;
    image.style.width = `${pieceSize}px`;
    image.style.height = `${pieceSize}px`;
    place(image, hexagon, tilt);
    board.appendChild(image);
    return image;
  }

  return { place, createImage };
}
