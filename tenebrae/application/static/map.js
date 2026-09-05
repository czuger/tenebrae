// Places the pieces on the map, and shows where they can go.
//
// This file knows no rules: it does display. A click is converted into cube coordinates "q, r, s"
// by geometry.js, then the server says what is reachable (/moves) and what is allowed (/move).
// The requests carry the key of the piece in hand, not its movement: it is the server that knows
// how many points it has.
//
// Positions are in map.jpg pixels, hence in the frame of reference of #board, which carries the
// image at its natural size and is only scaled afterwards: zooming in or out therefore changes
// nothing about what is placed on the map. The zoom itself is in zoom.js, shared with the
// map-fixing page, and the laying of the counters in pieces.js, shared with the scenario page.
//
// Everything the player reads stays in French; only the code is English.
//
// The page says what it does in the debug log (debug.js), silent unless it is turned on -
// "/?debug=1", or `tenebraeDebug.on()` from the console. Everything a game goes through passes
// there: the clicks, what is asked of the server and what it answers, the selection, the combat
// being composed, the phase, the stream and the view. What happens by the hundred - a pointer over
// the map, a scroll - speaks at "trace", the level `tenebraeDebug.level("info")` drops.

// The counter's numeric values, in the order the card gives them to read (see the "Values read
// off the counters" section of tenebrae/game_box/pions/README.md). "Mouvement" is the movement budget
// the server retained, the very one the engine uses. The symbol and the remarks are not in it:
// they are words, not numbers, and they have a line of their own. The labels are French, like
// everything the player reads.
const FIELDS = [
  ["strength", "Force"],
  ["movement", "Mouvement"],
  ["fire", "Tir"],
  ["range", "Portée"],
  ["flight_movement", "Vol"],
  ["special_abilities", "Facultés"],
];

const MISSING = "—"; // what the counter does not carry

const trace = debugScope("map.js");

const board = document.getElementById("board");
const map = document.getElementById("map");
const frame = document.getElementById("frame");
const canvas = document.getElementById("canvas");

const card = document.getElementById("card");
const cardImage = document.getElementById("card-image");
const cardName = document.getElementById("card-name");
const cardExtra = document.getElementById("card-extra");
const cardSymbol = document.getElementById("card-symbol");
const cardValues = document.getElementById("card-values");
const cardRemarks = document.getElementById("card-remarks");

const log = document.getElementById("log");
const logLines = document.getElementById("log-lines");
const logToggle = document.getElementById("log-toggle");

const panel = document.getElementById("panel");
const panelSideButton = document.getElementById("panel-side");
const pawnStyleButton = document.getElementById("pawn-style");

const phaseLabel = document.getElementById("phase-label");
const attackButton = document.getElementById("attack");
const cancelButton = document.getElementById("cancel-combat");
const ratioLabel = document.getElementById("combat-ratio");
const locateButton = document.getElementById("locate");
const nextPhaseButton = document.getElementById("next-phase");

const playerButton = document.getElementById("player");
const messageArea = document.getElementById("message");
const displacedArea = document.getElementById("displaced");
const tableDialog = document.getElementById("table-dialog");
const tableTitle = document.getElementById("table-title");
const tableSeats = document.getElementById("table-seats");
const leaveButton = document.getElementById("table-leave");
const gamesButton = document.getElementById("table-games");

// How long the counters of one fall-back wait between two of them, in milliseconds. The same half
// second the AI waits between two of its own actions (`PAUSE_BETWEEN_AI_ACTIONS` in
// `current_game.py`), the two being the places where several counters move without anyone touching
// them.
const FALL_BACK_PAUSE = 500;

/** Waits that many milliseconds. */
function pause(delay) {
  return new Promise((over) => { setTimeout(over, delay); });
}

// Which saved game this page was served for. The server plays one at a time and several have an
// address of their own: what the stream pushes says which, and a message carrying another one
// means this page is no longer looking at its own game (see `checkTheGame`).
const game = document.getElementById("game").value;

let pieces = JSON.parse(document.getElementById("pieces").value);
const grid = JSON.parse(document.getElementById("grid").value);
trace.info("state received from the page", { pieces: pieces.length, grid });
const { centre: hexagonCentre, hexagonOfPixel } = alignment(grid);
// The tilt of the placed pieces comes from the server, with the piece: it is part of the game
// state (see `tenebrae/engine/board.py`). The layer only draws one for the ghosts, which are
// placed nowhere.
// The layer draws and places; what a pawn shows is this file's business, and it passes it in (see
// "The face the pawns show"): a counter created at any moment - a scene laid out again, a ghost
// born under a selection - is dressed in the face in use, without anything having to think of it.
const { place, createImage } = pieceLayer({
  board, centre: hexagonCentre, pieceSize: grid.piece_size,
  dress: (image, piece) => dressThePawn(image, piece, pawnsAreDrawn()),
});

// The images placed on the map: the pieces, and the ghosts of the selected piece.
const placedPieces = [];
let ghosts = [];
let selection = null;
let hovered = null; // the piece whose card is open
let view = null; // the zoom, mounted once the map has loaded

// The current phase, as the server gives it: { side, type, army, label, number, unavailable }.
// The type is never "magie" - the server skips it. `unavailable` gives the squares of the units
// that have already had their turn this phase: { attackers: [...], targets: [...] }.
let phase = JSON.parse(document.getElementById("phase").value);
trace.info("opening phase", phase);

// Who is watching and who holds which side, as the server gives it: { connected, nickname, avatar,
// administrator, sides, armies, seats }. `sides` gives the sides **this** browser holds -
// ordinarily just one. `seats` gives each occupant's nickname, never their identifier.
let table = JSON.parse(document.getElementById("table").value);
trace.info("table as the page opens", table);

// The game log, as the server keeps it: a list of { time, text }, from the oldest line to the most
// recent. It arrives with the pieces and the phase, from the template when the page opens then
// from the stream at every move played - ours as well as the opponent's.
let logEntries = JSON.parse(document.getElementById("initial-log").value);

// Where the player was on the map at their last adjustment: { scale, x, y, fitted }, or null -
// anonymous, or nobody has adjusted anything yet. See "Finding one's map view again".
const storedView = JSON.parse(document.getElementById("view").value);
trace.info("stored view", storedView);

// The game's version number. It rises at every move played, ours as well as the opponent's. It
// opens the stream - the server thus knows whether we have catching up to do - and then serves as
// the identifier of the last message received (see "Following the opponent's game").
let version = Number(document.getElementById("version").value);
trace.info("game version at load", { version, logLines: logEntries.length });

// The combat phase's selection: one opposing target, and a set of friendly attackers.
let target = null;
let attackers = new Set();

// --- Finding the last clicked piece again ---
//
// Zooming into the map quickly loses sight of the unit one is manoeuvring: the "localiser" button
// brings it back to the centre. We keep the image, not a square - a piece that moves takes its
// marker with it. The memory crosses phases; only elimination erases it.

