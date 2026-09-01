"""Le journal de la partie tel que le serveur le sert : ses lignes, et le moment où elles partent.

Le journal n'était qu'un fichier local ; il est maintenant montré, en colonne sous la fiche. Deux
choses sont à éprouver de ce côté-ci — que la page et le flux le portent, et qu'une ligne écrite
au moment d'un coup **parte avec ce coup-là**. Le second point tient à un ordre d'appels :
`marquer_un_coup` photographie la partie, journal compris, et toute route qui journalise après
avoir sauvegardé pousserait aux navigateurs un compte rendu en retard d'un coup.

Le rendu de la colonne, lui, est dans `test_journal_navigateur.py`.
"""

import pytest

import app
from flux import Diffuseur
from moteur import combat
from moteur.hexagone import Hex
from moteur.pion import CATALOGUE

from test_serveur import lire_le_champ_cache

PLAINE = {"q": 1, "r": 26, "s": -27}
VOISINE = {"q": 2, "r": 26, "s": -28}

NAIN = "nains-01-5-infanteries"   # alliance, force 12
ARCHER = "yzent-03-8-archers"     # ténèbres, force 2 → rapport 6-1, dé 1 → DE


@pytest.fixture(autouse=True)
def plateau_isole(carte_deserte):
    """Chaque test part d'une carte déserte, comme dans `test_serveur.py`."""


@pytest.fixture(autouse=True)
def journal_vide():
    """Un journal vide au départ, et vide en sortant.

    La file est un module-global, et elle traverse les tests : sans ce nettoyage, un test lirait
    les lignes écrites par tous ceux qui l'ont précédé — à commencer par les tests de navigateur.
    """
    app.MEMOIRE_DU_JOURNAL.lignes.clear()
    yield app.MEMOIRE_DU_JOURNAL.lignes
    app.MEMOIRE_DU_JOURNAL.lignes.clear()


@pytest.fixture(autouse=True)
def diffuseur_neuf(monkeypatch):
    """Un diffuseur à soi : les tests de navigateur laissent des flux ouverts derrière eux, et
    on veut ici lire ce qui est publié, pas le partager (voir `test_flux.py`)."""
    monkeypatch.setattr(app, "DIFFUSEUR", Diffuseur())


def poser(hexagone, cle):
    app.PLATEAU.poser(Hex(**hexagone), CATALOGUE[cle])


def textes(lignes):
    return [ligne["texte"] for ligne in lignes]


# --- Ce que le journal retient -----------------------------------------------------------------

def test_une_ligne_journalisee_porte_son_heure_et_son_texte():
    app.JOURNAL.info("Phase : %s (tour %s)", "Phase de combat — Nains", 3)
    ligne = app.les_lignes_du_journal()[-1]
    assert ligne["texte"] == "Phase : Phase de combat — Nains (tour 3)"
    assert len(ligne["heure"].split(":")) == 3


def test_le_journal_ne_garde_que_ses_dernieres_lignes():
    """Un serveur qui tourne longtemps ne doit pas enfler d'une ligne par clic refusé."""
    for numero in range(app.LIGNES_RETENUES + 10):
        app.JOURNAL.info("ligne %s", numero)
    lignes = app.les_lignes_du_journal()
    assert len(lignes) == app.LIGNES_RETENUES
    assert lignes[0]["texte"] == "ligne 10"
    assert lignes[-1]["texte"] == f"ligne {app.LIGNES_RETENUES + 9}"


def test_les_lignes_servies_sont_une_copie():
    """La file continue de tourner pendant que le message voyage : on n'en donne pas la référence."""
    app.JOURNAL.info("première")
    lignes = app.les_lignes_du_journal()
    app.JOURNAL.info("seconde")
    assert textes(lignes) == ["première"]


# --- Ce que la page et le flux en portent -------------------------------------------------------

def test_la_page_porte_le_journal(client):
    app.JOURNAL.info("Nouvelle partie : scénario 4")
    porte = lire_le_champ_cache(client.get("/").get_data(as_text=True), "journal-initial")
    assert "Nouvelle partie : scénario 4" in textes(porte)


def test_l_etat_de_la_partie_porte_le_journal(client):
    app.JOURNAL.info("Combat résolu : Défenseur Éliminé — dé 1, rapport 6-1")
    etat = client.get("/partie/etat").json
    assert etat["change"] is True
    assert textes(etat["journal"])[-1] == "Combat résolu : Défenseur Éliminé — dé 1, rapport 6-1"


def test_l_instantane_partage_porte_le_journal():
    """C'est cet instantané-là qui voyage dans le flux : le journal y est, comme les pions."""
    app.JOURNAL.info("Phase : Phase de combat — Nains (tour 1)")
    assert textes(app.instantane_partage()["journal"]) == ["Phase : Phase de combat — Nains (tour 1)"]


