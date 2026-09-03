// Composing a scenario: pieces taken from the palette and laid on the map, then saved as a file.
//
// The server has passed everything in hidden fields - the palette, the grid, the whole map:
// placing, moving and removing ask it nothing. Only saving makes a round trip, to write a new file
// into tenebrae/scenarios/ in the format the engine reads. Nothing here knows the rules beyond the
// squares the server said no unit can occupy; the server checks everything again when saving.
//
// One thing in hand at a time: a palette piece, which each click on a free square lays down again
// - fifteen orc infantry are fifteen clicks -, or a placed piece, which the next click moves and
// the "Retirer" button removes. Escape empties the hand.
//
// Everything the administrator reads stays in French; only the code is English.

const TOOLTIP_GAP = 16; // pixels between the pointer and the box
const MESSAGE_DELAY = 4000; // milliseconds

// The sides, as the palette headings say them.
const SIDE_LABELS = { alliance: "Alliance", tenebres: "Ténèbres", neutre: "neutre" };

const frame = document.getElementById("frame");
const canvas = document.getElementById("canvas");
const board = document.getElementById("board");
const map = document.getElementById("map");
const highlight = document.getElementById("highlight");
const tooltip = document.getElementById("tooltip");
const messageArea = document.getElementById("message");
const statusArea = document.getElementById("status");
const counter = document.getElementById("counter");
const inHand = document.getElementById("in-hand");
const removeButton = document.getElementById("remove");
const saveButton = document.getElementById("save");
const paletteFactions = document.getElementById("palette-factions");

const saveDialog = document.getElementById("save-dialog");
const saveForm = document.getElementById("save-form");
const saveName = document.getElementById("save-name");
const saveTurns = document.getElementById("save-turns");
const saveError = document.getElementById("save-error");

const catalogue = JSON.parse(document.getElementById("pieces").value);
const grid = JSON.parse(document.getElementById("grid").value);
const hexagons = JSON.parse(document.getElementById("hexagons").value);
const forbidden = new Set(JSON.parse(document.getElementById("forbidden").value));
const { centre, hexagonOfPixel, vertices } = alignment(grid);
const { place, createImage } = pieceLayer({ board, centre, pieceSize: grid.piece_size });

const placed = []; // the images laid on the map
let chosen = null; // the palette piece in hand, with its button: { piece, button }
let selected = null; // the placed image in hand
let aimed = null; // the hexagon under the pointer
let view = null; // the zoom, mounted once the map has loaded

// --- The palette ---

function buildThePalette() {
  let faction = null;
  let list = null;
  for (const piece of catalogue) {
    if (piece.faction !== faction) {
      faction = piece.faction;
      list = openAFaction(faction, piece.side);
    }
    list.appendChild(paletteButton(piece));
  }
}

// A heading per faction - its name without its number, and its side - then its pieces.
function openAFaction(faction, side) {
  const section = document.createElement("section");
  section.className = "faction";
  const heading = document.createElement("h3");
  heading.textContent = `${faction.split("-").slice(1).join(" ")} — ${SIDE_LABELS[side] ?? side}`;
  const list = document.createElement("div");
  list.className = "faction-pieces";
  section.append(heading, list);
  paletteFactions.appendChild(section);
  return list;
}

function paletteButton(piece) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "palette-piece";
  button.dataset.key = piece.key;
  button.title = piece.name;
  const image = document.createElement("img");
  image.src = `/pieces/${piece.image}`;
  image.alt = "";
  image.loading = "lazy";
  const label = document.createElement("span");
  // The faction is in the heading: the button keeps the description alone.
  label.textContent = piece.name.split(" · ").pop();
  button.append(image, label);
  button.addEventListener("click", () => take(piece, button));
  return button;
}

// --- What is in hand ---

function take(piece, button) {
  const again = chosen && chosen.piece === piece;
  emptyTheHand();
  if (again) return; // a second click on the same piece puts it back
  chosen = { piece, button };
  button.classList.add("selected");
  showInHand(`en main : ${piece.name}`);
}

function select(image) {
  emptyTheHand();
  selected = image;
  image.classList.add("selected");
  removeButton.hidden = false;
  showInHand(`${image.piece.name} — ${key(image.dataset)}`);
}

function emptyTheHand() {
  if (chosen) chosen.button.classList.remove("selected");
  chosen = null;
  if (selected) selected.classList.remove("selected");
  selected = null;
  removeButton.hidden = true;
  inHand.hidden = true;
}

function showInHand(text) {
  inHand.textContent = text;
  inHand.hidden = false;
}

// --- The pieces on the map ---

function pieceOn(hexagon) {
  return placed.find((image) => image.dataset.q === String(hexagon.q)
    && image.dataset.r === String(hexagon.r)) ?? null;
}

function layAPiece(piece, hexagon) {
  const image = createImage(piece, hexagon, "piece");
  image.piece = piece;
  image.dataset.key = piece.key;
  image.title = piece.name;
  placed.push(image);
  count();
}

function removeThePiece(image) {
  const rank = placed.indexOf(image);
  if (rank >= 0) placed.splice(rank, 1);
  image.remove();
  if (selected === image) emptyTheHand();
  count();
}

function count() {
  const number = placed.length;
  counter.textContent = number === 0 ? "aucun pion" : number === 1 ? "1 pion" : `${number} pions`;
  saveButton.disabled = number === 0;
}

