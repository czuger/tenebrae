"""Se connecter par Discord, prendre place, et ce que le serveur refuse au reste du monde.

Aucun de ces tests ne sort de la machine : la configuration de test branche le client Discord
factice, dont l'URL d'autorisation renvoie vers **notre propre route de retour**. Le flux se
déroule donc pour de bon — l'état contre le CSRF, l'échange du code, la lecture de l'identité —
sans qu'aucun paquet ne parte vers discord.com.
"""

from urllib.parse import parse_qs, urlparse

import pytest

import app
from client_discord import IDENTITE_PAR_DEFAUT, ErreurDiscord
from config import ConfigDeTest

# Un second compte, pour asseoir quelqu'un en face. Son identifiant n'est pas dans
# `ConfigDeTest.ADMINISTRATEURS` : c'est le joueur ordinaire des tests d'administration.
AUTRE_JOUEUR = {"discord_id": "100000000000000002", "pseudo": "Grishnak",
                "nom_affiche": None, "avatar": None, "courriel": None}

ALLIANCE, TENEBRES = "alliance", "tenebres"

# Une case du scénario et l'un de ses voisins : de quoi former une demande de déplacement bien
# formée, que seul le refus d'autorisation doit arrêter.
PLAINE = {"q": 1, "r": 26, "s": -27}
VOISINE = {"q": 2, "r": 26, "s": -28}


@pytest.fixture(autouse=True)
def table_vide(carte_deserte, application):
    """Chaque test part d'une table levée, d'un plateau désert et d'un client factice remis à neuf.

    Le client Discord factice est porté par l'application, de portée session : un test qui lui
    fait servir un autre compte le laisserait à tout le monde.
    """
    app.PLACES.vider()
    application.extensions["discord"].identite_servie = dict(IDENTITE_PAR_DEFAUT)
    yield
    app.PLACES.vider()
    application.extensions["discord"].identite_servie = dict(IDENTITE_PAR_DEFAUT)


def se_connecter(client):
    """Déroule le flux entier, comme le ferait un navigateur : /connexion puis le retour."""
    depart = client.get("/connexion")
    return client.get(depart.headers["Location"])


def etat_de(reponse):
    """L'état que la redirection emporte dans son URL."""
    return parse_qs(urlparse(reponse.headers["Location"]).query)["state"][0]


# --- Le flux OAuth2 ------------------------------------------------------------------------------


def test_la_connexion_redirige_avec_un_etat(client_anonyme):
    reponse = client_anonyme.get("/connexion")
    assert reponse.status_code == 302
    assert etat_de(reponse)


def test_deux_connexions_ne_tirent_pas_le_meme_etat(client_anonyme):
    premier = etat_de(client_anonyme.get("/connexion"))
    second = etat_de(client_anonyme.get("/connexion"))
    assert premier != second


def test_le_retour_ouvre_la_session_et_enregistre_le_joueur(client_anonyme, application):
    reponse = se_connecter(client_anonyme)
    assert reponse.status_code == 302
    with client_anonyme.session_transaction() as session:
        assert session["joueur"] == IDENTITE_PAR_DEFAUT["discord_id"]
    joueur = application.extensions["depot_de_joueurs"].par_discord_id(
        IDENTITE_PAR_DEFAUT["discord_id"])
    assert joueur["pseudo"] == IDENTITE_PAR_DEFAUT["pseudo"]


def test_une_seconde_connexion_met_a_jour_le_pseudo(client_anonyme, application):
    se_connecter(client_anonyme)
    application.extensions["discord"].identite_servie |= {"pseudo": "Joueuse d'essai, deuxième"}
    se_connecter(client_anonyme)
    joueur = application.extensions["depot_de_joueurs"].par_discord_id(
        IDENTITE_PAR_DEFAUT["discord_id"])
    assert joueur["pseudo"] == "Joueuse d'essai, deuxième"


def test_un_retour_sans_etat_est_refuse(client_anonyme):
    assert client_anonyme.get("/connexion/retour?code=x").status_code == 400


