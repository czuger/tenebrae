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

// Laying and moving a counter happen by the dozen at every scene laid out again: both speak at
// "trace", the level one drops when only the moves played matter (debug.js).
const piecesTrace = debugScope("pieces.js");

function pieceLayer({ board, centre, pieceSize, dress }) {
  piecesTrace.info("piece layer mounted", { board: board?.id, pieceSize, dressed: Boolean(dress) });

  // How a counter is dressed: the source it takes, and whatever class goes with it. The board
  // passes its own, which swaps the photographs for icons (map.js, "The face the pawns show");
  // with none given, a piece wears its photograph - what the scenario page wants, where the
  // counter is the thing being placed.
  const dressThePiece = dress ?? ((image, piece) => { image.src = `/pieces/${piece.image}`; });

  function place(image, hexagon, tilt) {
    const point = centre(hexagon.q, hexagon.r);
    const angle = tilt ?? (Math.random() * 2 - 1) * MAXIMUM_ROTATION;
    piecesTrace.trace("place", { piece: image.piece?.key ?? image.alt, hexagon, point, angle,
                                 tiltFromTheServer: tilt ?? null });
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
    dressThePiece(image, piece);
    image.alt = piece.name;
    // The counter the image carries, on the image itself: its card, its ghosts and its face are
    // all read from here, and a ghost knows its unit as the piece it doubles does.
    image.piece = piece;
    image.style.width = `${pieceSize}px`;
    image.style.height = `${pieceSize}px`;
    place(image, hexagon, tilt);
    board.appendChild(image);
    piecesTrace.trace("createImage", { piece: piece.key, name: piece.name, hexagon, className });
    return image;
  }

  return { place, createImage };
}
