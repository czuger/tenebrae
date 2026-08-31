"""Ce que le serveur envoie : la mise en place du scénario et les fichiers de la boîte de jeu."""

import json
import re

import pytest

import app
from moteur.hexagone import CARTE, MOUVEMENT_PAR_DEFAUT, Hex
from moteur.pion import ALLIANCE, CATALOGUE, TENEBRES


@pytest.fixture(autouse=True)
def plateau_isole(carte_deserte):
    """Chaque test part d'une carte déserte, et la laisse déserte.

    Le plateau du serveur survit d'une requête à l'autre : sans ce nettoyage, les cinquante-deux
    unités du scénario resteraient sous les pieds du test suivant. Les tests qui veulent un
    plateau garni chargent « / » eux-mêmes.
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


def test_la_page_porte_les_deux_armees_du_scenario(client):
    """Le scénario n° 4 met 21 nains face à 31 orques : la page les porte toutes."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    assert len(pions) == len(app.SCENARIO) == 52
    camps = [pion["camp"] for pion in pions]
    assert camps.count(ALLIANCE) == 21
    assert camps.count(TENEBRES) == 31


def test_la_page_pose_chaque_pion_sur_la_case_du_scenario(client):
    """Le serveur n'invente rien : il sert le placement fixé dans `scenarios/`."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    pose = {f"{pion['q']},{pion['r']},{pion['s']}": pion["cle"] for pion in pions}
    assert pose == app.SCENARIO.placement


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


def test_chaque_pion_pose_porte_son_mouvement(client):
    """La mise en place dit quel pion est posé et de combien de points il dispose."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert pion["cle"] in CATALOGUE
        assert pion["mouvement"] == CATALOGUE[pion["cle"]].points_de_mouvement


def test_chaque_pion_pose_porte_son_camp(client):
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        assert pion["camp"] == CATALOGUE[pion["cle"]].camp


def test_chaque_pion_pose_porte_les_valeurs_de_son_carton(client):
    """La fiche du survol se lit dans le champ caché : tout le carton doit y être.

    Les valeurs absentes du carton partent à `None` — c'est le navigateur qui les rend par un
    tiret. `mouvement`, lui, reste le budget de déplacement, celui dont le moteur se sert, et non
    la valeur brute que `pions.json` laisse parfois vide.
    """
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    for pion in pions:
        pose = CATALOGUE[pion["cle"]]
        assert pion["faction"] == pose.faction
        assert pion["symbole"] == pose.symbole
        assert pion["force"] == pose.force
        assert pion["tir"] == pose.tir
        assert pion["portee"] == pose.portee
        assert pion["mouvement_vol"] == pose.mouvement_vol
        assert pion["facultes_speciales"] == pose.facultes_speciales
        assert pion["remarques"] == pose.remarques
        assert pion["mouvement"] == pose.points_de_mouvement


