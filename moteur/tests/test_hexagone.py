"""La classe Hex : coordonnées, voisinage, coûts de terrain et déplacements."""

import json
from fractions import Fraction

import pytest

from moteur import hexagone as moteur_hexagone
from moteur.hexagone import (CARTE, CARTE_TRANSCRITE, MOUVEMENT_PAR_DEFAUT, Hex, corriger,
                             lire_les_corrections)

# Hexagones de référence, relevés sur la carte du jeu — la transcription corrigée. Si une
# correction future en change un, ces tests le diront : il faudra alors en choisir un autre, pas
# défaire la correction.
PLAINE = Hex(1, 26, -27)          # entourée de six plaines
BOIS = Hex(0, 11, -11)            # borde une plaine
LAC = Hex(4, 35, -39)
FAILLE = Hex(9, -2, -7)
ROUTE = Hex(2, 20, -22)           # de terrain « route », et voisine d'une autre route
COLLINE = Hex(5, -2, -3)          # borde un massif
MONTAGNE_NUE = Hex(4, -1, -3)     # sans route ni chemin, voisine d'une plaine
COIN_NORD_OUEST = Hex(0, 0, 0)


def voisin_tel_que(hexagone, predicat):
    """Rend le premier voisin de `hexagone` qui satisfait `predicat`."""
    for voisin in hexagone.voisins():
        if predicat(voisin):
            return voisin
    raise AssertionError(f"aucun voisin de {hexagone} ne convient")


class TestConstruction:
    def test_les_trois_coordonnees(self):
        assert (Hex(3, -1, -2).q, Hex(3, -1, -2).r, Hex(3, -1, -2).s) == (3, -1, -2)

    def test_deux_coordonnees_suffisent(self):
        assert Hex(3, -1) == Hex(3, -1, -2)

    def test_un_hexagone_vide(self):
        vide = Hex()
        assert vide.est_vide
        assert repr(vide) == "Hex()"

    def test_des_coordonnees_incoherentes_sont_refusees(self):
        with pytest.raises(ValueError, match="incohérentes"):
            Hex(3, -1, 5)

    def test_une_seule_coordonnee_est_refusee(self):
        with pytest.raises(ValueError):
            Hex(3)

    def test_aller_retour_par_la_cle(self):
        assert Hex.depuis_cle("13,-4,-9") == Hex(13, -4, -9)
        assert Hex(13, -4, -9).cle == "13,-4,-9"

    def test_un_hexagone_vide_n_a_pas_de_position(self):
        for operation in (lambda: Hex().cle, lambda: Hex().voisins(), lambda: Hex().terrain):
            with pytest.raises(ValueError, match="vide"):
                operation()

    def test_les_hexagones_servent_de_cle_de_dictionnaire(self):
        assert {Hex(1, 2, -3): "ici"}[Hex(1, 2)] == "ici"
        assert Hex(1, 2, -3) != Hex(2, 1, -3)
        assert Hex(1, 2, -3) != "1,2,-3"


class TestCarte:
    def test_la_carte_est_lue_en_entier(self):
        assert len(CARTE) == 2280

    def test_la_carte_du_jeu_a_les_hexagones_de_la_transcription(self):
        """Une correction change un terrain ; elle n'ajoute ni ne retire d'hexagone."""
        assert CARTE.keys() == CARTE_TRANSCRITE.keys()

    def test_le_terrain_est_en_tete_des_elements(self):
        assert BOIS.terrain == "bois"
        assert BOIS.elements[0] == BOIS.terrain

    def test_un_hexagone_hors_carte_n_a_pas_de_terrain(self):
        dehors = Hex(99, 0, -99)
        assert not dehors.est_sur_la_carte
        assert dehors.terrain is None
        assert dehors.elements == ()

    def test_six_voisins_au_centre_de_la_carte(self):
        assert len(PLAINE.voisins()) == 6

    def test_moins_de_voisins_au_bord(self):
        assert len(COIN_NORD_OUEST.voisins()) == 2

    def test_les_voisins_sont_tous_sur_la_carte(self):
        for voisin in PLAINE.voisins():
            assert voisin.est_sur_la_carte

    def test_le_voisinage_est_reciproque(self):
        for voisin in PLAINE.voisins():
            assert PLAINE in voisin.voisins()


