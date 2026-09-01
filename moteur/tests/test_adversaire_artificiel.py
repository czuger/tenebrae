"""L'adversaire artificiel : le ciblage, la marche vers l'ennemi, la concentration des attaques.

Le fichier ne s'appelle pas `test_ia.py` : `application/tests/` en a déjà un, et pytest importe
les modules de test par leur seul nom de fichier.

Comme partout, les hexagones ne sont pas codés en dur : les figures sont cherchées sur la carte
du jeu — un coin de plaine nue, des ruines voisines d'une plaine — pour survivre à une correction
de terrain. Le dé est un appelable fourni par le test : l'IA est déterministe à dé égal.
"""

import pytest

from moteur import ia
from moteur.combat import DE, DR, SuiviDeCombat
from moteur.hexagone import CARTE, Hex
from moteur.phase import Tour
from moteur.pion import pion
from moteur.plateau import Plateau
from moteur.tests.plaines import alentours, couronne_de, plaine_bien_entouree

NAIN = "nains-01-5-infanteries"            # alliance, force 12, mouvement 3
ELFE = "elfes-01-5-infanteries"            # alliance, force 7, mouvement 4
ORQUE = "orques-01-15-infanteries"         # ténèbres, force 8, mouvement 4
ARCHER_ORQUE = "orques-03-5-archers"       # ténèbres, force 4, mouvement 4, tir 8, portée 3
ARCHER = "yzent-03-8-archers"              # ténèbres, force 2, mouvement 4, tir 4, portée 3


def le_de_ne_doit_pas_servir():
    raise AssertionError("aucun combat ne devait être livré")


def ruines_en_plaine():
    """Des ruines, une plaine voisine, et une seconde plaine voisine de la première."""
    for cle, elements in CARTE.items():
        if elements[0] != "ruines":
            continue
        ruines = Hex.depuis_cle(cle)
        for depuis in ruines.voisins():
            if CARTE[depuis.cle][0] != "plaine":
                continue
            for plaine in depuis.voisins():
                if plaine != ruines and CARTE[plaine.cle][0] == "plaine":
                    return ruines, depuis, plaine
    raise AssertionError("aucunes ruines bordées de deux plaines sur la carte")


@pytest.fixture
def coin():
    """Un centre de plaine nue, deux cases au contact qui se touchent, une case à deux cases."""
    a = plaine_bien_entouree()
    c, x1, _, large = couronne_de(a)
    return a, c, x1, large


class TestPrioriteDesCibles:
    def test_la_plus_proche_d_abord(self, coin):
        a, c, _, large = coin
        # L'orque au contact passe avant l'archer plus faible mais plus loin.
        plateau = Plateau([(c, pion(ORQUE)), (large, pion(ARCHER_ORQUE))])
        assert ia.priorite_des_cibles(plateau, a, "alliance") == [c, large]

    def test_la_plus_faible_a_distance_egale(self, coin):
        a, c, x1, _ = coin
        plateau = Plateau([(c, pion(ORQUE)), (x1, pion(ARCHER_ORQUE))])
        # Les deux sont au contact ; l'archer (force 4) passe avant l'orque (force 8).
        assert ia.priorite_des_cibles(plateau, a, "alliance")[0] == x1

    def test_le_terrain_renforce_la_cible(self):
        ruines, depuis, plaine = ruines_en_plaine()
        # Le même orque : force 8 en plaine, mais 16 dans les ruines qui doublent la défense.
        plateau = Plateau([(ruines, pion(ORQUE)), (plaine, pion(ORQUE))])
        assert ia.priorite_des_cibles(plateau, depuis, "alliance")[0] == plaine

    def test_l_ordre_est_departage_par_la_cle(self, coin):
        a, c, x1, _ = coin
        # Deux cibles identiques à la même distance : l'ordre des clés tranche, toujours pareil.
        plateau = Plateau([(c, pion(ORQUE)), (x1, pion(ORQUE))])
        attendu = [hexagone for hexagone in sorted((c, x1), key=lambda h: h.cle)]
        assert ia.priorite_des_cibles(plateau, a, "alliance") == attendu

    def test_sans_adversaire_pas_de_cible(self, coin):
        a, c, *_ = coin
        plateau = Plateau([(c, pion(NAIN))])
        assert ia.choisir_la_cible(plateau, a, "alliance") is None


