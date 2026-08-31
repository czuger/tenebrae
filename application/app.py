"""Petite application Flask qui affiche la carte d'Ave Tenebrae avec des pions posés dessus.

Le serveur pose la mise en place d'un scénario — le n° 4, « La guerre des nains » —, lue une
fois pour toutes dans `scenarios/`, et la passe au gabarit sous forme de JSON (champ caché).
C'est le JavaScript qui convertit les coordonnées cubiques en pixels et qui pose les pions sur la
carte. La mise en place est **fixe** : recharger la page repose les mêmes pions aux mêmes cases.

Les règles, elles, ne sont pas ici : les déplacements possibles et leur validation viennent de
`moteur.hexagone`, que les routes /deplacements et /deplacer se contentent d'exposer. Chaque pion
se déplace du nombre de points lu sur son carton (`moteur.pion`) : le navigateur dit **quel** pion
il a en main, jamais de combien de points il dispose — ce nombre est repris au catalogue.

Le serveur tient aussi le **tour** (`moteur.phase.Tour`, le module-global `TOUR`) : les routes
/phase/suivante, /combat et /combat/portee l'exposent, et /deplacer refuse un mouvement hors de la
phase de mouvement du camp. La résolution d'un combat est dans `moteur.combat` ; seul le jet de dé
(`lancer_le_de`) est ici, pour que les tests puissent le fixer. Le journal de la partie est un
fichier local, `journal_de_combat.log` — le second endroit où l'application écrit sur le disque.

À côté du tour, le module-global `SUIVI` (`moteur.combat.SuiviDeCombat`) retient ce que la phase
de combat en cours a déjà consommé : une unité n'attaque qu'une fois, une unité n'est attaquée
qu'une fois. Il se vide à chaque changement de phase, et /combat/portee comme /combat/cible le
consultent pour que le navigateur ne surligne pas une unité qui a déjà combattu.

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
import logging
import random
import sys
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory

# Le dépôt n'est pas un paquet installé : on l'ajoute à sys.path pour atteindre `moteur`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from moteur import combat  # noqa: E402
from moteur import hexagone as moteur_hexagone  # noqa: E402
from moteur.hexagone import CARTE_TRANSCRITE, Hex  # noqa: E402
from moteur.phase import COMBAT, Tour  # noqa: E402
from moteur.pion import CATALOGUE  # noqa: E402
from moteur.plateau import Plateau  # noqa: E402
from moteur.scenario import scenario  # noqa: E402

BOITE = Path(__file__).resolve().parent.parent / "game_box"
PIONS = BOITE / "pions"

# Les 16 terrains de la carte, dans l'ordre de priorité de game_box/carte.md : c'est aussi l'ordre
# des boutons de correction.
TERRAINS = ("ville", "fort", "chateau", "tour", "ruines", "village", "ile", "lac", "montagne",
            "colline", "bois", "faille", "riviere", "route", "chemin", "plaine")

# Le scénario que le serveur met en place au chargement de « / » : « La guerre des nains »,
# nains contre orques (voir `scenarios/README.md`).
NUMERO_DU_SCENARIO = 4

# Le journal de la partie : changements de phase, combats déclarés, unités hors de portée,
# résultats. C'est un simple fichier local — l'interface n'en montre que la phase courante.
CHEMIN_DU_JOURNAL = Path(__file__).resolve().parent / "journal_de_combat.log"

# Ce que le fascicule appelle « le résultat du jet de dé », de 1 à 6. Isolé dans une fonction pour
# que les tests puissent le fixer sans toucher au hasard du moteur.
def lancer_le_de():
    return random.randint(1, 6)


# Les trois issues de combat que le todo demande de jouer ; toute autre issue ne change rien.
MESSAGES_DE_COMBAT = {
    "DE": "Combat résolu : Défenseur Éliminé",
    "AE": "Combat résolu : Attaquant Éliminé",
    "EX": "Combat résolu : Échange — toutes les unités impliquées sont éliminées",
}

# Les deux refus qu'oppose le registre de la phase de combat. Ils partent au journal, et le
# navigateur s'en sert pour ne pas surligner une unité qui a déjà donné.
DEJA_ATTAQUE = "Cette unité a déjà attaqué durant cette phase de combat."
DEJA_ATTAQUEE = "Cette unité a déjà été attaquée durant cette phase de combat."

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

# Le journal est un fichier local, écrit une ligne par événement. On ne le configure qu'une fois.
JOURNAL = logging.getLogger("tenebrae.journal")
if not JOURNAL.handlers:
    _trace = logging.FileHandler(CHEMIN_DU_JOURNAL, encoding="utf-8")
    _trace.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    JOURNAL.addHandler(_trace)
    JOURNAL.setLevel(logging.INFO)


def est_un_pion(chemin):
    """Dit si `chemin`, relatif à `pions/`, montre bien un pion isolé."""
    repertoire, _, fichier = chemin.partition("/")
    return (repertoire not in REPERTOIRES_EXCLUS
            and not fichier.removesuffix(".jpg").endswith(SUFFIXE_EXCLU))


def charger_pions():
    """Rend la liste des pions disponibles, valeurs lues sur le carton comprises.

    Le catalogue du moteur porte les 127 photos ; on n'en garde que celles qui montrent un pion
    isolé. Les marqueurs restent du lot : ils se posent sur la carte, ils n'en bougent pas.

    Tout ce qui est imprimé sur le carton part avec — force, tir, portée, vol, symbole, facultés
    et remarques —, pour la fiche que le navigateur montre au survol. Les valeurs absentes du
    carton restent à `None` : c'est l'affichage qui les rend par un tiret.

    `Pion.en_dict()` n'est pas repris tel quel : son `mouvement` est la valeur brute du carton,
    parfois absente, quand la clé servie ici est le budget de déplacement, et son `image` est le
    chemin du dépôt, non celui de la route `/pions/`.
    """
    pions = []
    for pion in sorted(CATALOGUE.values(), key=lambda pion: pion.image):
        chemin = PIONS / pion.image.removeprefix("game_box/pions/")
        relatif = f"{chemin.parent.name}/{chemin.name}"
        if est_un_pion(relatif):
            pions.append({"cle": pion.cle, "chemin": relatif, "nom": nommer(chemin),
                          "mouvement": pion.points_de_mouvement, "camp": pion.camp,
                          "faction": pion.faction, "symbole": pion.symbole,
                          "force": pion.force, "tir": pion.tir, "portee": pion.portee,
                          "mouvement_vol": pion.mouvement_vol,
                          "facultes_speciales": pion.facultes_speciales,
                          "remarques": pion.remarques})
    return pions


def nommer(chemin):
    """« 01-yzent/yzent-05-1-belier.jpg » → « yzent · 1 belier ».

    Le nom de fichier reprend le nom du répertoire sans son numéro, suivi du rang du pion
    dans la faction puis de sa description (voir game_box/pions/README.md).
    """
    faction = chemin.parent.name.split("-", 1)[1]
    description = chemin.stem.removeprefix(f"{faction}-")[3:]
    return f"{faction.replace('-', ' ')} · {description.replace('-', ' ')}"


CATALOGUE_DES_PIONS = charger_pions()
PIONS_PAR_CLE = {pion["cle"]: pion for pion in CATALOGUE_DES_PIONS}

# La mise en place jouée, lue une fois au démarrage. Un scénario fixé ne change pas d'un
# chargement à l'autre : c'est ce qui permet d'éprouver les déplacements sur une position connue.
SCENARIO = scenario(NUMERO_DU_SCENARIO)

# L'état de partie du serveur : les pions actuellement posés. Il est refait à chaque chargement du
# plateau et suivi à chaque déplacement — c'est de lui que sortent les zones de contrôle, qui
# demandent de savoir qui occupe quelle case et dans quel camp.
PLATEAU = Plateau()

# La phase courante : quel camp joue, et à quoi. L'ordre des camps et le nom des armées viennent
# du scénario. Comme le plateau, le tour est remis à zéro à chaque chargement de « / ».
TOUR = Tour(SCENARIO.camps, {armee["camp"]: armee["armee"] for armee in SCENARIO.armees})

# Ce que la phase de combat en cours a déjà consommé. Il suit le tour : toute phase franchie le
# vide, ce qui couvre aussi bien le passage du combat des Nains à celui des Orques que le tour
# suivant. Le mouvement ne le consulte pas — le vider trop souvent ne coûte rien.
SUIVI = combat.SuiviDeCombat()


def poser_la_mise_en_place():
    """Refait le plateau du serveur d'après le scénario, et rend ses unités pour l'affichage.

    Le scénario ne donne qu'un couple « case → clé de pion » ; tout le reste — l'image, le nom et
    les valeurs du carton — est repris au catalogue, comme pour n'importe quel pion servi par
    l'application. L'entrée du catalogue part entière : ce qu'on lui ajoutera suivra tout seul.
    Seul `chemin` est renommé, en `image`, parce que c'est ce que le navigateur met dans `src`.
    """
    PLATEAU.vider()
    TOUR.recommencer()
    SUIVI.reinitialiser()
    poses = []
    for case, cle in SCENARIO.placement.items():
        hexagone = Hex.depuis_cle(case)
        pion = dict(PIONS_PAR_CLE[cle])
        PLATEAU.poser(hexagone, CATALOGUE[cle])
        poses.append({"q": hexagone.q, "r": hexagone.r, "s": hexagone.s,
                      "image": pion.pop("chemin")} | pion)
    return poses


def les_unites_indisponibles():
    """Les cases des unités qui ne peuvent plus attaquer, ou plus être attaquées, cette phase-ci.

    Les cases vidées par le combat sont écartées : le registre les garde — elles ne gênent
    personne, rien ne bouge d'ici la fin de la phase — mais le navigateur n'a plus de pion à y
    griser.
    """
    poses = PLATEAU.pions
    return {
        "attaquants": [Hex.depuis_cle(cle).en_dict()
                       for cle in sorted(SUIVI.attaquants_engages) if cle in poses],
        "cibles": [Hex.depuis_cle(cle).en_dict()
                   for cle in sorted(SUIVI.cibles_engagees) if cle in poses],
    }


def la_phase_courante():
    """La phase telle que le navigateur la reçoit : le tour, et ce que la phase a déjà consommé."""
    return TOUR.en_dict() | {"indisponibles": les_unites_indisponibles()}


@application.route("/")
def plateau():
    return render_template(
        "carte.html",
        pions=json.dumps(poser_la_mise_en_place(), ensure_ascii=False),
        grille=json.dumps({"origine": GRILLE_ORIGINE, "matrice": GRILLE_MATRICE,
                           "taille_pion": PION_TAILLE}),
        phase=json.dumps(la_phase_courante(), ensure_ascii=False),
    )


@application.route("/deplacements")
def deplacements():
    """Les hexagones qu'une unité posée en (q, r, s) peut atteindre.

    C'est ici que le navigateur vient chercher les cases à couvrir de fantômes : il n'applique
    aucune règle lui-même. C'est le **plateau du serveur** qui dit quel pion se tient là, dans
    quel camp, et quels adversaires lui opposent leurs zones de contrôle. Le paramètre `pion` ne
    sert qu'à interroger une case vide ; sans lui, le forfait de 5 points s'applique et la carte
    est réputée sans adversaire.
    """
    depart = lire_un_hexagone(request.args)
    pion = lire_un_pion(request.args.get("pion"))
    return decrire_un_deplacement(depart, pion) | {
        "hexagones": [hexagone.en_dict() for hexagone in PLATEAU.deplacements(depart, pion)],
    }


@application.route("/deplacer", methods=["POST"])
def deplacer():
    """Déplace une unité de `depart` vers `arrivee`, si la règle le permet.

    Le serveur ne croit pas le navigateur sur parole : il recalcule la portée, et c'est lui qui
    tient le plateau. Un déplacement accepté y est appliqué, sans quoi les zones de contrôle du
    coup d'après se calculeraient sur des positions périmées.

    Le mouvement n'est ouvert qu'au camp actif, et seulement pendant sa phase de mouvement : hors
    de là, le déplacement est refusé sans que le plateau ne bouge.
    """
    demande = request.get_json(silent=True) or {}
    depart = lire_un_hexagone(demande.get("depart") or {})
    arrivee = lire_un_hexagone(demande.get("arrivee") or {})
    pion = lire_un_pion(demande.get("pion"))
    decrit = decrire_un_deplacement(depart, pion)
    pose = PLATEAU.pion_sur(depart)
    hors_phase = pose is not None and not TOUR.autorise_mouvement(pose.camp)
    return decrit | {
        "autorise": not hors_phase and PLATEAU.deplacer(depart, arrivee, pion),
        "arrivee": arrivee.en_dict(),
    }


def decrire_un_deplacement(depart, pion):
    """Ce que le serveur sait de l'unité qui part : sa case, son pion, son camp, ses points."""
    pose = PLATEAU.pion_sur(depart) or pion
    return {
        "depart": depart.en_dict(),
        "pion": pose.cle if pose else None,
        "camp": pose.camp if pose else None,
        "mouvement": PLATEAU.mouvement_de(depart, pion),
    }