def test_un_etat_qui_ne_correspond_pas_est_refuse(client_anonyme):
    client_anonyme.get("/connexion")
    reponse = client_anonyme.get("/connexion/retour?code=x&state=un-etat-invente")
    assert reponse.status_code == 400
    with client_anonyme.session_transaction() as session:
        assert "joueur" not in session


def test_l_etat_ne_sert_qu_une_fois(client_anonyme):
    """Rejouer le retour ne doit plus rien trouver à quoi comparer l'état."""
    depart = client_anonyme.get("/connexion")
    retour = depart.headers["Location"]
    assert client_anonyme.get(retour).status_code == 302
    assert client_anonyme.get(retour).status_code == 400


def test_un_retour_sans_code_est_refuse(client_anonyme):
    depart = client_anonyme.get("/connexion")
    reponse = client_anonyme.get(f"/connexion/retour?state={etat_de(depart)}")
    assert reponse.status_code == 400


def test_un_refus_sur_la_page_de_discord_ramene_a_la_carte(client_anonyme):
    """« Cancel » chez Discord : on revient au plateau, sans session et sans erreur."""
    client_anonyme.get("/connexion")
    reponse = client_anonyme.get("/connexion/retour?error=access_denied")
    assert reponse.status_code == 302
    with client_anonyme.session_transaction() as session:
        assert "joueur" not in session


def test_un_discord_muet_rend_une_erreur_de_passerelle(client_anonyme, application, monkeypatch):
    def tomber(_code):
        raise ErreurDiscord("connexion impossible")

    monkeypatch.setattr(application.extensions["discord"], "echanger_le_code", tomber)
    depart = client_anonyme.get("/connexion")
    assert client_anonyme.get(depart.headers["Location"]).status_code == 502


def test_le_jeton_d_acces_ne_va_jamais_dans_la_session(client_anonyme):
    """Le cookie de session est signé, pas chiffré : rien de secret n'y a sa place.

    `_permanent` est de Flask, qui note ainsi la durée de vie demandée ; le reste doit se
    résumer à l'identifiant du joueur.
    """
    se_connecter(client_anonyme)
    with client_anonyme.session_transaction() as session:
        assert set(session) == {"joueur", "_permanent"}


def test_la_deconnexion_vide_la_session(client):
    assert client.post("/deconnexion").json == {"connecte": False}
    with client.session_transaction() as session:
        assert "joueur" not in session


def test_la_deconnexion_ne_rend_pas_la_place(client):
    """On revient s'y asseoir : quitter la table est un geste à part."""
    client.post("/deconnexion")
    assert app.PLACES.occupant(ALLIANCE) == IDENTITE_PAR_DEFAUT["discord_id"]


# --- Ce que voit un visiteur anonyme -------------------------------------------------------------


def test_un_visiteur_anonyme_voit_la_carte(client_anonyme):
    assert client_anonyme.get("/").status_code == 200


def test_un_visiteur_anonyme_consulte_les_deplacements(client_anonyme):
    reponse = client_anonyme.get("/deplacements", query_string=PLAINE)
    assert reponse.status_code == 200


def test_un_visiteur_anonyme_ne_deplace_rien(client_anonyme, carte_deserte):
    carte_deserte.poser(app.Hex(**PLAINE), app.CATALOGUE["nains-01-5-infanteries"])
    reponse = client_anonyme.post("/deplacer", json={
        "depart": PLAINE, "arrivee": VOISINE, "pion": "nains-01-5-infanteries"})
    assert reponse.status_code == 401
    assert carte_deserte.pion_sur(app.Hex(**PLAINE)) is not None


def test_un_visiteur_anonyme_ne_change_pas_la_phase(client_anonyme):
    assert client_anonyme.post("/phase/suivante").status_code == 401


def test_un_visiteur_anonyme_ne_recommence_pas_la_partie(client_anonyme):
    assert client_anonyme.post("/partie/nouvelle").status_code == 401


# --- Chacun son camp -----------------------------------------------------------------------------


