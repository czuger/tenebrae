// Fixing the map's terrains by eye.
//
// The server has passed the whole map in a hidden field: hovering reads inside it, without asking
// the server anything. Only choosing a terrain makes a round trip, to go and write itself into
// tenebrae/game_box/map_fix.json. The transcribed map itself is never touched.
//
// Everything the administrator reads stays in French, terrain names included: they are the
// vocabulary of the data files.
//
// What the page does goes into the debug log (debug.js), silent unless it is turned on -
// "/admin/map_fix?debug=1", or `tenebraeDebug.on()` from the console. Hovering, which fires at
// every pointer movement, speaks at "trace"; the fixes asked for and recorded at "info".

const TOOLTIP_GAP = 16; // pixels between the pointer and the box

const mapFixTrace = debugScope("map_fix.js");

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
mapFixTrace.info("map read from the page", { hexagons: Object.keys(hexagons).length,
                                             fixes: Object.keys(fixes).length,
                                             applied: Object.keys(applied).length,
                                             terrains: terrains.length });

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
  mapFixTrace.trace("drawTheFixes", { fixes: Object.keys(fixes).length,
                                      aimed: aimed ? key(aimed) : null });
  highlight.replaceChildren();
  for (const id of Object.keys(fixes)) {
    const [q, r, s] = id.split(",").map(Number);
    highlight.appendChild(polygon({ q, r, s }, "fixed"));
  }
  if (aimed) highlight.appendChild(polygon(aimed, "aimed"));
}

function sizeTheHighlight() {
  mapFixTrace.trace("sizeTheHighlight", { width: map.naturalWidth, height: map.naturalHeight });
  highlight.setAttribute("width", map.naturalWidth);
  highlight.setAttribute("height", map.naturalHeight);
  highlight.setAttribute("viewBox", `0 0 ${map.naturalWidth} ${map.naturalHeight}`);
}

// --- Hovering ---

function showTheTooltip(id, clientX, clientY) {
  const original = mapTerrain(id);
  const fix = fixes[id];
  mapFixTrace.trace("showTheTooltip", { id, original, fix: fix ?? null });
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
  mapFixTrace.trace("hideTheTooltip", { was: aimed ? key(aimed) : null });
  tooltip.hidden = true;
  aimed = null;
  drawTheFixes();
}

function onHover(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  const id = key(hexagon);
  if (!mapTerrain(id)) {
    mapFixTrace.trace("hover outside the map", { id });
    hideTheTooltip();
    return;
  }

  if (!aimed || key(aimed) !== id) {
    mapFixTrace.trace("hexagon aimed at", { from: aimed ? key(aimed) : null, to: id });
    aimed = hexagon;
    drawTheFixes();
  }
  showTheTooltip(id, event.clientX, event.clientY);
}

// --- The fixing dialog ---

function buildTheButtons() {
  mapFixTrace.info("terrain buttons built", { terrains });
  for (const terrain of terrains) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.terrain = terrain;
    button.textContent = terrain;
    button.addEventListener("click", () => {
      mapFixTrace.info("terrain chosen", { terrain, hexagon: beingFixed ? key(beingFixed) : null });
      fix(terrain);
    });
    choiceTerrains.appendChild(button);
  }
}

function openTheChoice(hexagon) {
  const id = key(hexagon);
  const original = mapTerrain(id);
  if (!original) {
    mapFixTrace.trace("click outside the map: no dialog", { id });
    return;
  }

  beingFixed = hexagon;
  const current = currentTerrain(id);
  mapFixTrace.info("the fixing dialog opens", { id, original, current, fixed: id in fixes });
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
  if (!hexagon) {
    mapFixTrace.warn("a fix was asked for with no hexagon in hand", { terrain });
    return;
  }
  mapFixTrace.enter("fix", { hexagon: key(hexagon), terrain });

  const answer = await mapFixTrace.fetch("/admin/map_fix", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: hexagon.q, r: hexagon.r, s: hexagon.s, terrain }),
  });
  // The server alone decides: as long as it has not answered, nothing moves here.
  if (!answer.ok) {
    mapFixTrace.warn("the fix was refused, nothing moves", { status: answer.status });
    return;
  }
  const { key: id, terrain: retained, fixed } = await answer.json();
  mapFixTrace.info(fixed ? "fix recorded" : "fix withdrawn", { id, terrain: retained, fixed });

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
  mapFixTrace.trace("count", { fixes: number, applied: Object.keys(applied).length });
  counter.textContent = number === 0 ? "aucune correction"
    : number === 1 ? "1 correction" : `${number} corrections`;
  // The engine merged the map at start-up: any difference calls for restarting it.
  restart.hidden = sameFixes(fixes, applied);
  if (!restart.hidden) mapFixTrace.info("the engine no longer has the fixes in force");
}

// --- Start-up ---

function start() {
  mapFixTrace.info("start");
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
    const hexagon = hexagonOfPixel(x, y);
    mapFixTrace.info("click on the map", { hexagon: key(hexagon) });
    openTheChoice(hexagon);
  });

  choiceReset.addEventListener("click", () => {
    mapFixTrace.info("\"rétablir\" clicked", { hexagon: beingFixed ? key(beingFixed) : null });
    fix(mapTerrain(key(beingFixed)));
  });
  document.getElementById("choice-cancel").addEventListener("click", () => {
    mapFixTrace.info("the fixing dialog is cancelled");
    choice.close();
  });
  mapFixTrace.info("the fixing page is ready");
}

if (map.complete) {
  mapFixTrace.info("the map image was already loaded");
  start();
} else {
  mapFixTrace.info("waiting for the map image");
  map.addEventListener("load", start);
}
