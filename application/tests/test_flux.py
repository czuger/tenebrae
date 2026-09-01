"""Le flux SSE au niveau Flask : en-têtes, message d'ouverture, diffusion, radiation.

Ce que ce fichier éprouve est la couture entre le diffuseur (`test_diffuseur.py`, sans Flask) et
le navigateur (`test_flux_navigateur.py`, dans Chromium) : la route `/flux`, le format des
messages, et ce que chaque abonné reçoit — car la table, elle, se compose par destinataire.

Un flux ne se termine jamais de lui-même : chaque test le lit par `lire`, qui prend le nombre de
messages qu'il attend puis **ferme le générateur**. Sans cette fermeture, le fil de lecture
resterait bloqué et l'abonné resterait au registre — ce qui est justement l'une des choses à
vérifier ici.
"""

import json
import threading

import pytest

import app
from client_discord import IDENTITE_PAR_DEFAUT
from flux import Diffuseur

ALLIANCE, TENEBRES = "alliance", "tenebres"

# Un second joueur, pour éprouver que la table diffère d'un abonné à l'autre.
AUTRE_IDENTITE = {"discord_id": "100000000000000002", "pseudo": "Adversaire", "avatar": None}

# La marge laissée à un fil pour se réveiller sur une machine chargée.
PATIENCE = 5.0


@pytest.fixture(autouse=True)
def diffuseur_neuf(monkeypatch):
    """Un diffuseur à soi pour la durée du test, et vide en sortant.

    Le diffuseur est un module-global, comme le plateau et le tour. Or les tests de navigateur
    tournent avant ceux-ci et laissent des flux ouverts derrière eux : une page Chromium fermée
    ne se voit qu'au battement suivant, et son abonné fausserait tous les comptes de ce fichier.
    On lui en substitue donc un neuf — `marquer_un_coup` comme le générateur du flux le relisent
    au module à chaque appel, la substitution porte donc sur les deux.

    En sortant, la vérification qui compte : ce test n'a laissé aucun abonné derrière lui.
    """
    monkeypatch.setattr(app, "DIFFUSEUR", Diffuseur())
    yield
    assert len(app.DIFFUSEUR) == 0, "ce test a laissé un flux ouvert"


@pytest.fixture(autouse=True)
def battement_court(monkeypatch):
    """Vingt secondes de battement rendraient chaque test du keepalive interminable."""
    monkeypatch.setattr(app, "BATTEMENT", 0.05)


def ouvrir_le_flux(client, version=None, dernier_evenement=None):
    """Ouvre `/flux` et rend la réponse. Il reste à la lire, morceau par morceau.

    `buffered=False` est ce qui rend le flux lisible : sans lui, le client de test voudrait
    consommer la réponse jusqu'au bout, et un flux qui n'a pas de fin ne se consomme pas.
    """
    entetes = {} if dernier_evenement is None else {"Last-Event-ID": dernier_evenement}
    requete = "/flux" if version is None else f"/flux?version={version}"
    return client.get(requete, headers=entetes, buffered=False)


def lire(reponse, combien=1):
    """Les `combien` premiers morceaux du flux, puis on ferme.

    Chaque `yield` du générateur est un morceau : un message complet, ou un commentaire. Les
    lire un par un plutôt que d'attendre la fin est tout l'intérêt du streaming — et la seule
    façon de lire un flux qui n'a pas de fin.
    """
    morceaux = []
    iterateur = reponse.response
    try:
        for morceau in iterateur:
            morceaux.append(morceau.decode("utf-8"))
            if len(morceaux) >= combien:
                break
    finally:
        reponse.close()
    return morceaux


def donnees(message):
    """Le JSON porté par la ligne `data:` d'un message SSE."""
    for ligne in message.splitlines():
        if ligne.startswith("data: "):
            return json.loads(ligne[len("data: "):])
    raise AssertionError(f"pas de ligne « data » dans {message!r}")


