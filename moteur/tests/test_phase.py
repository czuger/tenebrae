"""La machine à états des phases : l'ordre, la magie sautée, le compte des tours."""

import pytest

from moteur.phase import COMBAT, MOUVEMENT, Tour

CAMPS = ("alliance", "tenebres")
NOMS = {"alliance": "Nains", "tenebres": "Orques"}


@pytest.fixture
def tour():
    return Tour(CAMPS, NOMS)


class TestOrdreDesPhases:
    def test_le_tour_commence_par_le_mouvement_du_premier_joueur(self, tour):
        assert (tour.camp_actif, tour.type_de_phase) == ("alliance", MOUVEMENT)
        assert tour.numero == 1

    def test_la_magie_est_toujours_sautee(self, tour):
        vues = [(tour.camp_actif, tour.type_de_phase)]
        for _ in range(5):
            tour.suivante()
            vues.append((tour.camp_actif, tour.type_de_phase))
        assert vues == [
            ("alliance", MOUVEMENT),
            ("alliance", COMBAT),
            ("tenebres", MOUVEMENT),
            ("tenebres", COMBAT),
            ("alliance", MOUVEMENT),
            ("alliance", COMBAT),
        ]

    def test_un_tour_complet_incremente_le_numero(self, tour):
        tour.suivante()  # combat alliance
        tour.suivante()  # mouvement tenebres
        tour.suivante()  # combat tenebres
        assert tour.numero == 1
        tour.suivante()  # retour au mouvement alliance
        assert tour.numero == 2
        assert (tour.camp_actif, tour.type_de_phase) == ("alliance", MOUVEMENT)


class TestLibelle:
    def test_le_libelle_nomme_la_phase_et_l_armee(self, tour):
        assert tour.libelle == "Phase de mouvement — Nains"
        tour.suivante()
        assert tour.libelle == "Phase de combat — Nains"
        tour.suivante()
        assert tour.libelle == "Phase de mouvement — Orques"

    def test_a_defaut_de_nom_le_camp_fait_office(self):
        assert Tour(CAMPS).libelle == "Phase de mouvement — alliance"


class TestAutorisations:
    def test_le_mouvement_n_est_ouvert_qu_au_camp_actif_en_phase_de_mouvement(self, tour):
        assert tour.autorise_mouvement("alliance")
        assert not tour.autorise_mouvement("tenebres")
        assert not tour.autorise_combat("alliance")

    def test_le_combat_suit_la_phase(self, tour):
        tour.suivante()
        assert tour.autorise_combat("alliance")
        assert not tour.autorise_combat("tenebres")
        assert not tour.autorise_mouvement("alliance")


def test_en_dict_porte_l_essentiel(tour):
    assert Tour(CAMPS, NOMS).en_dict() == {
        "camp": "alliance", "type": MOUVEMENT, "armee": "Nains",
        "libelle": "Phase de mouvement — Nains", "numero": 1,
    }


class TestRestaurer:
    def test_restaurer_ramene_a_la_phase_sauvegardee(self, tour):
        tour.restaurer("tenebres", COMBAT, 7)
        assert (tour.camp_actif, tour.type_de_phase, tour.numero) == ("tenebres", COMBAT, 7)

    def test_l_aller_retour_par_en_dict_retombe_sur_la_meme_phase(self, tour):
        for _ in range(3):
            tour.suivante()
        sauvegarde = tour.en_dict()
        repris = Tour(CAMPS, NOMS).restaurer(
            sauvegarde["camp"], sauvegarde["type"], sauvegarde["numero"])
        assert repris.en_dict() == sauvegarde

    def test_restaurer_travaille_en_place(self, tour):
        assert tour.restaurer("alliance", COMBAT, 2) is tour

    def test_la_magie_est_refusee(self, tour):
        with pytest.raises(ValueError):
            tour.restaurer("alliance", "magie", 1)

    def test_un_camp_inconnu_est_refuse(self, tour):
        with pytest.raises(ValueError):
            tour.restaurer("empire", MOUVEMENT, 1)

    def test_la_partie_reprise_continue_normalement(self, tour):
        tour.restaurer("tenebres", COMBAT, 3)
        tour.suivante()
        assert (tour.camp_actif, tour.type_de_phase, tour.numero) == ("alliance", MOUVEMENT, 4)
