// The other face of the pawns: the counters replaced by drawn icons, on demand.
//
// The board lays the counters themselves - the 1986 cardboard, photographed one by one (pieces.js).
// Fitted to the window the map is a thousand pixels wide and a counter some fifteen: what one reads
// there is a small grey square, and which of two grey squares carries the cavalry is a matter of
// memory. This file gives the same units a second face - one icon per counter, in the colour of
// the army that fields it - and the two pages that lay counters the means to swap from one face
// to the other: the board through the button in its bar, the scenario page through `?icons=1`.
//
// --- Which counter is drawn as what: `static/pawn_icons.json` ---
//
// The correspondences are not in this file, they are in one of their own, so that adding a drawing
// is editing a data file and nothing else. It is a list of pairs, one row per counter:
//
//     [photograph, icon]
//
// `photograph` is the name of the counter's photograph, `"reissland-01-15-infanteries.jpg"`, the
// one name that tells two counters apart whatever they carry. The rows follow the box, faction by
// faction, and every counter the pages can lay has one; a counter with no drawing carries an
// **empty icon**, so adding a correspondence is filling a blank in and nothing else.
//
// --- Which army is drawn in what: `static/faction_colours.json` ---
//
// The colours are a data file too, one row per faction of the box:
//
//     [faction, square, drawing]
//
// `faction` is the directory `pions/` numbers the army by. `square` is what the counter is filled
// with and `drawing` the ink the icon is drawn in, both `"#rrggbb"`; two empty strings leave the
// army the tone of the cardboard it is printed on, which is what an army nobody has coloured takes
// rather than a colour invented for it. The drawing has to read on the square: the file's test
// holds the two of them apart in brightness.
//
// --- One counter's own colours: `static/pawn_colours.json` ---
//
// An army's colours say whose the unit is; now and then a single counter is worth telling from the
// rest of its army - a named character among the rank and file. That is a third file, and it holds
// exceptions only:
//
//     [photograph, square, drawing]
//
// A counter named there is painted in those two colours instead of its army's; a counter absent
// from it - which is nearly all of them - takes its army's, as before. The file is short on
// purpose: one line is added when one counter deserves one, and there is nothing to fill in
// otherwise.
//
// --- Where the icons come from, and where their colour does ---
//
// `static/icons/` is the game-icons.net set, and it carries one variant only: a black drawing on a
// white square, which is what "000000/ffffff" says in the path. The colour is therefore put on
// here rather than in a second set of files on disk: the SVG is read once, its two fills - the
// square and the drawing - are exchanged for the army's two colours, and what comes out is a
// `data:` URL that an <img> takes as it takes any other source.
//
// That the pawn stays an <img> is the whole point of doing it this way. The selection, the ghosts,
// the hovering, the click and the tests all read `img.piece`; only the source changes, and nothing
// else in the two pages has to learn that the face has.
//
// --- Which face is showing, and the button that turns it over ---
//
// Both pages that lay counters offer the same choice, and the same button in their bar: the board
// while a game is played, the scenario page while one is composed. So the choice itself lives
// here rather than in either of them - one key in `localStorage`, one reading of the address, one
// label on the button - and each page keeps only what is its own, which is the redrawing of what
// it has on screen.
//
// It belongs to this browser, as the panel's edge does: not to the player, and not to the game.
// One key for the two pages, deliberately - a face chosen on the board is the face the scenario
// page opens on, and a counter does not change appearance because one walked from one to the
// other.
//
// --- What has no icon keeps its photograph ---
//
// A unit whose row is blank keeps its counter, and the board then shows both faces at once. That is
// the honest answer - an icon invented for a unit the table does not name would say something the
// box does not.

const pawnsTrace = debugScope("pawns.js");

// Where the choice is kept, and the two faces between which it chooses.
const PAWN_STYLE_KEY = "tenebrae.pawnStyle";
const ICON_PAWNS = "icons";
const COUNTER_PAWNS = "counters";

