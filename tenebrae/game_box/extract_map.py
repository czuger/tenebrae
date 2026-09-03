#!/usr/bin/env python3
"""Extraction of the *Ave Tenebrae* hexagon grid from `map.jpg`.

Produces, in the current directory:

* `carte.json`          - dict `"q,r,s"` -> main terrain
* `carte_details.json`  - dict `"q,r,s"` -> list of every element of the hexagon
* `carte_controle.jpg`  - the map at a third of its size, each hexagon tinted with its terrain

Terrain names are in French: they are the vocabulary of the transcribed data, which the whole
project reads as it stands. Only the code around them is English.

Dependencies: Pillow, numpy, scipy.
Duration: about ten minutes, ~2 GB of memory.

The method is described in `map.md`. The numeric settings below were tuned on this precise scan
(6173 x 5102 px) and are not meant to be generic.
"""

from __future__ import annotations

import collections
import json
import sys
import warnings

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None

MAP = "map.jpg"

# Number of actually playable columns and rows. The hexagons that overflow are covered by the
# map's brown border; read by eye along the four edges.
COLUMNS, ROWS = 57, 40

# Seed for the grid alignment: step measured by autocorrelation of the white lines (period
# 107.6 px in x, 125.7 px in y) and approximate phase. The least-squares fit that follows
# converges to the exact grid from there.
SEED_SIZE = 72.2
SEED_ORIGIN = (50.0, 86.0)

SQ3 = np.sqrt(3.0)


# ---------------------------------------------------------------------------- tools

def dilate(mask: np.ndarray, r: float) -> np.ndarray:
    """Grows a boolean mask by a disc of radius `r` pixels."""
    return ndi.distance_transform_edt(~mask) <= r


def erode(mask: np.ndarray, r: float) -> np.ndarray:
    """Shrinks a boolean mask by a disc of radius `r` pixels."""
    return ndi.distance_transform_edt(mask) > r


def closing(mask: np.ndarray, r: float) -> np.ndarray:
    """Fills the gaps of a boolean mask narrower than `2 r` pixels."""
    return ~dilate(~dilate(mask, r), r)


def opening(mask: np.ndarray, r: float, r_dilate: float | None = None) -> np.ndarray:
    """Removes from a boolean mask what does not hold a disc of radius `r`.

    Args:
        mask: The boolean mask.
        r: The radius of the erosion.
        r_dilate: The radius of the dilation that follows; `r` when omitted.

    Returns:
        The opened mask, restricted to the original one.
    """
    core = erode(mask, r)
    if not core.any():
        return core
    return dilate(core, r if r_dilate is None else r_dilate) & mask


def log(*args: object) -> None:
    """Prints a progress line, unbuffered."""
    print(*args, flush=True)


# ---------------------------------------------------------------------- colour masks

