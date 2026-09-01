"""La reprise de partie, vue du navigateur : déplacer un pion, recharger, le retrouver là.

C'est ce que la persistance promet à l'utilisateur, et c'est ce qui se vérifie ici — en jouant
dans Chromium, pas en lançant l'application à la main. Le serveur tourne dans le processus des
tests, comme pour les autres tests de navigateur ; ce qui change est sa configuration : il est
branché sur une base, quand le serveur partagé de `conftest.py` ne l'est pas.

Deux bases possibles, et le fichier tourne sur les deux :

- **mongomock** par défaut, en mémoire : rien à installer, ces tests tournent partout ;
- le **vrai MongoDB** que `make test` monte, dès que `MONGODB_URI_TEST` le désigne et qu'il
  répond. C'est la seule façon d'éprouver la chaîne complète telle qu'elle tourne en vrai.

Ces tests demandent Chromium (`make navigateur`).
"""

import threading

import pytest

mongomock = pytest.importorskip("mongomock")

import mongoengine  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

import app  # noqa: E402
from test_persistance import URI_DE_TEST, ConfigMongoReel, ConfigMongomock, \
    mongodb_est_joignable  # noqa: E402


@pytest.fixture(params=["mongomock", "mongodb"])
def serveur_persistant(request, installer_le_joueur):
    """Un serveur branché sur une base, servi sur un port libre le temps du test.

    Le paramètre fait tourner chaque test deux fois : sur mongomock, et sur le vrai MongoDB s'il
    est joignable. La base est vidée avant et après — et les module-globaux de `app` avec elle,
    puisque tous les fichiers de tests se les partagent.
    """
    if request.param == "mongodb":
        if not mongodb_est_joignable():
            pytest.skip(f"aucun MongoDB joignable sur {URI_DE_TEST}")
        configuration = ConfigMongoReel
    else:
        configuration = ConfigMongomock

    application = app.create_app(configuration)
    from moteur.models.joueur import Joueur
    from moteur.models.partie import Partie
    Partie.objects.delete()
    Joueur.objects.delete()

    # `threaded=True` pour la même raison que dans `conftest.py` : la page tient un flux
    # SSE ouvert, et un serveur mono-thread ne servirait plus rien d'autre.
    serveur = make_server("127.0.0.1", 0, application, threaded=True)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    installer_le_joueur(application)
    yield f"http://127.0.0.1:{serveur.server_port}"

    serveur.shutdown()
    fil.join()
    Partie.objects.delete()
    Joueur.objects.delete()
    mongoengine.disconnect_all()
    app.PLATEAU.vider()
    app.TOUR.recommencer()
    app.SUIVI.reinitialiser()
    app.PLACES.vider()


@pytest.fixture
def plateau_persistant(page, serveur_persistant):
    """Ouvre le plateau et attend que la carte et les unités soient chargées."""
    page.set_viewport_size({"width": 1400, "height": 900})
    ouvrir(page, serveur_persistant)
    return page


def ouvrir(page, adresse):
    """Charge le plateau et attend que tout soit posé — comme au premier chargement.

    Le premier chargement passe par la connexion : jouer demande une place, et la session du
    navigateur se pose en déroulant le flux, que le client Discord factice referme sur nous.
    """
    if not page.context.cookies():
        page.goto(f"{adresse}/connexion")
    page.goto(adresse)
    page.wait_for_function(
        "document.querySelectorAll('img.pion').length === %d" % len(app.SCENARIO))
    page.wait_for_function(
        "[...document.querySelectorAll('img.pion'), document.getElementById('carte')]"
        ".every((i) => i.complete && i.naturalWidth > 0)")
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")
    return page