// The face in use. The pages read it through `pawnsAreDrawn` rather than by name: what they hand
// `dressThePawn` is a boolean, and one place decides what it is.
let pawnStyle = COUNTER_PAWNS;

// Where the set lies: the drawing's colour, the square's, the ratio, then the artist and the name.
const ICON_ROOT = "/static/icons/000000/ffffff/1x1";

// The correspondences, read once from their file (see the head of this file for their shape).
const CORRESPONDENCES_PATH = "/static/pawn_icons.json";

// The armies' colours, read the same way and from beside it.
const COLOURS_PATH = "/static/faction_colours.json";

// The counters that are painted in colours of their own rather than their army's.
const PAWN_COLOURS_PATH = "/static/pawn_colours.json";

// What turns the icons on from the address bar - "?icons=1" - and off again - "?icons=0". Both
// pages understand it, and on both it overrides what was stored.
const QUERY_KEY = "icons";
const REFUSALS = ["0", "no", "off", "false"];

// What an army whose row is blank - or absent - takes: the tone of the cardboard it is printed on,
// so that an icon never claims a colour the box does not give it. It is the one colour that is not
// a statement about an army, which is why it stays here and not in the file.
const ANY_OTHER_ARMY = { square: "#c3b393", drawing: "#2a2320" };

// Read once and kept: the correspondences, the files as they lie on disk, then the tinted result
// per army. A face swapped back and forth therefore reads nothing again, and a scenario opened on
// other units only tints what it brings.
let correspondences = null; // pawn_icons.json, as a photograph -> icon map
let armyColours = null; // faction_colours.json, as a faction -> { square, drawing } map
let pawnColours = null; // pawn_colours.json, as a photograph -> { square, drawing } map
const iconSources = new Map(); // "lorc/barbute" -> the SVG, as the file has it
// The tinted result is kept under the icon and the two colours it was painted with, not under the
// army: two counters of one army painted apart must not be handed each other's drawing.
const tintedIcons = new Map(); // "lorc/barbute|#a8cdf0|#10243d" -> the data URL an <img> takes
let loading = null; // the reading in flight, so that two clicks in a row make one

/**
 * Whether the address asks for a face: true for the icons, false for the counters, null for
 * neither - the parameter is absent and decides nothing.
 */
function pawnStyleAskedInTheAddress() {
  const asked = new URLSearchParams(window.location.search).get(QUERY_KEY);
  if (asked === null) return null;
  return !REFUSALS.includes(asked.toLowerCase());
}

async function readTheCorrespondences() {
  if (correspondences) return correspondences;
  const answer = await fetch(CORRESPONDENCES_PATH);
  if (!answer.ok) throw new Error(`the correspondences were not read (${answer.status})`);
  correspondences = new Map(await answer.json());
  pawnsTrace.info("pawn correspondences read", {
    rows: correspondences.size,
    drawn: [...correspondences.values()].filter(Boolean).length,
  });
  return correspondences;
}

/** The armies' colours, read once from their file: a blank row is an army left to the cardboard. */
async function readTheArmyColours() {
  if (armyColours) return armyColours;
  const answer = await fetch(COLOURS_PATH);
  if (!answer.ok) throw new Error(`the army colours were not read (${answer.status})`);
  const rows = await answer.json();
  armyColours = new Map(rows.filter(([, square, drawing]) => square && drawing)
                            .map(([faction, square, drawing]) => [faction, { square, drawing }]));
  pawnsTrace.info("army colours read", { rows: rows.length, coloured: armyColours.size });
  return armyColours;
}

