"""Le joueur dans la page : son bouton, la table, le grisage, et le coup de l'adversaire.

Ces tests demandent Chromium (`make navigateur`). Ils se connectent en déroulant le vrai flux —
le client Discord factice referme l'autorisation sur notre propre route de retour —, si bien que
le navigateur repart avec un cookie de session comme il en aurait un de Discord.
"""

import pytest

import app
from client_discord import IDENTITE_PAR_DEFAUT

ALLIANCE, TENEBRES = "alliance", "tenebres"

# Un PNG d'un pixel : un avatar qui charge vraiment, sans sortir de la machine.
PIXEL = ("data:image/png;base64,"
         "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5E"
         "rkJggg==")

AVEC_AVATAR = dict(IDENTITE_PAR_DEFAUT, avatar=PIXEL)

ORQUE = {"discord_id": "100000000000000002", "pseudo": "Grishnak",
         "nom_affiche": None, "avatar": None, "courriel": None}


@pytest.fixture(autouse=True)
def table_vide(application):
    """Chaque test part d'une table levée et d'un client factice remis à son compte d'origine."""
    app.PLACES.vider()
    application.extensions["discord"].identite_servie = dict(IDENTITE_PAR_DEFAUT)
    yield
    app.PLACES.vider()
    application.extensions["discord"].identite_servie = dict(IDENTITE_PAR_DEFAUT)


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


def hauteur_de_la_barre(page):
    return page.evaluate("() => document.getElementById('outils').getBoundingClientRect().height")


# --- Le bouton du compte -------------------------------------------------------------------------


def test_un_visiteur_anonyme_se_voit_proposer_de_se_connecter(page, serveur):
    ouvrir(page, serveur, connecte=False)
    assert page.locator("#joueur").inner_text().strip() == "Se connecter"


def test_le_bouton_montre_le_pseudo_apres_connexion(page, serveur):
    ouvrir(page, serveur)
    assert IDENTITE_PAR_DEFAUT["pseudo"] in page.locator("#joueur").inner_text()


def test_le_bouton_du_joueur_ne_fait_pas_grandir_la_barre(page, serveur, application):
    """La taille de référence de la barre est une contrainte documentée (carte.css).

    Le bouton du compte doit y tenir sans l'allonger d'un pixel, avatar compris. C'est ce test qui
    a fait dimensionner l'avatar en `em` : à 16 px, il dépassait la hauteur de ligne d'une fraction
    de pixel, et la barre entière y gagnait un pixel.
    """
    ouvrir(page, serveur, connecte=False)
    anonyme = hauteur_de_la_barre(page)

    application.extensions["discord"].identite_servie = dict(AVEC_AVATAR)
    ouvrir(page, serveur)
    page.wait_for_function("document.querySelector('#joueur img')?.complete === true")

    assert hauteur_de_la_barre(page) == anonyme


def test_un_pseudo_a_rallonge_ne_pousse_pas_les_boutons_hors_de_vue(page, serveur, application):
    application.extensions["discord"].identite_servie = dict(
        IDENTITE_PAR_DEFAUT, pseudo="Vorgtd fils de Vorgtd, seigneur des salles profondes")
    ouvrir(page, serveur)

    barre = page.locator("#outils").bounding_box()
    bouton = page.locator("#joueur").bounding_box()

    assert bouton["x"] + bouton["width"] <= barre["x"] + barre["width"] + 1


# --- Prendre place -------------------------------------------------------------------------------


def test_la_table_montre_les_deux_armees(page, serveur):
    ouvrir(page, serveur)
    page.locator("#joueur").click()
    lignes = page.locator("#table-places .camp")
    assert lignes.count() == 2
    assert "Nains" in lignes.first.inner_text() and "Orques" in lignes.last.inner_text()


def test_prendre_un_camp_ferme_le_dialogue_et_rend_la_main(page, serveur):
    """S'asseoir renvoie à la partie : le dialogue n'a plus rien à dire, et c'est notre tour."""
    ouvrir(page, serveur)
    page.locator("#joueur").click()
    page.locator(f'#table-places .camp[data-camp="{ALLIANCE}"] button').click()

    page.wait_for_function("() => !document.getElementById('table-dialogue').open")
    page.wait_for_function("() => !document.getElementById('phase-suivante').disabled")
    assert app.PLACES.occupant(ALLIANCE) == IDENTITE_PAR_DEFAUT["discord_id"]


def test_le_camp_tenu_se_lit_dans_la_table(page, serveur):
    ouvrir(page, serveur)
    page.locator("#joueur").click()
    page.locator(f'#table-places .camp[data-camp="{ALLIANCE}"] button').click()
    page.wait_for_function("() => !document.getElementById('table-dialogue').open")

    page.locator("#joueur").click()

    ligne = page.locator(f'#table-places .camp[data-camp="{ALLIANCE}"]')
    assert "mien" in ligne.get_attribute("class")
    assert "vous" in ligne.inner_text()


def test_un_camp_deja_tenu_ne_se_propose_pas(page, serveur, application, installer_le_joueur):
    installer_le_joueur(application, identite=ORQUE, camps=[ALLIANCE])
    ouvrir(page, serveur)
    page.locator("#joueur").click()

    ligne = page.locator(f'#table-places .camp[data-camp="{ALLIANCE}"]')
    assert ligne.locator("button").count() == 0