def test_on_ne_joue_pas_le_camp_qu_on_ne_tient_pas(application, installer_le_joueur,
                                                   carte_deserte):
    """Le joueur des Ténèbres ne bouge rien pendant la phase de l'Alliance."""
    client = application.test_client()
    installer_le_joueur(application, client, identite=AUTRE_JOUEUR, camps=[TENEBRES])
    carte_deserte.poser(app.Hex(**PLAINE), app.CATALOGUE["nains-01-5-infanteries"])

    reponse = client.post("/deplacer", json={
        "depart": PLAINE, "arrivee": VOISINE, "pion": "nains-01-5-infanteries"})

    assert reponse.status_code == 403
    assert "de jouer" in reponse.json["message"]
    assert carte_deserte.pion_sur(app.Hex(**PLAINE)) is not None


def test_un_connecte_sans_place_ne_joue_pas(application, installer_le_joueur):
    client = application.test_client()
    installer_le_joueur(application, client, camps=[])
    assert client.post("/phase/suivante").status_code == 403


def test_le_camp_actif_joue(client):
    """Le pendant du test précédent : assis au bon camp, la route passe."""
    assert client.post("/phase/suivante").status_code == 200


# --- Prendre place -------------------------------------------------------------------------------


@pytest.fixture
def client_sans_place(application, installer_le_joueur):
    """Un joueur connecté, mais debout : personne ne tient encore rien."""
    client = application.test_client()
    installer_le_joueur(application, client, camps=[])
    return client


def test_s_asseoir_prend_le_camp(client_sans_place):
    reponse = client_sans_place.post("/partie/place", json={"camp": ALLIANCE})
    assert reponse.status_code == 200
    assert reponse.json["assis"] is True
    assert reponse.json["camps"] == [ALLIANCE]
    assert app.PLACES.occupant(ALLIANCE) == IDENTITE_PAR_DEFAUT["discord_id"]


def test_la_table_dit_qui_tient_quoi_par_son_pseudo(client_sans_place):
    """Le navigateur reçoit des pseudos, jamais des identifiants Discord."""
    reponse = client_sans_place.post("/partie/place", json={"camp": ALLIANCE})
    assert reponse.json["places"] == {ALLIANCE: IDENTITE_PAR_DEFAUT["pseudo"], TENEBRES: None}
    assert IDENTITE_PAR_DEFAUT["discord_id"] not in reponse.get_data(as_text=True)


def test_un_camp_inconnu_du_scenario_est_refuse(client_sans_place):
    assert client_sans_place.post("/partie/place", json={"camp": "dragons"}).status_code == 400


def test_le_second_camp_est_refuse_a_qui_en_tient_deja_un(client_sans_place):
    client_sans_place.post("/partie/place", json={"camp": ALLIANCE})
    reponse = client_sans_place.post("/partie/place", json={"camp": TENEBRES})
    assert reponse.status_code == 409
    assert app.PLACES.est_libre(TENEBRES)


def test_se_rasseoir_a_sa_propre_place_ne_fait_pas_d_histoire(client_sans_place):
    client_sans_place.post("/partie/place", json={"camp": ALLIANCE})
    assert client_sans_place.post("/partie/place", json={"camp": ALLIANCE}).status_code == 200


def test_une_place_occupee_ne_se_reprend_pas(application, installer_le_joueur, client_sans_place):
    autre = application.test_client()
    installer_le_joueur(application, autre, identite=AUTRE_JOUEUR, camps=[ALLIANCE])

    reponse = client_sans_place.post("/partie/place", json={"camp": ALLIANCE})

    assert reponse.status_code == 409
    assert app.PLACES.occupant(ALLIANCE) == AUTRE_JOUEUR["discord_id"]


def test_les_deux_camps_se_prennent_par_deux_joueurs(application, installer_le_joueur,
                                                     client_sans_place):
    autre = application.test_client()
    installer_le_joueur(application, autre, identite=AUTRE_JOUEUR, camps=[])
    client_sans_place.post("/partie/place", json={"camp": ALLIANCE})

    reponse = autre.post("/partie/place", json={"camp": TENEBRES})

    assert reponse.status_code == 200
    assert reponse.json["places"] == {ALLIANCE: IDENTITE_PAR_DEFAUT["pseudo"],
                                      TENEBRES: AUTRE_JOUEUR["pseudo"]}