/** The counters painted apart from their army, read once from their file: exceptions only. */
async function readThePawnColours() {
  if (pawnColours) return pawnColours;
  const answer = await fetch(PAWN_COLOURS_PATH);
  if (!answer.ok) throw new Error(`the pawn colours were not read (${answer.status})`);
  const rows = await answer.json();
  pawnColours = new Map(rows.filter(([, square, drawing]) => square && drawing)
                            .map(([photograph, square, drawing]) => [photograph,
                                                                     { square, drawing }]));
  pawnsTrace.info("pawn colours read", { rows: rows.length, apart: pawnColours.size });
  return pawnColours;
}

/** The name of the counter's photograph, which is what a row of the file is found by. */
function photographOf(piece) {
  return (piece.image ?? "").split("/").pop();
}

/**
 * The icon that counter is drawn as, or null - its row is blank, or the file is not read yet.
 */
function pawnIconOf(piece) {
  const icon = correspondences?.get(photographOf(piece));
  // The file is written by hand, and a hand copying a path off the set brings its extension with
  // it: "lorc/barbute.svg" names the same icon as "lorc/barbute", and is not a row that draws
  // nothing.
  return icon ? icon.replace(/\.svg$/i, "") : null;
}

function armyColoursOf(piece) {
  return armyColours?.get(piece.faction) ?? ANY_OTHER_ARMY;
}

/** What the counter is painted in: its own row if it has one, its army's colours otherwise. */
function pawnColoursOf(piece) {
  return pawnColours?.get(photographOf(piece)) ?? armyColoursOf(piece);
}

/** What a tinted icon is kept under: the drawing, and the two colours it was painted with. */
function tintOf(file, colours) {
  return `${file}|${colours.square}|${colours.drawing}`;
}

async function readTheIcon(file) {
  if (iconSources.has(file)) return iconSources.get(file);
  const answer = await fetch(`${ICON_ROOT}/${file}.svg`);
  if (!answer.ok) throw new Error(`${file}: the icon was not read (${answer.status})`);
  const source = await answer.text();
  iconSources.set(file, source);
  pawnsTrace.trace("icon read", { file, bytes: source.length });
  return source;
}