# --- Le grisage ----------------------------------------------------------------------------------


def test_les_boutons_d_action_sont_eteints_quand_ce_n_est_pas_son_tour(page, serveur):
    """Le joueur des Ténèbres ouvre la partie : la première phase est celle de l'Alliance."""
    app.PLACES.asseoir(TENEBRES, IDENTITE_PAR_DEFAUT["discord_id"])
    ouvrir(page, serveur)
    assert page.locator("#phase-suivante").is_disabled()


def test_les_boutons_d_action_sont_allumes_a_son_tour(page, serveur):
    app.PLACES.asseoir(ALLIANCE, IDENTITE_PAR_DEFAUT["discord_id"])
    ouvrir(page, serveur)
    assert page.locator("#phase-suivante").is_enabled()


def test_un_visiteur_sans_place_ne_peut_pas_passer_la_phase(page, serveur):
    ouvrir(page, serveur)
    assert page.locator("#phase-suivante").is_disabled()


def test_un_coup_refuse_le_dit_au_joueur(page, serveur, carte_deserte):
    """Le grisage couvre le cas ordinaire ; le message couvre ce qu'il ne peut pas couvrir.

    Ici le joueur tient l'Alliance, mais le tour a passé aux Ténèbres pendant qu'il réfléchissait :
    la page n'en sait rien encore, et son clic part quand même.
    """
    app.PLACES.asseoir(ALLIANCE, IDENTITE_PAR_DEFAUT["discord_id"])
    ouvrir(page, serveur)
    app.TOUR.suivante()  # le serveur passe au camp d'en face, sans que la page le sache
    app.TOUR.suivante()

    page.evaluate("() => document.getElementById('phase-suivante').disabled = false")
    page.locator("#phase-suivante").click()

    page.wait_for_selector("#message:not([hidden])")
    assert "de jouer" in page.locator("#message").inner_text()


# --- Suivre l'adversaire -------------------------------------------------------------------------


def test_le_coup_de_l_adversaire_apparait_sans_recharger(browser, serveur, application):
    """Deux navigateurs, deux camps : celui qui attend voit la partie avancer sans rien faire.

    C'est ce que l'interrogation périodique promet, et la seule façon de l'éprouver est bien
    d'ouvrir deux fenêtres.
    """
    alliance = browser.new_context()
    tenebres = browser.new_context()
    try:
        page_alliance = ouvrir(alliance.new_page(), serveur)
        page_alliance.locator("#joueur").click()
        page_alliance.locator(f'#table-places .camp[data-camp="{ALLIANCE}"] button').click()
        # Le dialogue se referme de lui-même une fois la place prise ; on attend qu'il soit parti,
        # sans quoi son fond modal avalerait le clic suivant.
        page_alliance.wait_for_function(
            "() => !document.getElementById('table-dialogue').open"
            " && !document.getElementById('phase-suivante').disabled")

        application.extensions["discord"].identite_servie = dict(ORQUE)
        page_tenebres = ouvrir(tenebres.new_page(), serveur)
        libelle_avant = page_tenebres.locator("#phase-libelle").inner_text()

        page_alliance.locator("#phase-suivante").click()

        # Rien à cliquer de ce côté-ci : la page se met à jour d'elle-même.
        page_tenebres.wait_for_function(
            "(avant) => document.getElementById('phase-libelle').textContent !== avant",
            arg=libelle_avant, timeout=15000)
        assert page_tenebres.locator("#phase-libelle").inner_text() != libelle_avant
    finally:
        alliance.close()
        tenebres.close()


def test_la_place_prise_par_l_adversaire_apparait_sans_recharger(browser, serveur, application):
    naine = browser.new_context()
    orque = browser.new_context()
    try:
        page_naine = ouvrir(naine.new_page(), serveur)
        page_naine.locator("#joueur").click()
        page_naine.locator(f'#table-places .camp[data-camp="{ALLIANCE}"] button').click()
        page_naine.wait_for_function(
            "() => !document.getElementById('phase-suivante').disabled")
        # On rouvre la table : c'est là que la place d'en face doit apparaître d'elle-même.
        page_naine.locator("#joueur").click()

        application.extensions["discord"].identite_servie = dict(ORQUE)
        page_orque = ouvrir(orque.new_page(), serveur)
        page_orque.locator("#joueur").click()
        page_orque.locator(f'#table-places .camp[data-camp="{TENEBRES}"] button').click()

        # La page des Nains apprend, toute seule, que quelqu'un s'est assis en face.
        page_naine.wait_for_function(
            "() => document.querySelector('#table-places .camp[data-camp=\\'tenebres\\']')"
            "?.innerText.includes('Grishnak')", timeout=15000)
    finally:
        naine.close()
        orque.close()


# --- Se déconnecter ------------------------------------------------------------------------------


def test_se_deconnecter_ramene_le_bouton_de_connexion(page, serveur):
    ouvrir(page, serveur)
    page.locator("#joueur").click()
    page.locator("#table-deconnexion").click()
    page.wait_for_function(
        "() => document.getElementById('joueur').innerText.trim() === 'Se connecter'")