def identifiant(message):
    """Le numéro d'événement porté par la ligne `id:`."""
    for ligne in message.splitlines():
        if ligne.startswith("id: "):
            return int(ligne[len("id: "):])
    raise AssertionError(f"pas de ligne « id » dans {message!r}")


# --- Ce que la réponse annonce ---


def test_le_flux_est_un_evenement_serveur(client):
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    try:
        assert reponse.status_code == 200
        assert reponse.mimetype == "text/event-stream"
    finally:
        reponse.close()


def test_les_entetes_interdisent_le_cache_et_le_tampon(client):
    """`X-Accel-Buffering` est là dès maintenant : sans lui, Nginx retiendrait chaque message
    jusqu'à remplir son tampon, et le jeu paraîtrait figé (voir `DEPLOIEMENT.md`)."""
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    try:
        assert reponse.headers["Cache-Control"] == "no-cache"
        assert reponse.headers["X-Accel-Buffering"] == "no"
    finally:
        reponse.close()


def test_le_flux_est_public(client_anonyme):
    """Un visiteur de passage suit la partie comme il voit la carte."""
    reponse = ouvrir_le_flux(client_anonyme, version=app.VERSION)
    try:
        assert reponse.status_code == 200
    finally:
        reponse.close()


# --- L'ouverture du flux ---


def test_un_navigateur_a_jour_ne_recoit_qu_un_commentaire(client):
    """Rien n'a bougé depuis qu'il a chargé la page : lui renvoyer les 52 pions serait pour rien.

    Un commentaire SSE — une ligne qui commence par « : » — ouvre tout de même la connexion, ce
    qui fait passer l'`EventSource` du navigateur à l'état « ouvert ».
    """
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    assert lire(reponse) == [": partie suivie\n\n"]


def test_un_navigateur_en_retard_recoit_toute_la_partie(client):
    """Il rouvre son onglet après une coupure : l'adversaire a pu jouer entre-temps."""
    client.get("/")  # le plateau est un module-global : on le garnit avant de compter ses pions
    reponse = ouvrir_le_flux(client, version=app.VERSION - 1)
    etat = donnees(lire(reponse)[0])

    assert etat["version"] == app.VERSION
    assert len(etat["pions"]) == len(app.SCENARIO)
    assert etat["phase"]["libelle"] == app.TOUR.libelle
    assert etat["table"]["connecte"] is True


def test_un_navigateur_sans_version_recoit_toute_la_partie(client):
    """Aucun `?version` et aucun `Last-Event-ID` : on ne sait pas ce qu'il connaît, on dit tout."""
    reponse = ouvrir_le_flux(client)
    assert donnees(lire(reponse)[0])["version"] == app.VERSION


def test_le_dernier_evenement_prime_sur_le_parametre(client):
    """L'URL date de l'ouverture de la page ; le `Last-Event-ID`, de la dernière reconnexion.

    Un `EventSource` ne peut pas poser d'en-tête à la première connexion — d'où `?version=` —,
    mais il renvoie le `Last-Event-ID` de lui-même à chaque reconnexion, et celui-là est plus
    récent. C'est donc lui qui décide.
    """
    reponse = ouvrir_le_flux(client, version=app.VERSION - 1,
                             dernier_evenement=str(app.VERSION))
    assert lire(reponse) == [": partie suivie\n\n"]


def test_un_dernier_evenement_illisible_fait_tout_renvoyer(client):
    """L'en-tête vient du navigateur : vide, ou n'importe quoi. On ne plante pas pour si peu."""
    reponse = ouvrir_le_flux(client, dernier_evenement="")
    assert donnees(lire(reponse)[0])["version"] == app.VERSION


