"""Ce que le serveur envoie : le tirage des pions et les fichiers de la boîte de jeu."""

import json
import re

import app
from moteur.hexagone import CARTE, Hex


def lire_le_champ_cache(page, identifiant):
    """Rend le JSON porté par le champ caché `identifiant`."""
    balise = re.search(rf'<input type="hidden" id="{identifiant}" value="([^"]*)">', page)
    assert balise, f"champ caché « {identifiant} » absent de la page"
    contenu = (balise.group(1)
               .replace("&#34;", '"').replace("&lt;", "<").replace("&gt;", ">")
               .replace("&#39;", "'").replace("&amp;", "&"))
    return json.loads(contenu)


def test_la_page_repond(client):
    reponse = client.get("/")
    assert reponse.status_code == 200


def test_la_page_porte_dix_pions(client):
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    assert len(pions) == app.NOMBRE_DE_PIONS


def test_les_pions_sont_sur_des_hexagones_distincts(client):
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    positions = {(pion["q"], pion["r"], pion["s"]) for pion in pions}
    assert len(positions) == len(pions)


def test_les_coordonnees_sont_cubiques(client):
    """Un hexagone de la grille vérifie q + r + s = 0 et figure sur la carte."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert pion["q"] + pion["r"] + pion["s"] == 0
        assert f"{pion['q']},{pion['r']},{pion['s']}" in CARTE


def test_aucun_pion_sur_un_terrain_infranchissable(client):
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        terrain = CARTE[f"{pion['q']},{pion['r']},{pion['s']}"][0]
        assert terrain not in app.TERRAINS_INTERDITS


def test_les_images_de_pions_existent(client):
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert client.get(f"/pions/{pion['image']}").status_code == 200


def test_le_calage_de_la_grille_est_transmis(client):
    grille = lire_le_champ_cache(client.get("/").get_data(as_text=True), "grille")
    assert grille["origine"] == app.GRILLE_ORIGINE
    assert grille["matrice"] == app.GRILLE_MATRICE
    assert grille["taille_pion"] == app.PION_TAILLE


def test_le_tirage_change_d_un_chargement_a_l_autre(client):
    """Deux tirages de dix pions parmi 2008 hexagones ne doivent pas coïncider."""
    premier = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    second = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    assert premier != second


def test_la_carte_est_servie(client):
    reponse = client.get("/carte.jpg")
    assert reponse.status_code == 200
    assert reponse.headers["Content-Type"] == "image/jpeg"


def test_les_vues_d_ensemble_ne_sont_pas_servies(client):
    """Planches entières et planchettes de suivi ne sont pas des pions : ni servies, ni tirées."""
    for chemin in ("21-vues-d-ensemble/vues-d-ensemble-01-planches-de-pions.jpg",
                   "19-magiciens/magiciens-02-pions-de-magiciens-et-clercs-vue-d-ensemble.jpg"):
        assert (app.PIONS / chemin).exists()
        assert client.get(f"/pions/{chemin}").status_code == 404
        assert chemin not in [pion["chemin"] for pion in app.CATALOGUE_DES_PIONS]


def test_le_catalogue_couvre_les_pions_de_la_boite():
    """127 photos dans game_box/pions, moins les 4 planches et les 2 planchettes de suivi."""
    assert len(app.CATALOGUE_DES_PIONS) == 121
    assert all((app.PIONS / pion["chemin"]).exists() for pion in app.CATALOGUE_DES_PIONS)


def test_les_noms_de_pions_sont_lisibles():
    noms = {pion["chemin"]: pion["nom"] for pion in app.CATALOGUE_DES_PIONS}
    assert noms["01-yzent/yzent-05-1-belier.jpg"] == "yzent · 1 belier"
    assert noms["06-empire-de-lynn/empire-de-lynn-08-3-chars-legers.jpg"] == (
        "empire de lynn · 3 chars legers"
    )


def test_on_ne_sort_pas_du_repertoire_des_pions(client):
    assert client.get("/pions/../../CLAUDE.md").status_code == 404


# --- Déplacements ---------------------------------------------------------------------------

PLAINE = {"q": 1, "r": 26, "s": -27}
VOISINE = {"q": 2, "r": 26, "s": -28}
LOINTAINE = {"q": 30, "r": 2, "s": -32}


def test_les_deplacements_decrivent_le_depart(client):
    reponse = client.get("/deplacements", query_string=PLAINE).json
    assert reponse["depart"] == {**PLAINE, "terrain": "plaine"}
    assert reponse["mouvement"] == 5


def test_les_deplacements_sont_ceux_du_moteur(client):
    """La route n'ajoute aucune règle : elle expose Hex.deplacements()."""
    attendus = {(h.q, h.r, h.s) for h in Hex(**PLAINE).deplacements()}
    rendus = {(h["q"], h["r"], h["s"])
              for h in client.get("/deplacements", query_string=PLAINE).json["hexagones"]}
    assert rendus == attendus and rendus


def test_les_hexagones_rendus_portent_leur_terrain(client):
    for hexagone in client.get("/deplacements", query_string=PLAINE).json["hexagones"]:
        assert hexagone["q"] + hexagone["r"] + hexagone["s"] == 0
        assert hexagone["terrain"] == CARTE[f"{hexagone['q']},{hexagone['r']},{hexagone['s']}"][0]


def test_le_depart_ne_figure_pas_dans_ses_propres_deplacements(client):
    hexagones = client.get("/deplacements", query_string=PLAINE).json["hexagones"]
    assert PLAINE not in [{"q": h["q"], "r": h["r"], "s": h["s"]} for h in hexagones]


def test_des_coordonnees_illisibles_sont_refusees(client):
    assert client.get("/deplacements", query_string={"q": "a", "r": 0, "s": 0}).status_code == 400
    assert client.get("/deplacements", query_string={"q": 1, "r": 26}).status_code == 400
    assert client.get("/deplacements",
                      query_string={"q": 1, "r": 26, "s": 0}).status_code == 400


def test_un_hexagone_hors_carte_est_introuvable(client):
    assert client.get("/deplacements",
                      query_string={"q": 99, "r": 0, "s": -99}).status_code == 404


def test_un_deplacement_a_portee_est_autorise(client):
    reponse = client.post("/deplacer", json={"depart": PLAINE, "arrivee": VOISINE}).json
    assert reponse["autorise"] is True
    assert reponse["arrivee"] == {**VOISINE, "terrain": "plaine"}


def test_un_deplacement_hors_de_portee_est_refuse(client):
    reponse = client.post("/deplacer", json={"depart": PLAINE, "arrivee": LOINTAINE}).json
    assert reponse["autorise"] is False


def test_on_ne_se_deplace_pas_sur_place(client):
    assert client.post("/deplacer", json={"depart": PLAINE, "arrivee": PLAINE}).json["autorise"] is False


def test_une_demande_de_deplacement_incomplete_est_refusee(client):
    assert client.post("/deplacer", json={"depart": PLAINE}).status_code == 400
    assert client.post("/deplacer", json={}).status_code == 400
    assert client.post("/deplacer", data="pas du json").status_code == 400