let lastClickedPiece = null;
// The square the marker aims at, kept **beside** the image and not read back from it.
//
// A scene laid out again replaces every image, so the marker has to be found by square. Reading
// that square off the image at the moment of the re-layout is not enough: the stream delivers our
// own move back to us before the answer to it arrives (the server publishes inside the request),
// so the image still carries the square it has just left, which is by then empty - and the button
// went off exactly when one wants to find the unit one has just manoeuvred. `movePiece` therefore
// moves this square as soon as the move is **asked for**, and puts it back if it is refused.
let markedSquare = null;

function rememberThePiece(image) {
  lastClickedPiece = image;
  markedSquare = key(image.dataset);
  locateButton.disabled = false;
  trace.info("marker set", { piece: image.piece?.key, square: markedSquare });
}

function forgetThePiece() {
  trace.trace("marker cleared", { was: markedSquare });
  lastClickedPiece = null;
  markedSquare = null;
  locateButton.disabled = true;
}

function locate() {
  trace.enter("locate", { markedSquare, hasPiece: Boolean(lastClickedPiece) });
  if (!lastClickedPiece) {
    trace.trace("locate: nothing marked");
    return;
  }
  const { x, y } = hexagonCentre(Number(lastClickedPiece.dataset.q),
                                Number(lastClickedPiece.dataset.r));
  trace.info("locate: centring on the marked piece",
             { square: key(lastClickedPiece.dataset), x, y });
  view.centreOn(x, y);
}

function clickedHexagon(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  trace.trace("clickedHexagon", { x, y, hexagon: key(hexagon) });
  return hexagon;
}

// --- The card of the hovered unit ---
//
// Everything is already there: the server passed the counter's values in the hidden field, so
// hovering asks it nothing. The card extends the toolbar, which is outside #board: it keeps its
// size whatever the scale, and never lies on the map.
//
// Its box never leaves: leaving a piece empties it rather than removing it (`emptyTheCard`), so
// that the area stays the player's and the log column below it does not travel up and down at
// every pointer movement over the map. The "empty" class is what says which of the two states it
// is in.

function showTheCard(image) {
  const piece = image.piece;
  // The current square, read off the image: a piece that has moved is no longer on the scenario's.
  const hexagon = { q: image.dataset.q, r: image.dataset.r, s: image.dataset.s };

  cardImage.src = `/pieces/${piece.image}`;
  cardImage.alt = piece.name;
  cardName.textContent = piece.name;
  cardExtra.textContent = `${piece.side} — ${key(hexagon)}`;
  cardSymbol.textContent = piece.symbol ?? MISSING;
  // A remark is what the photograph leaves open: it only appears if there is one.
  cardRemarks.textContent = piece.remarks ?? "";
  cardRemarks.hidden = !piece.remarks;

  trace.trace("showTheCard", { piece: piece.key, name: piece.name, square: key(hexagon),
                               side: piece.side });
  cardValues.replaceChildren();
  for (const [field, label] of FIELDS) {
    const term = document.createElement("dt");
    term.textContent = label;
    const value = document.createElement("dd");
    const read = piece[field];
    value.textContent = read ?? MISSING;
    if (read === null || read === undefined) value.className = "missing";
    cardValues.append(term, value);
  }

  hovered = image;
  card.classList.remove("empty");
  // The piece owns that line now: it carries its own square (see "The square under the pointer").
  card.classList.remove("square");
}

// The card's width is set **once**, at start-up, to the widest of the cards the pieces in play
// give. Without it the box changed width from one unit to the next - a longer name, a remark - and
// the log column under it moved with it; the area is now the same whatever is hovered, and whether
// anything is.
//
// Once for all, as asked: the width is not measured again. A game opened on another set-up keeps
// it, and a name longer than any of these wraps inside the box rather than widening it. On a window
// too narrow to hold it, `max-width` in the stylesheet keeps it inside the panel.
function fixTheCardWidth() {
  trace.enter("fixTheCardWidth", { pieces: placedPieces.length });
  // The natural width, unclamped, for the length of the measurement: the box is filled with each
  // piece in turn and emptied again in one go, so nothing of it is painted.
  card.style.width = "max-content";
  card.style.maxWidth = "none";
  let widest = 0;
  for (const image of placedPieces) {
    showTheCard(image);
    widest = Math.max(widest, card.getBoundingClientRect().width);
  }
  emptyTheCard();
  card.style.maxWidth = "";
  if (widest > 0) card.style.width = `${Math.ceil(widest)}px`;
  trace.exit("fixTheCardWidth", { width: card.style.width, measured: placedPieces.length });
}

function emptyTheCard() {
  trace.trace("emptyTheCard", { was: hovered?.piece?.key ?? null });
  hovered = null;
  cardImage.removeAttribute("src");  // rather than an empty source, which draws a broken image
  cardImage.alt = "";
  cardName.textContent = "";
  cardExtra.textContent = "";
  cardSymbol.textContent = "";
  cardValues.replaceChildren();
  cardRemarks.textContent = "";
  cardRemarks.hidden = true;
  card.classList.add("empty");
}

// --- The square under the pointer ---
//
// With no unit under it the card is an empty box, and the square one is aiming at is written
// nowhere else in the page. Its coordinates go there, on the very line where a piece shows its
// own: the eye finds the square in the same place whether or not something is standing on it.
//
// The rest of the card stays invisible and the box keeps the width fixed at start-up: nothing
// moves under the pointer, which is what that reserved area is for (see `emptyTheCard`). It is
// the geometry that answers and not the server - the same `hexagonOfPixel` a click goes through,
// so what is read is the square a click would take.
//
// The state is the class and the line themselves, with no copy kept beside them: hovering fires at
// every pointer movement, and a second record of it would only be one more thing to keep in step.

function showTheSquareUnder(event) {
  if (hovered) return; // a unit is hovered: the card is its own, square included
  const { x, y } = pixelOfPointer(event, map);
  // Off the scan - the board is wider than the image once the map is fitted to the window - there
  // is no square to name: the line goes blank rather than count hexagons outside the map.
  if (x < 0 || y < 0 || x > map.naturalWidth || y > map.naturalHeight) {
    forgetTheSquareUnder();
    return;
  }
  const square = key(hexagonOfPixel(x, y));
  if (square === cardExtra.textContent) return; // still the same square: nothing to write
  cardExtra.textContent = square;
  card.classList.add("square");
  trace.trace("the square under the pointer", { square });
}

function forgetTheSquareUnder() {
  if (!card.classList.contains("square")) return;
  trace.trace("the pointer has left the map");
  card.classList.remove("square");
  cardExtra.textContent = "";
}

