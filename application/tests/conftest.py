"""Fixtures communes : client Flask et serveur réel pour les tests de navigateur."""

import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import application  # noqa: E402


@pytest.fixture
def client():
    """Client de test Flask, sans navigateur ni socket."""
    application.config["TESTING"] = True
    return application.test_client()


@pytest.fixture(scope="session")
def serveur():
    """Sert l'application sur un port libre, le temps de la session de tests."""
    serveur = make_server("127.0.0.1", 0, application)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{serveur.server_port}"
    serveur.shutdown()
    fil.join()
