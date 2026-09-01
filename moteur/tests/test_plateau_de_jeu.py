"""Le plateau : les pions posés, leurs camps, et les déplacements qu'il en tire.

Le fichier ne s'appelle pas `test_plateau.py` : `application/tests/` en a déjà un, et pytest
importe les modules de test par leur seul nom de fichier.
"""

import pytest

from moteur.hexagone import CARTE, MOUVEMENT_PAR_DEFAUT, Hex, zone_de_controle
from moteur.pion import ALLIANCE, NEUTRE, TENEBRES, pion
from moteur.plateau import INCLINAISON_MAXIMALE, Plateau
from moteur.tests.plaines import couronne_de, plaine_bien_entouree

ELFE = "elfes-01-5-infanteries"            # alliance, 4 points de mouvement
NAIN = "nains-01-5-infanteries"            # alliance, 3 points
ORQUE = "orques-01-15-infanteries"         # ténèbres, 4 points
CHAUVE_SOURIS = "conjurations-01-6-chauves-souris"  # neutre, 2 points
MARQUEUR = "marqueurs-03-paralysie"        # neutre, immobile

HORS_CARTE = Hex(99, 0, -99)


@pytest.fixture
def terrain():
    """Un coin de plaine nue : le centre A, deux cases de sa couronne, une case au large."""
    a = plaine_bien_entouree()
    c, x1, _, large = couronne_de(a)
    return a, c, x1, large


class TestPositions:
    def test_un_plateau_neuf_est_vide(self):
        plateau = Plateau()
        assert len(plateau) == 0
        assert plateau.pions == {}

    def test_poser_et_retrouver_un_pion(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau()
        plateau.poser(c, pion(ELFE))
        assert plateau.pion_sur(c).cle == ELFE
        assert len(plateau) == 1

    def test_une_case_vide_ne_porte_rien(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        assert plateau.pion_sur(x1) is None

    def test_un_plateau_se_construit_avec_ses_pions(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE)), (x1, pion(ORQUE))])
        assert len(plateau) == 2

    def test_retirer_rend_le_pion(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        assert plateau.retirer(c).cle == ELFE
        assert plateau.pion_sur(c) is None
        assert plateau.retirer(c) is None

    def test_vider_retire_tout(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE)), (x1, pion(ORQUE))])
        plateau.vider()
        assert len(plateau) == 0

    def test_on_ne_pose_pas_hors_de_la_carte(self):
        with pytest.raises(ValueError):
            Plateau().poser(HORS_CARTE, pion(ELFE))

    def test_les_positions_rendues_ne_sont_pas_celles_du_plateau(self, terrain):
        """`pions` est une copie : la modifier ne déplace personne."""
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        plateau.pions.clear()
        assert len(plateau) == 1


class TestCamps:
    def test_les_camps_s_opposent(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE)), (x1, pion(ORQUE))])
        assert plateau.adversaires_de(ALLIANCE) == {x1.cle}
        assert plateau.adversaires_de(TENEBRES) == {c.cle}

    def test_un_camp_ne_s_oppose_pas_a_lui_meme(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE)), (x1, pion(NAIN))])
        assert plateau.adversaires_de(ALLIANCE) == frozenset()
        assert plateau.cases_tenues_par(ALLIANCE) == {c.cle, x1.cle}

    def test_le_neutre_n_a_pas_d_adversaire(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(CHAUVE_SOURIS)), (x1, pion(ORQUE))])
        assert plateau.adversaires_de(NEUTRE) == frozenset()
        assert plateau.zones_de_controle_contre(NEUTRE) == frozenset()

    def test_le_neutre_n_est_l_adversaire_de_personne(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE)), (x1, pion(CHAUVE_SOURIS))])
        assert plateau.adversaires_de(ALLIANCE) == frozenset()


class TestZonesDeControle:
    def test_la_zone_adverse_couvre_les_six_cases_de_l_ennemi(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        assert plateau.zones_de_controle_contre(ALLIANCE) == zone_de_controle([a])

    def test_un_marqueur_n_exerce_aucune_zone(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(MARQUEUR))])
        assert plateau.zones_de_controle_contre(ALLIANCE) == frozenset()

    def test_les_amis_n_exercent_rien_contre_les_leurs(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(NAIN))])
        assert plateau.zones_de_controle_contre(ALLIANCE) == frozenset()