class TestJouerLeMouvement:
    def test_l_infanterie_vient_au_contact(self, coin):
        a, _, _, large = coin
        plateau = Plateau([(a, pion(ORQUE)), (large, pion(NAIN))])
        joues = ia.jouer_le_mouvement(plateau, "alliance")
        assert len(joues) == 1
        depart, arrivee = joues[0]
        assert depart == large
        assert arrivee.distance(a) == 1
        assert plateau.pion_sur(arrivee).cle == NAIN

    def test_une_unite_a_portee_tient_sa_position(self, coin):
        a, c, *_ = coin
        plateau = Plateau([(a, pion(ORQUE)), (c, pion(NAIN))])
        assert ia.jouer_le_mouvement(plateau, "alliance") == []
        assert plateau.pion_sur(c).cle == NAIN

    def test_le_tireur_s_arrete_a_portee(self):
        # Un coin de plaine assez large pour poser l'archer à quatre cases de sa cible.
        a = plaine_bien_entouree(rayon=4)
        loin = next(hexagone for hexagone in alentours(a, 4) if hexagone.distance(a) == 4)
        plateau = Plateau([(a, pion(NAIN)), (loin, pion(ARCHER_ORQUE))])
        joues = ia.jouer_le_mouvement(plateau, "tenebres")
        # Portée 3 : l'archer s'approche à portée de tir, et pas d'un pas de plus.
        assert len(joues) == 1
        assert joues[0][1].distance(a) == 3

    def test_sans_adversaire_personne_ne_bouge(self, coin):
        a, *_ = coin
        plateau = Plateau([(a, pion(NAIN))])
        assert ia.jouer_le_mouvement(plateau, "alliance") == []


class TestJouerLeCombat:
    def test_les_attaques_se_concentrent(self, coin):
        a, c, x1, _ = coin
        plateau = Plateau([(a, pion(ORQUE)), (c, pion(NAIN)), (x1, pion(ELFE))])
        suivi = SuiviDeCombat()
        # Nain et elfe (12 + 7) contre l'orque (8) : 2-1 ; dé 1 → DR, personne ne tombe.
        combats = ia.jouer_le_combat(plateau, "alliance", suivi, jet=lambda: 1)
        assert len(combats) == 1
        cible, attaquants, resultat = combats[0]
        assert cible == a
        assert sorted(hexagone.cle for hexagone in attaquants) == sorted([c.cle, x1.cle])
        assert resultat.resultat == DR
        assert suivi.en_dict() == {"attaquants_engages": sorted([c.cle, x1.cle]),
                                   "cibles_engagees": [a.cle]}

    def test_une_unite_n_attaque_qu_une_fois(self, coin):
        a, c, x1, _ = coin
        # Deux orques au contact du nain : il n'en engage qu'un, l'autre reste indemne.
        plateau = Plateau([(a, pion(ORQUE)), (x1, pion(ORQUE)), (c, pion(NAIN))])
        suivi = SuiviDeCombat()
        combats = ia.jouer_le_combat(plateau, "alliance", suivi, jet=lambda: 1)
        assert len(combats) == 1
        assert not suivi.peut_attaquer(c.cle)
        assert len(suivi.cibles_engagees) == 1

    def test_pas_d_attaque_sous_la_parite(self, coin):
        a, _, _, large = coin
        # L'archer orque (force 4, portée 3) voit le nain (force 12) : 1-3, il renonce.
        plateau = Plateau([(a, pion(NAIN)), (large, pion(ARCHER_ORQUE))])
        suivi = SuiviDeCombat()
        combats = ia.jouer_le_combat(plateau, "tenebres", suivi, jet=le_de_ne_doit_pas_servir)
        assert combats == []
        assert suivi.peut_attaquer(large.cle)

    def test_les_elimines_quittent_le_plateau(self, coin):
        a, c, *_ = coin
        plateau = Plateau([(a, pion(ARCHER)), (c, pion(NAIN))])
        suivi = SuiviDeCombat()
        # Nain 12 contre archer 2 : 6-1 ; dé 1 → DE, la cible est retirée.
        combats = ia.jouer_le_combat(plateau, "alliance", suivi, jet=lambda: 1)
        assert combats[0][2].resultat == DE
        assert plateau.pion_sur(a) is None
        assert plateau.pion_sur(c).cle == NAIN


class TestJouerLeTour:
    def test_le_tour_complet_rend_la_main(self, coin):
        a, _, _, large = coin
        plateau = Plateau([(a, pion(ELFE)), (large, pion(ORQUE))])
        tour = Tour(("alliance", "tenebres"))
        tour.suivante().suivante()            # alliance jouée : ténèbres, phase de mouvement
        suivi = SuiviDeCombat()
        deplacements, combats = ia.jouer_le_tour(plateau, tour, suivi, jet=lambda: 1)
        # L'orque a marché au contact puis engagé l'elfe (8 contre 7 : 1-1 ; dé 1 → DR).
        assert len(deplacements) == 1
        assert len(combats) == 1
        assert combats[0][2].resultat == DR
        # La main est rendue : phase de mouvement de l'alliance, tour suivant, registre vide.
        assert tour.camp_actif == "alliance"
        assert tour.type_de_phase == "mouvement"
        assert tour.numero == 2
        assert suivi.en_dict() == {"attaquants_engages": [], "cibles_engagees": []}

    def test_l_ia_refuse_d_entrer_hors_mouvement(self, coin):
        a, c, *_ = coin
        plateau = Plateau([(a, pion(ELFE)), (c, pion(ORQUE))])
        tour = Tour(("alliance", "tenebres"))
        tour.suivante()                       # alliance, phase de combat
        with pytest.raises(ValueError):
            ia.jouer_le_tour(plateau, tour, SuiviDeCombat(), jet=lambda: 1)
