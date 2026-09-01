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

# La ligne de front naine, telle qu'elle a été demandée : l'infanterie la tient d'un bout, les
# phalanges la prolongent jusqu'à l'autre. Les tests la redessinent au lieu de la recopier — c'est
# la ligne qui est la consigne, pas les sept clés qu'elle traverse.
DEBUT_DE_LA_LIGNE = "50,-7,-43"
FIN_DE_LA_LIGNE = "45,-8,-37"


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
        """18 nains, 30 orques : les deux armées moins ce que le moteur ne sait pas jouer."""
        poses = list(guerre_des_nains.placement.values())
        for armee in guerre_des_nains.armees:
            faction = "10-nains" if armee["armee"] == "Nains" else "11-orques"
            comptes = sum(1 for cle in poses if CATALOGUE[cle].faction == faction)
            assert comptes == armee["unites"]
        assert [armee["unites"] for armee in guerre_des_nains.armees] == [18, 30]
        assert len(guerre_des_nains) == 48

    def test_l_armee_naine_est_la_sans_ses_leaders_ni_son_mage(self, guerre_des_nains):
        """5 infanteries, 4 arbalétriers, 4 arbalétriers lourds, 5 phalanges — que du combat."""
        assert compter(guerre_des_nains, "10-nains") == {
            "nains-01-5-infanteries": 5,
            "nains-02-4-arbaletriers": 4,
            "nains-03-4-arbaletriers-lourds": 4,
            "nains-04-5-phalanges": 5,
        }

    def test_l_armee_orque_est_la_sans_ses_renforts_ni_son_leader(self, guerre_des_nains):
        """« Ne tiens pas compte des renforts » : les trois photos de renforts restent en boîte."""
        assert compter(guerre_des_nains, "11-orques") == {
            "orques-01-15-infanteries": 15,
            "orques-02-5-cavaleries": 5,
            "orques-03-5-archers": 5,
            "orques-04-5-archers-montes-a-cheval": 5,
        }

    def test_ni_leader_ni_jeteur_de_sorts_n_est_pose(self, guerre_des_nains):
        """Ne sont posées que les unités que le moteur sait jouer.

        Les leaders des deux camps et le mage Vorgtd restent en boîte : le moteur ne leur donne
        aucun effet — ni commandement, ni sortilège —, et une unité qui ne fait rien de plus
        qu'une autre encombre la ligne de bataille. Les deux camps se battent donc à armes
        égales, au carton et au terrain.
        """
        posees = set(guerre_des_nains.placement.values())
        assert not [cle for cle in posees if "leader" in cle or "mage" in cle]
        assert all(armee["jeteur_de_sorts"] is None for armee in guerre_des_nains.armees)

    def test_aucune_autre_faction_n_entre_en_jeu(self, guerre_des_nains):
        factions = {CATALOGUE[cle].faction for cle in guerre_des_nains.placement.values()}
        assert factions == {"10-nains", "11-orques"}

    def test_le_potentiel_de_magie_de_chaque_camp_est_note(self, guerre_des_nains):
        """« Le mage Vorgtd (45) » et « un nécromant mineur (20 points de magie) ».

        Les deux nombres restent notés alors qu'aucun jeteur de sorts n'est plus posé : ils
        viennent du fascicule, et c'est ce qu'il faudra dépenser le jour où la magie se jouera.
        """
        assert [armee["magie"] for armee in guerre_des_nains.armees] == [45, 20]

    def test_chaque_ancre_est_tenue(self, guerre_des_nains):
        """L'ancre n'est plus le centre d'un cercle mais le point de départ du déploiement : le
        premier hexagone de la ligne naine, et le fort de l'Orcreich chez les orques. Les deux
        sont occupés — une armée ne se déploie pas depuis une case vide."""
        ancres = [armee["ancre"] for armee in guerre_des_nains.armees]
        assert ancres == [DEBUT_DE_LA_LIGNE, "51,-13,-38"]
        assert guerre_des_nains.placement[DEBUT_DE_LA_LIGNE] == "nains-01-5-infanteries"
        assert guerre_des_nains.placement["51,-13,-38"] == "orques-01-15-infanteries"
        assert CARTE["51,-13,-38"][0] == "fort"

    def test_l_infanterie_naine_tient_la_ligne_demandee(self, guerre_des_nains):
        """La consigne : une ligne de (50,-7,-43) à (45,-8,-37), infanterie d'abord, phalanges
        ensuite. Les cinq infanteries la tiennent depuis le premier bout, les deux phalanges la
        prolongent jusqu'au second — la ligne est occupée de bout en bout, sans trou."""
        segment = ligne_cubique(Hex.depuis_cle(DEBUT_DE_LA_LIGNE),
                                Hex.depuis_cle(FIN_DE_LA_LIGNE))
        poses = [guerre_des_nains.placement.get(case.cle) for case in segment]
        assert poses == ["nains-01-5-infanteries"] * 5 + ["nains-04-5-phalanges"] * 2

    def test_les_arbaletriers_nains_sont_derriere(self, guerre_des_nains):
        """« Arbalétriers derrière » : pas un n'est aussi près des orques que la moindre unité de
        contact — l'arme de tir reste à couvert derrière l'infanterie et les phalanges."""
        orques = cases_de(guerre_des_nains, "11-orques")
        contact = distances(guerre_des_nains, orques, "nains-01", "nains-04")
        arriere = distances(guerre_des_nains, orques, "nains-02", "nains-03")
        assert len(contact) == 10 and len(arriere) == 8
        assert min(arriere) > max(contact)

    def test_l_infanterie_orque_fait_face_aux_nains(self, guerre_des_nains):
        """« L'infanterie fait face aux nains » : tout ce que les nains ont devant eux est de
        l'infanterie — ni archer ni cavalier n'est posé plus près qu'elle."""
        nains = cases_de(guerre_des_nains, "10-nains")
        for case, cle in guerre_des_nains.placement.items():
            if CATALOGUE[cle].faction != "11-orques":
                continue
            if min(Hex.depuis_cle(case).distance(nain) for nain in nains) <= 4:
                assert "infanteries" in cle, case

    def test_les_archers_orques_sont_groupes_derriere(self, guerre_des_nains):
        """« Les archers groupés derrière » : les dix — à pied et montés — ne font qu'un seul
        bloc, et pas un ne devance l'infanterie."""
        nains = cases_de(guerre_des_nains, "10-nains")
        archers = [Hex.depuis_cle(case) for case, cle in guerre_des_nains.placement.items()
                   if "archers" in cle]
        assert len(archers) == 10
        assert d_un_seul_tenant(archers)
        infanterie = distances(guerre_des_nains, nains, "orques-01")
        assert min(case.distance(nain) for case in archers for nain in nains) >= min(infanterie)

    def test_toute_la_cavalerie_orque_est_sur_la_rive_du_lac(self, guerre_des_nains):
        """« Les cavaliers, tous en haut près du lac » : les cinq bordent l'eau, et sont seuls à
        la border — c'est ce qui les distingue des archers montés juste derrière eux."""
        lac = [Hex.depuis_cle(case) for case, elements in CARTE.items() if elements[0] == "lac"]
        au_bord = {case for case, cle in guerre_des_nains.placement.items()
                   if min(Hex.depuis_cle(case).distance(eau) for eau in lac) == 1}
        assert au_bord == {case for case, cle in guerre_des_nains.placement.items()
                           if cle == "orques-02-5-cavaleries"}
        assert len(au_bord) == 5

    def test_chaque_armee_est_d_un_seul_tenant(self, guerre_des_nains):
        """Une armée massée : chaque unité touche au moins une autre de son camp."""
        for faction in ("10-nains", "11-orques"):
            assert d_un_seul_tenant(cases_de(guerre_des_nains, faction)), faction

    def test_les_deux_armees_ne_se_touchent_pas_encore(self, guerre_des_nains):
        """Elles se font face à quelques cases : le premier tour sert à marcher, pas à combattre."""
        nains = cases_de(guerre_des_nains, "10-nains")
        orques = cases_de(guerre_des_nains, "11-orques")
        assert min(nain.distance(orque) for nain in nains for orque in orques) == 3


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
        assert len(plateau.cases_tenues_par(ALLIANCE)) == 18
        assert len(plateau.adversaires_de(ALLIANCE)) == 30

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