def test_les_valeurs_du_carton_sont_celles_lues_sur_les_photos(client):
    """Deux pions du scénario, relevés dans `game_box/pions/pions.json`."""
    pions = {pion["cle"]: pion
             for pion in lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")}

    leaders = pions["nains-05-2-leaders"]
    assert (leaders["force"], leaders["tir"], leaders["portee"]) == (25, 5, 10)
    assert leaders["symbole"] == "leader"

    infanteries = pions["orques-01-15-infanteries"]
    assert infanteries["symbole"] == "infanterie"
    assert (infanteries["tir"], infanteries["portee"], infanteries["mouvement_vol"]) == (
        None, None, None)


def test_la_mise_en_place_garnit_le_plateau_du_serveur(client):
    """Le serveur retient ce qu'il a posé : c'est de là que sortent les zones de contrôle."""
    pions = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    assert len(app.PLATEAU) == len(pions)
    for pion in pions:
        pose = app.PLATEAU.pion_sur(Hex(pion["q"], pion["r"], pion["s"]))
        assert pose is not None and pose.cle == pion["cle"]


def test_recharger_la_page_remet_les_pions_a_leur_place(client):
    """Un pion déplacé revient à sa case de départ au rechargement : la mise en place est fixe."""
    depart = Hex.depuis_cle(next(iter(app.SCENARIO.placement)))
    client.get("/")
    arrivee = app.PLATEAU.deplacements(depart)[0]
    assert app.PLATEAU.deplacer(depart, arrivee)

    client.get("/")
    assert app.PLATEAU.pion_sur(arrivee) is None
    assert app.PLATEAU.pions.keys() == app.SCENARIO.placement.keys()


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


def test_la_mise_en_place_ne_change_pas_d_un_chargement_a_l_autre(client):
    """Un scénario fixé se rejoue à l'identique : c'est ce qu'on lui demande."""
    premier = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    second = lire_le_champ_cache(client.get("/").get_data(as_text=True), "pions")
    assert premier == second


def test_la_carte_est_servie(client):
    reponse = client.get("/carte.jpg")
    assert reponse.status_code == 200
    assert reponse.headers["Content-Type"] == "image/jpeg"


def test_les_vues_d_ensemble_ne_sont_pas_servies(client):
    """Planches entières et planchettes de suivi ne sont pas des pions : ni servies, ni posées."""
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


# --- Phases de jeu --------------------------------------------------------------------------

NAIN = "nains-01-5-infanteries"        # alliance, force 12
ARCHER = "yzent-03-8-archers"          # ténèbres, force 2, tir 4, portée 3


def test_la_page_porte_la_phase_courante(client):
    phase = lire_le_champ_cache(client.get("/").get_data(as_text=True), "phase")
    assert phase == {"camp": ALLIANCE, "type": "mouvement", "armee": "Nains",
                     "libelle": "Phase de mouvement — Nains", "numero": 1,
                     "indisponibles": {"attaquants": [], "cibles": []}}


def test_phase_suivante_saute_la_magie_et_alterne_les_joueurs(client):
    suite = [client.post("/phase/suivante").json for _ in range(4)]
    assert [(p["armee"], p["type"]) for p in suite] == [
        ("Nains", "combat"), ("Orques", "mouvement"), ("Orques", "combat"), ("Nains", "mouvement")]
    assert suite[-1]["numero"] == 2


def test_le_mouvement_est_bloque_hors_de_sa_phase(client):
    poser(PLAINE, NAIN)
    client.post("/phase/suivante")  # phase de combat des Nains
    refuse = client.post("/deplacer", json={"depart": PLAINE, "arrivee": VOISINE}).json
    assert refuse["autorise"] is False
    assert app.PLATEAU.pion_sur(Hex(**PLAINE)).cle == NAIN


def test_le_mouvement_est_bloque_pour_le_camp_inactif(client):
    poser(PLAINE, ARCHER)  # une unité des ténèbres, alors que c'est le tour des Nains
    refuse = client.post("/deplacer", json={"depart": PLAINE, "arrivee": VOISINE}).json
    assert refuse["autorise"] is False


# --- Résolution des combats ----------------------------------------------------------------

def test_la_portee_de_combat_suit_la_distance(client):
    poser(PLAINE, ARCHER)
    reponse = client.get("/combat/portee", query_string={
        "cq": VOISINE["q"], "cr": VOISINE["r"], "cs": VOISINE["s"],
        "aq": PLAINE["q"], "ar": PLAINE["r"], "as": PLAINE["s"]}).json
    assert reponse["a_portee"] is True
    loin = client.get("/combat/portee", query_string={
        "cq": LOINTAINE["q"], "cr": LOINTAINE["r"], "cs": LOINTAINE["s"],
        "aq": PLAINE["q"], "ar": PLAINE["r"], "as": PLAINE["s"]}).json
    assert loin["a_portee"] is False
    assert loin["message"] == "Cette unité n'est pas à portée de la cible"


def test_un_combat_hors_phase_est_refuse(client):
    poser(PLAINE, NAIN)
    poser(VOISINE, ARCHER)
    reponse = client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json
    assert reponse["resolu"] is False


def test_un_combat_gagne_retire_le_defenseur(client, monkeypatch):
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    poser(PLAINE, NAIN)       # force 12
    poser(VOISINE, ARCHER)    # force 2, ténèbres → rapport 6-1, dé 1 → DE
    client.post("/phase/suivante")  # phase de combat des Nains
    reponse = client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json
    assert reponse["resolu"] is True
    assert reponse["resultat"] == "DE"
    assert reponse["message"] == "Combat résolu : Défenseur Éliminé"
    assert reponse["elimines"] == [{**VOISINE, "terrain": "plaine"}]
    assert app.PLATEAU.pion_sur(Hex(**VOISINE)) is None
    assert app.PLATEAU.pion_sur(Hex(**PLAINE)).cle == NAIN


def test_un_recul_ne_change_rien_au_plateau(client, monkeypatch):
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    poser(PLAINE, NAIN)                       # force 12
    poser(VOISINE, ORQUE)                     # force 8 → rapport 1-1, dé 1 → DR
    client.post("/phase/suivante")
    reponse = client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json
    assert reponse["resultat"] in ("AR", "DR")
    assert app.PLATEAU.pion_sur(Hex(**VOISINE)).cle == ORQUE
    assert app.PLATEAU.pion_sur(Hex(**PLAINE)).cle == NAIN


def test_un_attaquant_hors_de_portee_ne_resout_pas_le_combat(client):
    poser(LOINTAINE, NAIN)
    poser(VOISINE, ORQUE)
    client.post("/phase/suivante")
    reponse = client.post("/combat", json={"cible": VOISINE, "attaquants": [LOINTAINE]}).json
    assert reponse["resolu"] is False
    assert app.PLATEAU.pion_sur(Hex(**VOISINE)).cle == ORQUE


def test_la_cible_doit_etre_adverse(client):
    poser(PLAINE, NAIN)
    poser(VOISINE, "nains-01-5-infanteries")
    client.post("/phase/suivante")
    reponse = client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json
    assert reponse["resolu"] is False


# --- Un seul combat par unité et par phase -------------------------------------------------

# Deux cases de plus au contact : un second orque à portée du nain de PLAINE, et un second nain à
# portée de l'orque de VOISINE. De quoi éprouver les deux règles séparément.
CONTACT = {"q": 1, "r": 27, "s": -28}
APPUI = {"q": 2, "r": 27, "s": -29}

# Un dé de 1 sur NAIN 12 contre ORQUE 8 donne un rapport 1-1 : un recul, que le moteur laisse sans
# effet. Les deux unités survivent donc au combat — et doivent pourtant en rester marquées.
UN_RECUL = 1


@pytest.fixture
def phase_de_combat(client, monkeypatch):
    """Passe en phase de combat des Nains, le dé fixé sur un recul : personne n'est éliminé."""
    monkeypatch.setattr(app, "lancer_le_de", lambda: UN_RECUL)
    client.post("/phase/suivante")
    return client


def test_un_attaquant_ne_peut_pas_attaquer_deux_fois(phase_de_combat):
    """Même sans effet — un recul —, le combat a eu lieu : l'attaquant a donné pour la phase."""
    poser(PLAINE, NAIN)
    poser(VOISINE, ORQUE)
    poser(CONTACT, ORQUE)
    premier = phase_de_combat.post("/combat",
                                   json={"cible": VOISINE, "attaquants": [PLAINE]}).json
    assert premier["resolu"] is True
    assert premier["resultat"] in ("AR", "DR")

    second = phase_de_combat.post("/combat", json={"cible": CONTACT, "attaquants": [PLAINE]}).json
    assert second["resolu"] is False
    assert app.DEJA_ATTAQUE in second["messages"]
    assert app.PLATEAU.pion_sur(Hex(**CONTACT)).cle == ORQUE


def test_une_cible_ne_peut_pas_etre_attaquee_deux_fois(phase_de_combat):
    """Même par un autre attaquant : c'est la cible qui est consommée, pas le couple."""
    poser(PLAINE, NAIN)
    poser(APPUI, NAIN)
    poser(VOISINE, ORQUE)
    assert phase_de_combat.post("/combat",
                                json={"cible": VOISINE, "attaquants": [PLAINE]}).json["resolu"]

    second = phase_de_combat.post("/combat", json={"cible": VOISINE, "attaquants": [APPUI]}).json
    assert second["resolu"] is False
    assert second["message"] == app.DEJA_ATTAQUEE


def test_tout_le_groupe_d_attaquants_est_marque(phase_de_combat):
    """Attaquer à deux engage les deux, pas seulement celui qui a été désigné le premier."""
    poser(PLAINE, NAIN)
    poser(APPUI, NAIN)
    poser(VOISINE, ORQUE)
    poser(CONTACT, ORQUE)
    phase_de_combat.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE, APPUI]})

    for depart in (PLAINE, APPUI):
        refus = phase_de_combat.post("/combat",
                                     json={"cible": CONTACT, "attaquants": [depart]}).json
        assert refus["resolu"] is False, depart


