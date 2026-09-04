// The other face of the pawns: the counters replaced by drawn icons, on demand.
//
// The board lays the counters themselves - the 1986 cardboard, photographed one by one (pieces.js).
// Fitted to the window the map is a thousand pixels wide and a counter some fifteen: what one reads
// there is a small grey square, and which of two grey squares carries the cavalry is a matter of
// memory. This file gives the same units a second face - one icon per kind of unit, in the colour
// of the army that fields it - and map.js the means to swap from one face to the other.
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
// else in the board has to learn that the face has.
//
// --- What has no icon keeps its photograph ---
//
// Five kinds of unit are drawn, which are the five the battle of Reissland fields. A phalanx, a
// ram, a leader, the populace have none: their counter stays as it is, and the board then shows
// both faces at once. That is the honest answer - an icon invented for a unit the table does not
// name would say something the box does not.

const pawnsTrace = debugScope("pawns.js");

// Where the set lies: the drawing's colour, the square's, the ratio, then the artist and the name.
const ICON_ROOT = "/static/icons/000000/ffffff/1x1";

// The icons, in the counters' own vocabulary: `symbole` as `pions.json` writes it and, where the
// symbol alone does not tell two counters apart, the values read off them. The infantries of the
// Reissland battle are two - 4/4 and 6/4 - and they wear two different helmets; every other kind
// is named by its symbol alone. The first entry that fits wins, so the ones carrying values come
// before the ones that do not.
const PAWN_ICONS = [
  { symbol: "infanterie", strength: 4, movement: 4, icon: "lorc/barbute" },
  { symbol: "infanterie", strength: 6, movement: 4, icon: "lorc/visored-helm" },
  { symbol: "cavalerie", icon: "delapouite/cavalry" },
  { symbol: "archer", icon: "lorc/bowman" },
  { symbol: "catapulte", icon: "heavenly-dog/catapult" },
];

// The two armies of the Reissland battle, told apart by their blue: Reissland's is clear, Yzent's
// is deep. The key is the faction as `pions.json` numbers it, and the drawing takes the colour
// that reads on the square - dark on the clear blue, pale on the deep one.
const ARMY_COLOURS = {
  "02-reissland": { square: "#a8cdf0", drawing: "#10243d" },
  "01-yzent": { square: "#16306b", drawing: "#dce8f7" },
};

// Every other faction. The two blues were given for the two armies above, and a blue invented for
// the dwarves would tell the player they have one: what the others take is the tone of the
// cardboard they are printed on, so that an icon never claims a colour the box does not give it.
const ANY_OTHER_ARMY = { square: "#c3b393", drawing: "#2a2320" };

// Read once and kept: the file as it lies on disk, then the tinted result per army. A pawn style
// swapped back and forth therefore reads nothing again, and a scenario opened on other units only
// tints what it brings.
const iconSources = new Map(); // "lorc/barbute" -> the SVG, as the file has it
const tintedIcons = new Map(); // "lorc/barbute|02-reissland" -> the data URL an <img> takes
let loading = null; // the reading in flight, so that two clicks in a row make one

function pawnIconOf(piece) {
  const found = PAWN_ICONS.find((entry) => entry.symbol === piece.symbol
    && (entry.strength === undefined || entry.strength === piece.strength)
    && (entry.movement === undefined || entry.movement === piece.movement));
  return found ? found.icon : null;
}

function armyColoursOf(piece) {
  return ARMY_COLOURS[piece.faction] ?? ANY_OTHER_ARMY;
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
  // which the board does not care about - it sets the counter's size itself - but which leaves
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
  const wanted = new Map();
  for (const piece of pieces) {
    const file = pawnIconOf(piece);
    if (!file) continue;
    const name = `${file}|${piece.faction}`;
    if (!tintedIcons.has(name)) wanted.set(name, { file, colours: armyColoursOf(piece) });
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
 * Reads and tints what the pieces in play need, once.
 *
 * Called again it costs nothing as long as the same units are on the board: what has been read
 * stays read and what has been tinted stays tinted. It is called again after a scenario is laid
 * out, which may bring units - or an army - that had no icon drawn yet.
 *
 * Returns whether the icons can be shown: a set that cannot be read leaves the counters alone
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
  return tintedIcons.get(`${file}|${piece.faction}`) ?? null;
}
