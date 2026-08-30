"""Les scénarios fixés dans `scenarios/` : ce qu'ils contiennent, et le plateau qu'ils donnent.

Ces tests gardent le placement cohérent avec la carte : une correction de terrain qui mettrait une
unité dans un lac se verrait ici, et non en cours de partie.
"""

import pytest

from moteur.hexagone import CARTE, INHABITABLES, Hex
from moteur.pion import ALLIANCE, CATALOGUE, TENEBRES
from moteur.scenario import SCENARIOS, Scenario, lire, scenario, scenarios_disponibles

GUERRE_DES_NAINS = 4
TERRAINS_INTERDITS = INHABITABLES | {"montagne"}


@pytest.fixture(scope="module")
def guerre_des_nains():
    return scenario(GUERRE_DES_NAINS)


class TestCatalogueDesScenarios:
    def test_le_repertoire_est_a_la_racine_du_depot(self):
        assert SCENARIOS.is_dir()
        assert SCENARIOS.name == "scenarios"

    def test_le_scenario_quatre_est_fixe(self):
        assert GUERRE_DES_NAINS in scenarios_disponibles()

    def test_un_scenario_non_fixe_est_introuvable(self):
        with pytest.raises(KeyError):
            scenario(99)

    def test_chaque_fichier_se_lit(self):
        for chemin in scenarios_disponibles().values():
            assert isinstance(lire(chemin), Scenario)


class TestGuerreDesNains:
    def test_il_se_presente(self, guerre_des_nains):
        assert guerre_des_nains.numero == GUERRE_DES_NAINS
        assert guerre_des_nains.nom == "La guerre des nains"
        assert "ave_tenebrae_regles.md" in guerre_des_nains.source

    def test_deux_armees_face_a_face(self, guerre_des_nains):
        assert [armee["armee"] for armee in guerre_des_nains.armees] == ["Nains", "Orques"]
        assert guerre_des_nains.camps == (ALLIANCE, TENEBRES)
        assert [armee["joueur"] for armee in guerre_des_nains.armees] == [1, 2]

    def test_les_effectifs_annonces_sont_ceux_qui_sont_poses(self, guerre_des_nains):
        """21 nains, 31 orques : les six photos naines et les cinq photos orques hors renforts."""
        poses = list(guerre_des_nains.placement.values())
        for armee in guerre_des_nains.armees:
            faction = "10-nains" if armee["armee"] == "Nains" else "11-orques"
            comptes = sum(1 for cle in poses if CATALOGUE[cle].faction == faction)
            assert comptes == armee["unites"]
        assert [armee["unites"] for armee in guerre_des_nains.armees] == [21, 31]
        assert len(guerre_des_nains) == 52

    def test_toute_l_armee_naine_est_la(self, guerre_des_nains):
        """5 infanteries, 4 arbalétriers, 4 arbalétriers lourds, 5 phalanges, 2 leaders, 1 mage."""
        assert compter(guerre_des_nains, "10-nains") == {
            "nains-01-5-infanteries": 5,
            "nains-02-4-arbaletriers": 4,
            "nains-03-4-arbaletriers-lourds": 4,
            "nains-04-5-phalanges": 5,
            "nains-05-2-leaders": 2,
            "nains-06-1-mage-vorgtd": 1,
        }

    def test_l_armee_orque_est_la_sans_ses_renforts(self, guerre_des_nains):
        """« Ne tiens pas compte des renforts » : les trois photos de renforts restent en boîte."""
        assert compter(guerre_des_nains, "11-orques") == {
            "orques-01-15-infanteries": 15,
            "orques-02-5-cavaleries": 5,
            "orques-03-5-archers": 5,
            "orques-04-5-archers-montes-a-cheval": 5,
            "orques-08-1-leader": 1,
        }

    def test_aucune_autre_faction_n_entre_en_jeu(self, guerre_des_nains):
        factions = {CATALOGUE[cle].faction for cle in guerre_des_nains.placement.values()}
        assert factions == {"10-nains", "11-orques"}

    def test_le_potentiel_de_magie_de_chaque_camp_est_note(self, guerre_des_nains):
        """« Le mage Vorgtd (45) » et « un nécromant mineur (20 points de magie) »."""
        assert [armee["magie"] for armee in guerre_des_nains.armees] == [45, 20]
        assert guerre_des_nains.armees[0]["jeteur_de_sorts"] == "nains-06-1-mage-vorgtd"
        assert guerre_des_nains.armees[1]["jeteur_de_sorts"] is None

    def test_les_nains_se_massent_au_sud_du_volcan(self, guerre_des_nains):
        """Toute l'armée naine est sur la ligne de son ancre ou au sud, et serrée autour d'elle."""
        ancre = Hex.depuis_cle(guerre_des_nains.armees[0]["ancre"])
        for case in cases_de(guerre_des_nains, "10-nains"):
            assert ligne(case) >= ligne(ancre)
            assert ancre.distance(case) <= 3

    def test_les_orques_tiennent_l_orcreich(self, guerre_des_nains):
        ancre = Hex.depuis_cle(guerre_des_nains.armees[1]["ancre"])
        for case in cases_de(guerre_des_nains, "11-orques"):
            assert ancre.distance(case) <= 3

    def test_chaque_armee_est_d_un_seul_tenant(self, guerre_des_nains):
        """Une armée massée : chaque unité touche au moins une autre de son camp."""
        for faction in ("10-nains", "11-orques"):
            cases = cases_de(guerre_des_nains, faction)
            for case in cases:
                assert any(case.distance(autre) == 1 for autre in cases if autre != case), case

    def test_les_deux_armees_ne_se_touchent_pas_encore(self, guerre_des_nains):
        """Elles se font face à quelques cases : le premier tour sert à marcher, pas à combattre."""
        nains = cases_de(guerre_des_nains, "10-nains")
        orques = cases_de(guerre_des_nains, "11-orques")
        assert min(nain.distance(orque) for nain in nains for orque in orques) > 1