class TestCouts:
    def test_la_plaine_coute_un_point(self):
        assert PLAINE.cout_depuis(voisin_tel_que(PLAINE, lambda v: True)) == 1

    def test_le_bois_coute_deux_points(self):
        assert BOIS.cout_depuis(voisin_tel_que(BOIS, lambda v: v.terrain == "plaine")) == 2

    def test_suivre_une_route_coute_un_tiers_de_point(self):
        autre = voisin_tel_que(ROUTE, lambda v: "route" in v.elements)
        assert autre.cout_depuis(ROUTE) == Fraction(1, 3)

    def test_rejoindre_une_route_se_paie_au_tarif_du_terrain(self):
        """Le fascicule : l'unité paie d'abord le terrain qui la sépare de la route."""
        hors_route = voisin_tel_que(ROUTE, lambda v: "route" not in v.elements)
        assert ROUTE.cout_depuis(hors_route) == 1

    def test_le_lac_et_la_faille_sont_infranchissables(self):
        for interdit in (LAC, FAILLE):
            assert interdit.cout_depuis(voisin_tel_que(interdit, lambda v: True)) is None

    def test_la_montagne_se_refuse_depuis_la_plaine(self):
        plaine = voisin_tel_que(MONTAGNE_NUE, lambda v: v.terrain == "plaine")
        assert MONTAGNE_NUE.cout_depuis(plaine) is None

    def test_la_montagne_s_aborde_par_la_colline(self):
        montagne = voisin_tel_que(COLLINE, lambda v: v.terrain == "montagne")
        assert montagne.cout_depuis(COLLINE) == 1

    def test_un_hexagone_hors_carte_est_sans_cout(self):
        assert Hex(99, 0, -99).cout_depuis(PLAINE) is None
        assert PLAINE.cout_depuis(Hex(99, 0, -99)) is None


class TestDeplacements:
    def test_un_seul_point_mene_aux_voisins_franchissables(self):
        atteints = PLAINE.deplacements(1)
        assert set(atteints) == set(PLAINE.voisins())

    def test_le_bois_est_hors_de_portee_avec_un_point(self):
        depart = voisin_tel_que(BOIS, lambda v: v.terrain == "plaine")
        assert BOIS not in depart.deplacements(1)
        assert BOIS in depart.deplacements(2)

    def test_le_depart_ne_figure_pas_dans_le_resultat(self):
        assert PLAINE not in PLAINE.deplacements()

    def test_aucun_terrain_infranchissable_n_est_atteint(self):
        for hexagone in PLAINE.deplacements():
            assert hexagone.terrain not in {"lac", "riviere", "faille", "fort", "chateau"}

    def test_on_ne_bouge_pas_depuis_un_terrain_inhabitable(self):
        """Une unité terrestre ne se tient ni dans un lac, ni dans une rivière, ni dans la faille."""
        assert LAC.deplacements() == []
        assert FAILLE.deplacements() == []

    def test_chaque_case_atteinte_est_reellement_a_portee(self):
        """Un chemin de proche en proche doit relier le départ à chaque case rendue."""
        budget = Fraction(MOUVEMENT_PAR_DEFAUT)
        atteints = {hexagone: None for hexagone in PLAINE.deplacements()}
        depenses = {PLAINE: Fraction(0)}
        a_traiter = [PLAINE]
        while a_traiter:
            courant = a_traiter.pop()
            for voisin in courant.voisins():
                cout = voisin.cout_depuis(courant)
                if cout is None:
                    continue
                total = depenses[courant] + cout
                if total <= budget and total < depenses.get(voisin, budget + 1):
                    depenses[voisin] = total
                    a_traiter.append(voisin)
        del depenses[PLAINE]
        assert set(atteints) == set(depenses)

    def test_la_route_porte_plus_loin_que_la_plaine(self):
        assert len(ROUTE.deplacements()) > len(PLAINE.deplacements())

    def test_les_hexagones_rendus_sont_uniques_et_sur_la_carte(self):
        atteints = PLAINE.deplacements()
        assert len(set(atteints)) == len(atteints)
        assert all(hexagone.est_sur_la_carte for hexagone in atteints)

    def test_le_mouvement_par_defaut_vaut_cinq(self):
        assert MOUVEMENT_PAR_DEFAUT == 5
        assert PLAINE.deplacements() == PLAINE.deplacements(5)

    def test_un_mouvement_nul_ne_mene_nulle_part(self):
        assert PLAINE.deplacements(0) == []


