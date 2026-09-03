// Zooming in and out on the map, shared by the pages that display it.
//
// The zoom scales #board. Its transform does not count in the layout: it is #canvas that carries
// the visible size, and hence the scrollbars of #frame. Everything placed on the map - the pieces,
// the highlight - stays expressed in map.jpg pixels and therefore has nothing to recompute when
// the scale changes.
//
// Nothing here knows the game: only the map image and the four elements that carry it, plus the
// toolbar buttons if they exist.
//
// Nor does anything here keep anything from one load to the next. A page that wants to find its
// view again on reload uses the three pieces exposed for that - `scale()`, `viewedCentre()` to
// read it, `set()` to restore it - and decides by itself where to store it: it is `map.js` that
// sends it to the server, and `map_fix.html`, which loads the same zoom, does nothing with it.

const MIN_SCALE = 0.05;
const MAX_SCALE = 1;
const BUTTON_STEP = 1.25; // one notch of "+" or "-"
const WHEEL_STEP = 0.002; // per pixel of scroll

function zoom({ frame, canvas, board, map, display, onChange }) {
  let scale = 1;
  // As long as nobody has touched the scale, the map follows the window and refits with it.
  let fittedToWindow = true;

  function fitScale() {
    // The frame's box, not the window's: a page that keeps a panel beside the map - the scenario
    // page and its palette - fits the map into what is left.
    const visible = frame.getBoundingClientRect();
    return Math.min(visible.width / map.naturalWidth, visible.height / map.naturalHeight);
  }

  function apply(value) {
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
    board.style.transform = `scale(${scale})`;
    canvas.style.width = `${map.naturalWidth * scale}px`;
    canvas.style.height = `${map.naturalHeight * scale}px`;
    if (display) display.textContent = `${Math.round(scale * 100)} %`;
  }

  function change(value, clientX, clientY) {
    // The point of the map under the pointer must stay there: we read it before, and replace the
    // scroll after.
    const point = pixelOfPointer({ clientX, clientY }, map);
    apply(value);
    fittedToWindow = false;
    const visible = frame.getBoundingClientRect();
    frame.scrollLeft = point.x * scale + visible.x - clientX;
    frame.scrollTop = point.y * scale + visible.y - clientY;
    if (onChange) onChange();
  }

  function frameCentre() {
    const visible = frame.getBoundingClientRect();
    return [visible.x + visible.width / 2, visible.y + visible.height / 2];
  }

  function fit() {
    apply(fitScale());
    fittedToWindow = true;
    frame.scrollTo(0, 0);
    if (onChange) onChange();
  }

  // Setting a scale without aiming at anything: that is what it takes to **restore** a stored
  // view, whose centre will be replaced just afterwards by `centreOn`. It leaves the fitted state,
  // like a wheel turn - the view being restored is that of someone who had set their zoom.
  // Nothing is signalled: putting back what we have just read is not a change.
  function set(value) {
    apply(value);
    fittedToWindow = false;
  }

  // Bring a point given in map.jpg pixels to the middle of the window. The canvas is centred by
  // its automatic margins as long as the map fits in the window: its offset therefore enters the
  // reckoning. The scroll bounds itself - a point near an edge comes as close to the centre as
  // the map allows, and nothing moves when the map fits entirely on screen.
  function centreOn(x, y) {
    // `clientWidth` and not the frame's rectangle: that is the visible part, scrollbars deducted,
    // and it is at its middle that the point must come.
    frame.scrollLeft = canvas.offsetLeft + x * scale - frame.clientWidth / 2;
    frame.scrollTop = canvas.offsetTop + y * scale - frame.clientHeight / 2;
  }

  // The inverse of `centreOn`: which point of the map is currently at the middle of the window.
  // That is what a page stores to find its view again, and not the scroll: a `scrollLeft` in
  // screen pixels would mean nothing at another scale, nor on another screen.
  function viewedCentre() {
    return {
      x: (frame.scrollLeft - canvas.offsetLeft + frame.clientWidth / 2) / scale,
      y: (frame.scrollTop - canvas.offsetTop + frame.clientHeight / 2) / scale,
    };
  }

  function bind(identifier, action) {
    document.getElementById(identifier)?.addEventListener("click", action);
  }

  frame.addEventListener("wheel", (event) => {
    event.preventDefault();
    change(scale * Math.exp(-event.deltaY * WHEEL_STEP), event.clientX, event.clientY);
  }, { passive: false });

  bind("zoom-in", () => change(scale * BUTTON_STEP, ...frameCentre()));
  bind("zoom-out", () => change(scale / BUTTON_STEP, ...frameCentre()));
  bind("fit", fit);

  // `followsWindow` says whether the scale is still the fitted one: a page being resized can thus
  // refit without undoing the zoom one has just set by hand. `centreOn` is left to the pages: the
  // one that knows what is on the map says what to aim at.
  return { fit, centreOn, set, viewedCentre, scale: () => scale,
           followsWindow: () => fittedToWindow };
}
