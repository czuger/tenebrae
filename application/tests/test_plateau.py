"""Ce que le navigateur affiche : les pions posés, centrés et inclinés sur la carte.

Ces tests demandent Chromium (`python3 -m playwright install chromium`).
"""

import math

import pytest

import app
from moteur.hexagone import CARTE, Hex
from moteur.pion import ADVERSAIRES, CATALOGUE


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


def geometrie_des_pions(page, selecteur="img.pion:not(.fantome)"):
    """Rend, pour chaque image de `selecteur`, sa position rendue en pixels de map.jpg."""
    return page.evaluate("""(selecteur) => {
        const carte = document.getElementById('carte');
        const cadreCarte = carte.getBoundingClientRect();
        const echelle = cadreCarte.width / carte.naturalWidth;
        return [...document.querySelectorAll(selecteur)].map((pion) => {
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
                opacite: Number(getComputedStyle(pion).opacity),
            };
        });
    }""", selecteur)


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


# --- Fantômes et déplacement ----------------------------------------------------------------


def pions_qui_peuvent_bouger(page, convient=lambda pion: True):
    """Les pions de la page qui ont des cases où aller, et que `convient` accepte.

    La portée est celle que le **plateau du serveur** calcule : le mouvement du carton, moins ce
    que les adversaires posés autour lui interdisent. Le serveur de test tourne dans ce processus,
    son plateau se lit donc directement.
    """
    for indice in range(app.NOMBRE_DE_PIONS):
        pion = page.locator("img.pion:not(.fantome)").nth(indice)
        position = pion.evaluate(
            "p => [Number(p.dataset.q), Number(p.dataset.r), Number(p.dataset.s)]")
        depart = Hex(*position)
        atteignables = app.PLATEAU.deplacements(depart)
        if atteignables and convient(app.PLATEAU.pion_sur(depart)):
            yield pion, depart, atteignables


def pion_qui_peut_bouger(page, convient=lambda pion: True):
    """Le premier pion de la page qui a des cases où aller."""
    for candidat in pions_qui_peuvent_bouger(page, convient):
        return candidat
    raise AssertionError("aucun des dix pions ne peut se déplacer")


def fantomes(page):
    return geometrie_des_pions(page, "img.fantome")


def montrer_les_fantomes(page, pion):
    """Clique le pion et attend ses fantômes."""
    pion.click()
    page.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    return fantomes(page)


def test_cliquer_un_pion_montre_ses_deplacements(plateau):
    pion, depart, atteignables = pion_qui_peut_bouger(plateau)
    poses = montrer_les_fantomes(plateau, pion)

    assert len(poses) == len(atteignables)
    assert {(f["q"], f["r"], f["s"]) for f in poses} == {(h.q, h.r, h.s) for h in atteignables}
    assert (depart.q, depart.r, depart.s) not in {(f["q"], f["r"], f["s"]) for f in poses}


def test_les_fantomes_suivent_le_mouvement_du_carton(plateau):
    """Le nombre de fantômes est celui du mouvement du pion, pas d'un forfait commun."""
    pion, depart, _ = pion_qui_peut_bouger(plateau)
    mouvement = app.PLATEAU.pion_sur(depart).points_de_mouvement
    poses = montrer_les_fantomes(plateau, pion)

    assert len(poses) == len(app.PLATEAU.deplacements(depart))
    assert len(poses) <= len(depart.deplacements(mouvement))


def contact_avec_un_adversaire(page):
    """Pose un adversaire au contact d'un pion de la page, et rend la figure obtenue.

    L'ennemi est posé sur le plateau du serveur sans image sur la carte : ce qu'on veut éprouver
    est la chaîne du clic à la règle, pas l'affichage de ce pion-là. On cherche une figure où il
    reste quelque chose à montrer — un pion acculé n'aurait aucun fantôme, et il n'y aurait rien
    à comparer.
    """
    for pion, depart, seul in pions_qui_peuvent_bouger(page, engage):
        voisine = next(voisin for voisin in depart.voisins() if voisin in seul)
        app.PLATEAU.poser(voisine, adversaire_de(app.PLATEAU.pion_sur(depart)))
        au_contact = app.PLATEAU.deplacements(depart)
        if 0 < len(au_contact) < len(seul):
            return pion, depart, seul, voisine
        app.PLATEAU.retirer(voisine)
    pytest.skip("aucun pion du tirage n'a de voisin où poser un adversaire")


