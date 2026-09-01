"""Fixtures communes : client Flask et serveur réel pour les tests de navigateur."""

import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import PLATEAU, SUIVI, TOUR, create_app  # noqa: E402
from config import ConfigDeTest  # noqa: E402


@pytest.fixture(scope="session")
def application():
    """L'application de test, construite une seule fois par la factory.

    Une seule instance pour toute la session : le client Flask et le serveur des tests de
    navigateur doivent parler au même objet. La configuration de test débranche la persistance
    (dépôt nul) — l'état de jeu reste dans les module-globaux de `app`, que les fixtures et les
    tests manipulent directement.
    """
    return create_app(ConfigDeTest)


@pytest.fixture
def client(application):
    """Client de test Flask, sans navigateur ni socket."""
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
    """Sert l'application sur un port libre, le temps de la session de tests."""
    serveur = make_server("127.0.0.1", 0, application)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{serveur.server_port}"
    serveur.shutdown()
    fil.join()