function isAPlacedPiece(element) {
  // Ghosts are discarded: they carry the already selected unit, and covering the map with hovers
  // repeating the same card would teach nothing.
  return element instanceof HTMLElement
    && element.classList.contains("piece") && !element.classList.contains("ghost");
}

function placeThePieces() {
  trace.enter("placeThePieces", { pieces: pieces.length });
  for (const piece of pieces) {
    const image = createImage(piece, { q: piece.q, r: piece.r, s: piece.s }, "piece", piece.tilt);
    placedPieces.push(image);
  }
  trace.exit("placeThePieces", { placed: placedPieces.length });
}

function pieceOnHexagon(hexagon) {
  return placedPieces.find((image) => image.dataset.q === String(hexagon.q)
    && image.dataset.r === String(hexagon.r)) ?? null;
}

function ghostOnHexagon(hexagon) {
  return ghosts.find((image) => image.dataset.q === String(hexagon.q)
    && image.dataset.r === String(hexagon.r)) ?? null;
}

function clearTheGhosts() {
  if (ghosts.length || selection) {
    trace.trace("clearTheGhosts", { ghosts: ghosts.length,
                                    selection: selection?.piece?.key ?? null });
  }
  for (const ghost of ghosts) ghost.remove();
  ghosts = [];
  if (selection) selection.classList.remove("selected");
  selection = null;
}

async function showTheMoves(image) {
  trace.enter("showTheMoves", { piece: image.piece.key, square: key(image.dataset) });
  clearTheGhosts();
  selection = image;
  image.classList.add("selected");

  const answer = await send(`/moves?q=${image.dataset.q}&r=${image.dataset.r}`
    + `&s=${image.dataset.s}&piece=${encodeURIComponent(image.piece.key)}`);
  if (!answer) {
    trace.warn("showTheMoves: no answer, the selection stays without ghosts",
               { piece: image.piece.key });
    return;
  }
  const { hexagons } = await answer.json();
  // The selection may have changed while the answer was awaited.
  if (selection !== image) {
    trace.warn("showTheMoves: answer dropped, the selection changed while it was awaited",
               { asked: image.piece.key, selected: selection?.piece?.key ?? null });
    return;
  }

  ghosts = hexagons.map((hexagon) => createImage(image.piece, hexagon, "piece ghost"));
  trace.exit("showTheMoves", { ghosts: ghosts.length, squares: hexagons.map(key) });
}

async function movePiece(image, hexagon) {
  // The marker follows the piece from here, before the request leaves: see `markedSquare`. A
  // refused move puts it back where it was.
  const wasMarked = lastClickedPiece === image;
  const squareLeft = markedSquare;
  if (wasMarked) markedSquare = key(hexagon);
  trace.enter("movePiece", { piece: image.piece.key, from: key(image.dataset),
                             to: key(hexagon), wasMarked, squareLeft });

  const answer = await send("/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin: { q: Number(image.dataset.q), r: Number(image.dataset.r), s: Number(image.dataset.s) },
      destination: hexagon,
      piece: image.piece.key,
    }),
  });
  if (!answer) {
    trace.warn("movePiece: refused before the rules, the marker goes back", { squareLeft });
    if (wasMarked) markedSquare = squareLeft;
    return;
  }
  const { allowed, destination, tilt } = await answer.json();
  if (!allowed) {
    trace.warn("movePiece: the server refuses the move, the marker goes back",
               { piece: image.piece.key, to: key(hexagon), squareLeft });
    if (wasMarked) markedSquare = squareLeft;
    return;
  }

  clearTheGhosts();
  // The piece has been picked up: it lies down askew again, differently from last time. It is the
  // server that drew this new angle, and that keeps it - the piece will stay lying that way.
  place(image, destination, tilt);
  trace.exit("movePiece", { piece: image.piece.key, destination: key(destination), tilt });
  // If the pointer had stayed on this piece, its card must say the square it has just reached.
  if (hovered === image) showTheCard(image);
}

function onClick(event) {
  const hexagon = clickedHexagon(event);
  trace.info("click on the board", { square: key(hexagon), phase: phase.type,
                                     side: phase.side, mine: itIsMyTurn() });

  // The marker is taken before any sorting: "localiser" follows the finger, not the rules. A click
  // on an empty square - or on a ghost, where the piece is not yet - leaves the previous marker.
  const clicked = pieceOnHexagon(hexagon);
  if (clicked) rememberThePiece(clicked);

  if (phase.type === "combat") {
    trace.trace("click handed to the combat phase", { square: key(hexagon) });
    onCombatClick(hexagon);
    return;
  }

  if (selection && ghostOnHexagon(hexagon)) {
    trace.info("click on a ghost: the piece moves", { piece: selection.piece.key,
                                                      to: key(hexagon) });
    movePiece(selection, hexagon);
    return;
  }

  const piece = pieceOnHexagon(hexagon);
  if (!piece || piece === selection || piece.piece.side !== phase.side) {
    // Outside its movement phase, a unit does not show its squares: only the active side plays.
    trace.trace("click shows nothing", { empty: !piece, alreadySelected: piece === selection,
                                         side: piece?.piece?.side ?? null, active: phase.side });
    clearTheGhosts();
    return;
  }
  showTheMoves(piece);
}

// --- The combat phase ---
//
// A click on an opposing unit makes it the target (highlighted in red). Subsequent clicks on units
// of the active side add them as attackers if they are in range (highlighted in gold); the server
// alone judges range. The "Attaquer" button resolves, "Annuler" clears the selection.
//
// A unit only fights once per phase - it attacks once, it is taken as a target only once. There
// again, it is the server that keeps count: the page asks it before highlighting, and greys out
// whatever it is told has already had its turn.

function hexagonOfPiece(image) {
  return { q: Number(image.dataset.q), r: Number(image.dataset.r), s: Number(image.dataset.s) };
}

function updateCombatButtons() {
  const inCombat = phase.type === "combat";
  cancelButton.hidden = !(inCombat && target);
  attackButton.hidden = !(inCombat && target && attackers.size > 0);
  trace.trace("combat buttons", { inCombat, target: target ? key(target.dataset) : null,
                                  attackers: attackers.size,
                                  attackShown: !attackButton.hidden });
  showTheRatio();
}

// What the combat being composed weighs: "Ratio : 3/1 (36/12)" - the column of Table I the attack
// would be read on, and the points on either side, the defender's terrain counted. The server
// weighs it: the terrain of a square is not in the page, and the ratio is a rule.
//
// One request per change of selection, as the range check is one per click. They can come back out
// of order - two clicks, two answers - so each one carries the number of the selection it was
// asked for, and an answer that is no longer the current one is dropped rather than shown.
let weighing = 0;

