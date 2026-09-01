"""Fixtures communes : client Flask connecté, joueur de test, et serveur réel pour le navigateur."""

import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import PLACES, PLATEAU, SCENARIO, SUIVI, TOUR, create_app  # noqa: E402
from client_discord import IDENTITE_PAR_DEFAUT  # noqa: E402
from config import ConfigDeTest  # noqa: E402


@pytest.fixture(scope="session")
def application():
    """L'application de test, construite une seule fois par la factory.

    Une seule instance pour toute la session : le client Flask et le serveur des tests de
    navigateur doivent parler au même objet. La configuration de test débranche la persistance
    (dépôt nul) — l'état de jeu reste dans les module-globaux de `app`, que les fixtures et les
    tests manipulent directement — et branche le client Discord factice.
    """
    return create_app(ConfigDeTest)


@pytest.fixture
def installer_le_joueur():
    """Rend de quoi asseoir un joueur à la table, et lève la table en sortant.

    La suite joue **les deux camps à la fois** : un seul joueur de test tient l'Alliance et les
    Ténèbres. Ce n'est pas ce que la route « prendre place » permet — elle refuse un second camp,
    et un test le vérifie —, mais le registre, lui, n'en sait rien : il ne défend que l'invariant
    « un camp, un occupant ». C'est cette séparation qui laisse jouer les deux côtés aux tests
    écrits avant les joueurs, sans en réécrire un seul.
    """
    PLACES.vider()

    def installer(application, client=None, identite=IDENTITE_PAR_DEFAUT, camps=None):
        application.extensions["depot_de_joueurs"].enregistrer(identite)
        for camp in (SCENARIO.camps if camps is None else camps):
            PLACES.asseoir(camp, identite["discord_id"])
        if client is not None:
            with client.session_transaction() as session:
                session["joueur"] = identite["discord_id"]
        return identite

    yield installer
    PLACES.vider()


@pytest.fixture
def client(application, installer_le_joueur):
    """Client de test Flask, **connecté et assis aux deux camps** (voir `installer_le_joueur`).

    Ce n'est plus le visiteur de passage qu'il était avant les joueurs : les routes qui changent
    l'état demandent maintenant une session et une place. Pour éprouver un anonyme, prendre
    `client_anonyme`.
    """
    client = application.test_client()
    installer_le_joueur(application, client)
    return client


@pytest.fixture
def client_anonyme(application):
    """Le même client, sans session : ce que voit un visiteur de passage."""
    return application.test_client()


@pytest.fixture
def carte_deserte():
    """Vide le plateau du serveur et ramène le tour à sa première phase, avant et après le test.

    Le tirage est groupé : sans cela, un secteur tombant près de l'hexagone de référence d'un test
    de déplacement y poserait des adversaires, et le résultat dépendrait du hasard. Le tour est
    partagé lui aussi — un test qui le fait avancer le laisserait avancé pour le suivant, et le
    registre des combats de la phase avec lui.
    """
    PLATEAU.vider()
    TOUR.recommencer()
    SUIVI.reinitialiser()
    yield PLATEAU
    PLATEAU.vider()
    TOUR.recommencer()
    SUIVI.reinitialiser()


@pytest.fixture(scope="session")
def serveur(application):
    """Sert l'application sur un port libre, le temps de la session de tests.

    `threaded=True` n'est pas un confort : depuis que la page tient un **flux SSE** ouvert
    (`/flux`, voir `application/flux.py`), une requête reste en cours tant que l'onglet vit. Un
    serveur mono-thread — ce que `make_server` donne par défaut — servirait ce flux et plus
    jamais rien d'autre, et toute la suite Playwright s'arrêterait là. Les fils de werkzeug sont
    des démons : l'arrêt n'attend pas les flux encore ouverts.
    """
    serveur = make_server("127.0.0.1", 0, application, threaded=True)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{serveur.server_port}"
    serveur.shutdown()
    fil.join()
