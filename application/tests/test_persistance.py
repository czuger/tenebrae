"""La partie sauvegardée : ce que MongoDB retient, et ce que « / » en reprend.

Ces tests tournent sur mongomock — un MongoDB en mémoire —, aucun serveur n'est demandé. Ils sont
les seuls du dépôt à brancher la persistance : partout ailleurs la configuration de test pose le
dépôt nul, et l'application se comporte comme avant.
"""

import os

import pytest

mongomock = pytest.importorskip("mongomock")

import mongoengine  # noqa: E402

import app  # noqa: E402
from config import ConfigDeTest  # noqa: E402
from moteur.hexagone import Hex  # noqa: E402
from moteur.pion import CATALOGUE  # noqa: E402
from moteur.phase import COMBAT, MOUVEMENT  # noqa: E402

# Les mêmes cases et les mêmes cartons que test_serveur.py : deux voisines de plaine, un nain de
# force 12 et un orque de force 8 — de quoi livrer un combat sans rien laisser au hasard.
PLAINE = {"q": 1, "r": 26, "s": -27}
VOISINE = {"q": 2, "r": 26, "s": -28}
NAIN = "nains-01-5-infanteries"
ORQUE = "orques-01-15-infanteries"


class ConfigMongomock(ConfigDeTest):
    """La configuration de test, mais avec la persistance branchée sur un Mongo en mémoire.

    Le schéma d'URI « mongomock:// » n'est plus reconnu par mongoengine : on lui passe la classe
    de client, ce qui est la voie supportée.
    """

    PERSISTANCE = "mongo"
    MONGODB_SETTINGS = {"db": "tenebrae_test", "mongo_client_class": mongomock.MongoClient}


@pytest.fixture
def application_mongo():
    """Une application dont le dépôt écrit dans mongomock, et qui ne laisse rien derrière elle.

    Mongoengine tient un registre global de connexions : il faut déconnecter en sortant, sans
    quoi les autres fichiers de tests hériteraient de celle-ci. Les module-globaux de `app` sont
    partagés par toute la session, on les remet à zéro de la même façon.
    """
    application = app.create_app(ConfigMongomock)
    from modeles import Partie
    Partie.objects.delete()
    yield application
    Partie.objects.delete()
    mongoengine.disconnect_all()
    app.PLATEAU.vider()
    app.TOUR.recommencer()
    app.SUIVI.reinitialiser()


@pytest.fixture
def client_mongo(application_mongo):
    return application_mongo.test_client()


@pytest.fixture
def parties():
    """Le modèle, importé une fois la connexion ouverte."""
    from modeles import Partie
    return Partie


def poser(hexagone, cle):
    app.PLATEAU.poser(Hex(**hexagone), CATALOGUE[cle])


class TestOuvertureDeLaPartie:
    def test_le_premier_chargement_ecrit_la_mise_en_place(self, client_mongo, parties):
        client_mongo.get("/")
        assert parties.objects.count() == 1
        partie = parties.objects.first()
        assert partie.scenario == app.NUMERO_DU_SCENARIO
        assert dict(partie.placement) == app.SCENARIO.placement
        assert (partie.camp_actif, partie.type_de_phase) == (app.TOUR.camp_actif, MOUVEMENT)
        assert partie.numero_de_tour == 1
        assert partie.attaquants_engages == [] and partie.cibles_engagees == []
        assert partie.creee_le is not None and partie.modifiee_le is not None

    def test_recharger_ne_cree_pas_une_seconde_partie(self, client_mongo, parties):
        client_mongo.get("/")
        client_mongo.get("/")
        assert parties.objects.count() == 1


class TestRepriseDeLaPartie:
    def test_un_deplacement_est_repris_apres_un_redemarrage(self, client_mongo, parties):
        """Le cœur de la persistance : le pion se retrouve à son arrivée, pas à son départ."""
        client_mongo.get("/")
        depart = Hex.depuis_cle(next(iter(app.SCENARIO.placement)))
        arrivee = app.PLATEAU.deplacements(depart)[0]
        reponse = client_mongo.post("/deplacer", json={
            "depart": depart.en_dict(), "arrivee": arrivee.en_dict(),
            "pion": app.PLATEAU.pion_sur(depart).cle})
        assert reponse.json["autorise"] is True

        # Le serveur redémarre : la mémoire est vide, seule la base sait où en était la partie.
        app.PLATEAU.vider()
        app.TOUR.recommencer()
        client_mongo.get("/")

        assert app.PLATEAU.pion_sur(depart) is None
        assert app.PLATEAU.pion_sur(arrivee) is not None
        assert dict(parties.objects.first().placement)[arrivee.cle] is not None

    def test_un_deplacement_refuse_ne_touche_pas_la_sauvegarde(self, client_mongo, parties):
        client_mongo.get("/")
        avant = dict(parties.objects.first().placement)
        depart = Hex.depuis_cle(next(iter(app.SCENARIO.placement)))
        # Une case à l'autre bout de la carte : hors de portée, le déplacement est refusé.
        lointaine = {"q": 30, "r": 2, "s": -32}
        reponse = client_mongo.post("/deplacer", json={
            "depart": depart.en_dict(), "arrivee": lointaine,
            "pion": app.PLATEAU.pion_sur(depart).cle})
        assert reponse.json["autorise"] is False
        assert dict(parties.objects.first().placement) == avant

    def test_la_phase_est_reprise(self, client_mongo, parties):
        client_mongo.get("/")
        client_mongo.post("/phase/suivante")
        assert parties.objects.first().type_de_phase == COMBAT

        app.TOUR.recommencer()
        client_mongo.get("/")
        assert app.TOUR.type_de_phase == COMBAT

    def test_la_sauvegarde_d_un_autre_scenario_est_ecartee(self, client_mongo, parties):
        """Changer de scénario ne fait pas reprendre une partie qui ne s'y rapporte plus."""
        client_mongo.get("/")
        parties.objects.update(set__scenario=99)
        client_mongo.get("/")
        assert parties.objects.count() == 2
        assert parties.objects.first().scenario == app.NUMERO_DU_SCENARIO


