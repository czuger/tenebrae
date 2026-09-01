"""La résolution des combats : le rapport de force, les modificateurs de terrain, le Tableau I.

Comme pour le mouvement, les hexagones de terrain ne sont pas codés en dur : ils sont cherchés
sur la carte du jeu pour survivre à une correction.
"""

import pytest

from moteur import combat
from moteur.combat import AE, AR, DE, DR, EX
from moteur.hexagone import CARTE, Hex
from moteur.pion import pion
from moteur.plateau import Plateau
from moteur.tests.plaines import couronne_de, plaine_bien_entouree

NAIN = "nains-01-5-infanteries"            # alliance, force 12
ORQUE = "orques-01-15-infanteries"        # ténèbres, force 8
ARCHER = "yzent-03-8-archers"             # ténèbres, force 2, tir 4, portée 3
ELFE = "elfes-01-5-infanteries"           # alliance, force 7
ARBALETRIER = "nains-02-4-arbaletriers"   # alliance, force 6, tir 4, portée 2
ARBALETRIER_LOURD = "nains-03-4-arbaletriers-lourds"   # alliance, force 8, tir 5


def hexagone_de_terrain(terrain):
    """Un hexagone dont le terrain principal est `terrain`."""
    return next(Hex.depuis_cle(cle) for cle, elements in CARTE.items() if elements[0] == terrain)


@pytest.fixture
def coin():
    """Un centre de plaine nue, une case au contact, une case à deux cases."""
    a = plaine_bien_entouree()
    c, _, _, large = couronne_de(a)
    return a, c, large


class TestRapportDeForce:
    def test_l_exemple_du_fascicule(self):
        # « 10/4 vaut pour 2 contre 1 » : arrondi en faveur du défenseur.
        assert combat.COLONNES[combat.colonne_du_rapport(10, 4)] == (2, 1)

    def test_le_defenseur_l_emporte(self):
        assert combat.COLONNES[combat.colonne_du_rapport(4, 10)] == (1, 3)

    def test_les_forces_egales(self):
        assert combat.COLONNES[combat.colonne_du_rapport(8, 8)] == (1, 1)

    def test_les_bornes(self):
        assert combat.COLONNES[combat.colonne_du_rapport(100, 1)] == (6, 1)
        assert combat.COLONNES[combat.colonne_du_rapport(1, 100)] == (1, 5)


class TestModificateursDeTerrain:
    def test_la_plaine_ne_change_rien(self):
        plaine = plaine_bien_entouree()
        assert combat.multiplicateur_de_defense(plaine, pion(ORQUE)) == 1
        assert combat.bonus_de_terrain(plaine) == 0

    def test_le_fort_triple_la_defense(self):
        assert combat.multiplicateur_de_defense(hexagone_de_terrain("fort"), pion(ORQUE)) == 3

    def test_les_ruines_doublent_la_defense(self):
        assert combat.multiplicateur_de_defense(hexagone_de_terrain("ruines"), pion(ORQUE)) == 2

    def test_le_bois_ne_protege_que_les_elfes(self):
        bois = hexagone_de_terrain("bois")
        assert combat.multiplicateur_de_defense(bois, pion(ELFE)) == 2
        assert combat.multiplicateur_de_defense(bois, pion(ORQUE)) == 1

    def test_la_colline_donne_deux_au_de(self):
        assert combat.bonus_de_terrain(hexagone_de_terrain("colline")) == 2

    def test_le_bois_donne_deux_au_de(self):
        assert combat.bonus_de_terrain(hexagone_de_terrain("bois")) == 2


class TestPortee:
    def test_l_infanterie_engage_au_contact_seulement(self, coin):
        a, c, large = coin
        assert combat.a_portee(c, pion(NAIN), a)
        assert not combat.a_portee(large, pion(NAIN), a)

    def test_l_archer_engage_jusqu_a_sa_portee(self, coin):
        a, _, large = coin
        assert combat.a_portee(large, pion(ARCHER), a)          # deux cases
        tres_loin = next(Hex.depuis_cle(cle) for cle in CARTE
                         if Hex.depuis_cle(cle).distance(a) == 4)
        assert not combat.a_portee(tres_loin, pion(ARCHER), a)


class TestTireDesMissiles:
    """Qui tire, au sens du moteur : un carton qui porte une force de tir **et** une portée."""

    def test_l_archer_tire(self):
        assert combat.tire_des_missiles(pion(ARCHER))

    def test_l_infanterie_ne_tire_pas(self):
        assert not combat.tire_des_missiles(pion(NAIN))

    def test_une_case_vide_ne_tire_pas(self):
        """`livrer_combat` interroge le plateau, qui peut ne rien rendre : pas d'exception ici."""
        assert not combat.tire_des_missiles(None)

    def test_la_portee_de_combat_suit_le_meme_partage(self):
        assert combat.portee_de_combat(pion(ARCHER)) == pion(ARCHER).portee
        assert combat.portee_de_combat(pion(NAIN)) == 1


