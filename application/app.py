"""Petite application Flask qui affiche la carte d'Ave Tenebrae avec des pions posés dessus.

Le serveur tire dix hexagones au hasard, leur associe un pion au hasard, et passe le tout
au gabarit sous forme de JSON (champ caché). C'est le JavaScript qui convertit les
coordonnées cubiques en pixels et qui pose les pions sur la carte.

Les règles, elles, ne sont pas ici : les déplacements possibles et leur validation viennent de
`moteur.hexagone`, que les routes /deplacements et /deplacer se contentent d'exposer. Chaque pion
se déplace du nombre de points lu sur son carton (`moteur.pion`) : le navigateur dit **quel** pion
il a en main, jamais de combien de points il dispose — ce nombre est repris au catalogue.

La route /admin/map_fix est à part : elle sert à corriger à l'œil les erreurs de la transcription
de la carte, et c'est le seul endroit où l'application écrit dans `game_box/` — dans un fichier à
elle, `map_fix.json`, jamais dans `carte.json` ni `carte_details.json`. Elle travaille toujours sur
la carte transcrite, quand le reste de l'application joue sur la carte corrigée que le moteur en
tire au démarrage.

Lancement (depuis ce répertoire) :

    python3 app.py

puis http://127.0.0.1:5000/
"""

import json
import random
import sys
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory

# Le dépôt n'est pas un paquet installé : on l'ajoute à sys.path pour atteindre `moteur`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from moteur import hexagone as moteur_hexagone  # noqa: E402
from moteur.hexagone import (CARTE, CARTE_TRANSCRITE, INHABITABLES,  # noqa: E402
                             MOUVEMENT_PAR_DEFAUT, Hex)
from moteur.pion import CATALOGUE  # noqa: E402

BOITE = Path(__file__).resolve().parent.parent / "game_box"
PIONS = BOITE / "pions"

# Les 16 terrains de la carte, dans l'ordre de priorité de game_box/carte.md : c'est aussi l'ordre
# des boutons de correction.
TERRAINS = ("ville", "fort", "chateau", "tour", "ruines", "village", "ile", "lac", "montagne",
            "colline", "bois", "faille", "riviere", "route", "chemin", "plaine")

# Nombre de pions posés sur la carte à chaque chargement.
NOMBRE_DE_PIONS = 10

# Terrains sur lesquels on ne pose pas de pion : ceux qu'une unité terrestre ne peut pas occuper,
# plus les montagnes, dont la plupart sont inaccessibles au sol (voir moteur/README.md).
TERRAINS_INTERDITS = INHABITABLES | {"montagne"}

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
    return [cle for cle, elements in CARTE.items() if elements[0] not in TERRAINS_INTERDITS]


def est_un_pion(chemin):
    """Dit si `chemin`, relatif à `pions/`, montre bien un pion isolé."""
    repertoire, _, fichier = chemin.partition("/")
    return (repertoire not in REPERTOIRES_EXCLUS
            and not fichier.removesuffix(".jpg").endswith(SUFFIXE_EXCLU))


def charger_pions():
    """Rend la liste des pions disponibles, valeurs lues sur le carton comprises.

    Le catalogue du moteur porte les 127 photos ; on n'en garde que celles qui montrent un pion
    isolé. Les marqueurs restent du lot : ils se posent sur la carte, ils n'en bougent pas.
    """
    pions = []
    for pion in sorted(CATALOGUE.values(), key=lambda pion: pion.image):
        chemin = PIONS / pion.image.removeprefix("game_box/pions/")
        relatif = f"{chemin.parent.name}/{chemin.name}"
        if est_un_pion(relatif):
            pions.append({"cle": pion.cle, "chemin": relatif, "nom": nommer(chemin),
                          "mouvement": pion.points_de_mouvement})
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
        tirage.append({"q": q, "r": r, "s": s, "cle": pion["cle"], "image": pion["chemin"],
                       "nom": pion["nom"], "mouvement": pion["mouvement"]})
    return tirage


@application.route("/")
def plateau():
    return render_template(
        "carte.html",
        pions=json.dumps(tirer_les_pions(), ensure_ascii=False),
        grille=json.dumps({"origine": GRILLE_ORIGINE, "matrice": GRILLE_MATRICE,
                           "taille_pion": PION_TAILLE}),
    )


@application.route("/deplacements")
def deplacements():
    """Les hexagones qu'une unité posée en (q, r, s) peut atteindre.

    C'est ici que le navigateur vient chercher les cases à couvrir de fantômes : il n'applique
    aucune règle lui-même. Le paramètre `pion` dit lequel est en main — son mouvement est repris
    au catalogue, jamais à la requête. Sans lui, le forfait de 5 points s'applique.
    """
    depart = lire_un_hexagone(request.args)
    mouvement = lire_le_mouvement(request.args.get("pion"))
    return {
        "depart": depart.en_dict(),
        "pion": request.args.get("pion"),
        "mouvement": mouvement,
        "hexagones": [hexagone.en_dict() for hexagone in depart.deplacements(mouvement)],
    }


