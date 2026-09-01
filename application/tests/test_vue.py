"""La vue de la carte : ce que le serveur en retient, et ce qu'il en rend au chargement suivant.

La carte fait 6173 × 5102 px et l'on y joue approché : chaque rechargement ramenait le joueur à
l'ajustement, la carte entière dans la fenêtre. Le serveur retient donc, par joueur, l'échelle et
le point qu'il avait au centre (`application/models/vue.py`).

Ce qui se passe dans le navigateur — relever la vue, la reposer — est dans
`test_vue_navigateur.py` ; ce que MongoDB en fait, dans `test_persistance.py`.
"""

import pytest

import app

from test_serveur import lire_le_champ_cache

# Un second compte, pour éprouver qu'une vue n'appartient qu'à une paire d'yeux.
AUTRE_IDENTITE = {"discord_id": "100000000000000002", "pseudo": "Adversaire", "avatar": None,
                  "nom_affiche": None, "courriel": None}

UNE_VUE = {"echelle": 0.42, "x": 1234.5, "y": 678.25, "ajustee": False}


@pytest.fixture(autouse=True)
def vues_vides(application):
    """Le dépôt de vues vit aussi longtemps que l'application, que la suite construit une seule
    fois : sans ce nettoyage, chaque test hériterait des vues du précédent."""
    application.extensions["depot_de_vues"].vider()
    yield application.extensions["depot_de_vues"]
    application.extensions["depot_de_vues"].vider()


def vue_de_la_page(client):
    return lire_le_champ_cache(client.get("/").get_data(as_text=True), "vue")


# --- Ce que la page porte -----------------------------------------------------------------------

def test_la_page_n_a_pas_de_vue_a_rendre_a_un_anonyme(client_anonyme):
    """Un visiteur de passage n'a nulle part où la ranger : la carte s'ouvre ajustée."""
    assert vue_de_la_page(client_anonyme) is None


def test_la_page_n_a_pas_de_vue_a_rendre_a_qui_n_a_rien_regle(client):
    assert vue_de_la_page(client) is None


def test_la_page_rend_la_vue_reglee(client):
    assert client.post("/vue", json=UNE_VUE).status_code == 200
    assert vue_de_la_page(client) == UNE_VUE


# --- Ce que la route accepte --------------------------------------------------------------------

def test_la_vue_reglee_est_rendue_telle_quelle(client):
    assert client.post("/vue", json=UNE_VUE).json == UNE_VUE


def test_un_anonyme_ne_peut_rien_ranger(client_anonyme):
    reponse = client_anonyme.post("/vue", json=UNE_VUE)
    assert reponse.status_code == 401
    assert reponse.json["autorise"] is False


def test_une_place_n_est_pas_demandee(application, client_anonyme, installer_le_joueur):
    """On retient la vue d'un spectateur connecté comme celle d'un joueur assis."""
    installer_le_joueur(application, client_anonyme, camps=[])
    assert client_anonyme.post("/vue", json=UNE_VUE).status_code == 200


@pytest.mark.parametrize("corps", [
    {},                                                    # rien
    {"echelle": 0.4, "x": 10},                             # un champ manque
    {"echelle": "beaucoup", "x": 10, "y": 20},             # pas un nombre
    {"echelle": float("inf"), "x": 10, "y": 20},           # pas un nombre fini
    {"echelle": float("nan"), "x": 10, "y": 20},
    [1, 2, 3],                                             # pas même un objet
])
def test_une_vue_illisible_est_refusee(client, corps):
    """Le corps vient du dehors : on n'y prend que ce qu'on attend."""
    assert client.post("/vue", json=corps).status_code == 400


def test_l_ajustement_est_un_booleen_et_se_passe_de_valeur(client):
    """Absent, il vaut « non » : une vue rangée sans le dire n'est pas un ajustement."""
    assert client.post("/vue", json={"echelle": 0.4, "x": 10, "y": 20}).json["ajustee"] is False
    assert client.post("/vue", json={**UNE_VUE, "ajustee": 1}).json["ajustee"] is True


def test_les_entiers_sont_admis_et_ranges_en_nombres(client):
    """Le navigateur envoie parfois des entiers ronds : ils ne doivent pas être refusés."""
    assert client.post("/vue", json={"echelle": 1, "x": 0, "y": 0}).json \
        == {"echelle": 1.0, "x": 0.0, "y": 0.0, "ajustee": False}


# --- À qui elle appartient ----------------------------------------------------------------------

def test_chaque_joueur_a_la_sienne(application, client, client_anonyme, installer_le_joueur):
    """Deux joueurs devant la même partie ne regardent pas le même coin de carte."""
    autre = application.test_client()
    installer_le_joueur(application, autre, identite=AUTRE_IDENTITE, camps=[])
    client.post("/vue", json=UNE_VUE)
    autre_vue = {"echelle": 1.0, "x": 10.0, "y": 20.0, "ajustee": False}
    autre.post("/vue", json=autre_vue)
    assert vue_de_la_page(client) == UNE_VUE
    assert vue_de_la_page(autre) == autre_vue


def test_regler_deux_fois_ecrase_la_precedente(client):
    """On ne garde pas d'historique de zoom : un document par joueur."""
    client.post("/vue", json=UNE_VUE)
    derniere = {"echelle": 0.1, "x": 1.0, "y": 2.0, "ajustee": True}
    client.post("/vue", json=derniere)
    assert vue_de_la_page(client) == derniere


# --- Ce qu'elle n'est pas -----------------------------------------------------------------------

def test_regler_sa_vue_n_est_pas_un_coup_joue(client):
    """Ni la version ne monte, ni rien n'est poussé aux flux : la vue de l'un ne doit pas faire
    sauter la carte de l'autre."""
    client.get("/")
    abonne = app.DIFFUSEUR.abonner()
    try:
        version = app.VERSION
        assert client.post("/vue", json=UNE_VUE).status_code == 200
        assert app.VERSION == version
        assert abonne.attendre(0) is None
    finally:
        app.DIFFUSEUR.radier(abonne)


def test_la_vue_ne_voyage_pas_avec_la_partie(client):
    """`/partie/etat` dit ce que **tous** les spectateurs ont en commun ; la vue n'en est pas."""
    client.post("/vue", json=UNE_VUE)
    assert "vue" not in client.get("/partie/etat").json
    assert "vue" not in app.instantane_partage()