@application.route("/phase")
def phase_courante():
    """La phase en cours — le navigateur s'en sert pour son libellé et ses blocages."""
    return la_phase_courante()


@application.route("/phase/suivante", methods=["POST"])
def phase_suivante():
    """Passe à la phase suivante ; la magie est franchie d'elle-même.

    Le registre des combats est vidé au passage : chaque phase de combat repart avec toutes ses
    unités disponibles, celle des Ténèbres comme celle de l'Alliance, à ce tour-ci comme au suivant.
    """
    TOUR.suivante()
    SUIVI.reinitialiser()
    JOURNAL.info("Phase : %s (tour %s)", TOUR.libelle, TOUR.numero)
    return la_phase_courante()


def lire_un_hexagone_prefixe(prefixe, source):
    """Un `Hex` depuis `{prefixe}q`, `{prefixe}r`, `{prefixe}s` — pour deux hexagones dans l'URL."""
    return lire_un_hexagone({nom: source.get(f"{prefixe}{nom}") for nom in ("q", "r", "s")})


@application.route("/combat/portee")
def verifier_la_portee():
    """Dit si l'unité en `a…` peut engager la cible en `c…` : à portée, et pas déjà engagée.

    Un attaquant hors de portée n'est pas ajouté au combat, et le refus part au journal — comme le
    veut le todo. Un attaquant qui a déjà donné cette phase-ci est refusé de la même façon : le
    navigateur n'a plus qu'à ne pas le surligner en or.
    """
    cible = lire_un_hexagone_prefixe("c", request.args)
    attaquant = lire_un_hexagone_prefixe("a", request.args)
    pion_attaquant = PLATEAU.pion_sur(attaquant)
    if pion_attaquant is None:
        return {"a_portee": False, "disponible": False, "message": "Aucune unité sur cette case."}
    dans_la_portee = combat.a_portee(attaquant, pion_attaquant, cible)
    disponible = SUIVI.peut_attaquer(attaquant.cle)
    if not disponible:
        message = DEJA_ATTAQUE
    elif not dans_la_portee:
        message = "Cette unité n'est pas à portée de la cible"
    else:
        message = None
    if message:
        JOURNAL.info(message)
    return {"a_portee": dans_la_portee, "disponible": disponible, "message": message}