def test_deux_unites_du_meme_carton_sont_suivies_a_part(phase_de_combat):
    """Un carton vaut pour plusieurs unités — `orques-01-15-infanteries` est posé quinze fois dans
    le scénario n° 4. Attaquer l'un des deux orques ne doit donc pas consommer l'autre."""
    poser(PLAINE, NAIN)
    poser(APPUI, NAIN)
    poser(VOISINE, ORQUE)
    poser(CONTACT, ORQUE)
    phase_de_combat.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]})

    autre = phase_de_combat.post("/combat", json={"cible": CONTACT, "attaquants": [APPUI]}).json
    assert autre["resolu"] is True


def test_la_phase_suivante_libere_les_unites(client, monkeypatch):
    """Chaque phase de combat repart avec toutes ses unités — celle d'en face, et le tour suivant."""
    monkeypatch.setattr(app, "lancer_le_de", lambda: UN_RECUL)
    poser(PLAINE, NAIN)
    poser(VOISINE, ORQUE)
    client.post("/phase/suivante")  # combat des Nains
    assert client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json["resolu"]

    client.post("/phase/suivante")  # mouvement des Orques
    client.post("/phase/suivante")  # combat des Orques : l'orque attaque à son tour
    assert client.post("/combat", json={"cible": PLAINE, "attaquants": [VOISINE]}).json["resolu"]

    client.post("/phase/suivante")  # mouvement des Nains, tour 2
    client.post("/phase/suivante")  # combat des Nains, tour 2
    assert client.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]}).json["resolu"]


