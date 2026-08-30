"""Ce que le serveur envoie : le tirage des pions et les fichiers de la boîte de jeu."""

import json
import re

import app


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
    """Un hexagone de la grille vérifie q + r + s = 0 et figure dans carte.json."""
    carte = json.loads((app.CARTE).read_text(encoding="utf-8"))
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert pion["q"] + pion["r"] + pion["s"] == 0
        assert f"{pion['q']},{pion['r']},{pion['s']}" in carte


def test_aucun_pion_sur_un_terrain_infranchissable(client):
    carte = json.loads((app.CARTE).read_text(encoding="utf-8"))
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        terrain = carte[f"{pion['q']},{pion['r']},{pion['s']}"]
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
