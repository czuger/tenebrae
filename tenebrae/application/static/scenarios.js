// Composing a scenario: pieces taken from the palette and laid on the map, then saved as a file.
//
// The server has passed everything in hidden fields - the palette, the grid, the whole map:
// placing, moving and removing ask it nothing. Only saving makes a round trip, to write a new file
// into tenebrae/scenarios/ in the format the engine reads. Nothing here knows the rules beyond the
// squares the server said no unit can occupy; the server checks everything again when saving.
//
// The same page edits a scenario: opened on /admin/scenarios/<number>/edit, it lays the file's
// pieces at start-up and fills the dialog with its title and turns; saving then rewrites that file.
// The chooser in the toolbar goes from one scenario to another, or back to a new one.
//
// One thing in hand at a time: a palette piece, which each click on a free square lays down again
// - fifteen orc infantry are fifteen clicks -, or a placed piece, which the next click moves and
// the "Retirer" button removes. Escape empties the hand.
//
// Everything the administrator reads stays in French; only the code is English.
//
// What the page does goes into the debug log (debug.js), silent unless it is turned on -
// "/admin/scenarios?debug=1", or `tenebraeDebug.on()` from the console. What is in hand, what is
// laid, moved or removed, and the saving with the server's answer are at "info"; hovering, which
// fires at every pointer movement, at "trace".

const TOOLTIP_GAP = 16; // pixels between the pointer and the box

const scenariosTrace = debugScope("scenarios.js");
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
const chooser = document.getElementById("chooser");
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
const scenarios = JSON.parse(document.getElementById("scenarios").value);
// The scenario being edited - number, name, max_turns, placement -, or null for a new one.
const scenario = JSON.parse(document.getElementById("scenario").value || "null");
const piecesByKey = new Map(catalogue.map((piece) => [piece.key, piece]));
const { centre, hexagonOfPixel, vertices } = alignment(grid);
const { place, createImage } = pieceLayer({ board, centre, pieceSize: grid.piece_size });
scenariosTrace.info("page loaded", { catalogue: catalogue.length,
                                     hexagons: Object.keys(hexagons).length,
                                     forbidden: forbidden.size, scenarios: scenarios.length,
                                     editing: scenario ? scenario.number : null });

const placed = []; // the images laid on the map
let chosen = null; // the palette piece in hand, with its button: { piece, button }
let selected = null; // the placed image in hand
let aimed = null; // the hexagon under the pointer
let view = null; // the zoom, mounted once the map has loaded

// --- The palette ---

function buildThePalette() {
  scenariosTrace.enter("buildThePalette", { pieces: catalogue.length });
  let faction = null;
  let list = null;
  for (const piece of catalogue) {
    if (piece.faction !== faction) {
      faction = piece.faction;
      list = openAFaction(faction, piece.side);
    }
    list.appendChild(paletteButton(piece));
  }
  scenariosTrace.exit("buildThePalette",
                      { factions: paletteFactions.querySelectorAll("section").length });
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
  button.addEventListener("click", () => {
    scenariosTrace.info("palette piece clicked", { piece: piece.key, name: piece.name });
    take(piece, button);
  });
  return button;
}

// --- The chooser: which scenario the page works on ---

function buildTheChooser() {
  for (const entry of scenarios) {
    const option = document.createElement("option");
    option.value = entry.number;
    // A scenario disabled by hand in its file is still edited here - that is the only way back -,
    // but it is marked: it is no longer offered when a new game is opened.
    option.textContent = `n° ${entry.number} — ${entry.name}`
      + (entry.enabled ? "" : " (désactivé)");
    chooser.appendChild(option);
  }
  chooser.value = scenario ? String(scenario.number) : "";
  chooser.addEventListener("change", () => {
    scenariosTrace.info("another scenario chosen, leaving the page", { number: chooser.value });
    window.location.href = chooser.value ? `/admin/scenarios/${chooser.value}/edit`
      : "/admin/scenarios";
  });
}

// --- The scenario being edited: its pieces laid at start-up, its title in the dialog ---

function hexagonOfKey(id) {
  const [q, r, s] = id.split(",").map(Number);
  return { q, r, s };
}