class TestConversion:
    def test_le_dict_decrit_l_hexagone(self):
        assert PLAINE.en_dict() == {"q": 1, "r": 26, "s": -27, "terrain": "plaine"}

    def test_le_dict_d_un_hexagone_vide(self):
        assert Hex().en_dict() == {"q": None, "r": None, "s": None, "terrain": None}

    def test_le_dict_passe_en_json(self):
        rendu = json.dumps([hexagone.en_dict() for hexagone in PLAINE.deplacements()])
        assert json.loads(rendu)[0]["terrain"]


class TestCorrections:
    """Le recouvrement de la transcription par `game_box/map_fix.json`."""

    TRANSCRITE = {
        "0,0,0": ("plaine",),
        "1,0,-1": ("bois", "route"),
        "1,-1,0": ("plaine", "chemin"),
    }

    def test_une_correction_remplace_le_terrain_principal(self):
        carte = corriger(self.TRANSCRITE, {"0,0,0": "colline"})
        assert carte["0,0,0"] == ("colline",)

    def test_les_elements_secondaires_survivent(self):
        """Corriger un bois de la route noire ne doit pas couper la route qu'il masque."""
        carte = corriger(self.TRANSCRITE, {"1,0,-1": "colline"})
        assert carte["1,0,-1"] == ("colline", "route")

    def test_le_terrain_corrige_ne_figure_pas_deux_fois(self):
        """Le chemin d'une plaine corrigée en chemin ne double pas le terrain principal."""
        carte = corriger(self.TRANSCRITE, {"1,-1,0": "chemin"})
        assert carte["1,-1,0"] == ("chemin",)

    def test_les_hexagones_non_corriges_ne_bougent_pas(self):
        carte = corriger(self.TRANSCRITE, {"0,0,0": "lac"})
        assert carte["1,0,-1"] == self.TRANSCRITE["1,0,-1"]

    def test_une_cle_hors_carte_est_ignoree(self):
        carte = corriger(self.TRANSCRITE, {"99,0,-99": "lac"})
        assert carte.keys() == self.TRANSCRITE.keys()

    def test_la_transcription_n_est_pas_modifiee(self):
        corriger(self.TRANSCRITE, {"0,0,0": "lac"})
        assert self.TRANSCRITE["0,0,0"] == ("plaine",)

    def test_une_carte_sans_correction_est_la_transcription(self):
        assert corriger(self.TRANSCRITE, {}) == self.TRANSCRITE

    def test_la_correction_agit_sur_le_mouvement(self, monkeypatch):
        """Une plaine corrigée en lac devient infranchissable."""
        voisine = voisin_tel_que(PLAINE, lambda hexagone: hexagone.terrain == "plaine")
        assert voisine in PLAINE.deplacements()

        monkeypatch.setitem(moteur_hexagone.CARTE, voisine.cle, ("lac",))
        assert voisine not in PLAINE.deplacements()

    def test_le_fichier_absent_ne_corrige_rien(self, tmp_path, monkeypatch):
        monkeypatch.setattr(moteur_hexagone, "CHEMIN_DES_CORRECTIONS", tmp_path / "map_fix.json")
        assert lire_les_corrections() == {}

    def test_les_corrections_sont_lues_dans_le_fichier(self, tmp_path, monkeypatch):
        chemin = tmp_path / "map_fix.json"
        chemin.write_text(json.dumps({"1,26,-27": "lac"}), encoding="utf-8")
        monkeypatch.setattr(moteur_hexagone, "CHEMIN_DES_CORRECTIONS", chemin)

        carte = corriger(CARTE_TRANSCRITE, lire_les_corrections())
        assert carte["1,26,-27"][0] == "lac"
        assert CARTE_TRANSCRITE["1,26,-27"][0] == "plaine"