def test_quitter_rend_la_place(client):
    reponse = client.post("/partie/place/quitter")
    assert reponse.json["assis"] is False
    assert app.PLACES.est_libre(ALLIANCE) and app.PLACES.est_libre(TENEBRES)


def test_un_anonyme_ne_prend_pas_place(client_anonyme):
    assert client_anonyme.post("/partie/place", json={"camp": ALLIANCE}).status_code == 401


def test_recommencer_garde_les_deux_joueurs_a_la_table(client):
    """Repartir de la mise en place ne renvoie personne : ce sont les mêmes deux personnes."""
    client.post("/partie/nouvelle")
    assert app.PLACES.camps_de(IDENTITE_PAR_DEFAUT["discord_id"]) == list(app.SCENARIO.camps)


# --- Corriger la carte ---------------------------------------------------------------------------


def test_la_correction_de_la_carte_demande_une_connexion(client_anonyme):
    assert client_anonyme.get("/admin/map_fix").status_code == 401
    assert client_anonyme.post("/admin/map_fix", json={}).status_code == 401


def test_la_correction_de_la_carte_est_refusee_a_un_joueur_ordinaire(application,
                                                                     installer_le_joueur):
    client = application.test_client()
    installer_le_joueur(application, client, identite=AUTRE_JOUEUR, camps=[TENEBRES])

    reponse = client.get("/admin/map_fix")

    assert reponse.status_code == 403
    assert "ADMIN_DISCORD_IDS" in reponse.json["message"]


def test_la_correction_de_la_carte_est_ouverte_a_un_administrateur(client):
    assert client.get("/admin/map_fix").status_code == 200


# --- La construction de l'application ------------------------------------------------------------
#
# La suite tourne sous `ConfigDeTest`, qui branche le client factice : rien n'éprouverait sinon le
# chemin que le serveur emprunte pour de vrai.


class ConfigDeJeu(ConfigDeTest):
    """La configuration de test, mais avec le vrai client Discord — celui qui parle au réseau.

    Aucun test ne l'appelle : on veut seulement s'assurer que ce chemin de `create_app` se
    construit, et que le fichier qui parle à Discord s'importe.
    """

    AUTHENTIFICATION = "discord"
    DISCORD_CLIENT_ID = "000"
    DISCORD_CLIENT_SECRET = "secret-de-pacotille"
    DISCORD_REDIRECT_URI = "http://127.0.0.1:5000/connexion/retour"


def test_la_configuration_de_jeu_branche_le_vrai_client_discord():
    from client_discord import ClientDiscord
    application = app.create_app(ConfigDeJeu)
    assert isinstance(application.extensions["discord"], ClientDiscord)


def test_le_vrai_client_envoie_bien_chez_discord():
    """L'URL d'autorisation, seule chose qu'on puisse vérifier sans appeler Discord."""
    application = app.create_app(ConfigDeJeu)
    with application.test_request_context():
        url = application.extensions["discord"].url_d_autorisation("un-etat")
    assert url.startswith("https://discord.com/oauth2/authorize?")
    assert "state=un-etat" in url and "scope=identify" in url
    assert "client_secret" not in url  # le secret ne part jamais dans une URL


def test_le_vrai_client_se_presente_a_discord(monkeypatch):
    """Chaque appel sortant porte un User-Agent : Cloudflare refoule d'un 403 celui d'`urllib`."""
    import client_discord

    requetes = []

    class ReponseFactice:
        def read(self):
            return b'{"access_token": "jeton"}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen_factice(requete, timeout=None):
        requetes.append(requete)
        return ReponseFactice()

    monkeypatch.setattr(client_discord, "urlopen", urlopen_factice)
    client = client_discord.ClientDiscord("000", "secret", "http://127.0.0.1:5000/retour")
    client.echanger_le_code("un-code")
    assert requetes and requetes[0].get_header("User-agent") == client_discord.AGENT


def test_sans_secret_key_l_application_refuse_de_demarrer():
    """Mieux vaut un échec au démarrage qu'une erreur au premier clic sur « se connecter »."""
    class SansClef(ConfigDeTest):
        SECRET_KEY = None

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        app.create_app(SansClef)
