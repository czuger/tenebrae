// Fixing the map's terrains by eye.
//
// The server has passed the whole map in a hidden field: hovering reads inside it, without asking
// the server anything. Only choosing a terrain makes a round trip, to go and write itself into
// tenebrae/game_box/map_fix.json. The transcribed map itself is never touched.
//
// Everything the administrator reads stays in French, terrain names included: they are the
// vocabulary of the data files.

const TOOLTIP_GAP = 16; // pixels between the pointer and the box

const frame = document.getElementById("frame");
const canvas = document.getElementById("canvas");
const board = document.getElementById("board");
const map = document.getElementById("map");
const highlight = document.getElementById("highlight");
const tooltip = document.getElementById("tooltip");
const counter = document.getElementById("counter");
const restart = document.getElementById("restart");
const scaleDisplay = document.getElementById("scale");

const choice = document.getElementById("choice");
const choiceTitle = document.getElementById("choice-title");
const choiceState = document.getElementById("choice-state");
const choiceTerrains = document.getElementById("choice-terrains");
const choiceReset = document.getElementById("choice-reset");

const hexagons = JSON.parse(document.getElementById("hexagons").value);
const fixes = JSON.parse(document.getElementById("fixes").value);
// The fixes the engine merged at start-up: the game's map stops there.
const applied = JSON.parse(document.getElementById("applied").value);
const terrains = JSON.parse(document.getElementById("terrains").value);
const grid = JSON.parse(document.getElementById("grid").value);
const { hexagonOfPixel, vertices } = alignment(grid);

let aimed = null; // the hexagon under the pointer
let beingFixed = null; // the one whose dialog is open

// --- The map, read from memory ---

function mapTerrain(id) {
  return hexagons[id] ?? null;
}

function currentTerrain(id) {
  return fixes[id] ?? hexagons[id] ?? null;
}

// --- Highlighting ---

function polygon(hexagon, className) {
  const shape = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  shape.setAttribute("points",
    vertices(hexagon.q, hexagon.r).map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "));
  shape.setAttribute("class", className);
  return shape;
}

function drawTheFixes() {
  highlight.replaceChildren();
  for (const id of Object.keys(fixes)) {
    const [q, r, s] = id.split(",").map(Number);
    highlight.appendChild(polygon({ q, r, s }, "fixed"));
  }
  if (aimed) highlight.appendChild(polygon(aimed, "aimed"));
}

function sizeTheHighlight() {
  highlight.setAttribute("width", map.naturalWidth);
  highlight.setAttribute("height", map.naturalHeight);
  highlight.setAttribute("viewBox", `0 0 ${map.naturalWidth} ${map.naturalHeight}`);
}

// --- Hovering ---

function showTheTooltip(id, clientX, clientY) {
  const original = mapTerrain(id);
  const fix = fixes[id];
  tooltip.textContent = `${id} — ${original}`;
  if (fix) {
    const arrow = document.createElement("span");
    arrow.className = "fix";
    arrow.textContent = ` → ${fix}`;
    tooltip.appendChild(arrow);
  }
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
  drawTheFixes();
}

function onHover(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  const id = key(hexagon);
  if (!mapTerrain(id)) {
    hideTheTooltip();
    return;
  }

  if (!aimed || key(aimed) !== id) {
    aimed = hexagon;
    drawTheFixes();
  }
  showTheTooltip(id, event.clientX, event.clientY);
}

// --- The fixing dialog ---

function buildTheButtons() {
  for (const terrain of terrains) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.terrain = terrain;
    button.textContent = terrain;
    button.addEventListener("click", () => fix(terrain));
    choiceTerrains.appendChild(button);
  }
}

function openTheChoice(hexagon) {
  const id = key(hexagon);
  const original = mapTerrain(id);
  if (!original) return;

  beingFixed = hexagon;
  const current = currentTerrain(id);
  choiceTitle.textContent = `Hexagone ${id}`;
  choiceState.textContent = fixes[id]
    ? `carte : ${original} — corrigé en ${fixes[id]}`
    : `carte : ${original}`;
  for (const button of choiceTerrains.children) {
    button.classList.toggle("current", button.dataset.terrain === current);
  }
  choiceReset.hidden = !fixes[id];
  choiceReset.textContent = `Rétablir (${original})`;
  choice.showModal();
}

async function fix(terrain) {
  const hexagon = beingFixed;
  if (!hexagon) return;

  const answer = await fetch("/admin/map_fix", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: hexagon.q, r: hexagon.r, s: hexagon.s, terrain }),
  });
  // The server alone decides: as long as it has not answered, nothing moves here.
  if (!answer.ok) return;
  const { key: id, terrain: retained, fixed } = await answer.json();

  if (fixed) fixes[id] = retained;
  else delete fixes[id];

  drawTheFixes();
  count();
  choice.close();
}

function sameFixes(ones, others) {
  // Content comparison: the order of the keys means nothing here.
  const ids = Object.keys(ones);
  return ids.length === Object.keys(others).length
    && ids.every((id) => ones[id] === others[id]);
}

function count() {
  const number = Object.keys(fixes).length;
  counter.textContent = number === 0 ? "aucune correction"
    : number === 1 ? "1 correction" : `${number} corrections`;
  // The engine merged the map at start-up: any difference calls for restarting it.
  restart.hidden = sameFixes(fixes, applied);
}

// --- Start-up ---

function start() {
  sizeTheHighlight();
  buildTheButtons();
  drawTheFixes();
  count();
  // The wheel, the "+", "-" and "ajuster" buttons: the mechanics are in zoom.js.
  zoom({ frame, canvas, board, map, display: scaleDisplay }).fit();

  board.addEventListener("mousemove", onHover);
  board.addEventListener("mouseleave", hideTheTooltip);
  board.addEventListener("click", (event) => {
    const { x, y } = pixelOfPointer(event, map);
    openTheChoice(hexagonOfPixel(x, y));
  });

  choiceReset.addEventListener("click", () => fix(mapTerrain(key(beingFixed))));
  document.getElementById("choice-cancel").addEventListener("click", () => choice.close());
}

if (map.complete) {
  start();
} else {
  map.addEventListener("load", start);
}
