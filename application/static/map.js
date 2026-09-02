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
// map-fixing page.
//
// Everything the player reads stays in French; only the code is English.

// The tilt of the placed pieces comes from the server: it is part of the game state, drawn at
// random when the piece is placed and saved with it (see `engine/board.py`). The page only draws
// one for the ghosts, which are placed nowhere - and for a piece arriving without one, which the
// server does not do.
const MAXIMUM_ROTATION = 5; // degrees, forwards or backwards

// The counter's numeric values, in the order the card gives them to read (see the "Valeurs lues
// sur les pions" section of game_box/pions/README.md). "Mouvement" is the movement budget the
// server retained, the very one the engine uses. The symbol and the remarks are not in it: they
// are words, not numbers, and they have a line of their own. The labels are French, like
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

const phaseLabel = document.getElementById("phase-label");
const attackButton = document.getElementById("attack");
const cancelButton = document.getElementById("cancel-combat");
const locateButton = document.getElementById("locate");
const nextPhaseButton = document.getElementById("next-phase");

const playerButton = document.getElementById("player");
const messageArea = document.getElementById("message");
const tableDialog = document.getElementById("table-dialog");
const tableTitle = document.getElementById("table-title");
const tableSeats = document.getElementById("table-seats");
const leaveButton = document.getElementById("table-leave");
const againstAIButton = document.getElementById("table-against-ai");

// The nickname the server gives to the seat held by the AI (see `engine/ai.py`).
const AI_NAME = "IA";

let pieces = JSON.parse(document.getElementById("pieces").value);
const grid = JSON.parse(document.getElementById("grid").value);
const { centre: hexagonCentre, hexagonOfPixel } = alignment(grid);

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

// Who is watching and who holds which side, as the server gives it: { connected, nickname, avatar,
// administrator, sides, armies, seats }. `sides` gives the sides **this** browser holds -
// ordinarily just one. `seats` gives each occupant's nickname, never their identifier.
let table = JSON.parse(document.getElementById("table").value);

// The game log, as the server keeps it: a list of { time, text }, from the oldest line to the most
// recent. It arrives with the pieces and the phase, from the template when the page opens then
// from the stream at every move played - ours as well as the opponent's.
let logEntries = JSON.parse(document.getElementById("initial-log").value);

// Where the player was on the map at their last adjustment: { scale, x, y, fitted }, or null -
// anonymous, or nobody has adjusted anything yet. See "Finding one's map view again".
const storedView = JSON.parse(document.getElementById("view").value);

// The game's version number. It rises at every move played, ours as well as the opponent's. It
// opens the stream - the server thus knows whether we have catching up to do - and then serves as
// the identifier of the last message received (see "Following the opponent's game").
let version = Number(document.getElementById("version").value);

// The combat phase's selection: one opposing target, and a set of friendly attackers.
let target = null;
let attackers = new Set();

// --- Finding the last clicked piece again ---
//
// Zooming into the map quickly loses sight of the unit one is manoeuvring: the "localiser" button
// brings it back to the centre. We keep the image, not a square - a piece that moves takes its
// marker with it. The memory crosses phases; only elimination erases it.

let lastClickedPiece = null;

function rememberThePiece(image) {
  lastClickedPiece = image;
  locateButton.disabled = false;
}

function forgetThePiece() {
  lastClickedPiece = null;
  locateButton.disabled = true;
}

function locate() {
  if (!lastClickedPiece) return;
  const { x, y } = hexagonCentre(Number(lastClickedPiece.dataset.q),
                                Number(lastClickedPiece.dataset.r));
  view.centreOn(x, y);
}

function clickedHexagon(event) {
  const { x, y } = pixelOfPointer(event, map);
  return hexagonOfPixel(x, y);
}

function place(image, hexagon, tilt) {
  const centre = hexagonCentre(hexagon.q, hexagon.r);
  const angle = tilt ?? (Math.random() * 2 - 1) * MAXIMUM_ROTATION;
  image.dataset.q = hexagon.q;
  image.dataset.r = hexagon.r;
  image.dataset.s = hexagon.s;
  image.style.left = `${centre.x}px`;
  image.style.top = `${centre.y}px`;
  // The half-offset centres the piece on the hexagon; the rotation comes after.
  image.style.transform = `translate(-50%, -50%) rotate(${angle.toFixed(2)}deg)`;
}