function layTheScenario() {
  if (!scenario) {
    scenariosTrace.info("a new scenario: nothing to lay out");
    return;
  }
  scenariosTrace.enter("layTheScenario", { number: scenario.number, name: scenario.name,
                                           squares: Object.keys(scenario.placement).length });
  const unknown = [];
  for (const [id, pieceKey] of Object.entries(scenario.placement)) {
    const piece = piecesByKey.get(pieceKey);
    if (piece) layAPiece(piece, hexagonOfKey(id));
    else unknown.push(`${pieceKey} (${id})`);
  }
  // A piece the palette does not offer cannot be laid, and a save would drop it: say so.
  if (unknown.length) {
    scenariosTrace.warn("pieces the palette does not offer, not laid out", { unknown });
    report(`Pions absents de la palette, non affichés : ${unknown.join(", ")}.`);
  }
  saveName.value = scenario.name;
  saveTurns.value = scenario.max_turns ?? "";
  scenariosTrace.exit("layTheScenario", { laid: placed.length, unknown: unknown.length });
}

// --- What is in hand ---

function take(piece, button) {
  const again = chosen && chosen.piece === piece;
  emptyTheHand();
  if (again) {
    scenariosTrace.info("the same palette piece again: the hand stays empty",
                        { piece: piece.key });
    return; // a second click on the same piece puts it back
  }
  scenariosTrace.info("palette piece in hand", { piece: piece.key, name: piece.name });
  chosen = { piece, button };
  button.classList.add("selected");
  showInHand(`en main : ${piece.name}`);
}

function select(image) {
  emptyTheHand();
  scenariosTrace.info("placed piece in hand", { piece: image.piece.key,
                                                square: key(image.dataset) });
  selected = image;
  image.classList.add("selected");
  removeButton.hidden = false;
  showInHand(`${image.piece.name} — ${key(image.dataset)}`);
}

function emptyTheHand() {
  if (chosen || selected) {
    scenariosTrace.trace("the hand is emptied", { palette: chosen?.piece?.key ?? null,
                                                  placed: selected?.piece?.key ?? null });
  }
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
  scenariosTrace.info("piece laid", { piece: piece.key, square: key(hexagon) });
  const image = createImage(piece, hexagon, "piece");
  image.dataset.key = piece.key;
  image.title = piece.name;
  placed.push(image);
  count();
}

function removeThePiece(image) {
  scenariosTrace.info("piece removed", { piece: image.piece.key, square: key(image.dataset) });
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
  scenariosTrace.trace("count", { pieces: number, saveEnabled: !saveButton.disabled });
}

function onClick(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  const id = key(hexagon);
  scenariosTrace.info("click on the map", { square: id, terrain: hexagons[id] ?? null,
                                            inHand: chosen?.piece?.key ?? null,
                                            selected: selected?.piece?.key ?? null });
  if (!(id in hexagons)) {
    scenariosTrace.trace("click outside the map", { square: id });
    return;
  }

  // A placed piece comes before whatever is in hand: clicking it takes it, clicking it again
  // puts it back.
  const occupant = pieceOn(hexagon);
  if (occupant) {
    if (occupant === selected) emptyTheHand();
    else select(occupant);
    return;
  }
  if (forbidden.has(id)) {
    scenariosTrace.warn("square refused to any unit", { square: id, terrain: hexagons[id] });
    report(`Un pion ne peut pas occuper cette case (${hexagons[id]}).`);
    return;
  }
  if (selected) {
    // Picked up, the piece lies down askew again: the layer draws it a new angle.
    scenariosTrace.info("placed piece moved", { piece: selected.piece.key,
                                                from: key(selected.dataset), to: id });
    place(selected, hexagon);
    showInHand(`${selected.piece.name} — ${id}`);
    return;
  }
  if (chosen) layAPiece(chosen.piece, hexagon);
  else scenariosTrace.trace("nothing in hand: the click lays nothing", { square: id });
}

function onKey(event) {
  if (saveDialog.open) return; // the keys belong to the form
  scenariosTrace.trace("key pressed", { key: event.key,
                                        selected: selected?.piece?.key ?? null });
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
  scenariosTrace.trace("drawTheHighlight", { aimed: aimed ? key(aimed) : null,
                                             refused: aimed ? forbidden.has(key(aimed)) : null });
  highlight.replaceChildren();
  if (aimed) highlight.appendChild(polygon(aimed, forbidden.has(key(aimed)) ? "refused" : "aimed"));
}