def test_le_serveur_redemarre_est_rattrape(client, carte_deserte):
    """Le navigateur connaît la version 12, le serveur repart de zéro : les numéros ne collent
    plus, et c'est précisément ce qui doit lui faire tout reprendre."""
    reponse = ouvrir_le_flux(client, dernier_evenement="12")
    assert donnees(lire(reponse)[0])["version"] == app.VERSION


# --- Ce qui arrive quand un coup est joué ---


def test_un_coup_joue_est_pousse_au_flux(client):
    """Le cœur du sujet : personne ne redemande rien, le serveur écrit."""
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    iterateur = reponse.response
    try:
        assert next(iterateur).decode() == ": partie suivie\n\n"

        # L'abonnement n'existe qu'une fois le générateur entamé : le coup se joue après.
        assert client.post("/phase/suivante").status_code == 200

        message = next(iterateur).decode()
        etat = donnees(message)
        assert etat["phase"]["libelle"] == app.TOUR.libelle
        assert identifiant(message) == etat["version"] == app.VERSION
    finally:
        reponse.close()


def test_le_flux_bat_quand_rien_ne_se_passe(client):
    """Le keepalive : sans lui, un intermédiaire refermerait une connexion qu'il croit morte."""
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    assert lire(reponse, combien=3) == [": partie suivie\n\n", ": battement\n\n",
                                        ": battement\n\n"]


def test_un_deplacement_pousse_le_plateau(client, carte_deserte):
    """Ce n'est pas que la phase : tout coup joué passe par `marquer_un_coup`."""
    depart = app.Hex(0, 0, 0)
    pion = app.CATALOGUE[next(iter(app.SCENARIO.placement.values()))]
    carte_deserte.poser(depart, pion)
    arrivee = next(iter(carte_deserte.deplacements(depart, pion)))

    reponse = ouvrir_le_flux(client, version=app.VERSION)
    iterateur = reponse.response
    try:
        next(iterateur)
        assert client.post("/deplacer", json={
            "depart": depart.en_dict(), "arrivee": arrivee.en_dict(), "pion": pion.cle,
        }).json["autorise"] is True

        cases = {(p["q"], p["r"], p["s"]) for p in donnees(next(iterateur).decode())["pions"]}
        assert (arrivee.q, arrivee.r, arrivee.s) in cases
    finally:
        reponse.close()


def test_une_partie_neuve_pousse_le_scenario_pose_et_non_un_plateau_vide(client):
    """`poser_la_mise_en_place` vide le plateau avant de le remplir.

    Marquer le coup au milieu — ce que faisait le code avant le flux — poussait la photo d'un
    plateau désert, et le navigateur de l'adversaire effaçait tous ses pions.
    """
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    iterateur = reponse.response
    try:
        next(iterateur)
        assert client.post("/partie/nouvelle").status_code == 200
        assert len(donnees(next(iterateur).decode())["pions"]) == len(app.SCENARIO)
    finally:
        reponse.close()


# --- Plusieurs clients à la fois ---


def test_deux_flux_recoivent_le_meme_coup(client, client_anonyme):
    """Deux joueurs, deux navigateurs : un seul coup, et les deux le voient."""
    joueur = ouvrir_le_flux(client, version=app.VERSION)
    visiteur = ouvrir_le_flux(client_anonyme, version=app.VERSION)
    fil_joueur, fil_visiteur = joueur.response, visiteur.response
    try:
        next(fil_joueur)
        next(fil_visiteur)
        assert len(app.DIFFUSEUR) == 2

        assert client.post("/phase/suivante").status_code == 200

        for iterateur in (fil_joueur, fil_visiteur):
            assert donnees(next(iterateur).decode())["phase"]["libelle"] == app.TOUR.libelle
    finally:
        joueur.close()
        visiteur.close()