def cases_posees(page):
    """Les cases des pions posés, telles que la page les porte."""
    return set(page.evaluate(
        "() => [...document.querySelectorAll('img.pion:not(.fantome)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))


def angles_poses(page):
    """L'angle de chaque pion posé, par case — lu sur la rotation que le navigateur a appliquée."""
    return page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('img.pion:not(.fantome)')].map((pion) => {
            const matrice = new DOMMatrix(getComputedStyle(pion).transform);
            const angle = Math.atan2(matrice.b, matrice.a) * 180 / Math.PI;
            return [`${pion.dataset.q},${pion.dataset.r},${pion.dataset.s}`,
                    Math.round(angle * 100) / 100];
        }))""")


def deplacer_un_pion(page):
    """Déplace la première unité qui a des cases où aller, et rend son départ et son arrivée."""
    for indice in range(len(app.SCENARIO)):
        pion = page.locator("img.pion:not(.fantome)").nth(indice)
        depart = pion.evaluate(
            "p => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`")
        pion.click()
        try:
            page.wait_for_function("document.querySelectorAll('img.fantome').length > 0",
                                   timeout=2000)
        except Exception:
            continue  # cette unité n'a nulle part où aller : on passe à la suivante
        fantome = page.locator("img.fantome").last
        arrivee = fantome.evaluate("f => `${f.dataset.q},${f.dataset.r},${f.dataset.s}`")
        fantome.click()
        page.wait_for_function("document.querySelectorAll('img.fantome').length === 0")
        return depart, arrivee
    raise AssertionError("aucune unité du scénario ne peut se déplacer")


def test_un_pion_deplace_reste_a_sa_nouvelle_case_apres_rechargement(plateau_persistant,
                                                                     serveur_persistant):
    """Le cœur de la persistance, vu de l'écran : recharger ne remet plus le scénario en place."""
    depart, arrivee = deplacer_un_pion(plateau_persistant)
    assert depart not in cases_posees(plateau_persistant)
    assert arrivee in cases_posees(plateau_persistant)

    ouvrir(plateau_persistant, serveur_persistant)

    posees = cases_posees(plateau_persistant)
    assert arrivee in posees, "le pion déplacé n'a pas été retrouvé à son arrivée"
    assert depart not in posees, "le pion est revenu à sa case de départ : rien n'a été repris"


def test_la_phase_est_reprise_apres_rechargement(plateau_persistant, serveur_persistant):
    plateau_persistant.locator("#phase-suivante").click()
    plateau_persistant.wait_for_function(
        "document.getElementById('phase-libelle').textContent === 'Phase de combat — Nains'")

    ouvrir(plateau_persistant, serveur_persistant)
    assert plateau_persistant.locator("#phase-libelle").inner_text() == "Phase de combat — Nains"


def test_recommencer_repose_le_scenario(plateau_persistant, serveur_persistant):
    """`POST /partie/nouvelle` ramène les 52 unités à leur case, et le rechargement le confirme."""
    depart, arrivee = deplacer_un_pion(plateau_persistant)

    reponse = plateau_persistant.request.post(f"{serveur_persistant}/partie/nouvelle")
    assert reponse.ok

    ouvrir(plateau_persistant, serveur_persistant)
    posees = cases_posees(plateau_persistant)
    assert posees == set(app.SCENARIO.placement)
    assert depart in posees and arrivee not in posees


def test_les_pions_gardent_leur_inclinaison_apres_rechargement(plateau_persistant,
                                                               serveur_persistant):
    """L'angle des cartons est sauvegardé avec les positions : recharger ne les recouche pas."""
    avant = angles_poses(plateau_persistant)
    ouvrir(plateau_persistant, serveur_persistant)
    assert angles_poses(plateau_persistant) == avant


def test_le_pion_deplace_garde_son_nouvel_angle_apres_rechargement(plateau_persistant,
                                                                   serveur_persistant):
    """Repris en main, il se recouche une fois — et la base retient ce nouvel angle."""
    _, arrivee = deplacer_un_pion(plateau_persistant)
    angle = angles_poses(plateau_persistant)[arrivee]

    ouvrir(plateau_persistant, serveur_persistant)

    assert angles_poses(plateau_persistant)[arrivee] == angle