class TestLivrerCombat:
    @pytest.fixture
    def duo(self):
        """Une cible en plaine et une case au contact."""
        a = plaine_bien_entouree()
        c, *_ = couronne_de(a)
        return a, c

    def test_defenseur_elimine_vide_sa_case(self, duo):
        cible, attaquant = duo
        plateau = Plateau([(cible, pion(ARCHER)), (attaquant, pion(NAIN))])
        # NAIN 12 contre ARCHER 2 → 6-1 ; dé 1 → DE.
        resultat = combat.livrer_combat(plateau, cible, [attaquant], jet=1)
        assert resultat.resultat == DE
        assert plateau.pion_sur(cible) is None
        assert plateau.pion_sur(attaquant) is not None
        assert resultat.elimines == [cible]
        assert resultat.rapport == (6, 1)

    def test_attaquant_elimine_vide_sa_case(self, duo):
        cible, attaquant = duo
        plateau = Plateau([(cible, pion(NAIN)), (attaquant, pion(ARCHER))])
        # ARCHER 2 contre NAIN 12 → 1-5 ; dé 2 → AE.
        resultat = combat.livrer_combat(plateau, cible, [attaquant], jet=2)
        assert resultat.resultat == AE
        assert plateau.pion_sur(attaquant) is None
        assert plateau.pion_sur(cible) is not None

    def test_echange_vide_les_deux_cases(self, duo):
        cible, attaquant = duo
        plateau = Plateau([(cible, pion(ARCHER)), (attaquant, pion(NAIN))])
        # NAIN 12 contre ARCHER 2 → 6-1 ; dé 6 → EX.
        resultat = combat.livrer_combat(plateau, cible, [attaquant], jet=6)
        assert resultat.resultat == EX
        assert plateau.pion_sur(cible) is None
        assert plateau.pion_sur(attaquant) is None

    def test_l_echange_epargne_les_tireurs(self, duo):
        """« Une unité tirant des missiles ne peut en aucun cas subir [...] un résultat d'échange. »

        Le fantassin tombe avec la cible, l'arbalétrier reste : il a frappé de loin.
        """
        cible, fantassin = duo
        _, _, tireur, *_ = couronne_de(cible)
        plateau = Plateau([(cible, pion(ARCHER)),
                           (fantassin, pion(NAIN)), (tireur, pion(ARBALETRIER))])
        # NAIN 12 + ARBALETRIER 6 = 18 contre ARCHER 2 → 6-1 ; dé 6 → EX.
        resultat = combat.livrer_combat(plateau, cible, [fantassin, tireur], jet=6)
        assert resultat.resultat == EX
        assert plateau.pion_sur(cible) is None
        assert plateau.pion_sur(fantassin) is None
        assert plateau.pion_sur(tireur) is not None
        assert resultat.elimines == [fantassin, cible]

    def test_un_tireur_seul_ressort_indemne_d_un_echange(self, duo):
        """L'échange vide alors la seule case de la cible : l'attaquant n'y laisse rien."""
        cible, tireur = duo
        plateau = Plateau([(cible, pion(ARCHER)), (tireur, pion(ARBALETRIER_LOURD))])
        # ARBALETRIER_LOURD 8 contre ARCHER 2 → 4-1 ; dé 6 → EX.
        resultat = combat.livrer_combat(plateau, cible, [tireur], jet=6)
        assert resultat.resultat == EX
        assert resultat.elimines == [cible]
        assert plateau.pion_sur(tireur) is not None

    def test_le_tireur_compte_quand_meme_dans_le_rapport(self, duo):
        """Épargné par l'échange, mais pas absent du combat : sa force pèse sur la colonne."""
        cible, fantassin = duo
        _, _, tireur, *_ = couronne_de(cible)
        plateau = Plateau([(cible, pion(ARCHER)),
                           (fantassin, pion(NAIN)), (tireur, pion(ARBALETRIER))])
        detail = combat.livrer_combat(plateau, cible, [fantassin, tireur], jet=6).detail
        assert detail.forces == [12, 6]
        assert detail.force_attaquante == 18

    def test_l_attaquant_elimine_n_epargne_pas_le_tireur(self, duo):
        """Le fascicule ne dispense les tireurs que de la retraite et de l'échange, pas de `AE`."""
        cible, tireur = duo
        plateau = Plateau([(cible, pion(NAIN)), (tireur, pion(ARBALETRIER))])
        # ARBALETRIER 6 contre NAIN 12 → 1-2 ; dé 6 → AR... on prend le rapport le plus défavorable.
        resultat = combat.livrer_combat(plateau, cible, [tireur], jet=2)
        assert resultat.resultat == AR
        plateau = Plateau([(cible, pion(NAIN)), (tireur, pion(ARCHER))])
        # ARCHER 2 contre NAIN 12 → 1-5 ; dé 2 → AE : le tireur est bien retiré.
        resultat = combat.livrer_combat(plateau, cible, [tireur], jet=2)
        assert resultat.resultat == AE
        assert plateau.pion_sur(tireur) is None

    def test_un_recul_ne_change_rien(self, duo):
        cible, attaquant = duo
        plateau = Plateau([(cible, pion(ORQUE)), (attaquant, pion(NAIN))])
        avant = dict(plateau.pions)
        resultat = combat.livrer_combat(plateau, cible, [attaquant], jet=1)  # 1-1, dé 1 → DR
        assert resultat.resultat in (AR, DR)
        assert plateau.pions == avant

    def test_le_terrain_du_defenseur_compte(self, duo):
        _, attaquant = duo
        ruines = hexagone_de_terrain("ruines")
        plateau = Plateau([(ruines, pion(ORQUE)), (attaquant, pion(NAIN))])
        # NAIN 12 contre ORQUE 8 → 1-1 en plaine, mais 12 contre 16 → 1-2 dans les ruines.
        sans_ruines = combat.colonne_du_rapport(12, 8)
        avec_ruines = combat.colonne_du_rapport(12, 8 * 2)
        assert avec_ruines < sans_ruines

    def test_une_cible_absente_ne_resout_rien(self, duo):
        cible, attaquant = duo
        plateau = Plateau([(attaquant, pion(NAIN))])
        resultat = combat.livrer_combat(plateau, cible, [attaquant], jet=6)
        assert resultat.resultat is None
        assert resultat.elimines == []