def test_chaque_flux_recoit_la_table_de_son_propre_joueur(application, client, client_anonyme):
    """La seule part du message qui n'est pas partagée.

    Le joueur assis reçoit ses camps ; le visiteur de passage reçoit une table anonyme — mais la
    **même partie**. C'est pour cela que la table se compose par destinataire et non une fois
    pour toutes.
    """
    joueur = ouvrir_le_flux(client, version=app.VERSION)
    visiteur = ouvrir_le_flux(client_anonyme, version=app.VERSION)
    fil_joueur, fil_visiteur = joueur.response, visiteur.response
    try:
        next(fil_joueur)
        next(fil_visiteur)
        assert client.post("/phase/suivante").status_code == 200

        du_joueur = donnees(next(fil_joueur).decode())["table"]
        du_visiteur = donnees(next(fil_visiteur).decode())["table"]

        assert du_joueur["connecte"] is True
        assert du_joueur["pseudo"] == IDENTITE_PAR_DEFAUT["pseudo"]
        assert du_joueur["camps"] == [ALLIANCE, TENEBRES]

        assert du_visiteur["connecte"] is False
        assert du_visiteur["pseudo"] is None
        assert du_visiteur["camps"] == []

        # Et pourtant la même partie : les places occupées se voient des deux côtés.
        assert du_joueur["places"] == du_visiteur["places"]
    finally:
        joueur.close()
        visiteur.close()


def test_le_joueur_est_relu_a_chaque_message(application, client):
    """Le flux ne met pas le joueur en cache : quitter sa place se voit au message suivant.

    C'est ce qui interdit `stream_with_context`, qui garderait `g.joueur` pour toute la durée de
    la connexion — c'est-à-dire tant que l'onglet reste ouvert.
    """
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    iterateur = reponse.response
    try:
        next(iterateur)
        assert client.post("/phase/suivante").status_code == 200
        assert donnees(next(iterateur).decode())["table"]["camps"] == [ALLIANCE, TENEBRES]

        assert client.post("/partie/place/quitter").status_code == 200
        assert donnees(next(iterateur).decode())["table"]["camps"] == []
    finally:
        reponse.close()


# --- Le nettoyage ---


def test_un_flux_ferme_libere_son_abonnement(client):
    """La fuite qu'on veut prendre : un onglet refermé qui laisse sa boîte derrière lui.

    Le serveur continuerait de lui déposer l'état de chaque coup joué, à jamais.
    """
    reponse = ouvrir_le_flux(client, version=app.VERSION)
    iterateur = reponse.response
    next(iterateur)
    assert len(app.DIFFUSEUR) == 1

    reponse.close()
    assert len(app.DIFFUSEUR) == 0


def test_dix_flux_ouverts_puis_refermes_ne_laissent_rien(client):
    """Un onglet qu'on ouvre et referme dix fois de suite ne doit rien accumuler."""
    for _ in range(10):
        reponse = ouvrir_le_flux(client, version=app.VERSION)
        next(reponse.response)
        reponse.close()
    assert len(app.DIFFUSEUR) == 0


def test_un_flux_lu_dans_un_autre_fil_recoit_aussi(client, application):
    """Le cas réel : le flux est servi par un fil, le coup joué par un autre.

    Le serveur de développement comme gunicorn servent chaque requête dans son propre fil ; ce
    test est le plus proche de ce qui se passe en vrai.
    """
    recu = []
    abonne = threading.Event()

    def ecouter():
        with application.test_client() as autre:
            reponse = ouvrir_le_flux(autre, version=app.VERSION)
            iterateur = reponse.response
            try:
                next(iterateur)
                abonne.set()
                recu.append(donnees(next(iterateur).decode()))
            finally:
                reponse.close()

    fil = threading.Thread(target=ecouter, daemon=True)
    fil.start()
    assert abonne.wait(PATIENCE), "le flux du second fil ne s'est pas ouvert"

    assert client.post("/phase/suivante").status_code == 200
    fil.join(PATIENCE)

    assert len(recu) == 1 and recu[0]["phase"]["libelle"] == app.TOUR.libelle
    assert len(app.DIFFUSEUR) == 0