class TestPlacementSurLaCarte:
    def test_chaque_case_est_sur_la_carte(self, guerre_des_nains):
        for case in guerre_des_nains.placement:
            assert case in CARTE

    def test_aucune_unite_sur_un_terrain_impraticable(self, guerre_des_nains):
        """Un lac, une rivière, la faille ou une montagne ne se tiennent pas."""
        for case in guerre_des_nains.placement:
            assert CARTE[case][0] not in TERRAINS_INTERDITS, case

    def test_une_case_ne_porte_qu_une_unite(self, guerre_des_nains):
        """Le placement est un dictionnaire : l'empilement est impossible par construction."""
        assert len(guerre_des_nains.placement) == len(set(guerre_des_nains.placement))

    def test_chaque_pion_existe_dans_la_boite(self, guerre_des_nains):
        for cle in guerre_des_nains.placement.values():
            assert cle in CATALOGUE
            assert CATALOGUE[cle].est_une_unite


class TestPlateauDuScenario:
    def test_le_plateau_porte_toutes_les_unites(self, guerre_des_nains):
        plateau = guerre_des_nains.plateau()
        assert len(plateau) == len(guerre_des_nains)

    def test_chaque_pion_est_sur_sa_case(self, guerre_des_nains):
        plateau = guerre_des_nains.plateau()
        for case, cle in guerre_des_nains.placement.items():
            assert plateau.pion_sur(Hex.depuis_cle(case)).cle == cle

    def test_les_camps_s_opposent_sur_le_plateau(self, guerre_des_nains):
        plateau = guerre_des_nains.plateau()
        assert len(plateau.cases_tenues_par(ALLIANCE)) == 21
        assert len(plateau.adversaires_de(ALLIANCE)) == 31

    def test_chaque_plateau_est_neuf(self, guerre_des_nains):
        """Deux parties ne partagent pas leurs pions : déplacer l'un ne bouge pas l'autre."""
        premier, second = guerre_des_nains.plateau(), guerre_des_nains.plateau()
        case = Hex.depuis_cle(next(iter(guerre_des_nains.placement)))
        premier.retirer(case)
        assert second.pion_sur(case) is not None

    def test_toute_l_armee_peut_marcher(self, guerre_des_nains):
        """Aucune unité n'est posée dans un cul-de-sac : chacune a au moins une case où aller."""
        plateau = guerre_des_nains.plateau()
        for case in guerre_des_nains.placement:
            assert plateau.deplacements(Hex.depuis_cle(case)), case


def cases_de(scenario_lu, faction):
    """Les cases occupées par cette faction."""
    return [Hex.depuis_cle(case) for case, cle in scenario_lu.placement.items()
            if CATALOGUE[cle].faction == faction]


def compter(scenario_lu, faction):
    """« clé de pion → nombre d'exemplaires posés » pour cette faction."""
    comptes = {}
    for cle in scenario_lu.placement.values():
        if CATALOGUE[cle].faction == faction:
            comptes[cle] = comptes.get(cle, 0) + 1
    return comptes


def ligne(hexagone):
    """La ligne odd-q de l'hexagone : elle croît vers le sud (voir game_box/carte.md)."""
    return hexagone.r + (hexagone.q - (hexagone.q & 1)) // 2