async function showTheRatio() {
  const asked = ++weighing;
  if (!(phase.type === "combat" && target && attackers.size > 0)) {
    ratioLabel.hidden = true;
    ratioLabel.textContent = "";
    return;
  }
  const c = target.dataset;
  const squares = [...attackers].map((image) => `a=${key(image.dataset)}`).join("&");
  // Nothing is awaited on this call: a weighing that fails leaves the bar as it was, and the
  // attack itself does not depend on it.
  const answer = await send(`/combat/ratio?cq=${c.q}&cr=${c.r}&cs=${c.s}&${squares}`)
    .catch(() => null);
  if (!answer || asked !== weighing) {
    trace.trace("weighing dropped", { asked, current: weighing, answered: Boolean(answer) });
    return;
  }
  const { ratio, attack, defence, outcomes } = await answer.json();
  if (asked !== weighing) return;
  ratioLabel.hidden = !ratio;
  ratioLabel.textContent = ratio
    ? `Ratio : ${ratio[0]}/${ratio[1]} (${attack}/${defence}) — ${punctuate(outcomes)}`
    : "";
  trace.info("combat weighed", { ratio, attack, defence, outcomes });
}

// The six faces of the die, in the order they can fall, punctuated so that the eye counts them
// without reading them: a comma between two faces that give the same thing, a semicolon where the
// outcome changes. Five chances of pushing the defender back and one of giving ground reads as
// "DR,DR,DR,DR,DR;AR" - the repetition is the information, which "5×DR" would take away.
function punctuate(outcomes) {
  return outcomes.reduce((written, outcome, face) => {
    if (face === 0) return outcome;
    return `${written}${outcome === outcomes[face - 1] ? "," : ";"}${outcome}`;
  }, "");
}

function clearTheCombat() {
  if (target || attackers.size) {
    trace.info("combat selection cleared", { target: target ? key(target.dataset) : null,
                                             attackers: attackers.size });
  }
  if (target) target.classList.remove("target");
  for (const attacker of attackers) attacker.classList.remove("attacker");
  target = null;
  attackers = new Set();
  updateCombatButtons();
}

async function onCombatClick(hexagon) {
  const piece = pieceOnHexagon(hexagon);
  trace.enter("onCombatClick", { square: key(hexagon), piece: piece?.piece?.key ?? null,
                                 target: target ? key(target.dataset) : null,
                                 attackers: attackers.size });
  if (!piece) {
    trace.trace("combat click on an empty square");
    return;
  }

  if (piece === target) {
    trace.info("the target is clicked again: the selection falls");
    clearTheCombat();
    return;
  }

  if (!target) {
    if (piece.piece.side === phase.side) {
      trace.trace("combat click ignored: an opposing target is needed first",
                  { side: piece.piece.side, active: phase.side });
      return; // an opposing target is needed first
    }
    const c = piece.dataset;
    const answer = await send(`/combat/target?cq=${c.q}&cr=${c.r}&cs=${c.s}`);
    if (!answer) {
      trace.warn("target refused before the rules", { square: key(c) });
      return;
    }
    const { available } = await answer.json();
    // Already attacked this phase: the refusal has gone to the server's log, and nothing reddens.
    if (!available || target) {
      trace.warn("target not taken", { available, targetMeanwhile: Boolean(target) });
      return;
    }
    target = piece;
    target.classList.add("target");
    trace.info("target taken", { square: key(target.dataset), piece: piece.piece.key });
    updateCombatButtons();
    return;
  }

  if (piece.piece.side !== phase.side) {
    trace.trace("another opposing unit clicked: no effect", { square: key(hexagon) });
    return; // another opposing unit: no effect
  }

  if (attackers.has(piece)) {
    attackers.delete(piece);
    piece.classList.remove("attacker");
    trace.info("attacker withdrawn", { square: key(piece.dataset), left: attackers.size });
    updateCombatButtons();
    return;
  }

  const c = target.dataset;
  const a = piece.dataset;
  const answer = await send(`/combat/range?cq=${c.q}&cr=${c.r}&cs=${c.s}`
    + `&aq=${a.q}&ar=${a.r}&as=${a.s}`);
  if (!answer) {
    trace.warn("range refused before the rules", { attacker: key(a), target: key(c) });
    return;
  }
  const { in_range: inRange, available } = await answer.json();
  if (!inRange || !available) {
    trace.warn("attacker not taken", { attacker: key(a), inRange, available });
    return; // the refusal has gone to the server's log
  }

  attackers.add(piece);
  piece.classList.add("attacker");
  trace.info("attacker taken", { square: key(a), piece: piece.piece.key,
                                 attackers: attackers.size });
  updateCombatButtons();
}

// Units that have already had their turn are greyed out: without that, nothing on the map would
// distinguish a unit one can still engage from one that will refuse the click.
function markTheUnavailable(unavailable) {
  const squares = new Set([...(unavailable?.attackers ?? []),
                           ...(unavailable?.targets ?? [])].map(key));
  for (const image of placedPieces) {
    image.classList.toggle("unavailable", squares.has(key(image.dataset)));
  }
  trace.info("units already engaged, greyed out", { squares: [...squares] });
}

async function attack() {
  trace.enter("attack", { target: target ? key(target.dataset) : null,
                          attackers: [...attackers].map((image) => key(image.dataset)) });
  if (!target || attackers.size === 0) {
    trace.warn("attack asked with nothing selected");
    return;
  }
  const answer = await send("/combat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target: hexagonOfPiece(target),
      attackers: [...attackers].map(hexagonOfPiece),
    }),
  });
  if (!answer) {
    trace.warn("attack refused before the rules");
    return;
  }
  const result = await answer.json();
  trace.info("combat resolved", result);
  if (result.resolved) {
    // The eliminations first: a unit that falls back may be taking over the square of one that
    // has just left the board, and the square must be free before it gets there.
    for (const eliminated of result.eliminated) removeThePiece(eliminated);
    await fallThePiecesBack(result.retreats);
  }
  clearTheCombat();
  markTheUnavailable(result.unavailable);
}

// A retreat moves counters - the unit that gives ground, and the friends it pushes to make room
// (tenebrae/engine/retreat.py). The other tabs get the whole scene again through the stream; this
// one has the answer in hand and moves them straight away, as it clears the eliminated squares.
//
// One counter at a time, half a second apart: a chain of pushes is three or four units changing
// square at once, and laid out in one go the whole figure jumps and nothing says which unit went
// where. The combat is not cleared until they have all landed - the "Attaquer" button therefore
// goes when the fall-back is over, and not before.
async function fallThePiecesBack(retreats) {
  if (!retreats?.length) return;
  trace.enter("fallThePiecesBack", { retreats: retreats.length });
  // Every unit is taken by the square it holds **before** any of them moves: along a chain of
  // pushes each square is handed to the unit behind, and looking one up after the first step would
  // find the unit that has just arrived on it rather than the one that must leave.
  const falling = retreats.map((retreat) => ({ ...retreat, image: pieceOnHexagon(retreat.from) }));
  let moved = 0;
  for (const { image, from, to, tilt } of falling) {
    if (!image) {
      trace.warn("nothing to fall back on this square", { square: key(from) });
      continue;
    }
    if (moved > 0) await pause(FALL_BACK_PAUSE);
    trace.info("piece falls back", { piece: image.piece?.key, from: key(from), to: key(to) });
    place(image, to, tilt);
    moved += 1;
  }
  trace.exit("fallThePiecesBack", { moved });
}

