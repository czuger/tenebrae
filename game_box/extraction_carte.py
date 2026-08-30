#!/usr/bin/env python3
"""Extraction de la grille d'hexagones d'*Ave Tenebrae* depuis `map.jpg`.

Produit, dans le répertoire courant :

* `carte.json`          — dict `"q,r,s"` → terrain principal
* `carte_details.json`  — dict `"q,r,s"` → liste de tous les éléments de l'hexagone
* `carte_controle.jpg`  — la carte au tiers, chaque hexagone teinté de son terrain

`map.jpg` n'est pas versionné (voir `.git/info/exclude`) : il faut l'avoir localement.

Dépendances : Pillow, numpy, scipy.
Durée : une dizaine de minutes, ~2 Go de mémoire.

La méthode est décrite dans `carte.md`. Les réglages numériques ci-dessous ont été
calés sur ce scan précis (6173 × 5102 px) et n'ont pas vocation à être génériques.
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

CARTE = "map.jpg"

# Nombre de colonnes et de lignes réellement jouables. Les hexagones qui débordent
# sont recouverts par le liseré brun de la carte ; relevé à l'œil sur les quatre bords.
NB_COL, NB_LIG = 57, 40

# Amorce du calage de la grille : pas mesuré par autocorrélation des lignes blanches
# (période 107,6 px en x, 125,7 px en y) et phase approchée. L'ajustement aux moindres
# carrés qui suit converge vers la grille exacte à partir de là.
AMORCE_TAILLE = 72.2
AMORCE_ORIGINE = (50.0, 86.0)

SQ3 = np.sqrt(3.0)


# --------------------------------------------------------------------------- outils

def dilate(masque: np.ndarray, r: float) -> np.ndarray:
    return ndi.distance_transform_edt(~masque) <= r


def erode(masque: np.ndarray, r: float) -> np.ndarray:
    return ndi.distance_transform_edt(masque) > r


def fermeture(masque: np.ndarray, r: float) -> np.ndarray:
    return ~dilate(~dilate(masque, r), r)


def ouverture(masque: np.ndarray, r: float, r_dil: float | None = None) -> np.ndarray:
    noyau = erode(masque, r)
    if not noyau.any():
        return noyau
    return dilate(noyau, r if r_dil is None else r_dil) & masque


def log(*args) -> None:
    print(*args, flush=True)


# ---------------------------------------------------------------- masques de couleur

def masques_de_base(a: np.ndarray):
    """Sépare les trois grandes familles de pixels : lignes de grille, eau, « chaud ».

    « Chaud » (R > V) réunit tout ce qui est brun ou rouge : massifs, routes, symboles
    de bâti, textes gothiques, liseré de la carte. Le tri se fait ensuite par la forme.
    """
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    blanc = (mn > 150) & ((mx - mn) < 70)
    bleu = (B > R + 25) & (B > G + 8) & (~blanc)
    chaud = (R > G - 5) & (~blanc) & (~bleu)
    return blanc, bleu, chaud


# ------------------------------------------------------------------ calage de grille

def ajuster_grille(blanc: np.ndarray):
    """Cale un réseau hexagonal affine sur le tracé blanc de la carte.

    Les centres d'hexagones sont les points les plus éloignés des lignes de grille :
    on les détecte comme maxima locaux de la transformée de distance, puis on ajuste
    `centre(q, r) = O + A · (q, r)` aux moindres carrés en réattribuant les indices à
    chaque itération. La matrice `A` (et non un simple pas régulier) absorbe la légère
    rotation résiduelle du scan.
    """
    dist = ndi.distance_transform_edt(~blanc)
    pics = (dist == ndi.maximum_filter(dist, size=61)) & (dist > 45)
    lab, n = ndi.label(pics)
    centres = np.array(ndi.center_of_mass(pics, lab, range(1, n + 1)))
    P = np.stack([centres[:, 1], centres[:, 0]], axis=1)  # (x, y)
    log(f"  {n} centres d'hexagones détectés")

    s = AMORCE_TAILLE
    A = np.array([[1.5 * s, 0.0], [SQ3 / 2 * s, SQ3 * s]])
    O = np.array(AMORCE_ORIGINE)
    for _ in range(12):
        QR = np.linalg.solve(A, (P - O).T).T
        QRr = np.round(QR)
        garde = np.max(np.abs(QR - QRr), axis=1) < 0.35
        X = np.hstack([QRr[garde], np.ones((garde.sum(), 1))])
        sol, *_ = np.linalg.lstsq(X, P[garde], rcond=None)
        A, O = sol[:2].T, sol[2]
    log(f"  A = {A.tolist()}\n  O = {O.tolist()}")
    return A, O


def centre(A, O, col, lig):
    q = col
    r = lig - ((col - (col & 1)) // 2)
    return O + A @ np.array([q, r], float)


def attribuer_pixels(A, O, H, W):
    """Rend, pour chaque pixel, la colonne et la ligne (odd-q) de son hexagone."""
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
    col = q
    lig = (r + ((q - (q & 1)) // 2)).astype(np.int16)
    return col, lig


def masque_liseré(pix_col, pix_lig, chaud):
    """Le cadre brun de la carte : hexagones hors plateau, plus ce qui déborde dessus.

    Le liseré mord de quelques dizaines de pixels sur les hexagones de bord ; on lui
    rattache les pixels chauds qui lui sont connexes dans une bande de 140 px.
    """
    hors = (pix_col < 0) | (pix_col > NB_COL - 1) | (pix_lig < 0) | (pix_lig > NB_LIG - 1)
    H, W = hors.shape
    bande = np.zeros((H, W), bool)
    bande[:140, :] = bande[-140:, :] = True
    bande[:, :140] = bande[:, -140:] = True
    lab, _ = ndi.label(chaud | hors)
    ids = np.unique(lab[hors & bande])
    ids = ids[ids > 0]
    return hors | (np.isin(lab, ids) & bande)


# -------------------------------------------------------- relief, voies, eau, bâti

def masques_chauds(chaud, blanc, liseré):
    """Trie les pixels chauds en massifs / routes / chemins / symboles de bâti.

    Les lignes de grille coupent les massifs en tranches d'un hexagone : on les
    rebouche, mais **uniquement à travers le blanc**, sinon le champ de gravats des
    ruines de Ghaarth se referme en un faux massif.
    """
    interne = chaud & ~liseré
    grille = dilate(blanc, 3)
    ferme = interne | (fermeture(interne, 8) & grille)

    # Un massif garde un cercle inscrit de 20 px ; une route de 20 px de large, non.
    massif = ouverture(ferme, 20, 22)

    reste = ferme & ~dilate(massif, 3)
    lineaire = ouverture(reste, 4, 5)  # supprime les traits fins : textes, pointillés

    lab, n = ndi.label(lineaire, structure=np.ones((3, 3)))
    tailles = np.bincount(lab.ravel())
    tailles[0] = 0
    boites = ndi.find_objects(lab)
    epaisseur = ndi.distance_transform_edt(lineaire)
    route = np.zeros_like(lineaire)
    chemin = np.zeros_like(lineaire)
    amas = np.zeros_like(lineaire)
    for i, sl in enumerate(boites, 1):
        if tailles[i] < 300:
            continue
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        diag = (h * h + w * w) ** 0.5
        sous = lab[sl] == i
        # allongée et longue → voie ; compacte → symbole (village, ruines, texte)
        if diag > 250 and tailles[i] / diag ** 2 < 0.06:
            large = np.percentile(epaisseur[sl][sous], 90) * 2 >= 13
            (route if large else chemin)[sl] |= sous
        else:
            amas[sl] |= sous
    bati = (reste & ~lineaire) | amas
    return ferme, massif, route, chemin, bati


def masques_eau(bleu, liseré):
    interne = fermeture(bleu & ~liseré, 6)
    lac = ouverture(interne, 16, 18)
    return lac, interne & ~lac


# --------------------------------------------------------------------------- bois

def fond_local(yel, ok):
    """Niveau de « jaunité » de la plaine, estimé localement et réajusté par itérations.

    Marche sur les lisières et les petits bosquets, mais s'aligne sur la forêt au cœur
    des grands massifs boisés — d'où le second estimateur ci-dessous.
    """
    H, W = yel.shape
    D = 32
    hh, ww = H // D, W // D
    Y = yel[:hh * D, :ww * D].reshape(hh, D, ww, D)
    valide = ok[:hh * D, :ww * D].reshape(hh, D, ww, D)
    fond = None
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # colonnes entièrement masquées
        for _ in range(6):
            V = np.where(valide, Y, np.nan)
            cnt = valide.sum(axis=(1, 3))
            g = np.nanpercentile(V, 70, axis=(1, 3))
            g[cnt < 0.25 * D * D] = np.nan
            g = _boucher(g, 400)
            g = ndi.gaussian_filter(g, 1.5)
            fond = np.array(Image.fromarray(g.astype(np.float32)).resize((W, H), Image.BICUBIC))
            rel = yel - fond
            valide = (ok & (rel > -22))[:hh * D, :ww * D].reshape(hh, D, ww, D)
    return yel - fond


def fond_global(yel, ok):
    """Même niveau, mais posé par un polynôme robuste sur toute la carte,
    puis corrigé localement. Rattrape le cœur des grandes forêts."""
    H, W = yel.shape
    S = 6
    ys, xs = np.mgrid[0:H:S, 0:W:S]
    oks = ok[::S, ::S]
    X = (xs[oks] / W).astype(np.float32)
    Y = (ys[oks] / H).astype(np.float32)
    V = yel[::S, ::S][oks]
    M = np.stack([(X ** i) * (Y ** j) for i in range(6) for j in range(6 - i)], 1)
    sel = np.ones(len(V), bool)
    for _ in range(6):
        c, *_ = np.linalg.lstsq(M[sel], V[sel], rcond=None)
        sel = (V - M @ c) > -18
    XX, YY = np.meshgrid(np.arange(W, dtype=np.float32) / W, np.arange(H, dtype=np.float32) / H)
    fond = np.zeros((H, W), np.float32)
    k = 0
    for i in range(6):
        for j in range(6 - i):
            fond += c[k] * (XX ** i) * (YY ** j)
            k += 1
    del XX, YY

    D = 32
    hh, ww = H // D, W // D
    for _ in range(4):
        rel = yel - fond
        plaine = ok & (rel > -18)
        m = plaine[:hh * D, :ww * D].reshape(hh, D, ww, D)
        v = np.where(m, rel[:hh * D, :ww * D].reshape(hh, D, ww, D), 0.0)
        cnt = m.sum(axis=(1, 3))
        corr = np.where(cnt > 0.20 * D * D, v.sum(axis=(1, 3)) / np.maximum(cnt, 1), np.nan)
        corr = ndi.gaussian_filter(_boucher(corr, 3000), 3.0)
        fond = fond + np.array(
            Image.fromarray(corr.astype(np.float32)).resize((W, H), Image.BICUBIC))
    return yel - fond


def _boucher(g, iterations):
    """Rebouche les cellules sans donnée par diffusion depuis leurs voisines."""
    trous = np.isnan(g)
    if not trous.any():
        return g
    out = g.copy()
    out[trous] = np.nanmean(g)
    for _ in range(iterations):
        out[trous] = ndi.uniform_filter(out, 3)[trous]
    return out


def masque_bois(a, blanc, bleu, chaud, liseré, proche):
    """Deux détecteurs réunis : la teinte, et l'écart au niveau local de la plaine.

    Le scan est fortement vigneté et les forêts n'ont pas la même teinte à gauche
    (vert-gris) et à droite (vert franc) de la carte : ni l'un ni l'autre ne suffit.
    """
    R, G, B = a[..., 0].astype(np.float32), a[..., 1].astype(np.float32), a[..., 2].astype(np.float32)
    mx, mn = a.max(2).astype(np.float32), a.min(2).astype(np.float32)
    amp = np.maximum(mx - mn, 1)
    teinte = np.where(mx == G, 60 * (2 + (B - R) / amp),
                      np.where(mx == R, 60 * (((G - B) / amp) % 6), 60 * (4 + (R - G) / amp)))
    teinte = ndi.median_filter(teinte.astype(np.float32), 7)

    yel = (G - B).astype(np.float32)
    rel_l = fond_local(yel, (~blanc) & (~bleu) & (~chaud))
    rel_g = fond_global(yel, (~blanc) & (~bleu) & (~chaud) & (~liseré))
    ok = (~blanc) & (~bleu) & (~chaud) & (~liseré) & (~proche)
    return ok & ((teinte > 93) | (rel_l < -25) | (rel_g < -30))


# --------------------------------------------------------------------- agrégation

def agreger(pix_col, pix_lig, coeur, masques):
    """Fraction de chaque hexagone couverte par chaque masque."""
    N = NB_COL * NB_LIG
    dedans = (pix_col >= 0) & (pix_col < NB_COL) & (pix_lig >= 0) & (pix_lig < NB_LIG)
    idx = np.where(dedans, pix_col.astype(np.int32) * NB_LIG + pix_lig.astype(np.int32), N).ravel()
    c = coeur.ravel()
    denom = np.bincount(idx[c], minlength=N + 1)[:N].astype(float)
    return {nom: np.bincount(idx[m.ravel() & c], minlength=N + 1)[:N] / np.maximum(denom, 1)
            for nom, m in masques.items()}


# ------------------------------------------------------- relevés faits à la main

# Établis en relisant un à un, sur le scan, les 64 amas de symboles et les 30 petites
# composantes brunes isolées : les étiquettes gothiques ont servi à nommer chaque site
# et à écarter les faux positifs (textes, frontières en pointillés, liseré).
MORGENSTERN = [(c, r) for c in (2, 3, 4) for r in (33, 34, 35, 36)]
FORTS = [(16, 20), (32, 20), (48, 20), (4, 16)]
CHATEAUX = [(1, 2), (2, 1), (2, 2), (3, 1)]
TOURS = [(27, 2)]
ILES = [(52, 4)]
RUINES = [(0, 1), (0, 2),
          (28, 3), (29, 3), (30, 3), (31, 3), (28, 4), (29, 4), (30, 4),
          (33, 2), (34, 2)]
VILLAGES = {(2, 9): "Hameau aux loups", (3, 14): "Reiss", (6, 11): "Hameaux des âmes",
            (10, 14): "Ulmar", (12, 17): "Hurlewind", (6, 22): "Sorrow",
            (6, 25): "Malfroy", (2, 30): "Stern", (15, 31): "Ghalmaz-Ar",
            (9, 39): "New Ark", (28, 30): "Dawn", (37, 34): "Angle", (38, 4): "Helden",
            (42, 36): "Lorift", (45, 30): "Denrift", (46, 28): "Aurilt",
            (48, 38): "Trillift", (50, 34): "Dendrill", (52, 27): "Voloors",
            (53, 8): "Sandhardt", (54, 31): "Virlilt", (56, 12): "Gròsht"}
FAILLE = [(9, 2), (10, 2), (10, 3), (10, 4), (11, 4), (11, 5), (12, 5), (12, 6),
          (13, 6), (13, 7), (14, 7), (14, 8), (15, 8), (16, 9), (17, 9)]

RELEVE = {}
for _liste, _t in [(MORGENSTERN, "ville"), (FORTS, "fort"), (CHATEAUX, "chateau"),
                   (TOURS, "tour"), (ILES, "ile"), (RUINES, "ruines"),
                   (VILLAGES, "village"), (FAILLE, "faille")]:
    for _h in _liste:
        RELEVE[_h] = _t

# Seuils de couverture d'un hexagone. `PRINCIPAL` décide du terrain retenu dans
# carte.json, `SECONDAIRE` (plus bas) de ce qui est signalé dans carte_details.json.
PRINCIPAL = dict(lac=.40, montagne=.45, colline=.15, bois=.40, riviere=.07, route=.06, chemin=.05)
SECONDAIRE = dict(lac=.12, montagne=.45, colline=.15, bois=.18, riviere=.04,
                  route=.035, chemin=.035, plaine=.35)

COULEURS = {"plaine": (190, 225, 110), "bois": (30, 105, 50), "montagne": (140, 90, 50),
            "colline": (205, 165, 85), "lac": (40, 85, 205), "riviere": (90, 155, 240),
            "route": (200, 80, 30), "chemin": (225, 170, 95), "village": (235, 60, 150),
            "ville": (255, 0, 80), "ruines": (175, 145, 205), "fort": (125, 55, 160),
            "chateau": (255, 135, 0), "tour": (255, 225, 0), "faille": (50, 45, 40),
            "ile": (0, 210, 180)}


def classer(F):
    """Terrain principal et liste complète, hexagone par hexagone.

    Priorité : lieux construits > lac > montagne > colline > bois > faille
    > rivière > route > chemin > plaine. Le terrain naturel l'emporte donc sur les
    voies ; ce qui est masqué reste dans `carte_details.json`.
    """
    def f(cle, c, r):
        return float(F[cle][c * NB_LIG + r])

    grille, details = {}, {}
    for c in range(NB_COL):
        for r in range(NB_LIG):
            if (c, r) in RELEVE:
                t = RELEVE[(c, r)]
            elif f("lac", c, r) >= PRINCIPAL["lac"]:
                t = "lac"
            elif f("massif", c, r) >= PRINCIPAL["montagne"]:
                t = "montagne"
            elif f("massif", c, r) >= PRINCIPAL["colline"]:
                t = "colline"
            elif f("bois", c, r) >= PRINCIPAL["bois"]:
                t = "bois"
            elif f("riviere", c, r) >= PRINCIPAL["riviere"]:
                t = "riviere"
            elif f("route", c, r) >= PRINCIPAL["route"]:
                t = "route"
            elif f("chemin", c, r) >= PRINCIPAL["chemin"]:
                t = "chemin"
            else:
                t = "plaine"
            grille[(c, r)] = t

            elems = [RELEVE[(c, r)]] if (c, r) in RELEVE else []
            if f("lac", c, r) >= SECONDAIRE["lac"]:
                elems.append("lac")
            if f("massif", c, r) >= SECONDAIRE["montagne"]:
                elems.append("montagne")
            elif f("massif", c, r) >= SECONDAIRE["colline"]:
                elems.append("colline")
            if f("bois", c, r) >= SECONDAIRE["bois"]:
                elems.append("bois")
            if f("riviere", c, r) >= SECONDAIRE["riviere"]:
                elems.append("riviere")
            if f("route", c, r) >= SECONDAIRE["route"]:
                elems.append("route")
            if f("chemin", c, r) >= SECONDAIRE["chemin"]:
                elems.append("chemin")
            if f("vert", c, r) - f("bois", c, r) >= SECONDAIRE["plaine"]:
                elems.append("plaine")
            # les murailles de Morgenstern et du château se lisent comme du relief
            if t in ("ville", "chateau"):
                elems = [e for e in elems if e not in ("montagne", "colline")]
            details[(c, r)] = [t] + [e for e in dict.fromkeys(elems) if e != t]
    return grille, details


def cle_cube(col, lig):
    q = col
    r = lig - ((col - (col & 1)) // 2)
    return f"{q},{r},{-q - r}"


def image_controle(A, O, grille, chemin_sortie):
    sx, sy = A[0, 0] / 1.5, A[1, 1] / SQ3
    im = Image.open(CARTE).convert("RGBA")
    calque = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    for (c, r), t in grille.items():
        cx, cy = centre(A, O, c, r)
        d.polygon([(cx + sx * 0.60 * np.cos(np.pi / 3 * k), cy + sy * 0.60 * np.sin(np.pi / 3 * k))
                   for k in range(6)], fill=COULEURS[t] + (120,))
    out = Image.alpha_composite(im, calque).convert("RGB")
    out.resize((im.width // 3, im.height // 3)).save(chemin_sortie, quality=88)


def main() -> int:
    log("Lecture de", CARTE)
    a = np.asarray(Image.open(CARTE).convert("RGB")).astype(np.int16)
    H, W, _ = a.shape
    log(f"  {W} × {H} px")

    log("Masques de couleur")
    blanc, bleu, chaud = masques_de_base(a)

    log("Calage de la grille")
    A, O = ajuster_grille(blanc)
    pix_col, pix_lig = attribuer_pixels(A, O, H, W)

    log("Liseré de la carte")
    liseré = masque_liseré(pix_col, pix_lig, chaud)

    log("Relief, routes et bâti")
    _, massif, route, chemin, bati = masques_chauds(chaud, blanc, liseré)
    log("Lacs et rivières")
    lac, riviere = masques_eau(bleu, liseré)

    proche = dilate(blanc, 4)
    vert = (~blanc) & (~bleu) & (~chaud) & (~proche) & (~liseré)

    log("Bois")
    bois = masque_bois(a, blanc, bleu, chaud, liseré, proche)
    del a

    log("Agrégation par hexagone")
    coeur = (~proche) & (~liseré)
    F = agreger(pix_col, pix_lig, coeur,
                dict(massif=massif, lac=lac, riviere=riviere, route=route,
                     chemin=chemin, bati=bati, vert=vert, bois=bois))

    log("Classement")
    grille, details = classer(F)
    log("  " + ", ".join(f"{t} {n}" for t, n in
                         collections.Counter(grille.values()).most_common()))

    json.dump({cle_cube(c, r): t for (c, r), t in grille.items()},
              open("carte.json", "w"), ensure_ascii=False, indent=0)
    json.dump({cle_cube(c, r): v for (c, r), v in details.items()},
              open("carte_details.json", "w"), ensure_ascii=False, indent=0)
    log("Image de contrôle")
    image_controle(A, O, grille, "carte_controle.jpg")
    log("carte.json, carte_details.json, carte_controle.jpg écrits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