@application.route("/combat/cible")
def verifier_la_cible():
    """Dit si l'unité en `c…` peut encore être prise pour cible durant cette phase de combat.

    Le navigateur demandait jusqu'ici son surlignage rouge sans rien demander au serveur ; il lui
    faut maintenant passer par ici, le registre de la phase étant seul à savoir qui a déjà été
    attaqué.
    """
    cible = lire_un_hexagone_prefixe("c", request.args)
    if PLATEAU.pion_sur(cible) is None:
        return {"disponible": False, "message": "Aucune unité sur cette case."}
    disponible = SUIVI.peut_etre_cible(cible.cle)
    message = None if disponible else DEJA_ATTAQUEE
    if message:
        JOURNAL.info(message)
    return {"disponible": disponible, "message": message}


@application.route("/combat", methods=["POST"])
def combattre():
    """Résout un combat : une cible adverse, un ou plusieurs attaquants du camp actif.

    Corps `{"cible": {q, r, s}, "attaquants": [{q, r, s}, …]}`. Le serveur revalide tout, écarte
    les attaquants hors de portée ou ayant déjà attaqué (avec un message au journal), lance le dé,
    applique le résultat au plateau et journalise l'issue en français.

    Le combat livré est inscrit au registre de la phase, **quelle que soit son issue** : un recul,
    que le moteur laisse sans effet, a tout de même engagé ses unités.
    """
    demande = request.get_json(silent=True) or {}
    if TOUR.type_de_phase != COMBAT:
        return {"resolu": False, "message": "Ce n'est pas la phase de combat."}

    cible = lire_un_hexagone(demande.get("cible") or {})
    if cible.cle not in PLATEAU.adversaires_de(TOUR.camp_actif):
        return {"resolu": False, "message": "La cible doit être une unité adverse."}
    if not SUIVI.peut_etre_cible(cible.cle):
        JOURNAL.info(DEJA_ATTAQUEE)
        return {"resolu": False, "message": DEJA_ATTAQUEE}

    valides, messages = [], []
    for case in demande.get("attaquants") or []:
        attaquant = lire_un_hexagone(case or {})
        pion_attaquant = PLATEAU.pion_sur(attaquant)
        if pion_attaquant is None or pion_attaquant.camp != TOUR.camp_actif:
            messages.append("Cette unité ne peut pas attaquer cette cible.")
        elif not SUIVI.peut_attaquer(attaquant.cle):
            messages.append(DEJA_ATTAQUE)
        elif not combat.a_portee(attaquant, pion_attaquant, cible):
            messages.append("Cette unité n'est pas à portée de la cible")
        else:
            valides.append(attaquant)
    for message in messages:
        JOURNAL.info(message)

    if not valides:
        return {"resolu": False, "message": "Aucun attaquant valide.", "messages": messages}

    jet = lancer_le_de()
    resultat = combat.livrer_combat(PLATEAU, cible, valides, jet)
    SUIVI.enregistrer([hexagone.cle for hexagone in valides], cible.cle)
    message = MESSAGES_DE_COMBAT.get(resultat.resultat, "Combat résolu : sans effet")
    JOURNAL.info("%s — dé %s, rapport %s", message, resultat.de,
                 "-".join(map(str, resultat.rapport)) if resultat.rapport else "?")
    return {
        "resolu": True,
        "resultat": resultat.resultat,
        "message": message,
        "elimines": [hexagone.en_dict() for hexagone in resultat.elimines],
        "jet": jet,
        "de": resultat.de,
        "rapport": list(resultat.rapport) if resultat.rapport else None,
        "indisponibles": les_unites_indisponibles(),
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


def lire_un_pion(cle):
    """Le pion de clé `cle` dans le catalogue, ou `None` si la requête n'en nomme pas.

    Le navigateur ne transmet qu'une clé : les points de mouvement et le camp sortent du
    catalogue, jamais de la requête. Une clé inconnue est un 400 — mieux vaut refuser que
    déplacer un pion imaginaire.
    """
    if cle is None:
        return None
    if cle not in CATALOGUE:
        abort(400, f"pion inconnu : {cle}")
    return CATALOGUE[cle]


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