function removeThePiece(hexagon) {
  const image = pieceOnHexagon(hexagon);
  if (!image) {
    trace.warn("nothing to remove on this square", { square: key(hexagon) });
    return;
  }
  trace.info("piece eliminated", { square: key(hexagon), piece: image.piece?.key });
  const rank = placedPieces.indexOf(image);
  if (rank >= 0) placedPieces.splice(rank, 1);
  attackers.delete(image);
  if (target === image) target = null;
  if (lastClickedPiece === image) forgetThePiece();
  image.remove();
}

// The label is the server's, phase or end of game: a game that has been won shows how it ended
// where the phase was (`current_phase`), and says as much through a class, the one thing the bar
// ever has to shout.
function showThePhaseLabel() {
  phaseLabel.textContent = phase.label;
  phaseLabel.classList.toggle("over", Boolean(phase.over));
}


function refreshThePhase(fresh) {
  trace.info("phase change", { from: phase?.label, to: fresh?.label, type: fresh?.type,
                               side: fresh?.side, number: fresh?.number });
  phase = fresh;
  showThePhaseLabel();
  clearTheGhosts();
  clearTheCombat();
  // A new combat phase starts again with all its units: the server sends empty lists, and the
  // greying falls away by itself.
  markTheUnavailable(phase.unavailable);
  updatePlayerButtons();
}

// The log column, rebuilt entirely: it counts only a few dozen lines, and the server alone owns
// it - comparing in order to add only the new lines would cost more code than rewriting the lot.
//
// The order is reversed on the way: the server gives from the oldest to the most recent, the
// column shows the last one at the top. It thus sits under the card, where the eye returns, and
// nothing needs to scroll anything in the player's stead.
function refreshTheLog(entries) {
  trace.trace("log rebuilt", { lines: entries.length, last: entries[entries.length - 1] ?? null });
  logEntries = entries;
  logLines.textContent = "";
  for (let i = entries.length - 1; i >= 0; i -= 1) {
    const line = document.createElement("li");
    const time = document.createElement("time");
    time.textContent = entries[i].time;
    const text = document.createElement("span");
    text.className = "text";
    text.textContent = entries[i].text;
    line.append(time, text);
    logLines.appendChild(line);
  }
  // Nothing to tell, nothing to frame: the column only appears once the game has begun - unless
  // the player has used its button, after which the box stays whatever the lines. A server
  // restarted has an empty memory, and the stream hands it over: hiding the box then would take
  // the button away with it, and nothing could bring the column back.
  log.hidden = entries.length === 0 && !logTouched;
}


// The column is tall and it lies over the map: the button reduces it to itself, and brings it
// back. The state is the class alone - `refreshTheLog` rewrites the lines, not the box, so a
// reduced column stays reduced while the game goes on. A reload opens it again: nothing is stored
// for it anywhere.
let logTouched = false; // the player has used the button: the box no longer hides itself

function toggleTheLog() {
  logTouched = true;
  log.hidden = false;
  const reduced = log.classList.toggle("reduced");
  logToggle.textContent = reduced ? "+" : "−";
  logToggle.title = reduced ? "Afficher le journal" : "Réduire le journal";
  logToggle.setAttribute("aria-expanded", String(!reduced));
  trace.info("the log column is toggled", { reduced });
}


// --- Which edge the block of information hangs from ---
//
// The bar, the message, the card and the log are one block, and that block lies over the map:
// wherever it sits, it covers the pieces one is playing. So it moves - to the left edge of the
// window or to the right one, and nowhere else: a block one could put anywhere would hide as much
// map for a decision to be made at every game.
//
// The choice is kept in `localStorage`, as the debug log's is (`static/debug.js`): it belongs to
// this browser and to nothing else - not to the player, whose stored view is the game's own
// (`/view`), and not to the game.

const PANEL_SIDE_KEY = "tenebrae.panelSide";
const RIGHT_SIDE = "right";
const LEFT_SIDE = "left";

function storedPanelSide() {
  try {
    return window.localStorage.getItem(PANEL_SIDE_KEY) === RIGHT_SIDE ? RIGHT_SIDE : LEFT_SIDE;
  } catch (error) {
    // Private browsing and a blocked storage throw rather than answer: the block then opens where
    // it always has.
    return LEFT_SIDE;
  }
}

function putThePanelOn(side) {
  const onTheRight = side === RIGHT_SIDE;
  panel.classList.toggle(RIGHT_SIDE, onTheRight);
  panelSideButton.textContent = onTheRight ? "←" : "→";
  panelSideButton.title = onTheRight
    ? "Déplacer le panneau à gauche"
    : "Déplacer le panneau à droite";
  trace.info("the block of information is anchored", { side });
}

function swapThePanelSide() {
  const side = panel.classList.contains(RIGHT_SIDE) ? LEFT_SIDE : RIGHT_SIDE;
  putThePanelOn(side);
  try {
    window.localStorage.setItem(PANEL_SIDE_KEY, side);
  } catch (error) {
    // Nothing to do: the choice will simply not survive the reload.
  }
}


// --- The face the pawns show ---
//
// The counter photographed is the game's own object, and at the scale the map opens at it is a
// small grey square: the second button of the bar puts a drawn icon on the units that have one,
// in the colour of their army (`static/pawns.js`), and puts the photographs back.
//
// A pawn is an <img> in both faces, and only its source changes: nothing else in this file - the
// selection, the ghosts, the card, the click - knows which face is showing. The face is not
// applied piece by piece from here either: `dressThePawn` is handed to the layer as `dress`, so
// that a counter born after the choice - the scene laid out again after a move, a ghost under a
// selection - arrives wearing it. Which counter is drawn as what is nobody's business here: it is
// `static/pawn_icons.json`, and `static/pawns.js` reads it.
//
// What has no icon keeps its photograph, and the board then shows both at once. The choice itself
// - where it is kept, what the address says about it, what the button announces - is in
// `static/pawns.js`, shared with the scenario page, which carries the same button: what is left
// here is the redrawing of what this page has on screen.

function showThePawnStyle() {
  labelThePawnStyleButton(pawnStyleButton);
  for (const image of [...placedPieces, ...ghosts]) {
    dressThePawn(image, image.piece, pawnsAreDrawn());
  }
  trace.info("the pawns are dressed", { drawn: pawnsAreDrawn(), pawns: placedPieces.length,
                                        ghosts: ghosts.length });
}

