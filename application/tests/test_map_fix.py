"""La route d'admin qui corrige les terrains de la carte, sans navigateur.

Aucun test n'écrit dans `game_box/` : la fixture `corrections` détourne le chemin du fichier de
corrections, qui appartient au moteur, vers un fichier temporaire.

La page travaille sur la carte **transcrite** — pas sur `CARTE`, que le moteur a déjà recouverte
des corrections en vigueur : c'est ce qui garde juste le terrain « d'origine » et son bouton
« Rétablir » après un redémarrage.
"""

import json

import pytest

import app
from moteur import hexagone as moteur_hexagone
from moteur.hexagone import CARTE_TRANSCRITE

from test_serveur import lire_le_champ_cache

# Un hexagone de plaine, et le premier bois venu : de quoi corriger l'un vers l'autre.
PLAINE = "1,26,-27"
AUTRE_TERRAIN = "bois"


@pytest.fixture
def corrections(tmp_path, monkeypatch):
    """Détourne le fichier de corrections, et rend son chemin."""
    chemin = tmp_path / "map_fix.json"
    monkeypatch.setattr(moteur_hexagone, "CHEMIN_DES_CORRECTIONS", chemin)
    return chemin


def relire(chemin):
    """Le contenu du fichier de corrections ; un dictionnaire vide s'il n'existe pas."""
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding="utf-8"))


def corriger(client, cle, terrain):
    q, r, s = (int(valeur) for valeur in cle.split(","))
    return client.post("/admin/map_fix", json={"q": q, "r": r, "s": s, "terrain": terrain})


# --- La page ---


def test_la_page_repond(client, corrections):
    assert client.get("/admin/map_fix").status_code == 200


def test_la_page_porte_toute_la_carte(client, corrections):
    """Le todo demande que le navigateur ait tout : il ne doit rien avoir à demander pour survoler."""
    hexagones = lire_le_champ_cache(client.get("/admin/map_fix").get_data(as_text=True),
                                    "hexagones")
    assert len(hexagones) == len(CARTE_TRANSCRITE)
    assert hexagones[PLAINE] == CARTE_TRANSCRITE[PLAINE][0]


def test_les_terrains_envoyes_sont_ceux_de_la_carte(client, corrections):
    hexagones = lire_le_champ_cache(client.get("/admin/map_fix").get_data(as_text=True),
                                    "hexagones")
    assert set(hexagones.values()) <= set(app.TERRAINS)


def test_la_liste_des_terrains_couvre_la_carte(client, corrections):
    """`TERRAINS` est le vocabulaire des boutons : il doit valoir exactement celui de la carte."""
    terrains = lire_le_champ_cache(client.get("/admin/map_fix").get_data(as_text=True), "terrains")
    assert set(terrains) == {elements[0] for elements in CARTE_TRANSCRITE.values()}
    assert len(terrains) == len(set(terrains))


def test_la_page_porte_le_calage_de_la_grille(client, corrections):
    grille = lire_le_champ_cache(client.get("/admin/map_fix").get_data(as_text=True), "grille")
    assert grille == {"origine": app.GRILLE_ORIGINE, "matrice": app.GRILLE_MATRICE}


def test_la_page_est_servie_sans_fichier_de_corrections(client, corrections):
    assert not corrections.exists()
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert lire_le_champ_cache(page, "corrections") == {}


def test_la_page_rappelle_les_corrections_deja_faites(client, corrections):
    corrections.write_text(json.dumps({PLAINE: AUTRE_TERRAIN}), encoding="utf-8")
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert lire_le_champ_cache(page, "corrections") == {PLAINE: AUTRE_TERRAIN}


# --- La correction ---


def test_corriger_ecrit_le_fichier(client, corrections):
    reponse = corriger(client, PLAINE, AUTRE_TERRAIN)
    assert reponse.status_code == 200
    assert reponse.get_json() == {"cle": PLAINE, "terrain": AUTRE_TERRAIN,
                                  "origine": CARTE_TRANSCRITE[PLAINE][0], "corrige": True}
    assert relire(corrections) == {PLAINE: AUTRE_TERRAIN}


def test_les_corrections_s_accumulent(client, corrections):
    corriger(client, PLAINE, AUTRE_TERRAIN)
    voisine = "1,27,-28"
    corriger(client, voisine, "colline")
    assert relire(corrections) == {PLAINE: AUTRE_TERRAIN, voisine: "colline"}


def test_corriger_deux_fois_le_meme_hexagone_remplace(client, corrections):
    corriger(client, PLAINE, AUTRE_TERRAIN)
    corriger(client, PLAINE, "colline")
    assert relire(corrections) == {PLAINE: "colline"}


def test_choisir_le_terrain_de_la_carte_retire_la_correction(client, corrections):
    corriger(client, PLAINE, AUTRE_TERRAIN)
    reponse = corriger(client, PLAINE, CARTE_TRANSCRITE[PLAINE][0])
    assert reponse.get_json()["corrige"] is False
    assert relire(corrections) == {}


def test_la_carte_transcrite_reste_intacte(client, corrections):
    """Le fichier de corrections est à part : la transcription ne bouge pas."""
    avant = CARTE_TRANSCRITE[PLAINE]
    corriger(client, PLAINE, AUTRE_TERRAIN)
    assert CARTE_TRANSCRITE[PLAINE] == avant


def test_la_page_montre_la_transcription_meme_corrigee(client, corrections):
    """Ce que la page appelle « la carte », c'est le scan — sinon on ne peut plus rétablir."""
    corriger(client, PLAINE, AUTRE_TERRAIN)
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert lire_le_champ_cache(page, "hexagones")[PLAINE] == CARTE_TRANSCRITE[PLAINE][0]
    assert lire_le_champ_cache(page, "corrections")[PLAINE] == AUTRE_TERRAIN


def test_la_page_dit_ce_que_le_moteur_a_deja_applique(client, corrections, monkeypatch):
    """Le champ « appliquées » sert à savoir si le serveur doit être relancé."""
    monkeypatch.setattr(moteur_hexagone, "CORRECTIONS_APPLIQUEES", {PLAINE: AUTRE_TERRAIN})
    page = client.get("/admin/map_fix").get_data(as_text=True)
    assert lire_le_champ_cache(page, "appliquees") == {PLAINE: AUTRE_TERRAIN}


def test_un_terrain_inconnu_est_refuse(client, corrections):
    assert corriger(client, PLAINE, "marecage").status_code == 400
    assert not corrections.exists()


def test_un_terrain_absent_est_refuse(client, corrections):
    assert client.post("/admin/map_fix", json={"q": 1, "r": 26, "s": -27}).status_code == 400


def test_des_coordonnees_illisibles_sont_refusees(client, corrections):
    assert client.post("/admin/map_fix",
                       json={"q": 1, "r": 26, "s": 0, "terrain": "bois"}).status_code == 400
    assert client.post("/admin/map_fix", json={"terrain": "bois"}).status_code == 400


def test_un_hexagone_hors_carte_est_refuse(client, corrections):
    assert corriger(client, "-1,0,1", "bois").status_code == 404