class TestDeplacements:
    def test_le_pion_pose_donne_son_mouvement(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(NAIN))])
        assert plateau.mouvement_de(c) == 3
        assert plateau.deplacements(c) == c.deplacements(3)

    def test_une_case_vide_repond_au_forfait(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau()
        assert plateau.mouvement_de(c) == MOUVEMENT_PAR_DEFAUT
        assert plateau.deplacements(c) == c.deplacements()

    def test_une_case_vide_s_interroge_avec_un_pion(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau()
        assert plateau.mouvement_de(c, pion(NAIN)) == 3
        assert plateau.deplacements(c, pion(NAIN)) == c.deplacements(3)

    def test_le_pion_pose_prime_sur_celui_qu_on_propose(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(NAIN))])
        assert plateau.deplacements(c, pion(ELFE)) == c.deplacements(3)

    def test_un_ennemi_proche_reduit_la_portee(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        seul = plateau.deplacements(c)
        plateau.poser(a, pion(ORQUE))
        assert len(plateau.deplacements(c)) < len(seul)

    def test_on_n_entre_pas_sur_la_case_de_l_ennemi(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        assert a not in plateau.deplacements(c)

    def test_un_ami_ne_gene_pas_le_parcours(self, terrain):
        """Une case amie ne barre pas la route : au-delà, tout reste atteignable."""
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        au_dela = [h for h in plateau.deplacements(c) if h.distance(a) == 1 and h != c]
        plateau.poser(a, pion(NAIN))
        atteints = plateau.deplacements(c)
        assert all(hexagone in atteints for hexagone in au_dela)

    def test_on_ne_s_arrete_pas_sur_une_case_occupee(self, terrain):
        """L'empilement : on traverse un ami, on ne prend pas sa place."""
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(NAIN))])
        assert a not in plateau.deplacements(c)

    def test_le_neutre_va_ou_il_veut(self, terrain):
        """Sans adversaire, ni zone ni case tenue ne l'arrêtent — hors cases occupées."""
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(CHAUVE_SOURIS)), (a, pion(ORQUE))])
        assert plateau.deplacements(c) == [h for h in c.deplacements(2) if h != a]


