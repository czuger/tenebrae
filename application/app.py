"""Petite application Flask qui affiche la carte d'Ave Tenebrae avec des pions posés dessus.

Le serveur tire dix hexagones au hasard, leur associe un pion au hasard, et passe le tout
au gabarit sous forme de JSON (champ caché). C'est le JavaScript qui convertit les
coordonnées cubiques en pixels et qui pose les pions sur la carte.

Lancement (depuis ce répertoire) :

    python3 app.py

puis http://127.0.0.1:5000/
"""

import json
import random
from pathlib import Path

from flask import Flask, abort, render_template, send_from_directory

BOITE = Path(__file__).resolve().parent.parent / "game_box"
CARTE = BOITE / "carte.json"
PIONS = BOITE / "pions"

# Nombre de pions posés sur la carte à chaque chargement.
NOMBRE_DE_PIONS = 10

# Terrains sur lesquels on ne pose pas de pion : le tableau des terrains les donne
# infranchissables (voir game_box/carte.md).
TERRAINS_INTERDITS = {"lac", "montagne", "faille", "riviere"}

# Ce qui, dans `pions/`, ne montre pas un pion isolé : le répertoire des planches entières,
# et les photos de planchettes de suivi prises « en vue d'ensemble ».
REPERTOIRES_EXCLUS = {"21-vues-d-ensemble"}
SUFFIXE_EXCLU = "-vue-d-ensemble"

# Calage de la grille sur map.jpg, relevé dans game_box/carte.md :
#     centre(q, r) = ORIGINE + MATRICE · (q, r)
# Les deux constantes sont passées au JavaScript, qui fait la conversion.
GRILLE_ORIGINE = [76.355, 70.511]
GRILLE_MATRICE = [[107.5724, -0.3407], [62.8901, 125.6828]]

# Côté du pion, en pixels de map.jpg (un hexagone fait environ 143 px de sommet à sommet).
PION_TAILLE = 104

application = Flask(__name__)


def charger_hexagones():
    """Rend la liste des hexagones où un pion peut se tenir, en clés « q,r,s »."""
    with CARTE.open(encoding="utf-8") as fichier:
        carte = json.load(fichier)
    return [cle for cle, terrain in carte.items() if terrain not in TERRAINS_INTERDITS]


def est_un_pion(chemin):
    """Dit si `chemin`, relatif à `pions/`, montre bien un pion isolé."""
    repertoire, _, fichier = chemin.partition("/")
    return (repertoire not in REPERTOIRES_EXCLUS
            and not fichier.removesuffix(".jpg").endswith(SUFFIXE_EXCLU))


def charger_pions():
    """Rend la liste des pions disponibles : chemin relatif à `pions/` et libellé."""
    pions = []
    for chemin in sorted(PIONS.glob("*/*.jpg")):
        relatif = f"{chemin.parent.name}/{chemin.name}"
        if est_un_pion(relatif):
            pions.append({"chemin": relatif, "nom": nommer(chemin)})
    return pions


def nommer(chemin):
    """« 01-yzent/yzent-05-1-belier.jpg » → « yzent · 1 belier ».

    Le nom de fichier reprend le nom du répertoire sans son numéro, suivi du rang du pion
    dans la faction puis de sa description (voir game_box/pions/README.md).
    """
    faction = chemin.parent.name.split("-", 1)[1]
    description = chemin.stem.removeprefix(f"{faction}-")[3:]
    return f"{faction.replace('-', ' ')} · {description.replace('-', ' ')}"


HEXAGONES = charger_hexagones()
CATALOGUE_DES_PIONS = charger_pions()


def tirer_les_pions(nombre=NOMBRE_DE_PIONS):
    """Tire `nombre` hexagones distincts et pose un pion au hasard sur chacun."""
    tirage = []
    for cle in random.sample(HEXAGONES, nombre):
        q, r, s = (int(valeur) for valeur in cle.split(","))
        pion = random.choice(CATALOGUE_DES_PIONS)
        tirage.append({"q": q, "r": r, "s": s, "image": pion["chemin"], "nom": pion["nom"]})
    return tirage


@application.route("/")
def plateau():
    return render_template(
        "carte.html",
        pions=json.dumps(tirer_les_pions(), ensure_ascii=False),
        grille=json.dumps({"origine": GRILLE_ORIGINE, "matrice": GRILLE_MATRICE,
                           "taille_pion": PION_TAILLE}),
    )


@application.route("/carte.jpg")
def image_de_la_carte():
    return send_from_directory(BOITE, "map.jpg")


@application.route("/pions/<path:chemin>")
def image_de_pion(chemin):
    if not est_un_pion(chemin):
        abort(404)
    return send_from_directory(PIONS, chemin)


if __name__ == "__main__":
    application.run(debug=True)
