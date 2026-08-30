"""Ce que le serveur envoie : le tirage des pions et les fichiers de la boîte de jeu."""

import json
import re

import pytest

import app
from moteur.hexagone import CARTE, MOUVEMENT_PAR_DEFAUT, Hex
from moteur.pion import ALLIANCE, CATALOGUE, TENEBRES


@pytest.fixture(autouse=True)
def plateau_isole(carte_deserte):
    """Chaque test part d'une carte déserte, et la laisse déserte.

    Le plateau du serveur survit d'une requête à l'autre : sans ce nettoyage, le tirage groupé
    d'un test poserait des adversaires que le test suivant trouverait sous ses pieds. Les tests
    qui veulent un plateau garni chargent « / » eux-mêmes.
    """


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


def test_chaque_pion_tire_porte_son_mouvement(client):
    """Le tirage dit quel pion est posé et de combien de points il dispose."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert pion["cle"] in CATALOGUE
        assert pion["mouvement"] == CATALOGUE[pion["cle"]].points_de_mouvement


def test_chaque_pion_tire_porte_son_camp(client):
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert pion["camp"] == CATALOGUE[pion["cle"]].camp


def test_le_tirage_est_groupe(client):
    """Les dix pions tiennent dans un même secteur : sinon les camps ne se croiseraient pas."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    cases = [Hex(pion["q"], pion["r"], pion["s"]) for pion in pions]
    for case in cases:
        assert all(case.distance(autre) <= 2 * app.RAYON_DU_TIRAGE for autre in cases)


def test_le_tirage_garnit_le_plateau_du_serveur(client):
    """Le serveur retient ce qu'il a posé : c'est de là que sortent les zones de contrôle."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    assert len(app.PLATEAU) == len(pions)
    for pion in pions:
        pose = app.PLATEAU.pion_sur(Hex(pion["q"], pion["r"], pion["s"]))
        assert pose is not None and pose.cle == pion["cle"]


def test_un_nouveau_tirage_remplace_l_ancien(client):
    """Rechargez la page : les pions d'avant ne restent pas sur la carte."""
    client.get("/")
    second = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    attendues = {f"{pion['q']},{pion['r']},{pion['s']}" for pion in second}
    assert app.PLATEAU.pions.keys() == attendues


def test_les_mouvements_du_catalogue_sont_ceux_des_cartons():
    for pion in app.CATALOGUE_DES_PIONS:
        assert pion["mouvement"] == CATALOGUE[pion["cle"]].points_de_mouvement
    mouvements = {pion["cle"]: pion["mouvement"] for pion in app.CATALOGUE_DES_PIONS}
    assert mouvements["reissland-02-8-cavaleries"] == 8       # la cavalerie va loin
    assert mouvements["yzent-05-1-belier"] == 2               # le bélier se traîne
    assert mouvements["marqueurs-03-paralysie"] == 0          # un marqueur ne bouge pas


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


LENT = "yzent-05-1-belier"            # 2 points
RAPIDE = "reissland-02-8-cavaleries"  # 8 points
MARQUEUR = "marqueurs-03-paralysie"   # immobile


def test_les_deplacements_decrivent_le_depart(client):
    reponse = client.get("/deplacements", query_string=PLAINE).json
    assert reponse["depart"] == {**PLAINE, "terrain": "plaine"}
    assert reponse["mouvement"] == MOUVEMENT_PAR_DEFAUT == 5
    assert reponse["pion"] is None


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


def test_le_mouvement_est_celui_du_pion(client):
    """Le pion en main donne le budget : celui du carton, pas le forfait."""
    for cle, attendu in ((LENT, 2), (RAPIDE, 8), (MARQUEUR, 0)):
        reponse = client.get("/deplacements", query_string={**PLAINE, "pion": cle}).json
        assert reponse["pion"] == cle
        assert reponse["mouvement"] == attendu
        assert len(reponse["hexagones"]) == len(Hex(**PLAINE).deplacements(attendu))


def test_le_pion_lent_va_moins_loin_que_le_rapide(client):
    lent = client.get("/deplacements", query_string={**PLAINE, "pion": LENT}).json
    rapide = client.get("/deplacements", query_string={**PLAINE, "pion": RAPIDE}).json
    atteints = {(h["q"], h["r"], h["s"]) for h in lent["hexagones"]}
    assert 0 < len(atteints) < len(rapide["hexagones"])
    assert atteints < {(h["q"], h["r"], h["s"]) for h in rapide["hexagones"]}


def test_un_marqueur_ne_va_nulle_part(client):
    reponse = client.get("/deplacements", query_string={**PLAINE, "pion": MARQUEUR}).json
    assert reponse["hexagones"] == []


def test_un_pion_inconnu_est_refuse(client):
    """Le mouvement vient du catalogue : un pion qui n'y est pas n'a pas de portée."""
    assert client.get("/deplacements",
                      query_string={**PLAINE, "pion": "pion-invente"}).status_code == 400
    assert client.post("/deplacer", json={"depart": PLAINE, "arrivee": VOISINE,
                                          "pion": "pion-invente"}).status_code == 400