// Every file of the set is built the same way: one path filling the square in white, then the one
// that draws, in black. Exchanging those two fills is the whole of the colouring - no rule is
// added and no shape is touched, so an icon the set corrects tomorrow arrives corrected.
function tintTheIcon(source, colours) {
  const drawing = new DOMParser().parseFromString(source, "image/svg+xml").documentElement;
  for (const painted of drawing.querySelectorAll('[fill="#fff"]')) {
    painted.setAttribute("fill", colours.square);
  }
  for (const painted of drawing.querySelectorAll('[fill="#000"]')) {
    painted.setAttribute("fill", colours.drawing);
  }
  // The set's files carry a `viewBox` and no size. An <img> is then left without an intrinsic one,
  // which the pages do not care about - they set the counter's size themselves - but which leaves
  // `naturalWidth` at nothing, the very thing by which one knows an image has arrived. The box's
  // own dimensions are therefore written on it.
  const [, , width, height] = (drawing.getAttribute("viewBox") ?? "").split(/[\s,]+/);
  if (width && height) {
    drawing.setAttribute("width", width);
    drawing.setAttribute("height", height);
  }
  const svg = new XMLSerializer().serializeToString(drawing);
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

async function drawThePawnIcons(pieces) {
  await Promise.all([readTheCorrespondences(), readTheArmyColours(), readThePawnColours()]);

  const wanted = new Map();
  for (const piece of pieces) {
    const file = pawnIconOf(piece);
    if (!file) continue;
    const colours = pawnColoursOf(piece);
    const name = tintOf(file, colours);
    if (!tintedIcons.has(name)) wanted.set(name, { file, colours });
  }
  if (wanted.size === 0) return;

  const files = [...new Set([...wanted.values()].map((asked) => asked.file))];
  pawnsTrace.info("reading the pawn icons", { files: files.length, tints: wanted.size });
  await Promise.all(files.map(readTheIcon));
  for (const [name, { file, colours }] of wanted) {
    tintedIcons.set(name, tintTheIcon(iconSources.get(file), colours));
  }
}

/**
 * Reads the correspondences, then what the pieces in play need of the set, once.
 *
 * Called again it costs nothing as long as the same units are on the board: the file stays read,
 * what has been read stays read and what has been tinted stays tinted. It is called again after a
 * scenario is laid out, which may bring units - or an army - whose icon has not been drawn yet.
 *
 * Returns whether the icons can be shown: a file that cannot be read leaves the counters alone
 * rather than empty the board.
 */
async function loadThePawnIcons(pieces) {
  if (!loading) loading = drawThePawnIcons(pieces);
  try {
    await loading;
    return true;
  } catch (error) {
    pawnsTrace.warn("the icons could not be read: the pawns keep their photographs",
                    { error: String(error) });
    return false;
  } finally {
    loading = null;
  }
}

/** The source the piece's icon is drawn from, or null - no icon for that unit, or none read yet. */
function pawnIconSource(piece) {
  const file = pawnIconOf(piece);
  if (!file) return null;
  return tintedIcons.get(tintOf(file, pawnColoursOf(piece))) ?? null;
}

/** What a pawn wears: its icon if there is one and the icons are on, its photograph otherwise. */
function dressThePawn(image, piece, icons) {
  const icon = icons ? pawnIconSource(piece) : null;
  image.src = icon ?? `/pieces/${piece.image}`;
  image.classList.toggle("icon", Boolean(icon));
}


// --- The choice between the two faces ---

/** Whether the pawns are showing their drawn face, which is what `dressThePawn` is handed. */
function pawnsAreDrawn() {
  return pawnStyle === ICON_PAWNS;
}

function storedPawnStyle() {
  try {
    return window.localStorage.getItem(PAWN_STYLE_KEY) === ICON_PAWNS ? ICON_PAWNS : COUNTER_PAWNS;
  } catch (error) {
    // Private browsing and a blocked storage throw rather than answer: the page then opens on the
    // counters, as it always has.
    return COUNTER_PAWNS;
  }
}

function rememberThePawnStyle(style) {
  try {
    window.localStorage.setItem(PAWN_STYLE_KEY, style);
  } catch (error) {
    // Nothing to do: the choice will simply not survive the reload.
  }
}

/**
 * Settles the face the page opens on, and returns it.
 *
 * The address decides when it says anything - "?icons=1", "?icons=0" - and what it says is kept,
 * as the debug log keeps what "?debug=1" asked for: one opens a page on a face, and it is still
 * that face on the next load. Said nothing, the address leaves the stored choice alone.
 */
function settleThePawnStyle() {
  const asked = pawnStyleAskedInTheAddress();
  pawnStyle = asked === null ? storedPawnStyle() : (asked ? ICON_PAWNS : COUNTER_PAWNS);
  if (asked !== null) {
    pawnsTrace.info("the address asks for a face", { style: pawnStyle });
    rememberThePawnStyle(pawnStyle);
  }
  return pawnStyle;
}

/** Turns the face over and keeps it. The redrawing is the page's own business. */
function turnThePawnStyleOver() {
  pawnStyle = pawnsAreDrawn() ? COUNTER_PAWNS : ICON_PAWNS;
  pawnsTrace.info("the face of the pawns is turned over", { style: pawnStyle });
  rememberThePawnStyle(pawnStyle);
  return pawnStyle;
}

/**
 * Says on the button which face is showing.
 *
 * The button **keeps its sign** rather than swapping it - the bars are held to a reference size,
 * and a second glyph is not held to the width of the first - so what it says is in `aria-pressed`
 * and in its tooltip.
 */
function labelThePawnStyleButton(button) {
  button.setAttribute("aria-pressed", String(pawnsAreDrawn()));
  button.title = pawnsAreDrawn()
    ? "Revenir aux pions photographiés (S)"
    : "Afficher les pions en icônes (S)";
}
