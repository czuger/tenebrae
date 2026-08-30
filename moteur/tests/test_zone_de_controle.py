"""Les zones de contrôle : ce que la présence d'un adversaire interdit au mouvement.

Les hexagones de référence sont cherchés sur la carte par `plaines.py`, et non codés en dur : le
test survit ainsi à une correction de terrain.
"""

import pytest

from moteur.hexagone import Hex, zone_de_controle
from moteur.tests.plaines import BUDGET_MAXIMAL, budget_minimal, couronne_de, plaine_bien_entouree


@pytest.fixture(scope="module")
def couronne():
    """L'unité adverse **A**, et trois cases consécutives de sa zone de contrôle : C, X1, X2.

    C'est la figure de l'exemple du fascicule : C se tient dans la zone de contrôle de A, X1 et X2
    aussi, et C voudrait rejoindre X2 en passant par X1.
    """
    a = plaine_bien_entouree()
    c, x1, x2, _ = couronne_de(a)
    return a, c, x1, x2


@pytest.fixture(scope="module")
def zone(couronne):
    """Les six cases que A tient sous son contrôle."""
    a, *_ = couronne
    return zone_de_controle([a])


class TestZoneDeControle:
    """La fonction qui dit quelles cases une unité tient sous son contrôle."""

    def test_ce_sont_les_six_cases_environnantes(self, couronne):
        a, *_ = couronne
        assert zone_de_controle([a]) == {voisin.cle for voisin in a.voisins()}
        assert len(zone_de_controle([a])) == 6

    def test_la_case_occupee_n_en_fait_pas_partie(self, couronne):
        a, *_ = couronne
        assert a.cle not in zone_de_controle([a])

    def test_les_zones_de_plusieurs_unites_se_rejoignent(self, couronne):
        a, c, *_ = couronne
        assert zone_de_controle([a, c]) == zone_de_controle([a]) | zone_de_controle([c])

    def test_elle_ne_deborde_pas_de_la_carte(self):
        coin = Hex(0, 0, 0)
        assert zone_de_controle([coin]) == {voisin.cle for voisin in coin.voisins()}
        assert len(zone_de_controle([coin])) < 6

    def test_sans_unite_il_n_y_a_pas_de_zone(self):
        assert zone_de_controle([]) == frozenset()


class TestMouvementSousControle:
    """Ce que la zone change au parcours, de la case de départ à la case d'arrivée."""

    def test_sans_adversaire_le_parcours_est_celui_du_terrain(self, couronne):
        _, c, *_ = couronne
        assert c.deplacements(4, ennemis=(), sous_controle=()) == c.deplacements(4)

    def test_on_entre_dans_une_zone_au_tarif_du_terrain(self, couronne):
        """« Sans dépense de points supplémentaires » : la case coûte ce que coûte sa plaine."""
        a, c, x1, x2 = couronne
        depuis_le_large = next(voisin for voisin in c.voisins()
                               if voisin.distance(a) == 2)
        assert budget_minimal(depuis_le_large, c, sous_controle=zone_de_controle([a])) == 1

    def test_on_s_arrete_des_qu_on_y_est_entre(self, couronne, zone):
        """Une fois dans la zone, on ne va pas plus loin : la case de A reste hors d'atteinte."""
        a, c, *_ = couronne
        depuis_le_large = next(voisin for voisin in c.voisins() if voisin.distance(a) == 2)
        atteints = depuis_le_large.deplacements(BUDGET_MAXIMAL, sous_controle=zone)
        assert c in atteints
        assert a not in atteints

    def test_on_ne_passe_pas_d_une_case_controlee_a_une_autre(self, couronne, zone):
        """C est déjà dans la zone : le pas direct vers X1, pourtant voisin, lui est interdit."""
        _, c, x1, _ = couronne
        assert x1 in c.deplacements(1)
        assert x1 not in c.deplacements(1, sous_controle=zone)

    def test_on_sort_de_la_zone_ou_l_on_se_trouve(self, couronne, zone):
        """L'unité qui commence son mouvement sous contrôle peut en sortir — par une case libre."""
        a, c, *_ = couronne
        sortie = next(voisin for voisin in c.voisins() if voisin.distance(a) == 2)
        assert sortie in c.deplacements(1, sous_controle=zone)

    def test_le_detour_de_l_exemple_du_fascicule(self, couronne, zone):
        """« Elle dépensera donc 4 points de mouvement au lieu de 2. »

        C, sous le contrôle de A, ne peut atteindre X2 par X1 : elle doit sortir de la zone,
        contourner X1 par le large et rentrer en X2. A tenant sa case, elle ne la traverse pas
        non plus. Le compte du fascicule tombe juste, à la case près.
        """
        a, c, _, x2 = couronne
        assert budget_minimal(c, x2) == 2
        assert budget_minimal(c, x2, ennemis={a.cle}, sous_controle=zone) == 4

    def test_la_zone_reduit_la_portee(self, couronne, zone):
        _, c, *_ = couronne
        assert len(c.deplacements(4, sous_controle=zone)) < len(c.deplacements(4))


class TestCasesTenues:
    """Les cases occupées par l'adversaire, où le mouvement n'entre pas."""

    def test_on_n_entre_pas_sur_une_case_ennemie(self, couronne):
        a, c, *_ = couronne
        assert a in c.deplacements(1)
        assert a not in c.deplacements(BUDGET_MAXIMAL, ennemis={a.cle})

    def test_une_case_ennemie_ne_se_traverse_pas(self, couronne):
        """Ce qui n'était accessible qu'à travers A demande maintenant un détour."""
        a, c, x1, x2 = couronne
        oppose = next(voisin for voisin in a.voisins()
                      if voisin.distance(c) == 2 and voisin.distance(x1) == 2)
        assert budget_minimal(c, oppose) == 2
        assert budget_minimal(c, oppose, ennemis={a.cle}) > 2

    def test_les_deux_regles_se_cumulent(self, couronne, zone):
        a, c, *_ = couronne
        atteints = c.deplacements(4, ennemis={a.cle}, sous_controle=zone)
        assert a not in atteints
        assert atteints and len(atteints) < len(c.deplacements(4))
