"""Le flux vu de l'écran : deux onglets, un coup joué dans l'un, la scène qui bouge dans l'autre.

C'est ce que la migration promet à l'utilisateur, et c'est ici que ça se vérifie — dans Chromium,
pas en ouvrant deux fenêtres à la main. Trois choses s'y éprouvent et nulle part ailleurs :

- que la page **ouvre bien un `EventSource`** et ne sonde plus `/partie/etat` ;
- qu'un coup joué dehors arrive **sans qu'elle ait rien demandé** ;
- que le repli sur le sondage se déclenche quand le flux ne passe pas, et que le jeu continue.

Ces tests demandent Chromium (`make navigateur`).
"""

import pytest

import app

# Un coup joué doit se voir en moins de temps qu'il n'en faudrait à l'ancien sondage : c'est la
# seule façon de distinguer « le flux a poussé » de « quelque chose a fini par redemander ».
DELAI_DU_FLUX = 1500  # millisecondes ; le sondage de repli était à 3000

# La patience ordinaire de Playwright pour ce qui n'est pas chronométré.
DELAI = 10_000

# Le repli, lui, se fait attendre par construction : cinq échecs, et Chromium espace ses
# reconnexions d'environ trois secondes. C'est délibéré — on ne renonce pas au flux sur un
# hoquet de réseau —, et il faut donc laisser passer la quinzaine de secondes que cela prend.
DELAI_DU_REPLI = 40_000

LIBELLE = "document.getElementById('phase-libelle').textContent"


@pytest.fixture(autouse=True)
def partie_neuve(application, installer_le_joueur):
    """Chaque test part du scénario en place, de la première phase, et d'un joueur assis.

    Le plateau et le tour sont des module-globaux partagés par tous les fichiers de tests ; sans
    cela, un test précédent laisserait la partie en phase de combat et les libellés attendus ici
    ne tomberaient pas.
    """
    installer_le_joueur(application)
    app.PLATEAU.vider()
    app.TOUR.recommencer()
    app.SUIVI.reinitialiser()
    for case, cle in app.SCENARIO.placement.items():
        app.PLATEAU.poser(app.Hex.depuis_cle(case), app.CATALOGUE[cle])
    yield
    app.PLATEAU.vider()
    app.TOUR.recommencer()
    app.SUIVI.reinitialiser()


@pytest.fixture
def adversaire(playwright, serveur):
    """Celui qui joue « dehors » : un client HTTP à lui, hors de tout navigateur.

    C'est ce qui rend ces tests honnêtes. Passer par `page.request` emprunterait les cookies de
    l'onglet observé — le coup viendrait alors de la page elle-même, et l'on n'éprouverait plus
    rien du tout pour un visiteur anonyme. Ici le coup vient vraiment d'ailleurs.

    La connexion déroule le vrai flux, que le client Discord factice referme sur nous ; le joueur
    obtenu est celui qu'`installer_le_joueur` a assis aux deux camps.
    """
    contexte = playwright.request.new_context(base_url=serveur)
    assert contexte.get("/connexion").ok
    yield contexte
    contexte.dispose()


def ouvrir(page, serveur, connecte=True):
    """Charge le plateau et attend que la scène soit posée **et le flux ouvert**.

    Attendre le flux ouvert n'est pas une précaution de confort : un coup joué avant que
    l'`EventSource` ne soit connecté ne serait poussé à personne, et le test échouerait pour une
    raison qui n'est pas celle qu'il éprouve.
    """
    page.set_viewport_size({"width": 1400, "height": 900})
    if connecte and not page.context.cookies():
        page.goto(f"{serveur}/connexion")
    page.goto(serveur)
    page.wait_for_function(
        "document.querySelectorAll('img.pion').length === %d" % len(app.SCENARIO))
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")
    attendre_le_flux(page)
    return page


def attendre_le_flux(page):
    """Attend que l'`EventSource` de la page soit à l'état « ouvert » (`readyState === 1`)."""
    page.wait_for_function("flux !== null && flux.readyState === 1", timeout=DELAI)