class TestCombatPersiste:
    def test_une_unite_eliminee_ne_revient_pas(self, client_mongo, parties, monkeypatch):
        monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
        client_mongo.get("/")
        app.PLATEAU.vider()
        poser(PLAINE, NAIN)      # force 12
        poser(VOISINE, ORQUE)    # force 8
        client_mongo.post("/phase/suivante")  # phase de combat de l'Alliance
        # Un rapport de 6 contre 1 : la cible est éliminée à coup sûr.
        app.PLATEAU.retirer(Hex(**VOISINE))
        poser(VOISINE, "yzent-03-8-archers")  # force 2
        reponse = client_mongo.post("/combat",
                                    json={"cible": VOISINE, "attaquants": [PLAINE]}).json
        assert reponse["resolu"] is True

        sauvegarde = dict(parties.objects.first().placement)
        assert Hex(**VOISINE).cle not in sauvegarde
        assert sauvegarde[Hex(**PLAINE).cle] == NAIN

    def test_le_registre_de_la_phase_est_sauvegarde_et_repris(self, client_mongo, parties,
                                                              monkeypatch):
        monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
        client_mongo.get("/")
        app.PLATEAU.vider()
        poser(PLAINE, NAIN)
        poser(VOISINE, ORQUE)   # rapport 1-1, dé 1 → un recul : personne n'est éliminé
        client_mongo.post("/phase/suivante")
        assert client_mongo.post("/combat",
                                 json={"cible": VOISINE, "attaquants": [PLAINE]}).json["resolu"]

        partie = parties.objects.first()
        assert partie.attaquants_engages == [Hex(**PLAINE).cle]
        assert partie.cibles_engagees == [Hex(**VOISINE).cle]

        app.SUIVI.reinitialiser()
        client_mongo.get("/")
        assert not app.SUIVI.peut_attaquer(Hex(**PLAINE).cle)
        assert not app.SUIVI.peut_etre_cible(Hex(**VOISINE).cle)

    def test_changer_de_phase_vide_le_registre_en_base(self, client_mongo, parties, monkeypatch):
        monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
        client_mongo.get("/")
        app.PLATEAU.vider()
        poser(PLAINE, NAIN)
        poser(VOISINE, ORQUE)
        client_mongo.post("/phase/suivante")
        client_mongo.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]})
        client_mongo.post("/phase/suivante")
        partie = parties.objects.first()
        assert partie.attaquants_engages == [] and partie.cibles_engagees == []


class TestNouvellePartie:
    def test_elle_repose_le_scenario_et_ouvre_un_second_document(self, client_mongo, parties):
        client_mongo.get("/")
        depart = Hex.depuis_cle(next(iter(app.SCENARIO.placement)))
        arrivee = app.PLATEAU.deplacements(depart)[0]
        client_mongo.post("/deplacer", json={
            "depart": depart.en_dict(), "arrivee": arrivee.en_dict(),
            "pion": app.PLATEAU.pion_sur(depart).cle})

        reponse = client_mongo.post("/partie/nouvelle").json
        assert len(reponse["pions"]) == len(app.SCENARIO)
        assert reponse["phase"]["type"] == MOUVEMENT
        assert parties.objects.count() == 2
        # La plus récente est celle qu'on vient d'ouvrir, et « / » reprend celle-là.
        assert dict(parties.objects.first().placement) == app.SCENARIO.placement
        client_mongo.get("/")
        assert app.PLATEAU.pion_sur(depart) is not None

    def test_deux_parties_de_la_meme_seconde_restent_dans_l_ordre(self, client_mongo, parties):
        """La date seule ne suffit pas à départager : deux écritures peuvent la partager.

        Sans l'identifiant en second critère, « recommencer » puis recharger pouvait reprendre la
        partie qu'on venait d'abandonner.
        """
        client_mongo.get("/")
        depart = Hex.depuis_cle(next(iter(app.SCENARIO.placement)))
        arrivee = app.PLATEAU.deplacements(depart)[0]
        client_mongo.post("/deplacer", json={
            "depart": depart.en_dict(), "arrivee": arrivee.en_dict(),
            "pion": app.PLATEAU.pion_sur(depart).cle})
        client_mongo.post("/partie/nouvelle")

        # Les deux parties sont datées à la même seconde, comme si tout s'était joué d'un trait.
        instant = parties.objects.first().modifiee_le
        parties.objects.update(set__modifiee_le=instant)

        assert parties.objects.count() == 2
        assert dict(parties.objects.first().placement) == app.SCENARIO.placement


