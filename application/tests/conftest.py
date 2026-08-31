"""Fixtures communes : client Flask et serveur réel pour les tests de navigateur."""

import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import PLATEAU, SUIVI, TOUR, application  # noqa: E402


@pytest.fixture
def client():
    """Client de test Flask, sans navigateur ni socket."""
    application.config["TESTING"] = True
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
def serveur():
    """Sert l'application sur un port libre, le temps de la session de tests."""
    serveur = make_server("127.0.0.1", 0, application)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{serveur.server_port}"
    serveur.shutdown()
    fil.join()
