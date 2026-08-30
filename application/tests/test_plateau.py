"""Ce que le navigateur affiche : les pions posés, centrés et inclinés sur la carte.

Ces tests demandent Chromium (`python3 -m playwright install chromium`).
"""

import math

import pytest

import app


@pytest.fixture
def plateau(page, serveur):
    """Ouvre la page et attend que la carte et les dix pions soient chargés."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(serveur)
    page.wait_for_function(
        "document.querySelectorAll('img.pion').length === %d" % app.NOMBRE_DE_PIONS
    )
    page.wait_for_function(
        "[...document.querySelectorAll('img.pion'), document.getElementById('carte')]"
        ".every((i) => i.complete && i.naturalWidth > 0)"
    )
    return page


def centre_attendu(q, r):
    """centre(q, r) = origine + matrice · (q, r), en pixels de map.jpg (game_box/carte.md)."""
    origine, matrice = app.GRILLE_ORIGINE, app.GRILLE_MATRICE
    return (origine[0] + matrice[0][0] * q + matrice[0][1] * r,
            origine[1] + matrice[1][0] * q + matrice[1][1] * r)


def geometrie_des_pions(page):
    """Rend, pour chaque pion, sa position rendue ramenée en pixels de map.jpg."""
    return page.evaluate("""() => {
        const carte = document.getElementById('carte');
        const cadreCarte = carte.getBoundingClientRect();
        const echelle = cadreCarte.width / carte.naturalWidth;
        return [...document.querySelectorAll('img.pion')].map((pion) => {
            const cadre = pion.getBoundingClientRect();
            const matrice = new DOMMatrix(getComputedStyle(pion).transform);
            return {
                q: Number(pion.dataset.q),
                r: Number(pion.dataset.r),
                s: Number(pion.dataset.s),
                x: (cadre.x + cadre.width / 2 - cadreCarte.x) / echelle,
                y: (cadre.y + cadre.height / 2 - cadreCarte.y) / echelle,
                angle: Math.atan2(matrice.b, matrice.a) * 180 / Math.PI,
                largeur: pion.offsetWidth,
                echelle: echelle,
            };
        });
    }""")


def test_la_carte_est_affichee(plateau):
    carte = plateau.evaluate(
        "() => { const c = document.getElementById('carte');"
        " return {l: c.naturalWidth, h: c.naturalHeight}; }"
    )
    assert (carte["l"], carte["h"]) == (6173, 5102)


def test_dix_pions_sont_poses(plateau):
    assert plateau.locator("img.pion").count() == app.NOMBRE_DE_PIONS


def test_les_images_de_pions_se_chargent(plateau):
    assert plateau.evaluate(
        "() => [...document.querySelectorAll('img.pion')].every((i) => i.naturalWidth > 0)"
    )


def test_chaque_pion_est_centre_sur_son_hexagone(plateau):
    """Le centre rendu du pion tombe sur le centre de l'hexagone, à moins d'un pixel près."""
    for pion in geometrie_des_pions(plateau):
        x, y = centre_attendu(pion["q"], pion["r"])
        assert math.isclose(pion["x"], x, abs_tol=1.0), pion
        assert math.isclose(pion["y"], y, abs_tol=1.0), pion


def test_chaque_pion_est_incline_de_moins_de_cinq_degres(plateau):
    for pion in geometrie_des_pions(plateau):
        assert abs(pion["angle"]) <= 5.0, pion


def test_les_inclinaisons_sont_tirees_au_hasard(plateau):
    """Des pions tous à la même inclinaison trahiraient une rotation figée."""
    angles = [round(pion["angle"], 3) for pion in geometrie_des_pions(plateau)]
    assert len(set(angles)) == len(angles)
    assert any(angle < 0 for angle in angles) or any(angle > 0 for angle in angles)


def test_les_pions_ont_la_taille_prevue(plateau):
    for pion in geometrie_des_pions(plateau):
        assert pion["largeur"] == app.PION_TAILLE


def test_le_plateau_tient_dans_la_fenetre(plateau):
    debordement = plateau.evaluate(
        "() => ({ l: document.documentElement.scrollWidth - window.innerWidth,"
        "         h: document.documentElement.scrollHeight - window.innerHeight })"
    )
    assert debordement["l"] <= 0 and debordement["h"] <= 0


def test_le_plateau_suit_le_redimensionnement(plateau):
    """Après un redimensionnement, la carte reste à l'échelle et les pions à leur place."""
    avant = geometrie_des_pions(plateau)[0]["echelle"]
    plateau.set_viewport_size({"width": 900, "height": 600})
    plateau.wait_for_function("() => window.innerWidth === 900 && window.innerHeight === 600")
    plateau.evaluate("() => new Promise(requestAnimationFrame)")
    apres = geometrie_des_pions(plateau)
    assert apres[0]["echelle"] < avant
    for pion in apres:
        x, y = centre_attendu(pion["q"], pion["r"])
        assert math.isclose(pion["x"], x, abs_tol=1.0), pion
        assert math.isclose(pion["y"], y, abs_tol=1.0), pion