class TestDepot:
    """L'aller-retour du dépôt seul, sans passer par une route."""

    def test_photographier_puis_restaurer_retombe_sur_la_meme_partie(self, application_mongo):
        with application_mongo.test_request_context():
            app.PLATEAU.vider()
            poser(PLAINE, NAIN)
            app.TOUR.restaurer(app.TOUR.camp_actif, COMBAT, 3)
            app.SUIVI.enregistrer([Hex(**PLAINE).cle], Hex(**VOISINE).cle)
            etat = app.photographier_la_partie()

            app.PLATEAU.vider()
            app.TOUR.recommencer()
            app.SUIVI.reinitialiser()
            app.restaurer_la_partie(etat)

            assert app.photographier_la_partie() == etat

    def test_sauvegarder_puis_charger_rend_le_meme_etat(self, application_mongo):
        with application_mongo.test_request_context():
            app.PLATEAU.vider()
            poser(PLAINE, NAIN)
            etat = app.photographier_la_partie()
            app.le_depot().sauvegarder(etat)
            assert app.le_depot().charger() == etat

    def test_charger_ne_trouve_rien_dans_une_base_vide(self, application_mongo):
        with application_mongo.test_request_context():
            assert app.le_depot().charger() is None


# --- Contre un vrai MongoDB ---------------------------------------------------------------------
#
# Mongomock imite l'API, pas le stockage : il n'éprouve ni l'encodage BSON des clés du placement —
# « 1,26,-27 », virgules et signe moins, là où Mongo refuse le point et le dollar en tête — ni
# l'aller-retour des dates. Ces tests-ci le font, quand une base est joignable ; sinon ils se
# sautent, et la suite continue de tourner sans serveur.
#
#     docker run -d --name tenebrae-mongo -p 27017:27017 mongo:7
#
# `MONGODB_URI_TEST` permet d'en viser une autre — un port distinct de celui du jeu, par exemple.

URI_DE_TEST = os.environ.get("MONGODB_URI_TEST", "mongodb://localhost:27017/tenebrae_test")


def mongodb_est_joignable():
    """Dit si un vrai MongoDB répond à `URI_DE_TEST`, sans attendre plus d'une seconde."""
    import pymongo
    try:
        client = pymongo.MongoClient(URI_DE_TEST, serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


class ConfigMongoReel(ConfigDeTest):
    PERSISTANCE = "mongo"
    MONGODB_SETTINGS = {"host": URI_DE_TEST}


@pytest.fixture
def client_mongo_reel():
    """Une application branchée sur un vrai MongoDB, et une base laissée propre en sortant."""
    if not mongodb_est_joignable():
        pytest.skip(f"aucun MongoDB joignable sur {URI_DE_TEST}")
    application = app.create_app(ConfigMongoReel)
    from modeles import Partie
    Partie.objects.delete()
    yield application.test_client()
    Partie.objects.delete()
    mongoengine.disconnect_all()
    app.PLATEAU.vider()
    app.TOUR.recommencer()
    app.SUIVI.reinitialiser()


class TestContreUnVraiMongo:
    def test_les_cases_passent_telles_quelles_en_base(self, client_mongo_reel):
        """Les clés du placement sont des clés de document Mongo : elles doivent y être admises."""
        client_mongo_reel.get("/")
        from modeles import Partie
        placement = dict(Partie.objects.first().placement)
        assert placement == app.SCENARIO.placement
        assert all("," in case for case in placement)
        assert any(case.count("-") for case in placement)

    def test_la_partie_est_reprise_apres_un_redemarrage(self, client_mongo_reel):
        client_mongo_reel.get("/")
        depart = Hex.depuis_cle(next(iter(app.SCENARIO.placement)))
        arrivee = app.PLATEAU.deplacements(depart)[0]
        client_mongo_reel.post("/deplacer", json={
            "depart": depart.en_dict(), "arrivee": arrivee.en_dict(),
            "pion": app.PLATEAU.pion_sur(depart).cle})
        client_mongo_reel.post("/phase/suivante")

        # Le serveur redémarre : seule la base sait où en était la partie.
        app.PLATEAU.vider()
        app.TOUR.recommencer()
        client_mongo_reel.get("/")

        assert app.PLATEAU.pion_sur(depart) is None
        assert app.PLATEAU.pion_sur(arrivee) is not None
        assert app.TOUR.type_de_phase == COMBAT

    def test_les_dates_reviennent_lisibles(self, client_mongo_reel):
        client_mongo_reel.get("/")
        from modeles import Partie
        partie = Partie.objects.first()
        assert partie.creee_le is not None
        assert partie.modifiee_le >= partie.creee_le