class TestDetailDuRapport:
    """Le calcul gardé pièce par pièce : c'est de quoi le raconter, pas de quoi le refaire.

    Le rapport ne se lit pas sur le plateau — le terrain du défenseur joue deux fois entre les
    cartons et la colonne du Tableau I —, et le détail est ce qui permet de le montrer.
    """

    @pytest.fixture
    def duo(self):
        a = plaine_bien_entouree()
        c, *_ = couronne_de(a)
        return a, c

    def test_le_detail_garde_les_forces_une_a_une(self, duo):
        """Le groupe d'attaquants ne se résume pas à son total : chaque carton a sa force."""
        cible, attaquant = duo
        _, second, *_ = couronne_de(cible)  # une seconde case au contact de la cible
        plateau = Plateau([(cible, pion(ARCHER)), (attaquant, pion(NAIN)), (second, pion(ELFE))])
        detail = combat.livrer_combat(plateau, cible, [attaquant, second], jet=1).detail
        assert detail.forces == [12, 7]
        assert detail.force_attaquante == 19

    def test_le_detail_garde_le_terrain_et_son_multiplicateur(self):
        ruines = hexagone_de_terrain("ruines")
        _, attaquant, *_ = couronne_de(ruines)
        plateau = Plateau([(ruines, pion(ORQUE)), (attaquant, pion(NAIN))])
        detail = combat.livrer_combat(plateau, ruines, [attaquant], jet=1).detail
        assert detail.terrain == "ruines"
        assert (detail.force_de_la_cible, detail.multiplicateur, detail.force_defensive) \
            == (8, 2, 16)

    def test_le_detail_garde_le_jet_et_le_bonus_du_terrain(self):
        """Le dé du résultat est déjà modifié : sans le détail, le jet brut serait perdu."""
        colline = hexagone_de_terrain("colline")
        _, attaquant, *_ = couronne_de(colline)
        plateau = Plateau([(colline, pion(ORQUE)), (attaquant, pion(NAIN))])
        detail = combat.livrer_combat(plateau, colline, [attaquant], jet=3).detail
        assert (detail.jet, detail.bonus_au_de, detail.de) == (3, 2, 5)

    def test_le_de_reste_dans_le_tableau(self):
        """Le Tableau I n'a que six lignes : un jet de 6 en colline y est ramené."""
        colline = hexagone_de_terrain("colline")
        _, attaquant, *_ = couronne_de(colline)
        plateau = Plateau([(colline, pion(ORQUE)), (attaquant, pion(NAIN))])
        detail = combat.livrer_combat(plateau, colline, [attaquant], jet=6).detail
        assert (detail.jet + detail.bonus_au_de, detail.de) == (8, 6)

    def test_le_detail_redonne_le_rapport_et_l_issue_du_resultat(self, duo):
        """Deux façons de lire le même combat : elles ne peuvent pas diverger."""
        cible, attaquant = duo
        plateau = Plateau([(cible, pion(ARCHER)), (attaquant, pion(NAIN))])
        resultat = combat.livrer_combat(plateau, cible, [attaquant], jet=1)
        assert resultat.detail.rapport == resultat.rapport == (6, 1)
        assert resultat.detail.de == resultat.de == 1
        assert resultat.detail.issue == resultat.resultat == DE

    def test_un_combat_non_resolu_n_a_rien_a_detailler(self, duo):
        cible, attaquant = duo
        plateau = Plateau([(attaquant, pion(NAIN))])
        assert combat.livrer_combat(plateau, cible, [attaquant], jet=6).detail is None

    def test_resoudre_lit_le_meme_calcul(self, duo):
        """`resoudre` et `livrer_combat` passent par `detailler` : une seule lecture du terrain."""
        cible, attaquant = duo
        plateau = Plateau([(cible, pion(ARCHER)), (attaquant, pion(NAIN))])
        issue = combat.resoudre([12], pion(ARCHER), cible, jet=1)
        assert issue == combat.livrer_combat(plateau, cible, [attaquant], jet=1).resultat