function onClick(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  const id = key(hexagon);
  if (!(id in hexagons)) return;

  // A placed piece comes before whatever is in hand: clicking it takes it, clicking it again
  // puts it back.
  const occupant = pieceOn(hexagon);
  if (occupant) {
    if (occupant === selected) emptyTheHand();
    else select(occupant);
    return;
  }
  if (forbidden.has(id)) {
    report(`Un pion ne peut pas occuper cette case (${hexagons[id]}).`);
    return;
  }
  if (selected) {
    // Picked up, the piece lies down askew again: the layer draws it a new angle.
    place(selected, hexagon);
    showInHand(`${selected.piece.name} — ${id}`);
    return;
  }
  if (chosen) layAPiece(chosen.piece, hexagon);
}

function onKey(event) {
  if (saveDialog.open) return; // the keys belong to the form
  if (event.key === "Escape") emptyTheHand();
  if ((event.key === "Delete" || event.key === "Backspace") && selected) {
    removeThePiece(selected);
  }
}

// --- Hovering: the hexagon aimed at, and its terrain ---

function polygon(hexagon, className) {
  const shape = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  shape.setAttribute("points",
    vertices(hexagon.q, hexagon.r).map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "));
  shape.setAttribute("class", className);
  return shape;
}

function drawTheHighlight() {
  highlight.replaceChildren();
  if (aimed) highlight.appendChild(polygon(aimed, forbidden.has(key(aimed)) ? "refused" : "aimed"));
}

function sizeTheHighlight() {
  highlight.setAttribute("width", map.naturalWidth);
  highlight.setAttribute("height", map.naturalHeight);
  highlight.setAttribute("viewBox", `0 0 ${map.naturalWidth} ${map.naturalHeight}`);
}

function showTheTooltip(hexagon, clientX, clientY) {
  const id = key(hexagon);
  const occupant = pieceOn(hexagon);
  tooltip.textContent = occupant ? `${id} — ${hexagons[id]} — ${occupant.piece.name}`
    : `${id} — ${hexagons[id]}`;
  tooltip.hidden = false;

  // The box moves to the other side of the pointer when it would overflow the window.
  const size = tooltip.getBoundingClientRect();
  const x = clientX + TOOLTIP_GAP + size.width > window.innerWidth
    ? clientX - TOOLTIP_GAP - size.width : clientX + TOOLTIP_GAP;
  const y = clientY + TOOLTIP_GAP + size.height > window.innerHeight
    ? clientY - TOOLTIP_GAP - size.height : clientY + TOOLTIP_GAP;
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideTheTooltip() {
  tooltip.hidden = true;
  aimed = null;
  drawTheHighlight();
}

function onHover(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  if (!(key(hexagon) in hexagons)) {
    hideTheTooltip();
    return;
  }
  if (!aimed || key(aimed) !== key(hexagon)) {
    aimed = hexagon;
    drawTheHighlight();
  }
  showTheTooltip(hexagon, event.clientX, event.clientY);
}

// --- Saying what was refused ---

function report(text) {
  messageArea.textContent = text;
  messageArea.hidden = false;
  clearTimeout(report.timer);
  report.timer = setTimeout(() => { messageArea.hidden = true; }, MESSAGE_DELAY);
}

// --- Saving ---

function placement() {
  const squares = {};
  for (const image of placed) squares[key(image.dataset)] = image.piece.key;
  return squares;
}

function openTheSaveDialog() {
  saveError.hidden = true;
  saveDialog.showModal();
  saveName.focus();
}

async function save(event) {
  event.preventDefault();
  const turns = saveTurns.value.trim();
  const answer = await fetch("/admin/scenarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: saveName.value.trim(),
      max_turns: turns === "" ? null : Number(turns),
      placement: placement(),
    }),
  }).catch(() => null);
  const result = answer ? await answer.json().catch(() => ({})) : {};
  // The server alone decides: its refusal is read in the dialog, which stays open.
  if (!answer || !result.saved) {
    saveError.textContent = result.message ?? "Le scénario n'a pas pu être enregistré.";
    saveError.hidden = false;
    return;
  }
  saveDialog.close();
  statusArea.textContent = `Scénario n° ${result.number} enregistré : ${result.file} `
    + `(${result.units} ${result.units === 1 ? "pion" : "pions"})`;
  statusArea.hidden = false;
}

// --- Start-up ---

function start() {
  sizeTheHighlight();
  buildThePalette();
  count();
  // The wheel, the "+", "-" and "ajuster" buttons: the mechanics are in zoom.js.
  view = zoom({ frame, canvas, board, map, display: document.getElementById("scale") });
  view.fit();

  board.addEventListener("click", onClick);
  board.addEventListener("mousemove", onHover);
  board.addEventListener("mouseleave", hideTheTooltip);
  document.addEventListener("keydown", onKey);
  removeButton.addEventListener("click", () => { if (selected) removeThePiece(selected); });
  saveButton.addEventListener("click", openTheSaveDialog);
  saveForm.addEventListener("submit", save);
  document.getElementById("save-cancel").addEventListener("click", () => saveDialog.close());
}

if (map.complete) {
  start();
} else {
  map.addEventListener("load", start);
}

// Resizing the window refits the map, as long as one has not set the scale oneself.
window.addEventListener("resize", () => {
  if (view && view.followsWindow()) view.fit();
});