def test_la_portee_refuse_un_attaquant_deja_engage(phase_de_combat):
    poser(PLAINE, NAIN)
    poser(VOISINE, ORQUE)
    poser(CONTACT, ORQUE)
    interrogation = {"cq": CONTACT["q"], "cr": CONTACT["r"], "cs": CONTACT["s"],
                     "aq": PLAINE["q"], "ar": PLAINE["r"], "as": PLAINE["s"]}
    avant = phase_de_combat.get("/combat/portee", query_string=interrogation).json
    assert avant == {"a_portee": True, "disponible": True, "message": None}

    phase_de_combat.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]})
    apres = phase_de_combat.get("/combat/portee", query_string=interrogation).json
    assert apres["disponible"] is False
    assert apres["message"] == app.DEJA_ATTAQUE


def test_la_cible_refuse_une_unite_deja_attaquee(phase_de_combat):
    poser(PLAINE, NAIN)
    poser(VOISINE, ORQUE)
    interrogation = {"cq": VOISINE["q"], "cr": VOISINE["r"], "cs": VOISINE["s"]}
    assert phase_de_combat.get("/combat/cible",
                               query_string=interrogation).json["disponible"] is True

    phase_de_combat.post("/combat", json={"cible": VOISINE, "attaquants": [PLAINE]})
    apres = phase_de_combat.get("/combat/cible", query_string=interrogation).json
    assert apres["disponible"] is False
    assert apres["message"] == app.DEJA_ATTAQUEE


def test_les_indisponibles_sont_dits_au_navigateur(phase_de_combat):
    """Le grisage de la carte se règle sur ces deux listes, données en cases."""
    poser(PLAINE, NAIN)
    poser(VOISINE, ORQUE)
    reponse = phase_de_combat.post("/combat",
                                   json={"cible": VOISINE, "attaquants": [PLAINE]}).json
    cases = lambda liste: [{"q": c["q"], "r": c["r"], "s": c["s"]} for c in liste]
    assert cases(reponse["indisponibles"]["attaquants"]) == [PLAINE]
    assert cases(reponse["indisponibles"]["cibles"]) == [VOISINE]

    # La phase suivante les libère, et la page le voit au même endroit.
    suivante = phase_de_combat.post("/phase/suivante").json
    assert suivante["indisponibles"] == {"attaquants": [], "cibles": []}
