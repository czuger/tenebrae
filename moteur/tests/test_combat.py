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