// The icons are read the first time they are asked for, and not before: a player who never leaves
// the counters fetches nothing. What has been read is kept, so the swap back and forth is free.
async function applyThePawnStyle() {
  if (pawnsAreDrawn()) await loadThePawnIcons(pieces);
  showThePawnStyle();
}

async function swapThePawnStyle() {
  turnThePawnStyleOver();
  await applyThePawnStyle();
}


async function nextPhase() {
  trace.enter("nextPhase", { from: phase.label });
  const answer = await send("/phase/next", { method: "POST" });
  if (!answer) {
    trace.warn("the phase was not advanced");
    return;
  }
  refreshThePhase(await answer.json());
}

// --- Talking to the server ---
//
// The server now refuses a move played out of turn, by a visitor with no account or by someone who
// has not taken a seat. A mute refusal - which is what `if (!answer.ok) return;` did - would look
// like a breakdown: we show those two, and only those. The other failures keep the silence they
// had, their refusals going to the server's log.

const MESSAGE_DELAY = 4000; // milliseconds

async function send(url, options) {
  // `trace.fetch` is `fetch` with the round trip written into the debug log; turned off, it is
  // `fetch` itself, and it answers and throws exactly the same in both cases.
  const answer = await trace.fetch(url, options);
  if (answer.status === 401 || answer.status === 403) {
    const { message } = await answer.json().catch(() => ({}));
    trace.warn("refused by the server", { url, status: answer.status, message });
    report(message ?? "Ce n'est pas à vous de jouer.");
    return null;
  }
  if (!answer.ok) trace.warn("failure kept silent from the player", { url, status: answer.status });
  return answer.ok ? answer : null;
}

function report(text) {
  trace.info("message shown to the player", { text });
  messageArea.textContent = text;
  messageArea.hidden = false;
  clearTimeout(report.timer);
  report.timer = setTimeout(() => { messageArea.hidden = true; }, MESSAGE_DELAY);
}

// --- The player and their seat ---

function itIsMyTurn() {
  return table.sides.includes(phase.side);
}

// A button that cannot be pressed goes off rather than returning a refusal. `#toolbar
// button:disabled` is already styled by zoom.css: the dimming comes without one more line.
// A game that has been won takes nothing more: the server refuses the move, the combat and the
// phase change alike (`while_the_game_lasts`), and the two buttons say so beforehand rather than
// let the player find out by being refused.
function updatePlayerButtons() {
  const playable = itIsMyTurn() && !phase.over;
  nextPhaseButton.disabled = !playable;
  attackButton.disabled = !playable;
  trace.trace("player buttons", { mine: itIsMyTurn(), over: Boolean(phase.over),
                                  sides: table.sides, active: phase.side });
}

function updateAccountButton() {
  trace.trace("account button", { connected: table.connected, nickname: table.nickname,
                                  sides: table.sides });
  playerButton.textContent = "";
  if (!table.connected) {
    playerButton.textContent = "Se connecter";
    playerButton.title = "S'identifier par Discord pour jouer";
    return;
  }
  if (table.avatar) {
    const avatar = document.createElement("img");
    avatar.src = table.avatar;
    avatar.alt = "";
    playerButton.appendChild(avatar);
  }
  const nickname = document.createElement("span");
  nickname.className = "nickname";
  nickname.textContent = table.nickname;
  playerButton.appendChild(nickname);
  const sides = table.sides.map((side) => table.armies[side]).join(", ");
  playerButton.title = sides ? `Vous tenez : ${sides}` : "Vous ne tenez aucun camp";
}

// One line per side: the army, its occupant, and the means to sit there if it is free.
function buildTheSeats() {
  trace.info("seats rebuilt", { seats: table.seats, mine: table.sides });
  tableSeats.textContent = "";
  for (const [side, army] of Object.entries(table.armies)) {
    const line = document.createElement("div");
    line.className = table.sides.includes(side) ? "side mine" : "side";
    line.dataset.side = side;

    const name = document.createElement("span");
    name.textContent = army;
    line.appendChild(name);

    const occupant = table.seats[side];
    if (occupant) {
      const held = document.createElement("span");
      held.className = "occupant";
      held.textContent = table.sides.includes(side) ? `${occupant} (vous)` : occupant;
      line.appendChild(held);
    } else if (table.sides.length > 0) {
      // We already hold a side: the seat stays free, but it is not for us.
      const free = document.createElement("span");
      free.className = "free";
      free.textContent = "libre";
      line.appendChild(free);
    } else {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Prendre ce camp";
      button.addEventListener("click", () => {
        trace.info("seat asked for", { side });
        takeASeat(side);
      });
      line.appendChild(button);
    }
    tableSeats.appendChild(line);
  }
  leaveButton.hidden = table.sides.length === 0;
  trace.trace("dialog buttons", { leave: !leaveButton.hidden });
}

function openTheTable() {
  trace.info("the table dialog opens", { alreadyOpen: tableDialog.open, sides: table.sides });
  tableTitle.textContent = table.sides.length
    ? `Vous jouez ${table.sides.map((side) => table.armies[side]).join(", ")}`
    : "Prenez place à un camp pour jouer";
  buildTheSeats();
  tableDialog.showModal();
}

function updateTheTable(fresh) {
  trace.info("table updated", { from: { sides: table.sides, seats: table.seats },
                                to: { sides: fresh.sides, seats: fresh.seats } });
  table = fresh;
  updateAccountButton();
  updatePlayerButtons();
  if (tableDialog.open) openTheTable();
}

async function takeASeat(side) {
  trace.enter("takeASeat", { side });
  const answer = await send("/game/seat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ side }),
  });
  if (!answer) {
    trace.warn("the seat was refused before the rules", { side });
    return;
  }
  const result = await answer.json();
  trace.info("seat answer", { side, seated: result.seated, message: result.message });
  if (!result.seated) report(result.message);
  // Seated, we have nothing left to do in this dialog: it closes on the game. Leaving it open
  // would mask the map, and its modal backdrop would swallow the next click.
  else tableDialog.close();
  updateTheTable(result);
}

async function leaveTheSeat() {
  trace.enter("leaveTheSeat", { sides: table.sides });
  const answer = await send("/game/seat/leave", { method: "POST" });
  if (!answer) {
    trace.warn("the seat was not left");
    return;
  }
  updateTheTable(await answer.json());
}

async function logOut() {
  trace.info("logging out");
  await trace.fetch("/logout", { method: "POST" });
  location.reload();
}

// --- Finding one's map view again ---
//
// The map is 6173 x 5102 px and it is played zoomed in: every page reload brought everyone back to
// the fit, the whole map inside the window, and one had to redo one's zoom and find one's corner
// of the front again. The server therefore keeps, per player, what they were looking at
// (`models/view.py`) and returns it at the next load.
//
// What is stored is not the scroll but the **point of the map that is at the centre of the
// window**, in map.jpg pixels: a `scrollLeft` in screen pixels would mean nothing at another
// scale, nor on another screen. And as long as the map is still set to the window, we store that
// fact rather than a scale: the next window will find its own fit instead of inheriting another
// screen's zoom.
//
// It is neither a move played nor shared state: nothing is published to the stream - one player's
// view must not make the other's map jump.

