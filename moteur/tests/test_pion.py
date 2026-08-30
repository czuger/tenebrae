"""Le catalogue des pions : les valeurs lues sur les cartons, et le mouvement qu'on en tire."""

import json

import pytest

from moteur.hexagone import Hex
from moteur.pion import (ALLIANCE, BOITE, CAMPS, CATALOGUE, IMMOBILE, NEUTRE, TENEBRES, Pion,
                         lire_le_catalogue, pion)

BELIER = "yzent-05-1-belier"                       # 10 en force, 2 en mouvement
INFANTERIE = "empire-01-26-infanteries"            # 4 et 4, la valeur la plus courante
CAVALERIE = "reissland-02-8-cavaleries"            # 8 points : la cavalerie va loin
CHAUVE_SOURIS = "conjurations-01-6-chauves-souris"  # mouvement au sol illisible, vol (2)
DRAGON = "dragons-01-pions-de-dragons-trois-couleurs"
MARQUEUR = "marqueurs-03-paralysie"
FEUILLE = "magiciens-01-pions-de-magiciens-vue-d-ensemble"


class TestCatalogue:
    def test_les_cent_vingt_sept_photos_sont_la(self):
        assert len(CATALOGUE) == 127

    def test_la_cle_est_le_nom_de_l_image(self):
        for cle, pion_lu in CATALOGUE.items():
            assert pion_lu.image.endswith(f"{cle}.jpg")

    def test_chaque_image_existe(self):
        """`image` est relatif à la racine du dépôt : « game_box/pions/… »."""
        racine = BOITE.parent
        for pion_lu in CATALOGUE.values():
            assert (racine / pion_lu.image).exists(), pion_lu

    def test_un_pion_inconnu_ne_passe_pas(self):
        with pytest.raises(KeyError):
            pion("pion-qui-n-existe-pas")

    def test_le_catalogue_se_relit_a_la_demande(self):
        """La lecture est une fonction pure : deux appels donnent les mêmes valeurs."""
        relu = lire_le_catalogue()
        assert relu.keys() == CATALOGUE.keys()
        assert relu[BELIER].en_dict() == CATALOGUE[BELIER].en_dict()


class TestValeursLues:
    def test_les_valeurs_du_carton(self):
        infanterie = pion(INFANTERIE)
        assert (infanterie.force, infanterie.mouvement) == (4, 4)
        assert (infanterie.tir, infanterie.portee) == (None, None)
        assert infanterie.symbole == "infanterie"

    def test_un_archer_porte_ses_valeurs_de_tir(self):
        archer = pion("elfes-02-4-archers")
        assert (archer.force, archer.mouvement, archer.tir, archer.portee) == (8, 4, 8, 3)

    def test_une_faculte_speciale_est_une_lettre(self):
        assert pion("empire-de-lynn-02-10-cavaleries-de-puissance-10").facultes_speciales == "P"
        assert pion(DRAGON).facultes_speciales == "s"

    def test_les_valeurs_absentes_du_carton_sont_nulles(self):
        marqueur = pion(MARQUEUR)
        assert (marqueur.force, marqueur.mouvement, marqueur.tir) == (None, None, None)
        assert marqueur.facultes_speciales == "PA"

    def test_une_lecture_incomplete_est_signalee(self):
        """Le mouvement au sol de la chauve-souris n'est pas lisible : `remarques` le dit."""
        chauve_souris = pion(CHAUVE_SOURIS)
        assert chauve_souris.mouvement is None
        assert "lisible" in chauve_souris.remarques


class TestUnites:
    def test_une_unite_porte_des_valeurs(self):
        assert pion(INFANTERIE).est_une_unite
        assert pion(CHAUVE_SOURIS).est_une_unite

    def test_un_marqueur_n_est_pas_une_unite(self):
        assert not pion(MARQUEUR).est_une_unite
        assert not pion(FEUILLE).est_une_unite

    def test_la_boite_compte_cent_quinze_unites(self):
        """127 photos, moins les 6 marqueurs, les 2 feuilles de suivi et les 4 vues d'ensemble."""
        assert sum(1 for pion_lu in CATALOGUE.values() if pion_lu.est_une_unite) == 115


