"""La partie contre l'IA : sa création, la place qu'elle tient, et son tour joué par le serveur.

L'IA n'a ni session ni compte Discord : elle occupe sa place sous la sentinelle `ia.JOUEUR_IA`,
et c'est le serveur qui joue son tour — dans la requête qui lui rend la main, jamais par HTTP.
Le dé est fixé par `monkeypatch` sur `app.lancer_le_de`, comme dans les tests de combat : à dé
égal, l'IA rejoue la même partie.
"""

import pytest

import app
from client_discord import IDENTITE_PAR_DEFAUT
from moteur import ia
from moteur.pion import CATALOGUE
from moteur.tests.plaines import couronne_de, plaine_bien_entouree

ELFE = "elfes-01-5-infanteries"            # alliance, force 7, mouvement 4
ORQUE = "orques-01-15-infanteries"         # ténèbres, force 8, mouvement 4

# Un second joueur humain, pour éprouver les camps déjà tenus.
GRISHNAK = IDENTITE_PAR_DEFAUT | {"discord_id": "100000000000000002", "pseudo": "Grishnak"}


@pytest.fixture
def client_alliance(application, installer_le_joueur):
    """Un client connecté qui ne tient que l'Alliance — le joueur d'une partie contre l'IA."""
    client = application.test_client()
    installer_le_joueur(application, client, camps=["alliance"])
    return client


@pytest.fixture
def client_tenebres(application, installer_le_joueur):
    """Le même, assis chez les Ténèbres : l'IA recevra l'Alliance, qui ouvre le scénario."""
    client = application.test_client()
    installer_le_joueur(application, client, camps=["tenebres"])
    return client


@pytest.fixture
def client_sans_place(application, installer_le_joueur):
    """Connecté, mais debout : de quoi éprouver `place_requise`."""
    client = application.test_client()
    installer_le_joueur(application, client, camps=[])
    return client


class TestNouvellePartieContreIA:
    def test_l_anonyme_est_refuse(self, client_anonyme, carte_deserte):
        assert client_anonyme.post("/partie/nouvelle", json={"contre_ia": True}).status_code == 401

    def test_sans_place_c_est_refuse(self, client_sans_place, carte_deserte):
        reponse = client_sans_place.post("/partie/nouvelle", json={"contre_ia": True})
        assert reponse.status_code == 403

    def test_un_camp_tenu_par_un_humain_n_est_pas_donne(self, client_alliance, carte_deserte):
        app.PLACES.asseoir("tenebres", GRISHNAK["discord_id"])
        reponse = client_alliance.post("/partie/nouvelle", json={"contre_ia": True})
        assert reponse.status_code == 409
        assert reponse.json["message"] == "Ce camp est déjà tenu."
        # Refusé veut dire laissé tel quel : la mise en place n'a pas été refaite.
        assert len(app.PLATEAU) == 0
        assert app.PLACES.occupant("tenebres") == GRISHNAK["discord_id"]

    def test_la_partie_est_creee_et_l_ia_assise(self, client_alliance, carte_deserte):
        reponse = client_alliance.post("/partie/nouvelle", json={"contre_ia": True})
        assert reponse.status_code == 200
        assert app.PLACES.occupant("tenebres") == ia.JOUEUR_IA
        assert reponse.json["places"]["tenebres"] == ia.NOM_IA
        # L'Alliance — le joueur humain — ouvre le scénario : l'IA n'a rien joué.
        assert reponse.json["phase"]["camp"] == "alliance"
        assert app.PLATEAU.en_dict() == app.SCENARIO.placement

    def test_l_ia_joue_immediatement_quand_elle_ouvre(self, client_tenebres, carte_deserte,
                                                      monkeypatch):
        monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
        reponse = client_tenebres.post("/partie/nouvelle", json={"contre_ia": True})
        assert reponse.status_code == 200
        assert app.PLACES.occupant("alliance") == ia.JOUEUR_IA
        # L'IA a joué son tour d'ouverture dans la foulée : la main est aux Ténèbres, et les
        # pions de la réponse sont ceux qu'elle a laissés, pas ceux de la mise en place.
        assert reponse.json["phase"]["camp"] == "tenebres"
        assert reponse.json["phase"]["type"] == "mouvement"
        assert app.PLATEAU.en_dict() != app.SCENARIO.placement

    def test_relancer_contre_l_ia_reste_permis(self, client_alliance, carte_deserte):
        client_alliance.post("/partie/nouvelle", json={"contre_ia": True})
        reponse = client_alliance.post("/partie/nouvelle", json={"contre_ia": True})
        assert reponse.status_code == 200
        assert app.PLACES.occupant("tenebres") == ia.JOUEUR_IA

    def test_sans_le_drapeau_rien_ne_change(self, client, carte_deserte):
        reponse = client.post("/partie/nouvelle")
        assert reponse.status_code == 200
        assert ia.JOUEUR_IA not in (app.PLACES.occupant(camp) for camp in app.SCENARIO.camps)