const VIEW_DELAY = 500; // milliseconds of quiet before sending

let viewTimer = null;
// What the server already has: we send it nothing as long as nothing has moved. That is also what
// avoids writing on load - restoring the view we have just received triggers a scroll, hence an
// event, and it says nothing new.
let lastSentView = storedView;

function currentView() {
  const { x, y } = view.viewedCentre();
  return { scale: view.scale(), x, y, fitted: view.followsWindow() };
}

function sameView(one, other) {
  if (!one || !other) return false;
  return one.fitted === other.fitted
    && Math.abs(one.scale - other.scale) < 0.0001
    && Math.abs(one.x - other.x) < 1
    && Math.abs(one.y - other.y) < 1;
}

// Called at every wheel turn, every zoom button and every scroll: we wait for quiet rather than
// send a hundred requests for a single gesture.
function rememberTheView() {
  if (!view || !table.connected) {
    trace.trace("view not stored", { mounted: Boolean(view), connected: table.connected });
    return; // an anonymous visitor has nowhere to store it
  }
  clearTimeout(viewTimer);
  viewTimer = setTimeout(sendTheView, VIEW_DELAY);
}

async function sendTheView() {
  const current = currentView();
  if (sameView(current, lastSentView)) {
    trace.trace("view unchanged, nothing sent", current);
    return;
  }
  trace.info("view stored", { from: lastSentView, to: current });
  lastSentView = current;
  // Without `send`: this is not a move, and a failure has nothing to report to the player - we
  // will simply find the fit again at the next load.
  await trace.fetch("/view", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(current),
  }).catch(() => null);
}

// Restore the stored view, or open the map fitted to the window as it always has been.
function applyTheView() {
  if (!storedView || storedView.fitted) {
    trace.info("view: the map opens fitted to the window", { stored: storedView });
    view.fit();
    return;
  }
  trace.info("view restored", storedView);
  view.set(storedView.scale);
  view.centreOn(storedView.x, storedView.y);
}

// --- Following the opponent's game ---
//
// Two players, two browsers: without this, each would stay in front of a stale board until they
// thought of reloading. The page therefore holds an **open stream** to the server (`/stream`,
// Server-Sent Events), and it is the server that writes when the game changes. We no longer ask
// for anything: we listen.
//
// It is a one-way channel, server -> browser, and it stays so: everything the player does - a
// move, a combat, a seat taken - goes out as a POST as before, and the stream only serves to carry
// the result of the move to the **others**. Nothing has changed on that side.
//
// The fallback is kept: if the `EventSource` fails too often - an intermediary that cuts SSE, a
// corporate proxy -, we fall back on the old polling of `/game/state`, which is still served for
// that. The game slows down, it does not break.

const POLL_PERIOD = 3000; // milliseconds, for the fallback alone
// Beyond that, we stop believing in the stream: the browser retries by itself between failures, so
// these are five attempts a few seconds apart.
const FAILURES_BEFORE_FALLBACK = 5;

let stream = null;
let streamFailures = 0;
let pollTimer = null;

// Whether this page is still looking at the game it was served for.
//
// The server plays one game at a time and every game has an address: someone opening another one
// takes the whole table with them, and what arrives here is then a board that is not ours. The
// version says nothing about it - it counts the moves of the **process**, not of one game - so the
// snapshot carries the identifier and we compare it.
//
// Once displaced, the page stops following rather than reloading onto its own game: reloading
// would take the table back from whoever has just opened theirs, and two tabs would pull at it
// forever. It says so and stops there.
let displaced = false;

function checkTheGame(state) {
  if (displaced) return false;
  if (state.game === game) return true;
  trace.error("another game has been opened on the server", { ours: game, theirs: state.game });
  displaced = true;
  closeTheStream();
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  displacedArea.textContent = "Une autre partie a été ouverte sur ce serveur : "
    + "cette page ne suit plus la sienne. Revenez à la liste des parties pour la rouvrir.";
  displacedArea.hidden = false;
  return false;
}

// Lay the scene out again, wherever the state comes from - the stream or the fallback poll.
function resumeTheGame(state) {
  if (!checkTheGame(state)) return;
  trace.info("state received", { from: version, to: state.version, pieces: state.pieces.length,
                                 phase: state.phase.label, logLines: state.log.length });
  version = state.version;
  // We do not undo what the player is doing on their side: a selection or a combat being composed
  // are abandoned, they bore on a position that is now out of date.
  layThePiecesOut(state.pieces);
  refreshThePhase(state.phase);
  refreshTheLog(state.log);
  updateTheTable(state.table);
}

function openTheStream() {
  // The known version travels in the URL: an `EventSource` cannot set a header. On subsequent
  // reconnections it is the browser that sends back by itself the "Last-Event-ID" of the last
  // message received, and the server prefers it - it is more recent than the URL.
  trace.info("opening the stream", { version });
  stream = new EventSource(`/stream?version=${version}`);

  stream.addEventListener("open", () => {
    trace.info("stream open", { failuresForgotten: streamFailures });
    streamFailures = 0;
  });

  stream.addEventListener("message", (event) => {
    trace.info("stream message", { id: event.lastEventId, bytes: event.data.length });
    streamFailures = 0;
    resumeTheGame(JSON.parse(event.data));
  });

  // The browser reconnects by itself - server restarted, network cut, laptop woken up - and there
  // is nothing to do about it. We only count repeated failures, which say that SSE does not get
  // through here at all.
  stream.addEventListener("error", () => {
    streamFailures += 1;
    trace.warn("stream failure, the browser will retry by itself",
               { failures: streamFailures, before: FAILURES_BEFORE_FALLBACK,
                 readyState: stream?.readyState });
    if (streamFailures < FAILURES_BEFORE_FALLBACK) return;
    trace.error("the stream does not get through: falling back on polling",
                { failures: streamFailures });
    closeTheStream();
    fallBackOnPolling();
  });
}

function closeTheStream() {
  if (!stream) return;
  trace.info("closing the stream", { readyState: stream.readyState });
  stream.close(); // without which the browser would retry the connection indefinitely
  stream = null;
}

// The old following, kept for the sole case where the stream does not get through. It asks for the
// state again every three seconds, giving the version number we know: as long as nothing has
// moved, the server returns only that number.
function fallBackOnPolling() {
  if (pollTimer) return;
  trace.warn("polling started", { period: POLL_PERIOD });
  pollTimer = setInterval(followTheGame, POLL_PERIOD);
}