// --- The card of the hovered unit ---
//
// Everything is already there: the server passed the counter's values in the hidden field, so
// hovering asks it nothing. The card extends the toolbar, which is outside #board: it keeps its
// size whatever the scale, and never lies on the map.

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
  card.hidden = false;
}

function hideTheCard() {
  hovered = null;
  card.hidden = true;
}

function isAPlacedPiece(element) {
  // Ghosts are discarded: they carry the already selected unit, and covering the map with hovers
  // repeating the same card would teach nothing.
  return element instanceof HTMLElement
    && element.classList.contains("piece") && !element.classList.contains("ghost");
}

function createImage(piece, hexagon, className, tilt) {
  const image = document.createElement("img");
  image.className = className;
  image.src = `/pieces/${piece.image}`;
  image.alt = piece.name;
  image.style.width = `${grid.piece_size}px`;
  image.style.height = `${grid.piece_size}px`;
  place(image, hexagon, tilt);
  board.appendChild(image);
  return image;
}

function placeThePieces() {
  for (const piece of pieces) {
    const image = createImage(piece, { q: piece.q, r: piece.r, s: piece.s }, "piece", piece.tilt);
    image.piece = piece; // the piece drawn by the server, for its ghosts and its card
    placedPieces.push(image);
  }
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
  for (const ghost of ghosts) ghost.remove();
  ghosts = [];
  if (selection) selection.classList.remove("selected");
  selection = null;
}

async function showTheMoves(image) {
  clearTheGhosts();
  selection = image;
  image.classList.add("selected");

  const answer = await send(`/moves?q=${image.dataset.q}&r=${image.dataset.r}`
    + `&s=${image.dataset.s}&piece=${encodeURIComponent(image.piece.key)}`);
  if (!answer) return;
  const { hexagons } = await answer.json();
  // The selection may have changed while the answer was awaited.
  if (selection !== image) return;

  ghosts = hexagons.map((hexagon) => createImage(image.piece, hexagon, "piece ghost"));
}

async function movePiece(image, hexagon) {
  const answer = await send("/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin: { q: Number(image.dataset.q), r: Number(image.dataset.r), s: Number(image.dataset.s) },
      destination: hexagon,
      piece: image.piece.key,
    }),
  });
  if (!answer) return;
  const { allowed, destination, tilt } = await answer.json();
  if (!allowed) return;

  clearTheGhosts();
  // The piece has been picked up: it lies down askew again, differently from last time. It is the
  // server that drew this new angle, and that keeps it - the piece will stay lying that way.
  place(image, destination, tilt);
  // If the pointer had stayed on this piece, its card must say the square it has just reached.
  if (hovered === image) showTheCard(image);
}

function onClick(event) {
  const hexagon = clickedHexagon(event);

  // The marker is taken before any sorting: "localiser" follows the finger, not the rules. A click
  // on an empty square - or on a ghost, where the piece is not yet - leaves the previous marker.
  const clicked = pieceOnHexagon(hexagon);
  if (clicked) rememberThePiece(clicked);

  if (phase.type === "combat") {
    onCombatClick(hexagon);
    return;
  }

  if (selection && ghostOnHexagon(hexagon)) {
    movePiece(selection, hexagon);
    return;
  }

  const piece = pieceOnHexagon(hexagon);
  if (!piece || piece === selection || piece.piece.side !== phase.side) {
    // Outside its movement phase, a unit does not show its squares: only the active side plays.
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
}

function clearTheCombat() {
  if (target) target.classList.remove("target");
  for (const attacker of attackers) attacker.classList.remove("attacker");
  target = null;
  attackers = new Set();
  updateCombatButtons();
}

async function onCombatClick(hexagon) {
  const piece = pieceOnHexagon(hexagon);
  if (!piece) return;

  if (piece === target) {
    clearTheCombat();
    return;
  }

  if (!target) {
    if (piece.piece.side === phase.side) return; // an opposing target is needed first
    const c = piece.dataset;
    const answer = await send(`/combat/target?cq=${c.q}&cr=${c.r}&cs=${c.s}`);
    if (!answer) return;
    const { available } = await answer.json();
    // Already attacked this phase: the refusal has gone to the server's log, and nothing reddens.
    if (!available || target) return;
    target = piece;
    target.classList.add("target");
    updateCombatButtons();
    return;
  }

  if (piece.piece.side !== phase.side) return; // another opposing unit: no effect

  if (attackers.has(piece)) {
    attackers.delete(piece);
    piece.classList.remove("attacker");
    updateCombatButtons();
    return;
  }

  const c = target.dataset;
  const a = piece.dataset;
  const answer = await send(`/combat/range?cq=${c.q}&cr=${c.r}&cs=${c.s}`
    + `&aq=${a.q}&ar=${a.r}&as=${a.s}`);
  if (!answer) return;
  const { in_range: inRange, available } = await answer.json();
  if (!inRange || !available) return; // the refusal has gone to the server's log

  attackers.add(piece);
  piece.classList.add("attacker");
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
}

async function attack() {
  if (!target || attackers.size === 0) return;
  const answer = await send("/combat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target: hexagonOfPiece(target),
      attackers: [...attackers].map(hexagonOfPiece),
    }),
  });
  if (!answer) return;
  const result = await answer.json();
  if (result.resolved) {
    for (const eliminated of result.eliminated) removeThePiece(eliminated);
  }
  clearTheCombat();
  markTheUnavailable(result.unavailable);
}