class TestCamps:
    """La répartition en camps de `game_box/pions/README.md`, faction par faction."""

    def test_chaque_pion_a_un_camp(self):
        for pion_lu in CATALOGUE.values():
            assert pion_lu.camp in (ALLIANCE, TENEBRES, NEUTRE), pion_lu

    def test_chaque_faction_de_la_boite_est_classee(self):
        assert {pion_lu.faction for pion_lu in CATALOGUE.values()} <= CAMPS.keys()

    def test_les_deux_camps_du_jeu(self):
        assert pion("elfes-01-5-infanteries").camp == ALLIANCE
        assert pion(INFANTERIE).camp == ALLIANCE          # Empire Tharque
        assert pion("orques-01-15-infanteries").camp == TENEBRES
        assert pion(BELIER).camp == TENEBRES              # Yzent, allié d'opportunité
        assert pion("machines-de-siege-01-juggernaut").camp == TENEBRES

    def test_les_neutres(self):
        assert pion(CHAUVE_SOURIS).camp == NEUTRE         # une conjuration
        assert pion("volants-01-5-infanteries").camp == NEUTRE
        assert pion(MARQUEUR).camp == NEUTRE

    def test_la_repartition_de_la_boite(self):
        """56 pions des ténèbres, 47 de l'alliance, 24 neutres — dont les 12 qui ne sont pas des
        pions."""
        camps = [pion_lu.camp for pion_lu in CATALOGUE.values()]
        assert (camps.count(TENEBRES), camps.count(ALLIANCE), camps.count(NEUTRE)) == (56, 47, 24)


class TestZoneDeControleExercee:
    def test_une_unite_d_un_camp_en_exerce_une(self):
        assert pion(INFANTERIE).exerce_une_zone_de_controle
        assert pion("orques-01-15-infanteries").exerce_une_zone_de_controle

    def test_un_marqueur_n_en_exerce_pas(self):
        assert not pion(MARQUEUR).exerce_une_zone_de_controle
        assert not pion(FEUILLE).exerce_une_zone_de_controle

    def test_un_neutre_n_en_exerce_pas(self):
        assert not pion(CHAUVE_SOURIS).exerce_une_zone_de_controle

    def test_les_exceptions_du_fascicule_ne_sont_pas_appliquees(self):
        """Leaders, démons et morts-vivants en exercent une ici : voir `moteur/README.md`."""
        assert pion("elfes-06-1-leader").exerce_une_zone_de_controle
        assert pion("demons-01-5-infanteries").exerce_une_zone_de_controle
        assert pion("morts-vivants-01-20-unites-de-squelettes").exerce_une_zone_de_controle


class TestPointsDeMouvement:
    def test_le_mouvement_lu_sur_le_carton(self):
        assert pion(BELIER).points_de_mouvement == 2
        assert pion(INFANTERIE).points_de_mouvement == 4
        assert pion(CAVALERIE).points_de_mouvement == 8

    def test_le_vol_sert_faute_de_mouvement_au_sol(self):
        assert pion(CHAUVE_SOURIS).points_de_mouvement == 2

    def test_le_mouvement_au_sol_prime_sur_le_vol(self):
        dragon = pion(DRAGON)
        assert (dragon.mouvement, dragon.mouvement_vol) == (5, 15)
        assert dragon.points_de_mouvement == 5

    def test_ce_qui_ne_porte_aucune_valeur_ne_bouge_pas(self):
        assert pion(MARQUEUR).points_de_mouvement == IMMOBILE == 0
        assert pion(FEUILLE).points_de_mouvement == IMMOBILE

    def test_toute_unite_a_de_quoi_bouger(self):
        for pion_lu in CATALOGUE.values():
            if pion_lu.est_une_unite:
                assert pion_lu.points_de_mouvement > 0, pion_lu

    def test_aucun_mouvement_farfelu(self):
        """Le plus lent fait 1 point, le plus rapide 20 : au-delà, c'est une faute de lecture."""
        for pion_lu in CATALOGUE.values():
            assert 0 <= pion_lu.points_de_mouvement <= 20, pion_lu


class TestDeplacements:
    """Ce que le mouvement du pion change à la portée, sur la carte du jeu."""

    PLAINE = Hex(1, 26, -27)

    def test_le_pion_lent_va_moins_loin_que_le_rapide(self):
        lent = self.PLAINE.deplacements(pion(BELIER).points_de_mouvement)
        rapide = self.PLAINE.deplacements(pion(CAVALERIE).points_de_mouvement)
        assert 0 < len(lent) < len(rapide)

    def test_un_marqueur_ne_va_nulle_part(self):
        assert self.PLAINE.deplacements(pion(MARQUEUR).points_de_mouvement) == []


class TestRendu:
    def test_le_dict_part_en_json(self):
        rendu = json.loads(json.dumps(pion(BELIER).en_dict()))
        assert rendu["cle"] == BELIER
        assert rendu["points_de_mouvement"] == 2
        assert rendu["camp"] == TENEBRES
        assert rendu["image"].startswith("game_box/pions/")

    def test_le_repr_dit_le_mouvement(self):
        assert repr(pion(BELIER)) == "Pion('yzent-05-1-belier', 2 PM)"

    def test_un_pion_se_construit_depuis_des_valeurs(self):
        valeurs = dict(CATALOGUE[BELIER].en_dict())
        del valeurs["cle"], valeurs["points_de_mouvement"]
        assert Pion("essai", valeurs).points_de_mouvement == 2