async function followTheGame() {
  // A hidden tab is watching nothing: no point keeping the server awake for it. That only holds
  // for polling - an open and silent stream costs nothing, and a hidden tab must stay up to date
  // for the moment one comes back to it.
  if (document.hidden) {
    trace.trace("hidden tab: the poll is skipped");
    return;
  }
  const answer = await trace.fetch(`/game/state?version=${version}`).catch(() => null);
  if (!answer || !answer.ok) {
    trace.warn("poll without an answer, retrying in three seconds",
               { status: answer?.status ?? null });
    return; // the server is restarting: we will retry in three seconds
  }
  const state = await answer.json();
  // Checked **before** the "nothing has moved" shortcut: the version is the process's and the game
  // under it may have been swapped without it rising a single step.
  if (!checkTheGame(state)) return;
  version = state.version;
  if (!state.changed) {
    trace.trace("poll: nothing has moved", { version });
    return;
  }
  resumeTheGame(state);
}

// Leaving the page closes the stream: the server sees the connection drop and removes the
// subscriber, instead of keeping a box for it and going on depositing every move played into it.
// Two events, and not one: "beforeunload" does not fire on mobile, where "pagehide" is the only
// reliable one.
window.addEventListener("beforeunload", closeTheStream);
window.addEventListener("pagehide", closeTheStream);

// ... and coming back to it reopens it. The browser keeps the page as it is in its navigation
// cache ("bfcache"): going back restores it without reloading, JavaScript included - but with the
// stream we have just closed. Without this, the board would stay frozen for good. The stream
// reopens with the version we know, and the server returns straight away what has been played
// meanwhile.
window.addEventListener("pageshow", (event) => {
  trace.info("pageshow", { persisted: event.persisted, stream: Boolean(stream),
                           polling: Boolean(pollTimer) });
  if (event.persisted && !stream && !pollTimer) openTheStream();
});

function layThePiecesOut(fresh) {
  trace.enter("layThePiecesOut", { from: placedPieces.length, to: fresh.length,
                                   marker: markedSquare });
  clearTheGhosts();
  clearTheCombat();
  // The "localiser" marker aims at an image that is about to be removed from the board: we keep
  // its **square** - `markedSquare`, which a move moves as soon as it is asked for - and put the
  // marker back on the image that takes that square over. Without that, the button went off at
  // every scene laid out again - hence, since the stream made them instantaneous, just after each
  // of one's own moves, at the precise moment when one wants to find the unit one has just
  // manoeuvred.
  const marker = markedSquare;

  for (const image of placedPieces) image.remove();
  placedPieces.length = 0;
  forgetThePiece();
  pieces = fresh;
  placeThePieces();
  // The pieces are already dressed in the face in use; a game opened on another scenario may
  // nevertheless bring a unit, or an army, whose icon has not been drawn yet. Reading it is not
  // waited for: the board is complete without it, and the icons take the place of the photographs
  // as soon as they are there.
  if (pawnsAreDrawn()) applyThePawnStyle();

  // The unit may have been eliminated meanwhile: there is then nothing left to aim at.
  const found = marker && placedPieces.find((image) => key(image.dataset) === marker);
  if (found) rememberThePiece(found);
  else if (marker) trace.info("the marked unit is no longer on the board", { marker });
  trace.exit("layThePiecesOut", { placed: placedPieces.length });
}

function start() {
  trace.info("start", { pieces: pieces.length, phase: phase.label, version,
                        connected: table.connected });
  placeThePieces();
  fixTheCardWidth();
  showThePhaseLabel();
  markTheUnavailable(phase.unavailable);
  refreshTheLog(logEntries);
  document.getElementById("next-phase").addEventListener("click", () => {
    trace.info("\"phase suivante\" clicked");
    nextPhase();
  });
  attackButton.addEventListener("click", () => {
    trace.info("\"attaquer\" clicked");
    attack();
  });
  cancelButton.addEventListener("click", () => {
    trace.info("\"annuler\" clicked");
    clearTheCombat();
  });
  locateButton.addEventListener("click", () => {
    trace.info("\"localiser\" clicked", { marker: markedSquare });
    locate();
  });
  logToggle.addEventListener("click", toggleTheLog);
  panelSideButton.addEventListener("click", swapThePanelSide);
  putThePanelOn(storedPanelSide());
  pawnStyleButton.addEventListener("click", swapThePawnStyle);
  // The counters are already laid: on the icons, the board is opened with the photographs and they
  // are put on as soon as the set is read, rather than the page waiting on five files for a face.
  settleThePawnStyle();
  applyThePawnStyle();
  playerButton.addEventListener("click", () => {
    trace.info("the player button is clicked", { connected: table.connected });
    if (table.connected) openTheTable();
    else location.href = "/login";
  });
  leaveButton.addEventListener("click", () => {
    trace.info("\"quitter ma place\" clicked");
    leaveTheSeat();
  });
  gamesButton.addEventListener("click", () => {
    trace.info("\"les parties\" clicked");
    location.href = "/";
  });
  document.getElementById("table-logout").addEventListener("click", logOut);
  document.getElementById("table-close").addEventListener("click", () => {
    trace.info("the table dialog is closed");
    tableDialog.close();
  });
  updateAccountButton();
  updatePlayerButtons();
  openTheStream();
  // The map is 6173 x 5102 px: it opens scaled down to the window, and the wheel or the "+", "-"
  // and "ajuster" buttons bring it closer - up to the size of the scan, where a piece really can
  // be read.
  view = zoom({ frame, canvas, board, map, display: document.getElementById("scale"),
                onChange: rememberTheView });
  applyTheView();
  // Scrolling by hand does not go through the zoom: it is watched here.
  frame.addEventListener("scroll", () => {
    trace.trace("scroll", { left: frame.scrollLeft, top: frame.scrollTop });
    rememberTheView();
  });
  board.addEventListener("click", onClick);
  // Delegated on the board, like the click: ghosts are born and die along the way, and one
  // listener per image would have to be redone at every move.
  board.addEventListener("mouseover", (event) => {
    if (isAPlacedPiece(event.target)) showTheCard(event.target);
  });
  board.addEventListener("mouseout", (event) => {
    if (isAPlacedPiece(event.target)) emptyTheCard();
  });
  // The square under the pointer, as long as no unit is: the card would otherwise show nothing.
  board.addEventListener("mousemove", showTheSquareUnder);
  board.addEventListener("mouseleave", forgetTheSquareUnder);
  trace.info("the board is ready");
}

if (map.complete) {
  trace.info("the map image was already loaded");
  start();
} else {
  trace.info("waiting for the map image");
  map.addEventListener("load", start);
}

// Resizing the window refits the map, as long as one has not set the scale oneself: that would
// undo the zoom one has just chosen.
window.addEventListener("resize", () => {
  trace.trace("window resized", { fitted: view ? view.followsWindow() : null,
                                  width: window.innerWidth, height: window.innerHeight });
  if (view && view.followsWindow()) view.fit();
});