class TestDeplacer:
    def test_un_deplacement_permis_change_la_case(self, terrain):
        _, c, _, large = terrain
        plateau = Plateau([(c, pion(ELFE))])
        assert plateau.deplacer(c, large) is True
        assert plateau.pion_sur(c) is None
        assert plateau.pion_sur(large).cle == ELFE

    def test_un_deplacement_hors_de_portee_ne_bouge_rien(self, terrain):
        _, c, *_ = terrain
        lointain = next(Hex.depuis_cle(cle) for cle in CARTE
                        if Hex.depuis_cle(cle).distance(c) == 20)
        plateau = Plateau([(c, pion(ELFE))])
        assert plateau.deplacer(c, lointain) is False
        assert plateau.pion_sur(c).cle == ELFE

    def test_on_ne_se_deplace_pas_sur_une_case_tenue(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        assert plateau.deplacer(c, a) is False
        assert plateau.pion_sur(a).cle == ORQUE

    def test_les_zones_suivent_le_pion_deplace(self, terrain):
        """Une fois l'ennemi parti, la portée redevient pleine."""
        a, c, _, large = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        genee = len(plateau.deplacements(c))
        plateau.retirer(a)
        assert len(plateau.deplacements(c)) > genee

    def test_une_case_vide_repond_sans_rien_deplacer(self, terrain):
        _, c, _, large = terrain
        plateau = Plateau()
        assert plateau.deplacer(c, large) is True
        assert len(plateau) == 0


class TestSerialisation:
    """`en_dict` et `restaurer` : la partie tient dans un dict « case → clé de pion »."""

    def test_en_dict_donne_le_format_du_scenario(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        assert plateau.en_dict() == {c.cle: ELFE, a.cle: ORQUE}

    def test_l_aller_retour_repose_les_memes_pions(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        copie = Plateau().restaurer(plateau.en_dict())
        assert copie.en_dict() == plateau.en_dict()
        assert copie.pion_sur(c).cle == ELFE

    def test_restaurer_travaille_en_place_et_ecrase_l_existant(self, terrain):
        a, c, _, large = terrain
        plateau = Plateau([(large, pion(NAIN))])
        rendu = plateau.restaurer({c.cle: ELFE, a.cle: ORQUE})
        assert rendu is plateau
        assert plateau.pion_sur(large) is None
        assert len(plateau) == 2

    def test_un_pion_inconnu_est_refuse_sans_toucher_au_plateau(self, terrain):
        _, c, _, large = terrain
        plateau = Plateau([(large, pion(NAIN))])
        with pytest.raises(KeyError):
            plateau.restaurer({c.cle: "carton-qui-n-existe-pas"})
        assert plateau.pion_sur(large).cle == NAIN

    def test_une_case_hors_carte_est_refusee_sans_toucher_au_plateau(self, terrain):
        _, _, _, large = terrain
        plateau = Plateau([(large, pion(NAIN))])
        with pytest.raises(ValueError):
            plateau.restaurer({HORS_CARTE.cle: ELFE})
        assert plateau.pion_sur(large).cle == NAIN


class TestInclinaisons:
    """L'angle du carton posé : tiré à la pose, retenu, et repris à la restauration.

    Ce n'est pas une règle du fascicule, mais c'est de l'état de partie — voir l'en-tête de
    `moteur/plateau.py` : un pion qui se recouche autrement à chaque relecture du plateau
    trahirait un angle recalculé au lieu d'être retenu.
    """

    def test_poser_couche_le_carton_de_travers(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        assert abs(plateau.inclinaison_sur(c)) <= INCLINAISON_MAXIMALE

    def test_une_case_vide_n_a_pas_d_inclinaison(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        assert plateau.inclinaison_sur(x1) is None

    def test_l_inclinaison_donnee_est_reprise_telle_quelle(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau()
        plateau.poser(c, pion(ELFE), 3.14)
        assert plateau.inclinaison_sur(c) == 3.14

    def test_les_cartons_ne_sont_pas_tous_couches_pareil(self):
        """Une inclinaison figée se verrait : cinquante poses ne donneraient qu'un seul angle."""
        cases = [Hex.depuis_cle(cle) for cle in list(CARTE)[:50]]
        plateau = Plateau([(case, pion(ELFE)) for case in cases])
        assert len(set(plateau.inclinaisons.values())) > len(cases) / 2

    def test_retirer_oublie_l_inclinaison(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        plateau.retirer(c)
        assert plateau.inclinaison_sur(c) is None
        assert plateau.inclinaisons == {}

    def test_vider_oublie_les_inclinaisons(self, terrain):
        _, c, x1, _ = terrain
        plateau = Plateau([(c, pion(ELFE)), (x1, pion(ORQUE))])
        plateau.vider()
        assert plateau.inclinaisons == {}

    def test_les_inclinaisons_rendues_ne_sont_pas_celles_du_plateau(self, terrain):
        _, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE))])
        plateau.inclinaisons.clear()
        assert plateau.inclinaison_sur(c) is not None

    def test_deplacer_recouche_le_carton(self, terrain):
        """Le seul moment où l'angle change : le pion est repris en main."""
        _, c, *_ = terrain
        plateau = Plateau()
        plateau.poser(c, pion(ELFE), 4.2)
        arrivee = plateau.deplacements(c)[0]
        assert plateau.deplacer(c, arrivee) is True
        assert plateau.inclinaison_sur(c) is None
        assert plateau.inclinaison_sur(arrivee) != 4.2
        assert abs(plateau.inclinaison_sur(arrivee)) <= INCLINAISON_MAXIMALE

    def test_un_deplacement_refuse_ne_recouche_rien(self, terrain):
        """Hors de portée, le pion ne bouge pas — il ne se recouche donc pas non plus."""
        _, c, *_ = terrain
        plateau = Plateau()
        plateau.poser(c, pion(ELFE), 4.2)
        assert plateau.deplacer(c, HORS_CARTE) is False
        assert plateau.inclinaison_sur(c) == 4.2

    def test_restaurer_repose_les_cartons_comme_ils_etaient(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau([(c, pion(ELFE)), (a, pion(ORQUE))])
        copie = Plateau().restaurer(plateau.en_dict(), plateau.inclinaisons)
        assert copie.inclinaisons == plateau.inclinaisons

    def test_restaurer_sans_inclinaisons_en_tire_de_neuves(self, terrain):
        """Une sauvegarde d'avant qu'on les retienne reste reprenable."""
        a, c, *_ = terrain
        plateau = Plateau().restaurer({c.cle: ELFE, a.cle: ORQUE})
        assert set(plateau.inclinaisons) == {c.cle, a.cle}
        assert all(abs(angle) <= INCLINAISON_MAXIMALE
                   for angle in plateau.inclinaisons.values())

    def test_une_case_absente_des_inclinaisons_en_recoit_une(self, terrain):
        a, c, *_ = terrain
        plateau = Plateau().restaurer({c.cle: ELFE, a.cle: ORQUE}, {c.cle: 1.5})
        assert plateau.inclinaison_sur(c) == 1.5
        assert plateau.inclinaison_sur(a) is not None
