"""Retrouver sa vue de la carte au rechargement : ce que le navigateur relève et repose.

La carte fait 6173 × 5102 px et l'on y joue approché. Avant, recharger la page ramenait à
l'ajustement — la carte entière dans la fenêtre — et il fallait refaire son zoom et retrouver son
coin de front. Ces tests-ci ouvrent la page, règlent la vue, rechargent, et regardent où l'on
retombe. Ce que le serveur en fait est dans `test_vue.py`.

Ces tests demandent Chromium (`python3 -m playwright install chromium`).
"""

import time

import pytest

from client_discord import IDENTITE_PAR_DEFAUT

# Le zoom est envoyé après un demi-seconde de calme (`DELAI_DE_LA_VUE` dans `static/carte.js`) :
# ces attentes-ci lui laissent de la marge sur une machine chargée.
PATIENCE = 5.0

# Les vues relevées de part et d'autre d'un rechargement ne sont pas au pixel près : le point
# visé se borne au bord de la carte, et les barres de défilement paraissent et disparaissent.
TOLERANCE = 2.0


@pytest.fixture
def vues(application):
    """Le dépôt de vues, vidé avant et après : il vit aussi longtemps que l'application."""
    depot = application.extensions["depot_de_vues"]
    depot.vider()
    yield depot
    depot.vider()


@pytest.fixture
def plateau(page, serveur, application, installer_le_joueur, vues):
    """Ouvre la page connectée, et attend que la carte soit posée et le zoom monté."""
    installer_le_joueur(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{serveur}/connexion")
    attendre_la_carte(page)
    return page


def attendre_la_carte(page):
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")


def vue_lue(page):
    """La vue que la page montre en ce moment : son échelle, son centre, son ajustement."""
    return page.evaluate(
        "() => ({ echelle: vue.echelle(), ...vue.centreVu(), ajustee: vue.suitLaFenetre() })")


def attendre(condition, secondes=PATIENCE):
    """Attend qu'une condition Python devienne vraie — la vue part après un temps de calme."""
    limite = time.monotonic() + secondes
    while time.monotonic() < limite:
        valeur = condition()
        if valeur:
            return valeur
        time.sleep(0.05)
    raise AssertionError("condition jamais remplie")


def vue_rangee(vues):
    """La vue que le serveur retient pour le joueur de test, ou `None`."""
    return vues.par_discord_id(IDENTITE_PAR_DEFAUT["discord_id"])


def attendre_la_vue(vues, accepter=None):
    """La vue rangée, une fois qu'elle est là et qu'elle satisfait `accepter`.

    Le navigateur attend un temps de calme avant d'envoyer : rien n'est encore rangé à l'instant
    du clic, et ce qui l'est peut dater du geste précédent.
    """
    def prete():
        vue = vue_rangee(vues)
        return vue if vue and (accepter is None or accepter(vue)) else None
    return attendre(prete)


def approcher(page, crans=3):
    """Approche la carte de quelques crans du bouton « + »."""
    for _ in range(crans):
        page.locator("#zoomer").click()


# --- Ce que le navigateur range -----------------------------------------------------------------

def test_la_carte_s_ouvre_ajustee_quand_rien_n_est_range(plateau):
    assert vue_lue(plateau)["ajustee"] is True


def test_approcher_range_la_vue(plateau, vues):
    approcher(plateau)
    rangee = attendre_la_vue(vues)
    montree = vue_lue(plateau)
    assert rangee["ajustee"] is False
    assert rangee["echelle"] == pytest.approx(montree["echelle"])
    assert (rangee["x"], rangee["y"]) == pytest.approx((montree["x"], montree["y"]),
                                                       abs=TOLERANCE)


def test_defiler_range_la_vue(plateau, vues):
    """Le défilement ne passe pas par le zoom : il est surveillé à part."""
    approcher(plateau)
    premiere = attendre_la_vue(vues)
    plateau.evaluate("() => document.getElementById('cadre').scrollBy(600, 400)")
    bougee = attendre_la_vue(vues, lambda vue: vue["x"] != premiere["x"])
    assert (bougee["x"], bougee["y"]) == pytest.approx(
        (vue_lue(plateau)["x"], vue_lue(plateau)["y"]), abs=TOLERANCE)


def test_un_anonyme_ne_range_rien(page, serveur, vues):
    """La carte est publique, mais un visiteur de passage n'a pas de place où la ranger."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{serveur}/")
    attendre_la_carte(page)
    approcher(page)
    page.wait_for_timeout(int(PATIENCE * 200))
    assert vue_rangee(vues) is None


# --- Ce qu'un rechargement retrouve -------------------------------------------------------------

def test_le_zoom_et_la_position_survivent_a_un_rechargement(plateau, serveur, vues):
    """C'est la demande : recharger la carte ne doit plus tout défaire."""
    approcher(plateau)
    approchee = attendre_la_vue(vues, lambda vue: not vue["ajustee"])
    # Le défilement est attendu à part : sans cela, la vue rangée pourrait n'être que celle du
    # zoom, et le rechargement retomberait juste sans que le défilement y soit pour rien.
    plateau.evaluate("() => document.getElementById('cadre').scrollBy(500, 300)")
    avant = attendre_la_vue(vues, lambda vue: vue["x"] != approchee["x"])

    plateau.goto(f"{serveur}/")
    attendre_la_carte(plateau)

    apres = vue_lue(plateau)
    assert apres["echelle"] == pytest.approx(avant["echelle"])
    assert (apres["x"], apres["y"]) == pytest.approx((avant["x"], avant["y"]), abs=TOLERANCE)
    assert apres["ajustee"] is False


def test_l_ajustement_se_retrouve_ajuste(plateau, serveur, vues):
    """Une carte réglée à la fenêtre ne fige aucune échelle : la fenêtre suivante retrouve la
    sienne, au lieu d'hériter du zoom d'un autre écran."""
    approcher(plateau)
    attendre_la_vue(vues, lambda vue: not vue["ajustee"])
    plateau.locator("#ajuster").click()
    attendre_la_vue(vues, lambda vue: vue["ajustee"])

    plateau.set_viewport_size({"width": 900, "height": 700})
    plateau.goto(f"{serveur}/")
    attendre_la_carte(plateau)

    apres = vue_lue(plateau)
    assert apres["ajustee"] is True
    ajustement = plateau.evaluate("""() => {
        const carte = document.getElementById('carte');
        return Math.min(window.innerWidth / carte.naturalWidth,
                        window.innerHeight / carte.naturalHeight);
    }""")
    assert apres["echelle"] == pytest.approx(ajustement)