function sizeTheHighlight() {
  scenariosTrace.trace("sizeTheHighlight", { width: map.naturalWidth,
                                             height: map.naturalHeight });
  highlight.setAttribute("width", map.naturalWidth);
  highlight.setAttribute("height", map.naturalHeight);
  highlight.setAttribute("viewBox", `0 0 ${map.naturalWidth} ${map.naturalHeight}`);
}

function showTheTooltip(hexagon, clientX, clientY) {
  const id = key(hexagon);
  const occupant = pieceOn(hexagon);
  scenariosTrace.trace("showTheTooltip", { square: id, terrain: hexagons[id],
                                           occupant: occupant?.piece?.key ?? null });
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
  scenariosTrace.trace("hideTheTooltip", { was: aimed ? key(aimed) : null });
  tooltip.hidden = true;
  aimed = null;
  drawTheHighlight();
}

function onHover(event) {
  const { x, y } = pixelOfPointer(event, map);
  const hexagon = hexagonOfPixel(x, y);
  if (!(key(hexagon) in hexagons)) {
    scenariosTrace.trace("hover outside the map", { square: key(hexagon) });
    hideTheTooltip();
    return;
  }
  if (!aimed || key(aimed) !== key(hexagon)) {
    scenariosTrace.trace("hexagon aimed at", { from: aimed ? key(aimed) : null,
                                               to: key(hexagon) });
    aimed = hexagon;
    drawTheHighlight();
  }
  showTheTooltip(hexagon, event.clientX, event.clientY);
}

// --- Saying what was refused ---

function report(text) {
  scenariosTrace.info("message shown to the administrator", { text });
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
  scenariosTrace.info("the save dialog opens", { pieces: placed.length,
                                                 name: saveName.value,
                                                 turns: saveTurns.value });
  saveError.hidden = true;
  saveDialog.showModal();
  saveName.focus();
}

async function save(event) {
  event.preventDefault();
  const turns = saveTurns.value.trim();
  scenariosTrace.enter("save", { url: saveForm.dataset.url, name: saveName.value.trim(),
                                 turns, pieces: placed.length });
  const answer = await scenariosTrace.fetch(saveForm.dataset.url, {
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
    scenariosTrace.warn("the scenario was not saved", { reached: Boolean(answer),
                                                        status: answer?.status ?? null,
                                                        message: result.message ?? null });
    saveError.textContent = result.message ?? "Le scénario n'a pas pu être enregistré.";
    saveError.hidden = false;
    return;
  }
  saveDialog.close();
  scenariosTrace.exit("save", { number: result.number, file: result.file, units: result.units });
  statusArea.textContent = `Scénario n° ${result.number} ${scenario ? "modifié" : "enregistré"} : `
    + `${result.file} (${result.units} ${result.units === 1 ? "pion" : "pions"})`;
  statusArea.hidden = false;
  // A new title renames the file and the chooser's entry.
  if (scenario) chooser.selectedOptions[0].textContent = `n° ${result.number} — ${result.name}`;
}

// --- Start-up ---

function start() {
  scenariosTrace.info("start");
  sizeTheHighlight();
  buildThePalette();
  buildTheChooser();
  layTheScenario();
  count();
  // The wheel, the "+", "-" and "ajuster" buttons: the mechanics are in zoom.js.
  view = zoom({ frame, canvas, board, map, display: document.getElementById("scale") });
  view.fit();

  board.addEventListener("click", onClick);
  board.addEventListener("mousemove", onHover);
  board.addEventListener("mouseleave", hideTheTooltip);
  document.addEventListener("keydown", onKey);
  removeButton.addEventListener("click", () => {
    scenariosTrace.info("\"retirer\" clicked", { selected: selected?.piece?.key ?? null });
    if (selected) removeThePiece(selected);
  });
  saveButton.addEventListener("click", openTheSaveDialog);
  saveForm.addEventListener("submit", save);
  document.getElementById("save-cancel").addEventListener("click", () => {
    scenariosTrace.info("the save dialog is cancelled");
    saveDialog.close();
  });
  scenariosTrace.info("the scenario page is ready");
}

if (map.complete) {
  scenariosTrace.info("the map image was already loaded");
  start();
} else {
  scenariosTrace.info("waiting for the map image");
  map.addEventListener("load", start);
}

// Resizing the window refits the map, as long as one has not set the scale oneself.
window.addEventListener("resize", () => {
  scenariosTrace.trace("window resized", { fitted: view ? view.followsWindow() : null });
  if (view && view.followsWindow()) view.fit();
});