def cases_posees(page):
    return set(page.evaluate(
        "() => [...document.querySelectorAll('img.pion:not(.fantome)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))


# --- La page tient bien un flux, et ne sonde plus ---


def test_la_page_ouvre_un_flux(page, serveur):
    ouvrir(page, serveur)
    assert page.evaluate("flux instanceof EventSource") is True


def test_la_page_ne_sonde_plus_l_etat(page, serveur, adversaire):
    """Le sondage est mort : plus un seul `/partie/etat`, même après un coup joué.

    L'ancien `setInterval` tirait toutes les trois secondes ; on en laisse passer quatre.
    """
    sondages = []
    page.on("request", lambda requete: sondages.append(requete.url)
            if "/partie/etat" in requete.url else None)

    ouvrir(page, serveur)
    assert adversaire.post("/phase/suivante").ok
    page.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'", timeout=DELAI_DU_FLUX)
    page.wait_for_timeout(4000)

    assert sondages == [], f"la page sonde encore : {sondages}"


def test_le_flux_est_le_seul_appel_au_serveur_quand_rien_ne_se_passe(page, serveur):
    """Une page ouverte et laissée tranquille ne doit plus rien demander du tout."""
    ouvrir(page, serveur)
    appels = []
    page.on("request", lambda requete: appels.append(requete.url))
    page.wait_for_timeout(4000)
    assert appels == [], f"la page appelle encore le serveur au repos : {appels}"


# --- Un coup joué dehors arrive tout seul ---


def test_un_coup_joue_dehors_arrive_sans_rien_demander(page, serveur, adversaire):
    """Le cœur du sujet, et en moins d'une seconde et demie — l'ancien sondage mettait trois
    secondes dans le meilleur des cas."""
    ouvrir(page, serveur)
    assert page.locator("#phase-libelle").inner_text() == "Phase de mouvement — Nains"

    assert adversaire.post("/phase/suivante").ok

    page.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'", timeout=DELAI_DU_FLUX)


def test_un_pion_deplace_dehors_se_repose_dans_la_page(page, serveur, adversaire):
    """Pas seulement la phase : le plateau entier voyage par le flux."""
    ouvrir(page, serveur)

    depart, arrivee, cle = un_deplacement_possible()
    reponse = adversaire.post("/deplacer", data={
        "depart": depart.en_dict(), "arrivee": arrivee.en_dict(), "pion": cle})
    assert reponse.json()["autorise"] is True

    page.wait_for_function(
        "(cases) => [...document.querySelectorAll('img.pion:not(.fantome)')]"
        ".some((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}` === cases)",
        arg=f"{arrivee.q},{arrivee.r},{arrivee.s}", timeout=DELAI_DU_FLUX)
    assert f"{depart.q},{depart.r},{depart.s}" not in cases_posees(page)


def un_deplacement_possible():
    """Une unité du camp actif, sa case, et une case où elle peut aller."""
    for case, pion in app.PLATEAU.pions.items():
        if pion.camp != app.TOUR.camp_actif:
            continue
        depart = app.Hex.depuis_cle(case)
        arrivees = app.PLATEAU.deplacements(depart, pion)
        if arrivees:
            return depart, next(iter(arrivees)), pion.cle
    raise AssertionError("aucune unité du camp actif ne peut se déplacer")


def test_deux_onglets_voient_le_meme_coup(page, context, serveur, adversaire):
    """Deux joueurs, deux navigateurs : c'est pour cela que tout ceci existe."""
    ouvrir(page, serveur)
    second = context.new_page()
    try:
        ouvrir(second, serveur)

        assert adversaire.post("/phase/suivante").ok

        for onglet in (page, second):
            onglet.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'",
                                     timeout=DELAI_DU_FLUX)
    finally:
        second.close()


def test_un_visiteur_sans_compte_suit_aussi_la_partie(page, serveur, adversaire):
    """Le flux est public, comme la carte : on peut regarder jouer sans compte."""
    ouvrir(page, serveur, connecte=False)
    assert page.evaluate("table.connecte") is False

    assert adversaire.post("/phase/suivante").ok

    page.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'", timeout=DELAI_DU_FLUX)


# --- Ce que la scène reposée ne doit pas défaire ---


def test_le_repere_de_localiser_survit_a_la_scene_reposee(page, serveur, adversaire):
    """« Localiser » vise le dernier pion cliqué, et doit le retrouver après un coup de l'adversaire.

    La scène reposée détruit toutes les images et les recrée : sans soin, le repère pointerait un
    élément qui n'est plus au plateau et le bouton s'éteindrait. C'était déjà vrai du sondage,
    mais il fallait attendre trois secondes pour le voir ; le flux, lui, le montre aussitôt.
    """
    ouvrir(page, serveur)
    pion = page.locator("img.pion:not(.fantome)").first
    case = pion.evaluate("p => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`")
    pion.click()
    page.wait_for_function("!document.getElementById('localiser').disabled")

    assert adversaire.post("/phase/suivante").ok
    page.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'", timeout=DELAI_DU_FLUX)

    assert page.locator("#localiser").is_enabled(), \
        "le repère de « localiser » a été perdu en reposant la scène"
    assert page.evaluate("`${dernierPionClique.dataset.q},${dernierPionClique.dataset.r},`"
                         "+ `${dernierPionClique.dataset.s}`") == case


# --- Le repli, et la reconnexion ---


def test_le_repli_sur_le_sondage_quand_le_flux_ne_passe_pas(page, serveur, adversaire):
    """Un intermédiaire qui coupe le SSE ne doit pas casser le jeu : il doit le ralentir.

    On refuse toute connexion à `/flux` : le navigateur retente de lui-même, la page compte les
    échecs, et au cinquième elle rouvre l'ancien sondage. Le coup joué dehors finit donc par
    arriver — en trois secondes au lieu d'une milliseconde.
    """
    page.route("**/flux*", lambda route: route.abort())
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{serveur}/connexion")
    page.goto(serveur)
    page.wait_for_function(
        "document.querySelectorAll('img.pion').length === %d" % len(app.SCENARIO))

    # Le repli s'installe une fois les cinq échecs comptés.
    page.wait_for_function("minuterieDuSondage !== null", timeout=DELAI_DU_REPLI)
    assert page.evaluate("flux === null"), "le flux aurait dû être refermé avant le repli"

    assert adversaire.post("/phase/suivante").ok
    page.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'", timeout=DELAI)


def test_la_page_se_reconnecte_apres_une_coupure(page, serveur, adversaire):
    """Le serveur redémarre, ou le réseau tombe : `EventSource` rouvre tout seul, et rattrape.

    La coupure est jouée en refusant `/flux` le temps d'une reconnexion, puis en le laissant
    repasser. Ce qu'on vérifie ensuite est ce qui compte : le flux est de nouveau ouvert, et un
    coup joué pendant la coupure a bien été rattrapé — c'est le `Last-Event-ID` qui le permet.
    """
    ouvrir(page, serveur)

    coupe = {"actif": True}
    page.route("**/flux*",
               lambda route: route.abort() if coupe["actif"] else route.continue_())
    page.evaluate("flux.close(); flux = null; ouvrirLeFlux();")  # la connexion tombe

    # Le coup est joué alors que la page n'écoute personne : elle ne peut pas le recevoir.
    assert adversaire.post("/phase/suivante").ok
    page.wait_for_timeout(300)
    assert page.locator("#phase-libelle").inner_text() == "Phase de mouvement — Nains"

    coupe["actif"] = False
    attendre_le_flux(page)

    # Reconnectée, la page rattrape ce qu'elle a manqué sans qu'on ait rien à lui redemander.
    page.wait_for_function(f"{LIBELLE} === 'Phase de combat — Nains'", timeout=DELAI)


# --- Le nettoyage ---


def test_un_onglet_ferme_libere_son_abonnement(page, context, serveur, adversaire):
    """La fuite qu'on veut prendre : le serveur ne doit pas garder de boîte pour un onglet parti."""
    ouvrir(page, serveur)
    abonnes = len(app.DIFFUSEUR)

    second = context.new_page()
    ouvrir(second, serveur)
    assert len(app.DIFFUSEUR) == abonnes + 1

    second.close()
    # La radiation se voit dès que le serveur tente d'écrire : le battement suffit à la
    # déclencher, et il est ici raccourci par le premier coup joué.
    assert adversaire.post("/phase/suivante").ok
    attendre(lambda: len(app.DIFFUSEUR) == abonnes)


def attendre(condition, secondes=10.0):
    """Attend qu'une condition Python devienne vraie — la radiation se fait dans un autre fil."""
    import time
    limite = time.monotonic() + secondes
    while time.monotonic() < limite:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError("condition jamais remplie")