def distances(scenario_lu, cibles, *morceaux):
    """Les distances aux `cibles` des unités dont la clé contient l'un des `morceaux`.

    Les morceaux se donnent préfixés de leur faction (« nains-01 » et non « infanteries ») :
    les deux camps ont de l'infanterie, et un morceau trop court prendrait celle d'en face.
    """
    return [min(Hex.depuis_cle(case).distance(cible) for cible in cibles)
            for case, cle in scenario_lu.placement.items()
            if any(morceau in cle for morceau in morceaux)]


def d_un_seul_tenant(cases):
    """Dit si ces hexagones ne font qu'un bloc : on les parcourt de proche en proche."""
    atteints, a_voir = {cases[0]}, [cases[0]]
    while a_voir:
        case = a_voir.pop()
        for voisine in cases:
            if voisine not in atteints and case.distance(voisine) == 1:
                atteints.add(voisine)
                a_voir.append(voisine)
    return len(atteints) == len(cases)


def ligne_cubique(depart, arrivee):
    """Les hexagones traversés en allant de `depart` à `arrivee` en ligne droite.

    L'interpolation se fait sur les trois coordonnées cubiques, puis l'arrondi rétablit
    `q + r + s = 0` en corrigeant celle qui s'en est le plus écartée — c'est le tracé de ligne
    usuel sur une grille hexagonale. Il sert ici à relire la consigne du déploiement : on n'a
    reçu que les deux bouts, et c'est la ligne entre eux qu'il faut retrouver.
    """
    pas = depart.distance(arrivee)
    tracee = []
    for etape in range(pas + 1):
        t = etape / pas
        flottantes = [debut + (fin - debut) * t for debut, fin
                      in ((depart.q, arrivee.q), (depart.r, arrivee.r), (depart.s, arrivee.s))]
        arrondies = [round(valeur) for valeur in flottantes]
        ecarts = [abs(arrondie - flottante)
                  for arrondie, flottante in zip(arrondies, flottantes)]
        derive = ecarts.index(max(ecarts))
        arrondies[derive] = -sum(arrondies[indice] for indice in range(3) if indice != derive)
        tracee.append(Hex(*arrondies))
    return tracee