def base_masks(a: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Separates the three large families of pixels: grid lines, water, "warm".

    "Warm" (R > G) gathers everything brown or red: massifs, roads, building symbols, gothic
    lettering, the map's border. The sorting is then done by shape.

    Args:
        a: The image, `(H, W, 3)` RGB.

    Returns:
        The `white`, `blue` and `warm` boolean masks.
    """
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    white = (mn > 150) & ((mx - mn) < 70)
    blue = (B > R + 25) & (B > G + 8) & (~white)
    warm = (R > G - 5) & (~white) & (~blue)
    return white, blue, warm


# ------------------------------------------------------------------- grid alignment

def fit_the_grid(white: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fits an affine hexagonal lattice onto the map's white line work.

    Hexagon centres are the points furthest from the grid lines: we detect them as local maxima of
    the distance transform, then fit `centre(q, r) = O + A . (q, r)` by least squares, reassigning
    the indices at each iteration. The matrix `A` (rather than a plain regular step) absorbs the
    scan's slight residual rotation.

    Args:
        white: The mask of the grid lines.

    Returns:
        The `(2, 2)` matrix `A` and the origin `O`.
    """
    dist = ndi.distance_transform_edt(~white)
    peaks = (dist == ndi.maximum_filter(dist, size=61)) & (dist > 45)
    lab, n = ndi.label(peaks)
    centres = np.array(ndi.center_of_mass(peaks, lab, range(1, n + 1)))
    P = np.stack([centres[:, 1], centres[:, 0]], axis=1)  # (x, y)
    log(f"  {n} hexagon centres detected")

    s = SEED_SIZE
    A = np.array([[1.5 * s, 0.0], [SQ3 / 2 * s, SQ3 * s]])
    O = np.array(SEED_ORIGIN)
    for _ in range(12):
        QR = np.linalg.solve(A, (P - O).T).T
        QRr = np.round(QR)
        keep = np.max(np.abs(QR - QRr), axis=1) < 0.35
        X = np.hstack([QRr[keep], np.ones((keep.sum(), 1))])
        solution, *_ = np.linalg.lstsq(X, P[keep], rcond=None)
        A, O = solution[:2].T, solution[2]
    log(f"  A = {A.tolist()}\n  O = {O.tolist()}")
    return A, O


def centre(A: np.ndarray, O: np.ndarray, column: int, row: int) -> np.ndarray:
    """Computes the pixel centre of a hexagon given in odd-q offset coordinates.

    Args:
        A: The lattice matrix.
        O: The lattice origin.
        column: The offset column.
        row: The offset row.

    Returns:
        The `(x, y)` centre.
    """
    q = column
    r = row - ((column - (column & 1)) // 2)
    return O + A @ np.array([q, r], float)


def assign_pixels(A: np.ndarray, O: np.ndarray, H: int, W: int) -> tuple[np.ndarray, np.ndarray]:
    """Finds, for each pixel, the hexagon it belongs to.

    Args:
        A: The lattice matrix.
        O: The lattice origin.
        H: The image height.
        W: The image width.

    Returns:
        Two `(H, W)` int16 arrays: the odd-q column and row of each pixel's hexagon.
    """
    Ai = np.linalg.inv(A)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xs - O[0], ys - O[1]
    del xs, ys
    x = Ai[0, 0] * dx + Ai[0, 1] * dy
    z = Ai[1, 0] * dx + Ai[1, 1] * dy
    del dx, dy
    y = -x - z
    rx, ry, rz = np.round(x), np.round(y), np.round(z)
    ex, ey, ez = np.abs(rx - x), np.abs(ry - y), np.abs(rz - z)
    del x, y, z
    c1 = (ex > ey) & (ex > ez)
    c2 = (~c1) & (ey > ez)
    RX = np.where(c1, -ry - rz, rx)
    RY = np.where(c2, -rx - rz, ry)
    RZ = np.where(~(c1 | c2), -RX - RY, rz)
    del rx, ry, rz, ex, ey, ez, c1, c2, RY
    q = RX.astype(np.int16)
    r = RZ.astype(np.int16)
    del RX, RZ
    column = q
    row = (r + ((q - (q & 1)) // 2)).astype(np.int16)
    return column, row


def border_mask(pixel_column: np.ndarray, pixel_row: np.ndarray, warm: np.ndarray) -> np.ndarray:
    """Masks the map's brown frame: hexagons off the board, plus whatever overflows onto it.

    The border bites a few tens of pixels into the edge hexagons; we attach to it the warm pixels
    connected to it within a 140 px band.

    Args:
        pixel_column: Each pixel's hexagon column.
        pixel_row: Each pixel's hexagon row.
        warm: The mask of warm pixels.

    Returns:
        The boolean mask of the border.
    """
    outside = ((pixel_column < 0) | (pixel_column > COLUMNS - 1)
               | (pixel_row < 0) | (pixel_row > ROWS - 1))
    H, W = outside.shape
    band = np.zeros((H, W), bool)
    band[:140, :] = band[-140:, :] = True
    band[:, :140] = band[:, -140:] = True
    lab, _ = ndi.label(warm | outside)
    ids = np.unique(lab[outside & band])
    ids = ids[ids > 0]
    return outside | (np.isin(lab, ids) & band)


# ------------------------------------------------- relief, ways, water, buildings

def warm_masks(warm: np.ndarray, white: np.ndarray,
               border: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray,
                                            np.ndarray]:
    """Sorts the warm pixels into massifs / roads / paths / building symbols.

    The grid lines cut the massifs into one-hexagon slices: we patch them up, but **only across
    white**, otherwise the rubble field of the ruins of Ghaarth closes up into a false massif.

    Args:
        warm: The mask of warm pixels.
        white: The mask of the grid lines.
        border: The mask of the map's frame.

    Returns:
        The `closed`, `massif`, `road`, `path` and `buildings` masks.
    """
    inner = warm & ~border
    grid = dilate(white, 3)
    closed = inner | (closing(inner, 8) & grid)

    # A massif keeps an inscribed circle of 20 px; a road 20 px wide does not.
    massif = opening(closed, 20, 22)

    rest = closed & ~dilate(massif, 3)
    linear = opening(rest, 4, 5)  # removes thin strokes: lettering, dotted lines

    lab, n = ndi.label(linear, structure=np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    boxes = ndi.find_objects(lab)
    thickness = ndi.distance_transform_edt(linear)
    road = np.zeros_like(linear)
    path = np.zeros_like(linear)
    clusters = np.zeros_like(linear)
    for i, sl in enumerate(boxes, 1):
        if sizes[i] < 300:
            continue
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        diagonal = (h * h + w * w) ** 0.5
        part = lab[sl] == i
        # elongated and long -> a way; compact -> a symbol (village, ruins, lettering)
        if diagonal > 250 and sizes[i] / diagonal ** 2 < 0.06:
            wide = np.percentile(thickness[sl][part], 90) * 2 >= 13
            (road if wide else path)[sl] |= part
        else:
            clusters[sl] |= part
    buildings = (rest & ~linear) | clusters
    return closed, massif, road, path, buildings


def water_masks(blue: np.ndarray, border: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sorts the blue pixels into lakes and rivers, by width.

    Args:
        blue: The mask of blue pixels.
        border: The mask of the map's frame.

    Returns:
        The `lake` and `river` masks.
    """
    inner = closing(blue & ~border, 6)
    lake = opening(inner, 16, 18)
    return lake, inner & ~lake


# --------------------------------------------------------------------------- woods

def local_background(yellowness: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """Measures each pixel's departure from the plain's local level of "yellowness".

    The level is estimated by 32 px blocks and readjusted by iteration. Works on forest edges and
    small copses, but aligns itself on the forest at the heart of large wooded massifs - hence the
    second estimator below.

    Args:
        yellowness: `G - B`, per pixel.
        ok: The pixels that may belong to the plain.

    Returns:
        `yellowness` minus the estimated background.
    """
    H, W = yellowness.shape
    D = 32
    hh, ww = H // D, W // D
    Y = yellowness[:hh * D, :ww * D].reshape(hh, D, ww, D)
    valid = ok[:hh * D, :ww * D].reshape(hh, D, ww, D)
    background = None
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # entirely masked columns
        for _ in range(6):
            V = np.where(valid, Y, np.nan)
            count = valid.sum(axis=(1, 3))
            g = np.nanpercentile(V, 70, axis=(1, 3))
            g[count < 0.25 * D * D] = np.nan
            g = _fill_holes(g, 400)
            g = ndi.gaussian_filter(g, 1.5)
            background = np.array(
                Image.fromarray(g.astype(np.float32)).resize((W, H), Image.BICUBIC))
            relative = yellowness - background
            valid = (ok & (relative > -22))[:hh * D, :ww * D].reshape(hh, D, ww, D)
    return yellowness - background


def global_background(yellowness: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """Measures the same departure against a robust polynomial fitted over the whole map.

    The polynomial is then corrected locally. Catches the heart of the large forests.

    Args:
        yellowness: `G - B`, per pixel.
        ok: The pixels that may belong to the plain.

    Returns:
        `yellowness` minus the estimated background.
    """
    H, W = yellowness.shape
    S = 6
    ys, xs = np.mgrid[0:H:S, 0:W:S]
    oks = ok[::S, ::S]
    X = (xs[oks] / W).astype(np.float32)
    Y = (ys[oks] / H).astype(np.float32)
    V = yellowness[::S, ::S][oks]
    M = np.stack([(X ** i) * (Y ** j) for i in range(6) for j in range(6 - i)], 1)
    selection = np.ones(len(V), bool)
    for _ in range(6):
        c, *_ = np.linalg.lstsq(M[selection], V[selection], rcond=None)
        selection = (V - M @ c) > -18
    XX, YY = np.meshgrid(np.arange(W, dtype=np.float32) / W, np.arange(H, dtype=np.float32) / H)
    background = np.zeros((H, W), np.float32)
    k = 0
    for i in range(6):
        for j in range(6 - i):
            background += c[k] * (XX ** i) * (YY ** j)
            k += 1
    del XX, YY

    D = 32
    hh, ww = H // D, W // D
    for _ in range(4):
        relative = yellowness - background
        plain = ok & (relative > -18)
        m = plain[:hh * D, :ww * D].reshape(hh, D, ww, D)
        v = np.where(m, relative[:hh * D, :ww * D].reshape(hh, D, ww, D), 0.0)
        count = m.sum(axis=(1, 3))
        correction = np.where(count > 0.20 * D * D,
                              v.sum(axis=(1, 3)) / np.maximum(count, 1), np.nan)
        correction = ndi.gaussian_filter(_fill_holes(correction, 3000), 3.0)
        background = background + np.array(
            Image.fromarray(correction.astype(np.float32)).resize((W, H), Image.BICUBIC))
    return yellowness - background


def _fill_holes(g: np.ndarray, iterations: int) -> np.ndarray:
    """Fills the cells with no data by diffusion from their neighbours.

    Args:
        g: A float grid with `NaN` holes.
        iterations: How many diffusion passes to run.

    Returns:
        A copy of `g`, holes filled.
    """
    holes = np.isnan(g)
    if not holes.any():
        return g
    out = g.copy()
    out[holes] = np.nanmean(g)
    for _ in range(iterations):
        out[holes] = ndi.uniform_filter(out, 3)[holes]
    return out


def woods_mask(a: np.ndarray, white: np.ndarray, blue: np.ndarray, warm: np.ndarray,
               border: np.ndarray, near: np.ndarray) -> np.ndarray:
    """Masks the woods, combining two detectors: the hue, and the departure from the plain's level.

    The scan is heavily vignetted and the forests do not have the same hue on the left (grey-green)
    and on the right (true green) of the map: neither detector alone is enough.

    Args:
        a: The image, `(H, W, 3)` RGB.
        white: The mask of the grid lines.
        blue: The mask of water.
        warm: The mask of warm pixels.
        border: The mask of the map's frame.
        near: The pixels next to a grid line, left out.

    Returns:
        The boolean mask of the woods.
    """
    R, G, B = (a[..., 0].astype(np.float32), a[..., 1].astype(np.float32),
               a[..., 2].astype(np.float32))
    mx, mn = a.max(2).astype(np.float32), a.min(2).astype(np.float32)
    amplitude = np.maximum(mx - mn, 1)
    hue = np.where(mx == G, 60 * (2 + (B - R) / amplitude),
                   np.where(mx == R, 60 * (((G - B) / amplitude) % 6),
                            60 * (4 + (R - G) / amplitude)))
    hue = ndi.median_filter(hue.astype(np.float32), 7)

    yellowness = (G - B).astype(np.float32)
    relative_local = local_background(yellowness, (~white) & (~blue) & (~warm))
    relative_global = global_background(yellowness, (~white) & (~blue) & (~warm) & (~border))
    ok = (~white) & (~blue) & (~warm) & (~border) & (~near)
    return ok & ((hue > 93) | (relative_local < -25) | (relative_global < -30))


# ----------------------------------------------------------------------- aggregation

def aggregate(pixel_column: np.ndarray, pixel_row: np.ndarray, core: np.ndarray,
              masks: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Measures the fraction of each hexagon covered by each mask.

    Args:
        pixel_column: Each pixel's hexagon column.
        pixel_row: Each pixel's hexagon row.
        core: The pixels that count, away from the grid lines and the frame.
        masks: Name -> boolean mask.

    Returns:
        Name -> array of `COLUMNS * ROWS` fractions, indexed by `column * ROWS + row`.
    """
    N = COLUMNS * ROWS
    inside = ((pixel_column >= 0) & (pixel_column < COLUMNS)
              & (pixel_row >= 0) & (pixel_row < ROWS))
    idx = np.where(inside,
                   pixel_column.astype(np.int32) * ROWS + pixel_row.astype(np.int32), N).ravel()
    c = core.ravel()
    denominator = np.bincount(idx[c], minlength=N + 1)[:N].astype(float)
    return {name: np.bincount(idx[m.ravel() & c], minlength=N + 1)[:N]
            / np.maximum(denominator, 1)
            for name, m in masks.items()}


# ---------------------------------------------------------------- readings by hand

# Established by rereading one by one, on the scan, the 64 symbol clusters and the 30 isolated
# small brown components: the gothic labels served to name each site and to discard the false
# positives (lettering, dotted borders, the map's edging).
MORGENSTERN = [(c, r) for c in (2, 3, 4) for r in (33, 34, 35, 36)]
FORTS = [(16, 20), (32, 20), (48, 20), (4, 16)]
CASTLES = [(1, 2), (2, 1), (2, 2), (3, 1)]
TOWERS = [(27, 2)]
ISLANDS = [(52, 4)]
RUINS = [(0, 1), (0, 2),
         (28, 3), (29, 3), (30, 3), (31, 3), (28, 4), (29, 4), (30, 4),
         (33, 2), (34, 2)]
VILLAGES = {(2, 9): "Hameau aux loups", (3, 14): "Reiss", (6, 11): "Hameaux des âmes",
            (10, 14): "Ulmar", (12, 17): "Hurlewind", (6, 22): "Sorrow",
            (6, 25): "Malfroy", (2, 30): "Stern", (15, 31): "Ghalmaz-Ar",
            (9, 39): "New Ark", (28, 30): "Dawn", (37, 34): "Angle", (38, 4): "Helden",
            (42, 36): "Lorift", (45, 30): "Denrift", (46, 28): "Aurilt",
            (48, 38): "Trillift", (50, 34): "Dendrill", (52, 27): "Voloors",
            (53, 8): "Sandhardt", (54, 31): "Virlilt", (56, 12): "Gròsht"}
RIFT = [(9, 2), (10, 2), (10, 3), (10, 4), (11, 4), (11, 5), (12, 5), (12, 6),
        (13, 6), (13, 7), (14, 7), (14, 8), (15, 8), (16, 9), (17, 9)]

BY_HAND = {}
for _entries, _terrain in [(MORGENSTERN, "ville"), (FORTS, "fort"), (CASTLES, "chateau"),
                           (TOWERS, "tour"), (ISLANDS, "ile"), (RUINS, "ruines"),
                           (VILLAGES, "village"), (RIFT, "faille")]:
    for _hexagon in _entries:
        BY_HAND[_hexagon] = _terrain

# Coverage thresholds for a hexagon. `MAIN` decides the terrain retained in carte.json,
# `SECONDARY` (lower) what is reported in carte_details.json.
MAIN = dict(lac=.40, montagne=.45, colline=.15, bois=.40, riviere=.07, route=.06, chemin=.05)
SECONDARY = dict(lac=.12, montagne=.45, colline=.15, bois=.18, riviere=.04,
                 route=.035, chemin=.035, plaine=.35)

COLOURS = {"plaine": (190, 225, 110), "bois": (30, 105, 50), "montagne": (140, 90, 50),
           "colline": (205, 165, 85), "lac": (40, 85, 205), "riviere": (90, 155, 240),
           "route": (200, 80, 30), "chemin": (225, 170, 95), "village": (235, 60, 150),
           "ville": (255, 0, 80), "ruines": (175, 145, 205), "fort": (125, 55, 160),
           "chateau": (255, 135, 0), "tour": (255, 225, 0), "faille": (50, 45, 40),
           "ile": (0, 210, 180)}


def classify(F: dict[str, np.ndarray]) -> tuple[dict[tuple[int, int], str],
                                                 dict[tuple[int, int], list[str]]]:
    """Decides the main terrain and the complete list of elements, hexagon by hexagon.

    Priority: built places > lake > mountain > hill > woods > rift > river > road > path > plain.
    Natural terrain therefore prevails over ways; what is masked stays in `carte_details.json`.

    Args:
        F: The coverage fractions from `aggregate`.

    Returns:
        `(column, row)` -> main terrain, and `(column, row)` -> every element, main terrain first.
    """
    def f(key: str, c: int, r: int) -> float:
        """The coverage of mask `key` on hexagon `(c, r)`."""
        return float(F[key][c * ROWS + r])

    grid, details = {}, {}
    for c in range(COLUMNS):
        for r in range(ROWS):
            if (c, r) in BY_HAND:
                t = BY_HAND[(c, r)]
            elif f("lac", c, r) >= MAIN["lac"]:
                t = "lac"
            elif f("massif", c, r) >= MAIN["montagne"]:
                t = "montagne"
            elif f("massif", c, r) >= MAIN["colline"]:
                t = "colline"
            elif f("bois", c, r) >= MAIN["bois"]:
                t = "bois"
            elif f("riviere", c, r) >= MAIN["riviere"]:
                t = "riviere"
            elif f("route", c, r) >= MAIN["route"]:
                t = "route"
            elif f("chemin", c, r) >= MAIN["chemin"]:
                t = "chemin"
            else:
                t = "plaine"
            grid[(c, r)] = t

            elements = [BY_HAND[(c, r)]] if (c, r) in BY_HAND else []
            if f("lac", c, r) >= SECONDARY["lac"]:
                elements.append("lac")
            if f("massif", c, r) >= SECONDARY["montagne"]:
                elements.append("montagne")
            elif f("massif", c, r) >= SECONDARY["colline"]:
                elements.append("colline")
            if f("bois", c, r) >= SECONDARY["bois"]:
                elements.append("bois")
            if f("riviere", c, r) >= SECONDARY["riviere"]:
                elements.append("riviere")
            if f("route", c, r) >= SECONDARY["route"]:
                elements.append("route")
            if f("chemin", c, r) >= SECONDARY["chemin"]:
                elements.append("chemin")
            if f("green", c, r) - f("bois", c, r) >= SECONDARY["plaine"]:
                elements.append("plaine")
            # the walls of Morgenstern and of the castle read as relief
            if t in ("ville", "chateau"):
                elements = [e for e in elements if e not in ("montagne", "colline")]
            details[(c, r)] = [t] + [e for e in dict.fromkeys(elements) if e != t]
    return grid, details


def cube_key(column: int, row: int) -> str:
    """Converts odd-q offset coordinates to the "q,r,s" key of the data files.

    Args:
        column: The offset column.
        row: The offset row.

    Returns:
        The cube key.
    """
    q = column
    r = row - ((column - (column & 1)) // 2)
    return f"{q},{r},{-q - r}"


def control_image(A: np.ndarray, O: np.ndarray, grid: dict[tuple[int, int], str],
                  output_path: str) -> None:
    """Writes the map at a third of its size, each hexagon tinted with its terrain.

    Args:
        A: The lattice matrix.
        O: The lattice origin.
        grid: `(column, row)` -> main terrain.
        output_path: Where to write the JPEG.
    """
    sx, sy = A[0, 0] / 1.5, A[1, 1] / SQ3
    im = Image.open(MAP).convert("RGBA")
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (c, r), t in grid.items():
        cx, cy = centre(A, O, c, r)
        d.polygon([(cx + sx * 0.60 * np.cos(np.pi / 3 * k), cy + sy * 0.60 * np.sin(np.pi / 3 * k))
                   for k in range(6)], fill=COLOURS[t] + (120,))
    out = Image.alpha_composite(im, layer).convert("RGB")
    out.resize((im.width // 3, im.height // 3)).save(output_path, quality=88)


def main() -> int:
    """Runs the whole extraction and writes the three output files.

    Returns:
        The process exit code, 0.
    """
    log("Reading", MAP)
    a = np.asarray(Image.open(MAP).convert("RGB")).astype(np.int16)
    H, W, _ = a.shape
    log(f"  {W} x {H} px")

    log("Colour masks")
    white, blue, warm = base_masks(a)

    log("Grid alignment")
    A, O = fit_the_grid(white)
    pixel_column, pixel_row = assign_pixels(A, O, H, W)

    log("Map border")
    border = border_mask(pixel_column, pixel_row, warm)

    log("Relief, roads and buildings")
    _, massif, road, path, buildings = warm_masks(warm, white, border)
    log("Lakes and rivers")
    lake, river = water_masks(blue, border)

    near = dilate(white, 4)
    green = (~white) & (~blue) & (~warm) & (~near) & (~border)

    log("Woods")
    woods = woods_mask(a, white, blue, warm, border, near)
    del a

    log("Aggregation by hexagon")
    core = (~near) & (~border)
    F = aggregate(pixel_column, pixel_row, core,
                  dict(massif=massif, lac=lake, riviere=river, route=road,
                       chemin=path, bati=buildings, green=green, bois=woods))

    log("Classification")
    grid, details = classify(F)
    log("  " + ", ".join(f"{t} {n}" for t, n in
                         collections.Counter(grid.values()).most_common()))

    json.dump({cube_key(c, r): t for (c, r), t in grid.items()},
              open("carte.json", "w"), ensure_ascii=False, indent=0)
    json.dump({cube_key(c, r): v for (c, r), v in details.items()},
              open("carte_details.json", "w"), ensure_ascii=False, indent=0)
    log("Control image")
    control_image(A, O, grid, "carte_controle.jpg")
    log("carte.json, carte_details.json, carte_controle.jpg written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
