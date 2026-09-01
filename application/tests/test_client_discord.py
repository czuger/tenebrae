"""Ce que `ClientDiscord` fait des réponses de Discord — sans sortir de la machine.

`urlopen` est remplacé dans le module : les trois appels HTTP du flux ne partent nulle part, et
l'on regarde ce que le client rend, ou ce qu'il lève, selon ce qu'on lui fait recevoir.
"""

import io
import json
from urllib.error import HTTPError, URLError

import pytest

import client_discord
from client_discord import ClientDiscord, ErreurDiscord


@pytest.fixture
def client():
    return ClientDiscord("identifiant", "secret", "http://127.0.0.1:5000/connexion/retour")


def repondre(monkeypatch, corps):
    """Fait rendre `corps` (un dict) à `urlopen`, comme une réponse 200."""
    class Reponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    monkeypatch.setattr(client_discord, "urlopen",
                        lambda requete, timeout: Reponse(json.dumps(corps).encode()))


def tomber(monkeypatch, souci):
    def lever(requete, timeout):
        raise souci
    monkeypatch.setattr(client_discord, "urlopen", lever)


def test_le_jeton_est_lu_dans_la_reponse(client, monkeypatch):
    repondre(monkeypatch, {"access_token": "jeton", "token_type": "Bearer"})
    assert client.echanger_le_code("code") == "jeton"


def test_une_erreur_http_porte_le_statut_et_le_corps_de_discord(client, monkeypatch):
    """C'est dans le corps que Discord dit *pourquoi* — `invalid_grant`, `invalid_client` — et
    `str(HTTPError)` ne le montre pas : le message de l'erreur doit le reprendre."""
    corps = json.dumps({"error": "invalid_grant",
                        "error_description": "Invalid \"code\" in request."}).encode()
    tomber(monkeypatch, HTTPError(client_discord.JETON, 400, "Bad Request", {},
                                  io.BytesIO(corps)))
    with pytest.raises(ErreurDiscord) as releve:
        client.echanger_le_code("code")
    message = str(releve.value)
    assert "400 Bad Request" in message
    assert client_discord.JETON in message
    assert "invalid_grant" in message
    assert 'Invalid \\"code\\" in request.' in message
    assert isinstance(releve.value.__cause__, HTTPError)


def test_un_discord_injoignable_dit_lequel_et_pourquoi(client, monkeypatch):
    tomber(monkeypatch, URLError("Connection refused"))
    with pytest.raises(ErreurDiscord, match="Connection refused") as releve:
        client.identite("jeton")
    assert client_discord.MOI in str(releve.value)


def test_une_reponse_sans_jeton_est_une_erreur(client, monkeypatch):
    repondre(monkeypatch, {"token_type": "Bearer"})
    with pytest.raises(ErreurDiscord, match="jeton"):
        client.echanger_le_code("code")
