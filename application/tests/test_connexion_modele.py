"""Le modèle de connexion : ce que la session porte, et le joueur du moteur qu'elle désigne.

Ces tests portent sur la classe seule, sans requête ni route — comme `moteur/tests/test_places.py`
le fait du registre des places. `Connexion` ne demande qu'une session (n'importe quel mapping qui
accepte aussi l'attribut `permanent` : la vraie session de Flask en est un) et un dépôt de
joueurs ; on lui donne ici le dépôt en mémoire du moteur, qui est le vrai dépôt des tests.

Ce qui est vérifié tient en trois points, et ce sont les trois raisons d'être de la classe :
la session ne porte **que** l'identifiant, le joueur est **relu** au dépôt à chaque demande, et
l'état de l'OAuth2 est **retiré** de la session dès qu'on le reprend.
"""

import pytest

from client_discord import IDENTITE_PAR_DEFAUT
from models.connexion import CLE_DE_L_ETAT_OAUTH, CLE_DU_JOUEUR, Connexion
from moteur.depots.joueur import DepotDeJoueursEnMemoire


class SessionFactice(dict):
    """Un mapping qui accepte `permanent`, comme la session de Flask."""

    permanent = False


@pytest.fixture
def joueurs():
    return DepotDeJoueursEnMemoire()


@pytest.fixture
def session():
    return SessionFactice()


@pytest.fixture
def connexion(session, joueurs):
    return Connexion(session, joueurs)


class TestOuvrir:

    def test_ouvrir_enregistre_le_joueur_et_rend_son_dict(self, connexion, joueurs):
        joueur = connexion.ouvrir(IDENTITE_PAR_DEFAUT)
        assert joueur["pseudo"] == IDENTITE_PAR_DEFAUT["pseudo"]
        assert joueurs.par_discord_id(IDENTITE_PAR_DEFAUT["discord_id"]) == joueur

    def test_la_session_ne_porte_que_l_identifiant(self, connexion, session):
        """Ni pseudo, ni avatar, ni jeton : le cookie de Flask est signé, pas chiffré."""
        connexion.ouvrir(IDENTITE_PAR_DEFAUT)
        assert dict(session) == {CLE_DU_JOUEUR: IDENTITE_PAR_DEFAUT["discord_id"]}

    def test_ouvrir_repart_d_une_session_neuve(self, connexion, session):
        """Rien de ce qu'un anonyme y aurait laissé ne survit à l'ouverture d'un compte."""
        session["trace-d-anonyme"] = "à jeter"
        connexion.ouvrir(IDENTITE_PAR_DEFAUT)
        assert "trace-d-anonyme" not in session

    def test_ouvrir_rend_la_session_permanente(self, connexion, session):
        connexion.ouvrir(IDENTITE_PAR_DEFAUT)
        assert session.permanent is True


class TestLeJoueurDesigne:

    def test_une_session_vide_ne_designe_personne(self, connexion):
        assert connexion.identifiant is None
        assert connexion.joueur() is None

    def test_le_joueur_est_relu_au_depot_a_chaque_demande(self, connexion, joueurs):
        """Le pseudo n'est pas recopié dans la session : un changement se voit dès la suite."""
        connexion.ouvrir(IDENTITE_PAR_DEFAUT)
        joueurs.enregistrer(IDENTITE_PAR_DEFAUT | {"pseudo": "Rebaptisée"})
        assert connexion.joueur()["pseudo"] == "Rebaptisée"

    def test_un_identifiant_inconnu_redevient_anonyme(self, session, joueurs):
        """Base vidée, dépôt de mémoire d'un serveur relancé : le visiteur redevient anonyme."""
        session[CLE_DU_JOUEUR] = "100000000000000009"
        connexion = Connexion(session, joueurs)
        assert connexion.identifiant == "100000000000000009"
        assert connexion.joueur() is None

    def test_fermer_ne_laisse_rien_dans_la_session(self, connexion, session):
        connexion.ouvrir(IDENTITE_PAR_DEFAUT)
        connexion.fermer()
        assert dict(session) == {}
        assert connexion.joueur() is None


class TestEtatOAuth:

    def test_poser_range_l_etat_dans_la_session_et_le_rend(self, connexion, session):
        etat = connexion.poser_un_etat_oauth()
        assert session[CLE_DE_L_ETAT_OAUTH] == etat
        assert len(etat) >= 32

    def test_deux_etats_ne_se_ressemblent_pas(self, connexion):
        assert connexion.poser_un_etat_oauth() != connexion.poser_un_etat_oauth()

    def test_reprendre_retire_l_etat_de_la_session(self, connexion, session):
        """Un retour rejoué ne trouve plus rien à quoi se comparer."""
        etat = connexion.poser_un_etat_oauth()
        assert connexion.reprendre_l_etat_oauth() == etat
        assert CLE_DE_L_ETAT_OAUTH not in session
        assert connexion.reprendre_l_etat_oauth() is None

    def test_reprendre_sans_etat_rend_none(self, connexion):
        assert connexion.reprendre_l_etat_oauth() is None
