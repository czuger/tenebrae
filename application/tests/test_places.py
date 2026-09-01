"""Le registre des places : qui tient quel camp, et ce qu'il refuse.

Ces tests portent sur la classe seule, sans requête ni base : `Places` ne connaît que des
identifiants de joueurs et des noms de camps.
"""

import pytest

from places import Places

ALLIANCE, TENEBRES = "alliance", "tenebres"

NAINE = "100000000000000001"
ORQUE = "100000000000000002"


@pytest.fixture
def table():
    return Places()


def test_une_table_neuve_a_tous_ses_camps_libres(table):
    assert table.est_libre(ALLIANCE) and table.est_libre(TENEBRES)
    assert table.occupant(ALLIANCE) is None


def test_s_asseoir_prend_le_camp(table):
    table.asseoir(ALLIANCE, NAINE)
    assert table.occupant(ALLIANCE) == NAINE
    assert not table.est_libre(ALLIANCE)
    assert table.tient(NAINE, ALLIANCE)


def test_le_camp_d_a_cote_reste_libre(table):
    table.asseoir(ALLIANCE, NAINE)
    assert table.est_libre(TENEBRES)
    assert not table.tient(NAINE, TENEBRES)


def test_une_place_occupee_ne_se_prend_pas(table):
    table.asseoir(ALLIANCE, NAINE)
    with pytest.raises(ValueError):
        table.asseoir(ALLIANCE, ORQUE)
    assert table.occupant(ALLIANCE) == NAINE


def test_se_rasseoir_a_sa_propre_place_ne_change_rien(table):
    table.asseoir(ALLIANCE, NAINE).asseoir(ALLIANCE, NAINE)
    assert table.occupant(ALLIANCE) == NAINE


def test_un_meme_joueur_peut_tenir_les_deux_camps(table):
    """Le registre ne défend qu'un invariant : un camp, un occupant.

    C'est la route qui refuse un second camp à qui en tient déjà un. La suite de tests, elle,
    joue la partie à elle seule des deux côtés — et c'est cette séparation qui le permet.
    """
    table.asseoir(ALLIANCE, NAINE).asseoir(TENEBRES, NAINE)
    assert table.camps_de(NAINE) == [ALLIANCE, TENEBRES]


def test_les_camps_d_un_spectateur_sont_une_liste_vide(table):
    table.asseoir(ALLIANCE, NAINE)
    assert table.camps_de(ORQUE) == []


def test_personne_ne_tient_un_camp_pour_un_joueur_inconnu(table):
    assert table.tient(None, ALLIANCE) is False


def test_liberer_rend_le_camp(table):
    table.asseoir(ALLIANCE, NAINE).liberer(ALLIANCE)
    assert table.est_libre(ALLIANCE)
    assert table.camps_de(NAINE) == []


def test_liberer_un_camp_libre_ne_fait_pas_d_histoire(table):
    table.liberer(ALLIANCE)
    assert table.est_libre(ALLIANCE)


def test_vider_leve_toute_la_table(table):
    table.asseoir(ALLIANCE, NAINE).asseoir(TENEBRES, ORQUE).vider()
    assert table.est_libre(ALLIANCE) and table.est_libre(TENEBRES)


def test_le_registre_se_serialise_et_se_restaure(table):
    table.asseoir(ALLIANCE, NAINE).asseoir(TENEBRES, ORQUE)
    reprise = Places().restaurer(table.en_dict()["places"])
    assert reprise.occupant(ALLIANCE) == NAINE
    assert reprise.occupant(TENEBRES) == ORQUE


def test_restaurer_remplace_les_places_precedentes(table):
    table.asseoir(ALLIANCE, NAINE)
    table.restaurer({TENEBRES: ORQUE})
    assert table.est_libre(ALLIANCE)
    assert table.occupant(TENEBRES) == ORQUE


def test_restaurer_sans_places_leve_la_table(table):
    """Une partie enregistrée avant les joueurs n'a pas de places : elle reste reprenable."""
    table.asseoir(ALLIANCE, NAINE)
    table.restaurer(None)
    assert table.est_libre(ALLIANCE)