# --- Le détail du calcul du rapport ------------------------------------------------------------
#
# La phrase seule, sur un détail fabriqué : ce qui se passe sur la carte est éprouvé dans
# `moteur/tests/test_combat.py`, ce qui part au journal plus bas.

def phrase(forces, force_de_la_cible, terrain, multiplicateur, bonus_au_de, jet):
    """La ligne que le journal écrirait pour ce calcul-là."""
    detail = combat.DetailDuRapport(forces, force_de_la_cible, terrain, multiplicateur,
                                    bonus_au_de, jet)
    return app.detailler_le_rapport(
        combat.ResultatDeCombat(detail.issue, [], detail.rapport, detail.de, detail))


def test_le_terrain_est_nomme_meme_quand_il_ne_fait_rien():
    """C'est ce qu'on est venu chercher : la plaine se dit, comme la montagne."""
    assert phrase([12], 2, "plaine", 1, 0, 1) \
        == "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1"


def test_le_terrain_qui_multiplie_montre_son_calcul():
    assert phrase([12], 8, "montagne", 3, 0, 4) \
        == "Rapport 1-2 : attaque 12 contre défense 8 × 3 = 24 (montagne) — dé 4"


def test_un_groupe_d_attaquants_montre_ses_forces_une_a_une():
    assert phrase([12, 8], 8, "montagne", 3, 0, 4) \
        == "Rapport 1-2 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4"


def test_le_terrain_qui_ajoute_au_de_montre_son_calcul():
    assert phrase([12], 7, "bois", 2, 2, 3) \
        == "Rapport 1-2 : attaque 12 contre défense 7 × 2 = 14 (bois) — dé 3 + 2 = 5"


def test_un_de_hors_du_tableau_dit_qu_il_y_est_ramene():
    """Le Tableau I n'a que six lignes : sans cela, l'addition paraîtrait fausse."""
    assert phrase([12], 2, "colline", 1, 2, 6) \
        == "Rapport 6-1 : attaque 12 contre défense 2 (colline) — dé 6 + 2 = 8, ramené à 6"


# --- Journaliser avant de marquer le coup -------------------------------------------------------
#
# Ce que chaque test vérifie : la ligne du coup est **dans l'état publié par ce coup-là**, et non
# dans le suivant. On s'abonne au diffuseur, on joue, et on lit ce qui a été déposé.

def dernier_publie(abonne):
    """Le dernier état déposé chez cet abonné. La boîte n'en garde qu'un — le plus récent."""
    etat = abonne.attendre(0)
    assert etat is not None, "aucun coup n'a été publié"
    return etat


@pytest.fixture
def abonne():
    """Un flux ouvert sur la partie, sans navigateur : la boîte où le serveur dépose ses états."""
    return app.DIFFUSEUR.abonner()


def test_le_changement_de_phase_part_avec_sa_ligne(client, abonne):
    client.post("/phase/suivante")
    assert textes(dernier_publie(abonne)["journal"])[-1] \
        == "Phase : Phase de combat — Nains (tour 1)"


def test_le_combat_part_avec_son_calcul_et_son_resultat(client, abonne, monkeypatch):
    """Deux lignes, et dans cet ordre : le calcul, puis l'issue.

    L'ordre n'est pas indifférent — la colonne du navigateur se lit à l'envers du fichier, et
    c'est ce qui met l'issue en tête, son détail juste dessous.
    """
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    poser(PLAINE, NAIN)       # force 12
    poser(VOISINE, ARCHER)    # force 2, en plaine → rapport 6-1, dé 1 → DE
    client.post("/phase/suivante")  # phase de combat des Nains
    assert client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json["resolu"]
    assert textes(dernier_publie(abonne)["journal"])[-2:] == [
        "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1",
        "Combat résolu : Défenseur Éliminé",
    ]


def test_la_place_prise_part_avec_sa_ligne(application, client_anonyme, abonne,
                                           installer_le_joueur):
    """La table est faite de places : les prendre est un coup, et il se raconte comme un autre."""
    identite = installer_le_joueur(application, client_anonyme, camps=[])
    reponse = client_anonyme.post("/partie/place", json={"camp": "alliance"})
    assert reponse.json["assis"] is True
    assert textes(dernier_publie(abonne)["journal"])[-1] \
        == f"Place prise : alliance par {identite['pseudo']}"


def test_la_partie_neuve_part_avec_sa_ligne(client, abonne):
    client.post("/partie/nouvelle")
    assert "Nouvelle partie : scénario 4" in textes(dernier_publie(abonne)["journal"])