@application.route("/deplacer", methods=["POST"])
def deplacer():
    """Dit si une unité peut passer de `depart` à `arrivee`, en recalculant la portée ici.

    Le serveur ne croit pas le navigateur sur parole : c'est ce point qui accueillera l'état de
    partie (qui occupe quelle case, dans quel camp) quand il existera.
    """
    demande = request.get_json(silent=True) or {}
    depart = lire_un_hexagone(demande.get("depart") or {})
    arrivee = lire_un_hexagone(demande.get("arrivee") or {})
    mouvement = lire_le_mouvement(demande.get("pion"))
    return {
        "autorise": arrivee in depart.deplacements(mouvement),
        "depart": depart.en_dict(),
        "arrivee": arrivee.en_dict(),
        "pion": demande.get("pion"),
        "mouvement": mouvement,
    }


def ecrire_les_corrections(corrections):
    """Réécrit `map_fix.json`, trié et à raison d'une entrée par ligne, pour rester lisible.

    L'application est seule à écrire ce fichier ; c'est le moteur qui le lit, et le chemin est à
    lui. Le moteur ne le relira qu'au prochain démarrage.
    """
    with moteur_hexagone.CHEMIN_DES_CORRECTIONS.open("w", encoding="utf-8") as fichier:
        json.dump(dict(sorted(corrections.items())), fichier, ensure_ascii=False, indent=0)
        fichier.write("\n")


@application.route("/admin/map_fix")
def corriger_la_carte():
    """La carte, le terrain de chaque hexagone au survol, et un clic pour le corriger.

    Toute la carte part au navigateur d'un coup : il n'y a rien à demander au serveur pour
    afficher un terrain, seulement pour en enregistrer un. C'est la carte **transcrite** qui part,
    corrections à part : la page dit ce que le scan a donné, et ce qu'on en a corrigé.
    """
    return render_template(
        "map_fix.html",
        carte=json.dumps({cle: elements[0] for cle, elements in CARTE_TRANSCRITE.items()}),
        corrections=json.dumps(moteur_hexagone.lire_les_corrections(), ensure_ascii=False),
        appliquees=json.dumps(moteur_hexagone.CORRECTIONS_APPLIQUEES, ensure_ascii=False),
        terrains=json.dumps(TERRAINS),
        grille=json.dumps({"origine": GRILLE_ORIGINE, "matrice": GRILLE_MATRICE}),
    )


@application.route("/admin/map_fix", methods=["POST"])
def corriger_un_hexagone():
    """Note la correction d'un hexagone — corps `{q, r, s, terrain}`.

    Choisir le terrain que la carte **transcrite** donne déjà retire la correction au lieu d'en
    écrire une : c'est ainsi qu'on revient en arrière, et cela reste vrai une fois que le moteur
    joue sur la carte corrigée.
    """
    demande = request.get_json(silent=True) or {}
    vise = lire_un_hexagone(demande)
    terrain = demande.get("terrain")
    if terrain not in TERRAINS:
        abort(400, f"terrain inconnu ; attendu l'un de {', '.join(TERRAINS)}")

    origine = CARTE_TRANSCRITE[vise.cle][0]
    corrections = moteur_hexagone.lire_les_corrections()
    if terrain == origine:
        corrections.pop(vise.cle, None)
    else:
        corrections[vise.cle] = terrain
    ecrire_les_corrections(corrections)

    return {"cle": vise.cle, "terrain": terrain, "origine": origine,
            "corrige": terrain != origine}


def lire_le_mouvement(cle):
    """Les points de mouvement du pion `cle` ; le forfait par défaut si aucun pion n'est donné.

    Le navigateur ne transmet que la clé du pion : le nombre de points, lui, sort du catalogue.
    Une clé inconnue est un 400 — mieux vaut refuser que déplacer un pion imaginaire.
    """
    if cle is None:
        return MOUVEMENT_PAR_DEFAUT
    if cle not in CATALOGUE:
        abort(400, f"pion inconnu : {cle}")
    return CATALOGUE[cle].points_de_mouvement


def lire_un_hexagone(source):
    """Construit un `Hex` depuis des paramètres q, r, s ; 400 s'ils sont illisibles, 404 hors carte."""
    try:
        hexagone = Hex(*(int(source[nom]) for nom in ("q", "r", "s")))
    except (KeyError, TypeError, ValueError):
        abort(400, "coordonnées q, r et s attendues, entières et de somme nulle")
    if not hexagone.est_sur_la_carte:
        abort(404, f"l'hexagone {hexagone.cle} n'est pas sur la carte")
    return hexagone


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