function removeThePiece(hexagon) {
  const image = pieceOnHexagon(hexagon);
  if (!image) return;
  const rank = placedPieces.indexOf(image);
  if (rank >= 0) placedPieces.splice(rank, 1);
  attackers.delete(image);
  if (target === image) target = null;
  if (lastClickedPiece === image) forgetThePiece();
  image.remove();
}

function refreshThePhase(fresh) {
  phase = fresh;
  phaseLabel.textContent = phase.label;
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
  // Nothing to tell, nothing to frame: the column only appears once the game has begun.
  log.hidden = entries.length === 0;
}


async function nextPhase() {
  const answer = await send("/phase/next", { method: "POST" });
  if (!answer) return;
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
  const answer = await fetch(url, options);
  if (answer.status === 401 || answer.status === 403) {
    const { message } = await answer.json().catch(() => ({}));
    report(message ?? "Ce n'est pas à vous de jouer.");
    return null;
  }
  return answer.ok ? answer : null;
}

function report(text) {
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
function updatePlayerButtons() {
  nextPhaseButton.disabled = !itIsMyTurn();
  attackButton.disabled = !itIsMyTurn();
}

function updateAccountButton() {
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
      button.addEventListener("click", () => takeASeat(side));
      line.appendChild(button);
    }
    tableSeats.appendChild(line);
  }
  leaveButton.hidden = table.sides.length === 0;
  // Starting from scratch against the AI requires being seated, and the other side being there to
  // give: free, or already held by the AI. A side held by a human is not there to give.
  const opposing = Object.keys(table.armies).filter((side) => !table.sides.includes(side));
  againstAIButton.hidden = table.sides.length === 0
    || !opposing.every((side) => !table.seats[side] || table.seats[side] === AI_NAME);
}

function openTheTable() {
  tableTitle.textContent = table.sides.length
    ? `Vous jouez ${table.sides.map((side) => table.armies[side]).join(", ")}`
    : "Prenez place à un camp pour jouer";
  buildTheSeats();
  tableDialog.showModal();
}

function updateTheTable(fresh) {
  table = fresh;
  updateAccountButton();
  updatePlayerButtons();
  if (tableDialog.open) openTheTable();
}

async function takeASeat(side) {
  const answer = await send("/game/seat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ side }),
  });
  if (!answer) return;
  const result = await answer.json();
  if (!result.seated) report(result.message);
  // Seated, we have nothing left to do in this dialog: it closes on the game. Leaving it open
  // would mask the map, and its modal backdrop would swallow the next click.
  else tableDialog.close();
  updateTheTable(result);
}

async function leaveTheSeat() {
  const answer = await send("/game/seat/leave", { method: "POST" });
  if (!answer) return;
  updateTheTable(await answer.json());
}

async function newGameAgainstAI() {
  const answer = await send("/game/new", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ against_ai: true }),
  });
  if (!answer) return;
  const result = await answer.json();
  // The answer carries the whole fresh game - and if the AI opened the scenario, its first turn is
  // already played: the pieces arrive as it left them.
  layThePiecesOut(result.pieces);
  refreshThePhase(result.phase);
  updateTheTable(result);
  tableDialog.close();
}

async function logOut() {
  await fetch("/logout", { method: "POST" });
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
  if (!view || !table.connected) return; // an anonymous visitor has nowhere to store it
  clearTimeout(viewTimer);
  viewTimer = setTimeout(sendTheView, VIEW_DELAY);
}