def test_le_mouvement_ne_se_demande_pas(client):
    """Le navigateur ne transmet qu'une clé : un budget dans la requête est sans effet."""
    reponse = client.get("/deplacements",
                         query_string={**PLAINE, "pion": LENT, "mouvement": 99}).json
    assert reponse["mouvement"] == 2


# --- Zones de contrôle ----------------------------------------------------------------------

ELFE = "elfes-01-5-infanteries"        # alliance, 4 points
ORQUE = "orques-01-15-infanteries"     # ténèbres, 4 points


def poser(hexagone, cle):
    """Pose un pion sur le plateau du serveur, comme le ferait un tirage."""
    app.PLATEAU.poser(Hex(**hexagone), CATALOGUE[cle])


def test_le_pion_pose_fait_foi(client):
    """La case occupée décide : le pion nommé dans la requête ne s'y substitue pas."""
    poser(PLAINE, ELFE)
    reponse = client.get("/deplacements", query_string={**PLAINE, "pion": LENT}).json
    assert (reponse["pion"], reponse["camp"], reponse["mouvement"]) == (ELFE, ALLIANCE, 4)


def test_une_case_vide_se_laisse_interroger(client):
    reponse = client.get("/deplacements", query_string={**PLAINE, "pion": LENT}).json
    assert (reponse["pion"], reponse["camp"], reponse["mouvement"]) == (LENT, TENEBRES, 2)


def test_un_adversaire_proche_reduit_la_portee(client):
    poser(PLAINE, ELFE)
    seul = client.get("/deplacements", query_string=PLAINE).json["hexagones"]
    poser(VOISINE, ORQUE)
    gene = client.get("/deplacements", query_string=PLAINE).json["hexagones"]
    assert 0 < len(gene) < len(seul)


def test_on_ne_va_pas_sur_la_case_d_un_adversaire(client):
    poser(PLAINE, ELFE)
    poser(VOISINE, ORQUE)
    hexagones = client.get("/deplacements", query_string=PLAINE).json["hexagones"]
    assert VOISINE not in [{"q": h["q"], "r": h["r"], "s": h["s"]} for h in hexagones]
    assert client.post("/deplacer",
                       json={"depart": PLAINE, "arrivee": VOISINE}).json["autorise"] is False


def test_un_ami_ne_reduit_pas_la_portee(client):
    """Deux pions du même camp ne se gênent pas : seule leur case est prise."""
    poser(PLAINE, ELFE)
    seul = client.get("/deplacements", query_string=PLAINE).json["hexagones"]
    poser(VOISINE, "nains-01-5-infanteries")
    avec_l_ami = client.get("/deplacements", query_string=PLAINE).json["hexagones"]
    assert len(avec_l_ami) == len(seul) - 1


def test_un_deplacement_accepte_change_le_plateau(client):
    """Le pion quitte vraiment sa case : les zones du coup d'après en tiennent compte."""
    poser(PLAINE, ELFE)
    assert client.post("/deplacer", json={"depart": PLAINE, "arrivee": VOISINE}).json["autorise"]
    assert app.PLATEAU.pion_sur(Hex(**PLAINE)) is None
    assert app.PLATEAU.pion_sur(Hex(**VOISINE)).cle == ELFE


def test_un_deplacement_refuse_laisse_le_plateau_en_place(client):
    poser(PLAINE, ELFE)
    assert client.post("/deplacer",
                       json={"depart": PLAINE, "arrivee": LOINTAINE}).json["autorise"] is False
    assert app.PLATEAU.pion_sur(Hex(**PLAINE)).cle == ELFE


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


def test_un_deplacement_hors_de_portee_du_pion_est_refuse(client):
    """Une case atteinte par le forfait ne l'est plus si le pion en main est plus lent."""
    loin = next(hexagone for hexagone in Hex(**PLAINE).deplacements(5)
                if hexagone not in Hex(**PLAINE).deplacements(2))
    arrivee = {"q": loin.q, "r": loin.r, "s": loin.s}

    assert client.post("/deplacer", json={"depart": PLAINE, "arrivee": arrivee}).json["autorise"]
    refuse = client.post("/deplacer",
                         json={"depart": PLAINE, "arrivee": arrivee, "pion": LENT}).json
    assert refuse["autorise"] is False
    assert (refuse["pion"], refuse["mouvement"]) == (LENT, 2)


def test_un_marqueur_ne_se_deplace_pas(client):
    reponse = client.post("/deplacer",
                          json={"depart": PLAINE, "arrivee": VOISINE, "pion": MARQUEUR}).json
    assert reponse["autorise"] is False


def test_une_demande_de_deplacement_incomplete_est_refusee(client):
    assert client.post("/deplacer", json={"depart": PLAINE}).status_code == 400
    assert client.post("/deplacer", json={}).status_code == 400
    assert client.post("/deplacer", data="pas du json").status_code == 400