def test_les_fantomes_s_arretent_devant_l_adversaire(plateau):
    """Un adversaire posé au contact réduit ce que le clic affiche."""
    pion, _, seul, voisine = contact_avec_un_adversaire(plateau)

    poses = montrer_les_fantomes(plateau, pion)
    assert len(poses) < len(seul)
    assert (voisine.q, voisine.r, voisine.s) not in {(f["q"], f["r"], f["s"]) for f in poses}


def engage(pion):
    """Dit si le pion appartient à un camp : un neutre n'a pas d'adversaire à lui opposer."""
    return pion.camp in ADVERSAIRES


def adversaire_de(pion):
    """Un pion du camp opposé, pris au catalogue."""
    return next(autre for autre in CATALOGUE.values()
                if autre.camp == ADVERSAIRES[pion.camp] and autre.est_une_unite)


def test_le_libelle_du_pion_dit_son_camp_et_son_mouvement(plateau):
    for indice in range(app.NOMBRE_DE_PIONS):
        pion = plateau.locator("img.pion:not(.fantome)").nth(indice)
        titre, cle = pion.evaluate("p => [p.title, p.pion.cle]")
        pose = CATALOGUE[cle]
        assert f"({pose.camp})" in titre, titre
        assert titre.endswith(f"— {pose.points_de_mouvement} PM"), titre


def test_les_fantomes_sont_a_moitie_transparents(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    for fantome in fantomes(plateau):
        assert fantome["opacite"] == 0.5


def test_les_fantomes_reprennent_l_image_du_pion(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    source = pion.evaluate("p => p.src")
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    assert plateau.evaluate(
        "(src) => [...document.querySelectorAll('img.fantome')].every((f) => f.src === src)", source
    )


def test_chaque_fantome_est_centre_et_incline(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    for fantome in fantomes(plateau):
        x, y = centre_attendu(fantome["q"], fantome["r"])
        assert math.isclose(fantome["x"], x, abs_tol=1.0), fantome
        assert math.isclose(fantome["y"], y, abs_tol=1.0), fantome
        assert abs(fantome["angle"]) <= 5.0, fantome


def test_cliquer_un_fantome_deplace_le_pion(plateau):
    pion, depart, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    cible = plateau.locator("img.fantome").last
    arrivee = cible.evaluate("f => [Number(f.dataset.q), Number(f.dataset.r), Number(f.dataset.s)]")
    cible.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    assert pion.evaluate(
        "p => [Number(p.dataset.q), Number(p.dataset.r), Number(p.dataset.s)]") == arrivee
    assert arrivee != [depart.q, depart.r, depart.s]

    pose = next(p for p in geometrie_des_pions(plateau) if [p["q"], p["r"], p["s"]] == arrivee)
    x, y = centre_attendu(*arrivee[:2])
    assert math.isclose(pose["x"], x, abs_tol=1.0) and math.isclose(pose["y"], y, abs_tol=1.0)
    assert abs(pose["angle"]) <= 5.0


def test_les_dix_pions_restent_dix_apres_un_deplacement(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    plateau.locator("img.fantome").last.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    assert plateau.locator("img.pion:not(.fantome)").count() == app.NOMBRE_DE_PIONS


def test_recliquer_le_pion_efface_les_fantomes(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")


def test_cliquer_ailleurs_efface_les_fantomes(plateau):
    """Un clic sur une case sans pion ni fantôme repose la sélection."""
    pion, depart, atteignables = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    occupes = set(plateau.evaluate(
        "() => [...document.querySelectorAll('img.pion:not(.fantome)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))
    interdits = {hexagone.cle for hexagone in atteignables} | {depart.cle} | occupes
    ailleurs = next(Hex.depuis_cle(cle) for cle in CARTE if cle not in interdits)
    cliquer_l_hexagone(plateau, ailleurs)
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")


def cliquer_l_hexagone(page, hexagone):
    """Clique au centre de l'hexagone, en pixels d'écran."""
    x, y = centre_attendu(hexagone.q, hexagone.r)
    point = page.evaluate("""([x, y]) => {
        const carte = document.getElementById('carte');
        const cadre = carte.getBoundingClientRect();
        const echelle = cadre.width / carte.naturalWidth;
        return [cadre.x + x * echelle, cadre.y + y * echelle];
    }""", [x, y])
    page.mouse.click(point[0], point[1])