class TestDeclenchementDeLIA:
    @pytest.fixture
    def face_a_face(self, carte_deserte):
        """Un elfe du joueur humain et un orque de l'IA à deux cases l'un de l'autre."""
        a = plaine_bien_entouree()
        *_, large = couronne_de(a)
        app.PLATEAU.poser(a, CATALOGUE[ELFE])
        app.PLATEAU.poser(large, CATALOGUE[ORQUE])
        app.PLACES.asseoir("tenebres", ia.JOUEUR_IA)
        return a, large

    def test_l_ia_ne_joue_pas_tant_que_la_main_est_humaine(self, client_alliance, face_a_face):
        a, large = face_a_face
        # Fin du mouvement de l'Alliance : sa phase de combat commence, l'IA n'a rien à jouer.
        reponse = client_alliance.post("/phase/suivante")
        assert (reponse.json["camp"], reponse.json["type"]) == ("alliance", "combat")
        assert app.PLATEAU.pion_sur(large).cle == ORQUE

    def test_l_ia_joue_son_tour_quand_la_main_lui_vient(self, client_alliance, face_a_face,
                                                        monkeypatch):
        monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
        a, large = face_a_face
        client_alliance.post("/phase/suivante")
        version_avant = app.VERSION
        # Fin du combat de l'Alliance : la main passe aux Ténèbres, donc à l'IA, qui joue son
        # tour entier — l'orque marche au contact et engage l'elfe (8 contre 7 : 1-1, dé 1, un
        # recul sans effet) — puis rend la main.
        reponse = client_alliance.post("/phase/suivante")
        assert (reponse.json["camp"], reponse.json["type"]) == ("alliance", "mouvement")
        assert reponse.json["numero"] == 2
        assert app.PLATEAU.pion_sur(large) is None
        assert any(voisin for voisin in a.voisins()
                   if (pose := app.PLATEAU.pion_sur(voisin)) and pose.cle == ORQUE)
        assert app.PLATEAU.pion_sur(a).cle == ELFE
        assert app.VERSION > version_avant

    def test_le_camp_de_l_ia_ne_se_prend_pas(self, application, client_alliance, face_a_face,
                                             installer_le_joueur):
        second = application.test_client()
        installer_le_joueur(application, second, identite=GRISHNAK, camps=[])
        reponse = second.post("/partie/place", json={"camp": "tenebres"})
        assert reponse.status_code == 409
        assert reponse.json["message"] == "Ce camp est déjà tenu."


class TestLaTableAvecLIA:
    def test_la_place_de_l_ia_est_montree_occupee(self, client_alliance, carte_deserte):
        client_alliance.post("/partie/nouvelle", json={"contre_ia": True})
        table = client_alliance.get("/partie/etat").json["table"]
        assert table["places"]["tenebres"] == ia.NOM_IA