async function sendTheView() {
  const current = currentView();
  if (sameView(current, lastSentView)) return;
  lastSentView = current;
  // Without `send`: this is not a move, and a failure has nothing to report to the player - we
  // will simply find the fit again at the next load.
  await fetch("/view", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(current),
  }).catch(() => null);
}

// Restore the stored view, or open the map fitted to the window as it always has been.
function applyTheView() {
  if (!storedView || storedView.fitted) {
    view.fit();
    return;
  }
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

// Lay the scene out again, wherever the state comes from - the stream or the fallback poll.
function resumeTheGame(state) {
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
  stream = new EventSource(`/stream?version=${version}`);

  stream.addEventListener("open", () => { streamFailures = 0; });

  stream.addEventListener("message", (event) => {
    streamFailures = 0;
    resumeTheGame(JSON.parse(event.data));
  });

  // The browser reconnects by itself - server restarted, network cut, laptop woken up - and there
  // is nothing to do about it. We only count repeated failures, which say that SSE does not get
  // through here at all.
  stream.addEventListener("error", () => {
    streamFailures += 1;
    if (streamFailures < FAILURES_BEFORE_FALLBACK) return;
    closeTheStream();
    fallBackOnPolling();
  });
}

function closeTheStream() {
  if (!stream) return;
  stream.close(); // without which the browser would retry the connection indefinitely
  stream = null;
}

// The old following, kept for the sole case where the stream does not get through. It asks for the
// state again every three seconds, giving the version number we know: as long as nothing has
// moved, the server returns only that number.
function fallBackOnPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(followTheGame, POLL_PERIOD);
}

async function followTheGame() {
  // A hidden tab is watching nothing: no point keeping the server awake for it. That only holds
  // for polling - an open and silent stream costs nothing, and a hidden tab must stay up to date
  // for the moment one comes back to it.
  if (document.hidden) return;
  const answer = await fetch(`/game/state?version=${version}`).catch(() => null);
  if (!answer || !answer.ok) return; // the server is restarting: we will retry in three seconds
  const state = await answer.json();
  version = state.version;
  if (!state.changed) return;
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
  if (event.persisted && !stream && !pollTimer) openTheStream();
});

function layThePiecesOut(fresh) {
  clearTheGhosts();
  clearTheCombat();
  // The "localiser" marker aims at an image that is about to be removed from the board: we keep
  // its **square**, and put the marker back on the image that takes it over. Without that, the
  // button went off at every scene laid out again - hence, since the stream made them
  // instantaneous, just after each of one's own moves, at the precise moment when one wants to
  // find the unit one has just manoeuvred.
  const marker = lastClickedPiece ? key(lastClickedPiece.dataset) : null;

  for (const image of placedPieces) image.remove();
  placedPieces.length = 0;
  forgetThePiece();
  pieces = fresh;
  placeThePieces();

  // The unit may have been eliminated meanwhile: there is then nothing left to aim at.
  const found = marker && placedPieces.find((image) => key(image.dataset) === marker);
  if (found) rememberThePiece(found);
}

function start() {
  placeThePieces();
  phaseLabel.textContent = phase.label;
  markTheUnavailable(phase.unavailable);
  refreshTheLog(logEntries);
  document.getElementById("next-phase").addEventListener("click", nextPhase);
  attackButton.addEventListener("click", attack);
  cancelButton.addEventListener("click", clearTheCombat);
  locateButton.addEventListener("click", locate);
  playerButton.addEventListener("click", () => {
    if (table.connected) openTheTable();
    else location.href = "/login";
  });
  leaveButton.addEventListener("click", leaveTheSeat);
  againstAIButton.addEventListener("click", newGameAgainstAI);
  document.getElementById("table-logout").addEventListener("click", logOut);
  document.getElementById("table-close").addEventListener("click", () => {
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
  frame.addEventListener("scroll", rememberTheView);
  board.addEventListener("click", onClick);
  // Delegated on the board, like the click: ghosts are born and die along the way, and one
  // listener per image would have to be redone at every move.
  board.addEventListener("mouseover", (event) => {
    if (isAPlacedPiece(event.target)) showTheCard(event.target);
  });
  board.addEventListener("mouseout", (event) => {
    if (isAPlacedPiece(event.target)) hideTheCard();
  });
}

if (map.complete) {
  start();
} else {
  map.addEventListener("load", start);
}

// Resizing the window refits the map, as long as one has not set the scale oneself: that would
// undo the zoom one has just chosen.
window.addEventListener("resize", () => {
  if (view && view.followsWindow()) view.fit();
});