class TestSuiviDeCombat:
    """Une unité ne livre qu'un combat par phase, et n'est prise pour cible qu'une fois.

    Le registre désigne les unités par leur case : un carton vaut pour plusieurs unités, la case
    n'en désigne qu'une, et rien ne bouge pendant une phase de combat.
    """

    @pytest.fixture
    def suivi(self):
        return combat.SuiviDeCombat()

    @pytest.fixture
    def cases(self, coin):
        """Trois cases distinctes : le centre, une case au contact, une case à deux cases."""
        centre, contact, large = coin
        return centre.cle, contact.cle, large.cle

    def test_tout_est_disponible_au_depart(self, cases, suivi):
        centre, contact, _ = cases
        assert suivi.peut_attaquer(contact)
        assert suivi.peut_etre_cible(centre)

    def test_un_attaquant_engage_ne_peut_plus_attaquer(self, cases, suivi):
        centre, contact, _ = cases
        suivi.enregistrer([contact], centre)
        assert not suivi.peut_attaquer(contact)
        # Il reste attaquable, lui : c'est l'affaire de la phase de combat d'en face.
        assert suivi.peut_etre_cible(contact)

    def test_une_cible_engagee_ne_peut_plus_etre_attaquee(self, cases, suivi):
        centre, contact, _ = cases
        suivi.enregistrer([contact], centre)
        assert not suivi.peut_etre_cible(centre)
        assert suivi.peut_attaquer(centre)

    def test_tout_le_groupe_d_attaquants_est_marque(self, cases, suivi):
        centre, contact, large = cases
        suivi.enregistrer([contact, large], centre)
        assert not suivi.peut_attaquer(contact)
        assert not suivi.peut_attaquer(large)

    def test_une_unite_hors_du_combat_reste_libre(self, cases, suivi):
        centre, contact, large = cases
        suivi.enregistrer([contact], centre)
        assert suivi.peut_attaquer(large)
        assert suivi.peut_etre_cible(large)

    def test_la_nouvelle_phase_libere_tout_le_monde(self, cases, suivi):
        centre, contact, _ = cases
        suivi.enregistrer([contact], centre)
        suivi.reinitialiser()
        assert suivi.peut_attaquer(contact)
        assert suivi.peut_etre_cible(centre)

    def test_en_dict_livre_les_deux_listes_triees(self, cases, suivi):
        centre, contact, large = cases
        suivi.enregistrer([large, contact], centre)
        assert suivi.en_dict() == {"attaquants_engages": sorted([contact, large]),
                                   "cibles_engagees": [centre]}

    def test_restaurer_remplace_le_registre_en_place(self, cases, suivi):
        centre, contact, large = cases
        suivi.enregistrer([large], large)
        sauvegarde = {"attaquants_engages": [contact], "cibles_engagees": [centre]}
        assert suivi.restaurer(**sauvegarde) is suivi
        assert suivi.en_dict() == sauvegarde
        # Ce que la sauvegarde ne cite pas est redevenu libre.
        assert suivi.peut_attaquer(large) and suivi.peut_etre_cible(large)
        assert not suivi.peut_attaquer(contact)
        assert not suivi.peut_etre_cible(centre)
