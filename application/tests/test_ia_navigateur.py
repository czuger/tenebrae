"""La partie contre l'IA, vue du navigateur : le bouton du dialogue, la place « IA », l'ouverture.

Ces tests demandent Chromium (`make navigateur`). Comme partout, la connexion déroule le vrai
flux : le client Discord factice referme l'autorisation sur notre propre route de retour.
"""

import pytest

import app
from client_discord import IDENTITE_PAR_DEFAUT
from moteur import ia

ALLIANCE, TENEBRES = "alliance", "tenebres"


@pytest.fixture(autouse=True)
def table_vide(application):
    """Chaque test part d'une table levée ; le plateau, lui, se repose à chaque chargement."""
    app.PLACES.vider()
    yield
    app.PLACES.vider()


def ouvrir(page, serveur, connecte=True):
    """Charge le plateau, connecté ou non, et attend que la scène soit posée."""
    page.set_viewport_size({"width": 1400, "height": 900})
    if connecte:
        page.goto(f"{serveur}/connexion")
    page.goto(serveur)
    page.wait_for_function(
        "document.querySelectorAll('img.pion').length === %d" % len(app.SCENARIO))
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")
    return page


def cliquer_le_bouton_contre_l_ia(page):
    """Ouvre la table, clique « Nouvelle partie contre l'IA », attend que le dialogue se referme.

    Le dialogue ne se referme qu'à la réponse du serveur : l'attendre fermé, c'est attendre que
    la partie neuve — et l'éventuel tour d'ouverture de l'IA — soit jouée.
    """
    page.locator("#joueur").click()
    page.locator("#table-contre-ia").click()
    page.wait_for_function("!document.getElementById('table-dialogue').open")


def test_un_joueur_sans_place_ne_voit_pas_le_bouton(page, serveur):
    ouvrir(page, serveur)
    page.locator("#joueur").click()
    assert page.locator("#table-contre-ia").is_hidden()


def test_le_bouton_confie_le_camp_adverse_a_l_ia(page, serveur):
    ouvrir(page, serveur)
    # S'asseoir à l'Alliance par le dialogue, comme un joueur le ferait.
    page.locator("#joueur").click()
    page.locator(f"#table-places .camp[data-camp='{ALLIANCE}'] button").click()
    page.wait_for_function("!document.getElementById('table-dialogue').open")

    cliquer_le_bouton_contre_l_ia(page)

    assert app.PLACES.occupant(TENEBRES) == ia.JOUEUR_IA
    # La table rouverte montre la place occupée par « IA ».
    page.locator("#joueur").click()
    assert ia.NOM_IA in page.locator(f"#table-places .camp[data-camp='{TENEBRES}']").inner_text()


def test_l_ia_ouvre_le_scenario_quand_elle_tient_l_alliance(page, serveur):
    app.PLACES.asseoir(TENEBRES, IDENTITE_PAR_DEFAUT["discord_id"])
    ouvrir(page, serveur)

    cliquer_le_bouton_contre_l_ia(page)

    # L'IA a reçu l'Alliance, joué son tour d'ouverture, et rendu la main aux Ténèbres.
    assert app.PLACES.occupant(ALLIANCE) == ia.JOUEUR_IA
    assert (app.TOUR.camp_actif, app.TOUR.type_de_phase) == (TENEBRES, "mouvement")
    assert app.PLATEAU.en_dict() != app.SCENARIO.placement
    # Et la page l'affiche : la phase montrée est celle du joueur humain.
    assert "Orques" in page.locator("#phase-libelle").inner_text()
