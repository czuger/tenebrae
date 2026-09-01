"""Petite application Flask qui affiche la carte d'Ave Tenebrae avec des pions posés dessus.

Le serveur pose la mise en place d'un scénario — le n° 4, « La guerre des nains » —, lue une
fois pour toutes dans `scenarios/`, et la passe au gabarit sous forme de JSON (champ caché).
C'est le JavaScript qui convertit les coordonnées cubiques en pixels et qui pose les pions sur la
carte.

La partie est **sauvegardée dans MongoDB** : chaque coup joué l'enregistre, et « / » la reprend là
où on l'a laissée. Les routes ne voient pas la base — elles passent par le dépôt que `create_app`
accroche à l'application (`moteur/depots/`), et lui parlent en dicts d'état. `POST /partie/nouvelle`
repart de la mise en place. Sans persistance (`PERSISTANCE=aucune`, et la configuration de test),
le dépôt ne retient rien : chaque chargement de « / » repose alors les mêmes pions aux mêmes
cases, comme avant.

Les règles, elles, ne sont pas ici : les déplacements possibles et leur validation viennent de
`moteur.hexagone`, que les routes /deplacements et /deplacer se contentent d'exposer. Chaque pion
se déplace du nombre de points lu sur son carton (`moteur.pion`) : le navigateur dit **quel** pion
il a en main, jamais de combien de points il dispose — ce nombre est repris au catalogue.

Le serveur tient aussi le **tour** (`moteur.phase.Tour`, le module-global `TOUR`) : les routes
/phase/suivante, /combat et /combat/portee l'exposent, et /deplacer refuse un mouvement hors de la
phase de mouvement du camp. La résolution d'un combat est dans `moteur.combat` ; seul le jet de dé
(`lancer_le_de`) est ici, pour que les tests puissent le fixer. Le journal de la partie s'écrit
à deux endroits : `journal_de_combat.log` — le second endroit où l'application écrit sur le
disque —, et une file bornée en mémoire, dont le navigateur fait une colonne sous la fiche. D'où
la règle que suivent les routes : **journaliser avant de marquer le coup**, l'instantané poussé
aux flux portant le journal (voir `instantane_partage`).

À côté du tour, le module-global `SUIVI` (`moteur.combat.SuiviDeCombat`) retient ce que la phase
de combat en cours a déjà consommé : une unité n'attaque qu'une fois, une unité n'est attaquée
qu'une fois. Il se vide à chaque changement de phase, et /combat/portee comme /combat/cible le
consultent pour que le navigateur ne surligne pas une unité qui a déjà combattu.

La partie se joue **à deux, un joueur par camp**, identifiés par Discord (voir `client_discord.py`
pour le flux OAuth2, `moteur/models/places.py` pour la table, `models/connexion.py` pour le lien
entre la session et le joueur du moteur). La carte reste publique — un visiteur de passage
la voit et consulte les déplacements possibles —, mais tout ce qui change l'état demande d'être
connecté et d'occuper le camp dont c'est la phase : c'est ce que posent les décorateurs
`connexion_requise`, `place_requise` et `camp_actif_requis`. Le module-global `PLACES` retient qui
tient quoi, et `VERSION` monte à chaque coup joué.

Chaque navigateur suit la partie de l'autre par un **flux ouvert**, /flux, du Server-Sent Events :
il ne demande plus rien, le serveur lui pousse la partie quand elle change. Le registre des flux
ouverts est dans `flux.py` ; le seul point d'où l'on publie est `marquer_un_coup`, par où passe
tout ce qui bouge. La route /partie/etat, que le navigateur sondait avant, reste servie comme
**repli** — une page dont l'EventSource ne passe pas y retombe. Voir `DEPLOIEMENT.md` pour ce que
le flux demandera derrière Nginx.

La route /admin/map_fix est à part : elle sert à corriger à l'œil les erreurs de la transcription
de la carte, et c'est le seul endroit où l'application écrit dans `game_box/` — dans un fichier à
elle, `map_fix.json`, jamais dans `carte.json` ni `carte_details.json`. Elle travaille toujours sur
la carte transcrite, quand le reste de l'application joue sur la carte corrigée que le moteur en
tire au démarrage. Elle est réservée aux comptes de `ADMIN_DISCORD_IDS`.

Lancement (depuis ce répertoire) :

    python3 app.py

puis http://127.0.0.1:5000/
"""

import collections
import json
import logging
import math
import random
import secrets
import sys
import time
from functools import wraps
from pathlib import Path

from itsdangerous import BadSignature
from flask import Blueprint, Flask, abort, current_app, g, redirect, render_template, \
    request, send_from_directory, session, url_for

# Le dépôt n'est pas un paquet installé : on l'ajoute à sys.path pour atteindre `moteur`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config  # noqa: E402
from flux import Diffuseur  # noqa: E402
from models.connexion import Connexion  # noqa: E402
from moteur import combat  # noqa: E402
from moteur import hexagone as moteur_hexagone  # noqa: E402
from moteur import ia  # noqa: E402
from moteur.hexagone import CARTE_TRANSCRITE, Hex  # noqa: E402
from moteur.phase import COMBAT, Tour  # noqa: E402
from moteur.pion import CATALOGUE  # noqa: E402
from moteur.plateau import Plateau  # noqa: E402
from moteur.models.places import Places  # noqa: E402
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
# résultats. Il est écrit à deux endroits à la fois — un fichier local, qui garde tout, et une
# file bornée en mémoire, dont le navigateur fait sa colonne sous la fiche.
CHEMIN_DU_JOURNAL = Path(__file__).resolve().parent / "journal_de_combat.log"

# Ce que la colonne du navigateur montre : les dernières lignes, et pas plus. Le fichier reste
# l'archive ; la page, elle, n'a que la place de la fin de la partie, et une file bornée la lui
# sert sans jamais grossir.
LIGNES_RETENUES = 60

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


def detailler_le_rapport(resultat):
    """Le calcul du rapport de force en une phrase, pour la ligne que le journal lui consacre.

    Ce que le rapport seul ne dit pas, et qui décide pourtant du combat : ce que le groupe
    d'attaquants totalise, ce que le défenseur oppose **une fois son terrain compté**, et le dé
    tel que ce même terrain l'a modifié. Un 12 contre un 8 donne un rapport 1-1 en plaine et
    1-2 en montagne, et rien ne le montrait.

        Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4

    Les trois termes ne s'écrivent en détail que lorsqu'il y a un détail à écrire : un attaquant
    seul, un terrain qui ne multiplie rien, un dé que rien n'augmente s'écrivent d'un seul nombre.
    Le terrain, lui, est **toujours** nommé — c'est ce qu'on est venu chercher, y compris quand il
    ne fait rien.

    Le moteur ne fabrique pas cette phrase : il rend les nombres (`combat.DetailDuRapport`), et
    c'est ici qu'ils se mettent en français, comme les issues de `MESSAGES_DE_COMBAT`.
    """
    detail = resultat.detail
    attaque = " + ".join(str(force) for force in detail.forces)
    if len(detail.forces) > 1:
        attaque += f" = {detail.force_attaquante}"
    defense = str(detail.force_de_la_cible)
    if detail.multiplicateur != 1:
        defense += f" × {detail.multiplicateur} = {detail.force_defensive}"
    de = str(detail.jet)
    if detail.bonus_au_de:
        de += f" + {detail.bonus_au_de} = {detail.jet + detail.bonus_au_de}"
        # Le Tableau I n'a que six lignes : au-delà, le dé y est ramené, et le dire évite une
        # addition qui paraîtrait fausse.
        if detail.jet + detail.bonus_au_de != detail.de:
            de += f", ramené à {detail.de}"
    rapport = "-".join(map(str, detail.rapport))
    return (f"Rapport {rapport} : attaque {attaque} contre défense {defense} "
            f"({detail.terrain}) — dé {de}")


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

# Les routes vivent sur un blueprint : c'est la factory `create_app`, en fin de fichier, qui les
# enregistre — après avoir branché la persistance. L'état de jeu, lui, reste aux module-globaux
# ci-dessous : une seule partie courante par processus, que les tests lisent par `app.PLATEAU`.
jeu = Blueprint("jeu", __name__)


class JournalEnMemoire(logging.Handler):
    """Les dernières lignes du journal, retenues pour que le navigateur puisse les montrer.

    C'est un *handler*, et non un appel ajouté à côté de chaque `JOURNAL.info` : le journal garde
    ainsi un seul point d'écriture, et la colonne du navigateur ne peut pas dire autre chose que
    le fichier. La file est bornée — un serveur qui tourne longtemps ne doit pas enfler d'une
    ligne par clic refusé.

    `deque.append` est atomique : le fil qui joue un coup écrit ici pendant qu'un fil de flux
    recopie la file, et il n'y a rien de plus à verrouiller.
    """

    def __init__(self, capacite):
        super().__init__()
        self.lignes = collections.deque(maxlen=capacite)

    def emit(self, enregistrement):
        self.lignes.append({
            "heure": time.strftime("%H:%M:%S", time.localtime(enregistrement.created)),
            "texte": enregistrement.getMessage(),
        })


# Le journal est écrit une ligne par événement, dans le fichier et dans la mémoire. On ne le
# configure qu'une fois.
JOURNAL = logging.getLogger("tenebrae.journal")
MEMOIRE_DU_JOURNAL = JournalEnMemoire(LIGNES_RETENUES)
if not JOURNAL.handlers:
    _trace = logging.FileHandler(CHEMIN_DU_JOURNAL, encoding="utf-8")
    _trace.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    JOURNAL.addHandler(_trace)
    JOURNAL.addHandler(MEMOIRE_DU_JOURNAL)
    JOURNAL.setLevel(logging.INFO)


def les_lignes_du_journal():
    """Le journal tel que la page le montre : les dernières lignes, de la plus ancienne à la
    plus récente. Une copie — la file continue de tourner pendant que le message voyage."""
    return list(MEMOIRE_DU_JOURNAL.lignes)


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

# Qui tient quel camp (voir `moteur/models/places.py`). Comme le plateau et le tour, il n'y a
# qu'une table par processus : les deux joueurs jouent la même partie, chacun de son navigateur.
# Contrairement au plateau, elle **ne se refait pas** à chaque chargement de « / » ni à chaque
# nouvelle partie : recommencer ne renvoie personne de la table.
PLACES = Places()

# Le numéro de version de la partie : il monte d'un cran à chaque coup joué. C'est à cela que le
# navigateur de l'adversaire voit qu'il a quelque chose à reprendre. Un simple entier suffit : il
# n'y a qu'un processus, et deux navigateurs qui lisent la même partie. Il sert deux fois — c'est
# aussi l'**identifiant d'événement** du flux SSE, celui que le navigateur renvoie en
# `Last-Event-ID` quand il se reconnecte (voir `/flux`).
VERSION = 0

# À qui pousser la partie quand elle change (voir `flux.py`). Un abonné par onglet ouvert ; le
# registre est en mémoire, dans ce processus.
DIFFUSEUR = Diffuseur()


def marquer_un_coup():
    """Note qu'un coup a été joué, et le pousse aux navigateurs qui suivent la partie.

    C'est le passage obligé de tout ce qui bouge — `poser_la_mise_en_place` et
    `sauvegarder_la_partie` sont ses deux seuls appelants, et toute route qui change quoi que ce
    soit passe par l'un des deux. Brancher la diffusion ici, et nulle part ailleurs, est ce qui
    garantit qu'aucun coup ne peut être joué sans que les flux ouverts l'apprennent.

    L'instantané est pris **ici**, dans le fil qui vient d'écrire, et c'est lui qui voyage : les
    générateurs de flux n'ont ainsi jamais à relire le plateau depuis leur propre fil pendant
    qu'un autre le modifie (voir l'en-tête de `flux.py`).
    """
    global VERSION
    VERSION += 1
    DIFFUSEUR.publier(instantane_partage())
    return VERSION


def instantane_partage():
    """L'état de la partie que **tous** les spectateurs ont en commun.

    Tout n'est pas partagé : `la_table` dit à chacun s'il est connecté, sous quel pseudo et quels
    camps il tient — c'est la seule part du message qui se compose par destinataire, et le flux
    l'ajoute au moment d'écrire (voir `/flux`).

    Le journal en est, et pour la même raison que les pions : les deux joueurs regardent la même
    partie, ils en lisent le même compte rendu. Il est photographié ici, avec le reste — d'où la
    règle que suivent les routes ci-dessous : **journaliser avant de marquer le coup**, sans quoi
    la ligne qu'on vient d'écrire ne partirait qu'au coup suivant.
    """
    return {"version": VERSION, "pions": les_unites_posees(), "phase": la_phase_courante(),
            "journal": les_lignes_du_journal()}


def poser_la_mise_en_place():
    """Refait le plateau du serveur d'après le scénario, et rend ses unités pour l'affichage.

    Le scénario ne donne qu'un couple « case → clé de pion » : les pions sont posés, puis c'est
    le plateau qu'on décrit, par `les_unites_posees` — la mise en place n'a rien à dire de plus
    qu'une partie reprise, et l'inclinaison que la pose vient de tirer est déjà là.

    La table n'y est pas touchée : recommencer une partie ne renvoie personne de sa place.

    Le coup est marqué **une fois les pions posés**, et non avant : `marquer_un_coup` photographie
    la partie pour la pousser aux flux ouverts, et une photo prise entre le `vider` et la pose
    montrerait un plateau désert. C'était déjà vrai du sondage — un `/partie/etat` tombant dans
    cet intervalle rendait une partie vide —, mais il fallait tomber juste ; le flux, lui, y
    serait tombé à chaque fois.
    """
    PLATEAU.vider()
    TOUR.recommencer()
    SUIVI.reinitialiser()
    for case, cle in SCENARIO.placement.items():
        PLATEAU.poser(Hex.depuis_cle(case), CATALOGUE[cle])
    marquer_un_coup()
    return les_unites_posees()


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


# --- La partie sauvegardée ---
#
# Les routes ne connaissent pas MongoDB : elles passent par le dépôt que la factory a accroché à
# l'application (voir `moteur/depots/`), et n'échangent avec lui que des dicts d'état. Sous la
# configuration de test — et sous `PERSISTANCE=aucune` — ce dépôt ne retient rien, et tout se
# passe comme avant : chaque chargement de « / » repart de la mise en place.


def le_depot():
    """Le dépôt de partie de l'application courante."""
    return current_app.extensions["depot_de_partie"]


def le_depot_de_joueurs():
    """Le dépôt de joueurs de l'application courante."""
    return current_app.extensions["depot_de_joueurs"]


def le_depot_de_vues():
    """Le dépôt des vues de la carte de l'application courante (voir `models/vue.py`)."""
    return current_app.extensions["depot_de_vues"]


def la_vue_du_joueur():
    """Où le joueur de la session en était sur la carte, ou `None`.

    `None` pour un anonyme comme pour un joueur qui n'a encore rien réglé : dans les deux cas la
    page s'ouvre ajustée à la fenêtre, comme elle l'a toujours fait.
    """
    joueur = le_joueur_courant()
    return le_depot_de_vues().par_discord_id(joueur["discord_id"]) if joueur else None


def lire_une_vue(donnees):
    """La vue envoyée par le navigateur, ramenée à ses quatre champs — ou `None` si elle ne l'est
    pas.

    Le corps vient du dehors : on n'y prend que ce qu'on attend, et on refuse ce qui n'est pas un
    nombre. L'échelle n'est pas bornée ici — c'est `appliquer` (`static/zoom.js`) qui la borne
    pour de bon, à la pose comme à la reprise, et une borne de plus, écrite ailleurs, finirait par
    dire autre chose que celle-là.
    """
    if not isinstance(donnees, dict):
        return None
    try:
        vue = {champ: float(donnees[champ]) for champ in ("echelle", "x", "y")}
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(valeur) for valeur in vue.values()):
        return None
    vue["ajustee"] = bool(donnees.get("ajustee"))
    return vue


def photographier_la_partie():
    """Tout l'état de jeu du serveur, sous la forme que le dépôt sait écrire.

    Rien d'autre ne change en jouant : la carte, les cartons et le scénario sont des référentiels
    lus au démarrage, et c'est le numéro du scénario qui dit sur laquelle de ces mises en place
    la sauvegarde se lit.
    """
    return {"scenario": NUMERO_DU_SCENARIO,
            "placement": PLATEAU.en_dict(),
            "inclinaisons": PLATEAU.inclinaisons,
            "camp_actif": TOUR.camp_actif,
            "type_de_phase": TOUR.type_de_phase,
            "numero_de_tour": TOUR.numero} | SUIVI.en_dict() | PLACES.en_dict()


def restaurer_la_partie(etat):
    """Repose le plateau, le tour, le registre des combats et la table tels qu'une sauvegarde les
    tenait.

    `.get` sur les places : une partie enregistrée avant les joueurs n'en a pas, et elle doit
    rester reprenable — la table est alors simplement vide, et chacun vient s'y asseoir.
    """
    # Les inclinaisons se reposent avec les pions : une partie reprise retrouve ses cartons
    # couchés comme on les a laissés. `.get` pour la même raison que les places — une sauvegarde
    # d'avant qu'on les retienne n'en a pas, et le plateau en tire alors des neuves.
    PLATEAU.restaurer(etat["placement"], etat.get("inclinaisons"))
    TOUR.restaurer(etat["camp_actif"], etat["type_de_phase"], etat["numero_de_tour"])
    SUIVI.restaurer(etat["attaquants_engages"], etat["cibles_engagees"])
    PLACES.restaurer(etat.get("places"))


def sauvegarder_la_partie():
    """Enregistre la partie après un coup joué — un déplacement, un combat, un changement de phase.

    C'est aussi le point de passage obligé de tout ce qui bouge : la version monte ici, et le
    navigateur de l'adversaire l'apprend à son prochain sondage.
    """
    marquer_un_coup()
    le_depot().sauvegarder(photographier_la_partie())


def faire_jouer_l_ia():
    """Si le camp actif est tenu par l'IA, elle joue son tour entier, et la partie est sauvée.

    Le tour se joue en entier dans la requête — mouvement, combat, et la main rendue au camp
    d'en face : quelques millisecondes pour une trentaine d'unités. Une seule sauvegarde à la
    fin ; la version monte, et le navigateur voit les coups de l'IA à son prochain sondage,
    comme il verrait ceux d'un adversaire humain.

    Un `if`, pas un `while` : l'IA ne tient qu'un camp — la création de partie y veille — et
    son tour joué rend toujours la main. Une sauvegarde ne tombe donc jamais sur une phase
    tenue par l'IA, et « / » n'a jamais à la faire jouer.
    """
    if PLACES.occupant(TOUR.camp_actif) != ia.JOUEUR_IA:
        return
    deplacements, combats = ia.jouer_le_tour(PLATEAU, TOUR, SUIVI, lancer_le_de)
    for depart, arrivee in deplacements:
        JOURNAL.info("IA : déplacement %s → %s", depart.cle, arrivee.cle)
    for cible, attaquants, resultat in combats:
        message = MESSAGES_DE_COMBAT.get(resultat.resultat, "Combat résolu : sans effet")
        if resultat.detail is not None:
            JOURNAL.info("IA : %s", detailler_le_rapport(resultat))
        JOURNAL.info("IA : %s attaquant(s) sur %s — %s",
                     len(attaquants), cible.cle, message)
    JOURNAL.info("IA : tour joué — %s (tour %s)", TOUR.libelle, TOUR.numero)
    sauvegarder_la_partie()


def les_unites_posees():
    """Les unités du plateau sous la forme que le navigateur attend, comme à la mise en place.

    Tout ce qui n'est pas la case vient du catalogue — l'image, le nom, les valeurs du carton —,
    et l'entrée en part entière : ce qu'on lui ajoutera suivra tout seul. Seul `chemin` est
    renommé, en `image`, parce que c'est ce que le navigateur met dans `src`. S'y ajoute
    l'inclinaison, qui n'est pas du carton mais du plateau : elle dit comment **ce** pion-ci est
    couché, et le navigateur la reprend telle quelle au lieu d'en tirer une (voir
    `moteur/plateau.py`).

    Une partie neuve passe par ici comme une partie reprise : `poser_la_mise_en_place` pose les
    pions du scénario, puis appelle cette fonction.
    """
    poses = []
    for case, pion_pose in PLATEAU.pions.items():
        hexagone = Hex.depuis_cle(case)
        pion = dict(PIONS_PAR_CLE[pion_pose.cle])
        poses.append({"q": hexagone.q, "r": hexagone.r, "s": hexagone.s,
                      "inclinaison": PLATEAU.inclinaison_sur(hexagone),
                      "image": pion.pop("chemin")} | pion)
    return poses


# --- Les joueurs -------------------------------------------------------------------------------
#
# Deux joueurs, un par camp, identifiés par Discord. Le serveur ne les distingue que par leur
# identifiant Discord — celui-là même qui voyage dans la session, dans les places et dans le dict
# d'état : il n'y a qu'une notion d'identité dans tout le projet.
#
# Ce que la session porte, et la façon de l'ouvrir, sont dans un seul endroit : `Connexion`
# (`models/connexion.py`), le seul modèle que l'application se garde. Les routes ne touchent plus
# à `session` elles-mêmes — elles demandent `la_connexion()`, qui désigne le joueur du **moteur**
# par son identifiant Discord et va le relire au dépôt. Le pseudo et l'avatar ne sont donc jamais
# recopiés dans la session : un changement de pseudo se voit dès la requête suivante.


def le_client_discord():
    """Le client d'identité de l'application courante — le vrai, ou le factice des tests."""
    return current_app.extensions["discord"]


def la_connexion():
    """La connexion de la requête courante : la session, et le dépôt où relire le joueur.

    Un objet de passage, sans état propre : le construire ne coûte rien, et il n'y a donc pas à
    le retenir.
    """
    return Connexion(session, le_depot_de_joueurs())


def le_joueur_courant():
    """Le joueur de la session, ou `None`.

    Retenu sur `g` : plusieurs décorateurs le demandent dans une même requête, et ce serait autant
    d'allers-retours en base. Un identifiant qui ne correspond plus à personne — base vidée, dépôt
    de mémoire d'un serveur relancé — rend `None` sans faire d'histoire : le visiteur redevient
    anonyme.
    """
    if "joueur" not in g:
        g.joueur = la_connexion().joueur()
    return g.joueur


def est_administrateur(joueur):
    """Dit si ce joueur peut corriger la carte — voir `ADMINISTRATEURS` dans `config.py`."""
    return joueur is not None and joueur["discord_id"] in current_app.config["ADMINISTRATEURS"]


def la_table():
    """La table telle que la voit le visiteur de la requête courante."""
    return la_table_de(le_joueur_courant())


def la_table_de(joueur):
    """Qui regarde, qui tient quoi — sous la forme que le navigateur reçoit.

    Les identifiants Discord n'en sont pas : le navigateur n'a besoin que d'un pseudo et d'un
    avatar pour dire qui tient l'Alliance, et servir un identifiant à tout visiteur serait donner
    une donnée personnelle pour rien.

    Le joueur est passé plutôt que lu dans la session : c'est la **seule** part de l'état qui
    diffère d'un spectateur à l'autre, et le flux SSE la compose hors de toute requête, pour un
    joueur qu'il a relu au dépôt lui-même (voir `/flux`). Les routes, elles, appellent
    `la_table()` et ne voient aucune différence.
    """

    def occupant_de(camp):
        """Le joueur assis à ce camp — l'IA n'est pas en base, elle n'a qu'un nom."""
        occupant = PLACES.occupant(camp)
        if occupant == ia.JOUEUR_IA:
            return {"pseudo": ia.NOM_IA}
        return le_depot_de_joueurs().par_discord_id(occupant)

    occupants = {camp: occupant_de(camp) for camp in SCENARIO.camps}
    return {
        "connecte": joueur is not None,
        "pseudo": joueur["pseudo"] if joueur else None,
        "avatar": joueur["avatar"] if joueur else None,
        "administrateur": est_administrateur(joueur),
        # Une liste, et non un camp : d'ordinaire zéro ou un, mais la suite de tests assied un
        # même joueur des deux côtés pour jouer la partie à elle seule.
        "camps": PLACES.camps_de(joueur["discord_id"]) if joueur else [],
        "armees": {armee["camp"]: armee["armee"] for armee in SCENARIO.armees},
        "places": {camp: (occupant["pseudo"] if occupant else None)
                   for camp, occupant in occupants.items()},
    }


def connexion_requise(vue):
    """Refuse la route à qui n'a pas ouvert de session — 401, « je ne sais pas qui vous êtes »."""
    @wraps(vue)
    def enveloppe(*args, **kwargs):
        if le_joueur_courant() is None:
            return {"autorise": False, "message": "Connectez-vous pour jouer."}, 401
        return vue(*args, **kwargs)
    return enveloppe


def place_requise(vue):
    """Refuse la route à qui ne tient aucun camp — 403, « vous n'êtes pas à la table »."""
    @wraps(vue)
    @connexion_requise
    def enveloppe(*args, **kwargs):
        if not PLACES.camps_de(le_joueur_courant()["discord_id"]):
            return {"autorise": False, "message": "Prenez place à un camp pour jouer."}, 403
        return vue(*args, **kwargs)
    return enveloppe


def camp_actif_requis(vue):
    """Refuse la route à qui ne tient pas le camp dont c'est la phase — 403, « pas votre tour ».

    Le décorateur ne regarde que la **place**. Le type de phase et le camp du pion visé restent
    vérifiés dans les routes, depuis le tour et le plateau : un mouvement hors de la phase de
    mouvement continue de rendre 200 et `autorise: false`, un combat hors phase 200 et
    `resolu: false`. C'est cette frontière qui laisse intactes les vérifications d'avant.
    """
    @wraps(vue)
    @connexion_requise
    def enveloppe(*args, **kwargs):
        if not PLACES.tient(le_joueur_courant()["discord_id"], TOUR.camp_actif):
            return {"autorise": False,
                    "message": f"C'est au camp {TOUR.armee_active} de jouer."}, 403
        return vue(*args, **kwargs)
    return enveloppe


def administrateur_requis(vue):
    """Réserve la route aux comptes déclarés dans `ADMIN_DISCORD_IDS`.

    Une liste vide n'admet personne : une variable de sécurité dont l'absence ouvrirait tout
    serait un piège, et le refus dit comment s'y déclarer.
    """
    @wraps(vue)
    @connexion_requise
    def enveloppe(*args, **kwargs):
        if not est_administrateur(le_joueur_courant()):
            return {"autorise": False,
                    "message": "Corriger la carte demande un compte déclaré dans "
                               "ADMIN_DISCORD_IDS."}, 403
        return vue(*args, **kwargs)
    return enveloppe


def diagnostic_de_l_etat_oauth(attendu, recu):
    """Pourquoi l'état anti-CSRF ne passe pas, en clair pour le journal.

    Trois cas, et ils ne se soignent pas pareil : un état absent de la **session** veut dire que
    le cookie posé au départ n'est pas revenu — hôte différent entre l'aller et le retour
    (`localhost` contre `127.0.0.1`), cookie « Secure » sur du http, session vidée entre-temps ;
    un état absent de la **requête**, que Discord n'a pas rendu le paramètre ; deux états
    différents, un retour rejoué ou forgé. Le journal dit lequel, l'hôte demandé et si un cookie
    de session est arrivé du tout — sans jamais écrire les états eux-mêmes.
    """
    if not attendu:
        cause = "état d'authentification absent de la session"
    elif not recu:
        cause = "état d'authentification absent de la requête"
    else:
        cause = "état d'authentification différent de celui de la session"
    return f"{cause} (hôte {request.host}, {etat_du_cookie_de_session()})"


def etat_du_cookie_de_session():
    """Le cookie de session tel qu'il est arrivé : absent, illisible, ou lisible et portant quoi.

    Un cookie **présent mais vide de l'état** a deux explications qui ne se ressemblent pas, et
    seule cette ligne les départage. Illisible — la signature ne passe pas —, c'est qu'il a été
    signé par une autre `SECRET_KEY` : la clé a changé dans `.env`, ou deux serveurs se
    répondent sur le même hôte. Lisible, c'est qu'une autre requête a réécrit le cookie entre
    l'aller et le retour — un onglet voisin, un sondage en vol — et la liste des clés qu'il
    porte encore dit d'où venait cette session-là. Les clés seules : jamais les valeurs.
    """
    cookie = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
    if cookie is None:
        return "cookie de session absent"
    try:
        current_app.session_interface.get_signing_serializer(current_app).loads(cookie)
    except BadSignature:
        return "cookie de session présent mais illisible — signé par une autre SECRET_KEY ?"
    contenu = ", ".join(sorted(session.keys()))
    return f"cookie de session lisible, session {'portant ' + contenu if contenu else 'vide'}"


@jeu.route("/connexion")
def connexion():
    """Part chez Discord, avec un état à usage unique contre le CSRF."""
    etat = la_connexion().poser_un_etat_oauth()
    return redirect(le_client_discord().url_d_autorisation(etat))


@jeu.route("/connexion/retour")
def retour_de_connexion():
    """Le retour de Discord : on vérifie l'état, on échange le code, on ouvre la session.

    L'état est **retiré** de la session avant toute chose — c'est `Connexion.reprendre_l_etat_oauth`
    qui s'en charge : un retour rejoué ne trouvera plus rien à quoi se comparer. La comparaison
    passe par `compare_digest` — c'est un secret, il ne se compare pas caractère à caractère.
    """
    if request.args.get("error"):  # le joueur a refusé sur la page de Discord
        return redirect(url_for("jeu.plateau"))

    connexion = la_connexion()
    attendu = connexion.reprendre_l_etat_oauth()
    recu = request.args.get("state")
    if not attendu or not recu or not secrets.compare_digest(attendu, recu):
        JOURNAL.info("Connexion refusée : %s", diagnostic_de_l_etat_oauth(attendu, recu))
        abort(400, "état d'authentification absent ou inattendu")
    code = request.args.get("code")
    if not code:
        JOURNAL.info("Connexion refusée : code d'autorisation absent de la requête")
        abort(400, "code d'autorisation absent")

    # Pas de `try` autour des deux échanges : une `ErreurDiscord` remonte telle quelle, avec le
    # statut et le corps de la réponse de Discord dans son message, et Flask en trace la pile.
    # L'attraper pour rendre un 502 muet ne laissait que « Discord n'a pas répondu » à lire.
    jeton = le_client_discord().echanger_le_code(code)
    identite = le_client_discord().identite(jeton)

    joueur = connexion.ouvrir(identite)
    JOURNAL.info("Connexion : %s", joueur["pseudo"])
    return redirect(url_for("jeu.plateau"))


@jeu.route("/deconnexion", methods=["POST"])
def deconnexion():
    """Ferme la session. La place tenue n'est pas rendue : on revient s'y asseoir.

    En POST, comme tout ce qui change quelque chose ici : un lien ou une image d'un autre site ne
    doit pas pouvoir déconnecter le joueur.
    """
    la_connexion().fermer()
    return {"connecte": False}


@jeu.route("/partie/place", methods=["POST"])
@connexion_requise
def prendre_place():
    """S'asseoir à un camp libre — corps `{"camp": "alliance"}`.

    Deux règles, et elles ne vivent pas au même endroit : un camp occupé ne se reprend pas, et
    c'est le registre qui la tient ; un joueur ne tient qu'un camp, et c'est ici et nulle part
    ailleurs — un joueur assis des deux côtés jouerait seul contre lui-même.
    """
    camp = (request.get_json(silent=True) or {}).get("camp")
    if camp not in SCENARIO.camps:
        abort(400, f"camp inconnu ; attendu l'un de {', '.join(SCENARIO.camps)}")

    joueur = le_joueur_courant()["discord_id"]
    if PLACES.tient(joueur, camp):
        return {"assis": True, "camp": camp} | la_table()
    if PLACES.camps_de(joueur):
        return {"assis": False, "message": "Vous tenez déjà un camp."} | la_table(), 409
    if not PLACES.est_libre(camp):
        return {"assis": False, "message": "Ce camp est déjà tenu."} | la_table(), 409

    PLACES.asseoir(camp, joueur)
    JOURNAL.info("Place prise : %s par %s", camp, le_joueur_courant()["pseudo"])
    sauvegarder_la_partie()
    return {"assis": True, "camp": camp} | la_table()


@jeu.route("/partie/place/quitter", methods=["POST"])
@connexion_requise
def quitter_la_place():
    """Rend sa place : le camp redevient libre, la partie reste où elle en est."""
    joueur = le_joueur_courant()["discord_id"]
    for camp in PLACES.camps_de(joueur):
        PLACES.liberer(camp)
    sauvegarder_la_partie()
    return {"assis": False} | la_table()


@jeu.route("/vue", methods=["POST"])
@connexion_requise
def enregistrer_la_vue():
    """Retient où le joueur en est sur la carte — corps `{echelle, x, y, ajustee}`.

    C'est la seule route de tout le serveur qui n'a rien à voir avec la partie : elle ne touche ni
    au plateau, ni au tour, ni à la version, et **ne publie rien** — une vue n'appartient qu'à une
    paire d'yeux, et la pousser au flux ferait sauter la carte de l'autre joueur. Elle n'est donc
    pas non plus un coup joué : rien ne monte, rien n'est diffusé.

    Connexion requise, et pas de place : on retient la vue d'un spectateur connecté comme celle
    d'un joueur assis. Un anonyme, lui, n'a pas d'endroit où la ranger.
    """
    vue = lire_une_vue(request.get_json(silent=True))
    if vue is None:
        abort(400, "vue illisible ; attendu {echelle, x, y, ajustee}")
    return le_depot_de_vues().enregistrer(le_joueur_courant()["discord_id"], vue)


@jeu.route("/")
def plateau():
    """La carte, ses pions et la phase courante.

    La partie est reprise là où on l'a laissée : le dépôt rend la dernière sauvegarde, et le
    serveur la repose. Faute de sauvegarde — première visite, base vide, dépôt nul —, ou si la
    sauvegarde est celle d'un autre scénario que celui qu'on joue, la mise en place du scénario
    est refaite et une nouvelle partie ouverte.
    """
    etat = le_depot().charger()
    if etat is None or etat["scenario"] != NUMERO_DU_SCENARIO:
        poses = poser_la_mise_en_place()
        le_depot().nouvelle_partie(photographier_la_partie())
    else:
        restaurer_la_partie(etat)
        poses = les_unites_posees()
    return render_template(
        "carte.html",
        pions=json.dumps(poses, ensure_ascii=False),
        grille=json.dumps({"origine": GRILLE_ORIGINE, "matrice": GRILLE_MATRICE,
                           "taille_pion": PION_TAILLE}),
        phase=json.dumps(la_phase_courante(), ensure_ascii=False),
        table=json.dumps(la_table(), ensure_ascii=False),
        journal=json.dumps(les_lignes_du_journal(), ensure_ascii=False),
        vue=json.dumps(la_vue_du_joueur()),
        version=VERSION,
    )


@jeu.route("/partie/nouvelle", methods=["POST"])
@place_requise
def nouvelle_partie():
    """Recommence : la mise en place du scénario, et une partie neuve en base.

    Les parties précédentes restent en base — c'est le dépôt qui en décide —, mais celle-ci
    devient la plus récente, donc celle que « / » reprendra.

    Avec un corps `{"contre_ia": true}`, le camp que le demandeur ne tient pas est confié à
    l'IA — s'il est libre, ou déjà à elle : on ne met pas un joueur humain à la porte. Et si le
    scénario ouvre sur le camp de l'IA, elle joue son premier tour dans la foulée : la réponse
    porte les pions tels qu'elle les a laissés.
    """
    contre_ia = bool((request.get_json(silent=True) or {}).get("contre_ia"))
    if contre_ia:
        joueur = le_joueur_courant()["discord_id"]
        camps_adverses = [camp for camp in SCENARIO.camps if not PLACES.tient(joueur, camp)]
        if not camps_adverses:
            return {"message": "Aucun camp à confier à l'IA."} | la_table(), 409
        for camp in camps_adverses:
            if PLACES.occupant(camp) not in (None, ia.JOUEUR_IA):
                return {"message": "Ce camp est déjà tenu."} | la_table(), 409

    # La table est mise, puis la ligne écrite, et la mise en place seulement ensuite : c'est elle
    # qui marque le coup et pousse la partie aux flux ouverts (voir `instantane_partage`), et
    # elle doit la pousser avec l'IA déjà assise et la ligne déjà au journal.
    if contre_ia:
        for camp in camps_adverses:
            PLACES.asseoir(camp, ia.JOUEUR_IA)
        JOURNAL.info("Nouvelle partie contre l'IA : scénario %s, l'IA tient %s",
                     NUMERO_DU_SCENARIO, ", ".join(camps_adverses))
    else:
        JOURNAL.info("Nouvelle partie : scénario %s", NUMERO_DU_SCENARIO)
    poser_la_mise_en_place()
    le_depot().nouvelle_partie(photographier_la_partie())
    faire_jouer_l_ia()
    return {"pions": les_unites_posees(), "phase": la_phase_courante()} | la_table()


@jeu.route("/partie/etat")
def etat_de_la_partie():
    """Où en est la partie — le **repli** du flux SSE, et rien de plus.

    C'est la route que le navigateur sondait toutes les trois secondes. Il ne la sonde plus : il
    tient un flux ouvert (`/flux`) et le serveur lui pousse la partie quand elle change. Elle
    reste servie pour deux raisons, et elle est écrite pour n'avoir jamais à changer :

    - un navigateur dont l'`EventSource` échoue cinq fois de suite y retombe (voir
      `suivreLaPartie` dans `carte.js`) — un intermédiaire qui casse le SSE ne doit pas casser
      le jeu ;
    - elle dit l'état en un aller-retour, ce qui est commode à interroger.

    Avec `?version=N`, elle ne rend que le numéro tant que rien n'a bougé ; dès que la version a
    changé, tout revient d'un coup — les pions, la phase, la table — et le navigateur repose la
    scène.

    Elle est publique : un visiteur de passage suit la partie comme il voit la carte.
    """
    connue = request.args.get("version", type=int)
    if connue == VERSION:
        return {"version": VERSION, "change": False}
    return {"version": VERSION, "change": True, "pions": les_unites_posees(),
            "phase": la_phase_courante(), "table": la_table(),
            "journal": les_lignes_du_journal()}


# --- Le flux : la partie poussée à ceux qui la regardent ---------------------------------------
#
# Un `GET /flux` par onglet ouvert, qui ne se referme jamais de lui-même. Le serveur y écrit un
# message à chaque coup joué — pas une seconde avant, pas une de plus —, et un simple commentaire
# de loin en loin pour que la connexion reste vivante.
#
# Le format est celui du Server-Sent Events, que le navigateur sait lire tout seul par
# `EventSource` : reconnexion comprise, avec l'identifiant du dernier message reçu en
# `Last-Event-ID`. Cet identifiant, ici, est le numéro de version de la partie — il ne restait
# rien à inventer.

# Le battement de cœur : au bout de ce silence, le flux écrit un commentaire SSE plutôt que rien.
# Une ligne qui commence par « : » est ignorée par le navigateur, mais elle traverse la
# connexion, et c'est tout ce qu'on lui demande — sans quoi un pare-feu, un proxy ou le
# navigateur lui-même finirait par refermer une connexion qu'il croit morte.
#
# TODO: PRODUCTION — 20 s tient sous les valeurs par défaut usuelles (Nginx `proxy_read_timeout`
# à 60 s, ALB à 60 s). Voir `DEPLOIEMENT.md` : augmenter le timeout de l'intermédiaire plutôt que
# de descendre celui-ci.
BATTEMENT = 20  # secondes


def message_sse(etat, joueur):
    """Un événement SSE : l'état partagé, la table de *ce* joueur, et la version pour identifiant.

    L'identifiant est ce que le navigateur renverra en `Last-Event-ID` s'il se reconnecte : le
    serveur saura alors s'il a manqué quelque chose entre-temps.
    """
    corps = json.dumps(etat | {"table": la_table_de(joueur)}, ensure_ascii=False)
    return f"id: {etat['version']}\ndata: {corps}\n\n"


def flux_de_la_partie(application, identifiant, version_connue):
    """Le générateur du flux : l'état d'entrée s'il y a lieu, puis un message par coup joué.

    Il tourne **hors de toute requête** — werkzeug le déroule après que la vue a rendu sa
    réponse. D'où le contexte d'application poussé à la main : composer la table demande le dépôt
    de joueurs et la liste des administrateurs, tous deux accrochés à l'application.

    Ce contexte est poussé et retiré **entre deux `yield`**, jamais à cheval sur l'un d'eux, et
    c'est la seule façon de faire : Flask tient ses contextes dans des `ContextVar`, qu'un
    générateur ne possède pas en propre — il les partage avec qui le déroule. Un `with
    application.app_context():` enveloppant la boucle serait entré dans un appelant et quitté
    dans un autre, et Flask le dit sans détour : « Popped wrong app context ».

    On ne se sert pas non plus de `stream_with_context`, qui garderait le contexte de *requête*
    ouvert pour toute la durée du flux — c'est-à-dire tant que l'onglet reste ouvert : `g.joueur`
    y serait mis en cache une fois pour toutes, et un joueur qui change de pseudo ou quitte sa
    place ne le verrait jamais. Ici le joueur est relu au dépôt à chaque message, comme partout
    ailleurs dans le projet.

    L'abonnement, lui, enveloppe bien toute la boucle : c'est un objet à nous, sans `ContextVar`.
    Quoi qu'il arrive — onglet fermé, réseau coupé, serveur arrêté —, le générateur est fermé,
    `GeneratorExit` traverse le `with`, et l'abonné est radié.
    """
    joueurs = application.extensions["depot_de_joueurs"]

    def composer(etat):
        """Le message à écrire, table comprise — le seul endroit qui demande l'application."""
        with application.app_context():
            joueur = joueurs.par_discord_id(identifiant) if identifiant else None
            return message_sse(etat, joueur)

    with DIFFUSEUR.abonnement() as abonne:
        # L'état d'entrée. Le navigateur arrive avec le numéro qu'il connaît — du gabarit à la
        # première connexion, du `Last-Event-ID` à une reconnexion. S'il est à jour, on ne lui
        # renvoie pas tout le plateau pour rien : un commentaire suffit à ouvrir le flux, ce qui
        # fait passer son `EventSource` à l'état « ouvert ». S'il ne l'est pas — l'adversaire a
        # joué pendant la coupure, ou le serveur a redémarré et sa version est repartie de
        # zéro —, il rattrape tout d'un coup.
        yield ": partie suivie\n\n" if version_connue == VERSION \
            else composer(instantane_partage())

        while True:
            etat = abonne.attendre(BATTEMENT)
            yield ": battement\n\n" if etat is None else composer(etat)


@jeu.route("/flux")
def flux_de_partie():
    """Le flux d'événements de la partie. Publique, comme `/partie/etat`.

    La version que connaît le navigateur vient de deux endroits, et jamais des deux à la fois :
    `?version=N` à la première connexion — un `EventSource` ne peut pas poser d'en-tête —, et
    l'en-tête `Last-Event-ID` que le navigateur renvoie de lui-même à chaque reconnexion. C'est
    ce dernier qui prime : il est plus récent que l'URL, qui date de l'ouverture de la page.

    Tout ce que le générateur aura besoin de savoir est capturé **ici**, tant qu'on est encore
    dans la requête : l'objet application, et l'identifiant Discord de la session. Le générateur,
    lui, tourne après.
    """
    dernier = request.headers.get("Last-Event-ID")
    version_connue = _en_entier(dernier) if dernier is not None \
        else request.args.get("version", type=int)

    reponse = current_app.response_class(
        flux_de_la_partie(current_app._get_current_object(),
                          la_connexion().identifiant, version_connue),
        mimetype="text/event-stream")
    reponse.headers["Cache-Control"] = "no-cache"
    reponse.headers["Connection"] = "keep-alive"
    # TODO: PRODUCTION — Nginx tamponne les réponses par défaut, et retiendrait chaque message
    # jusqu'à remplir son tampon : le jeu paraîtrait figé. Cet en-tête le lui interdit pour cette
    # réponse-ci, sans rien avoir à configurer. Le `proxy_buffering off;` de `DEPLOIEMENT.md`
    # dit la même chose côté serveur ; les deux ensemble, l'un ne dépendant pas de l'autre.
    reponse.headers["X-Accel-Buffering"] = "no"
    return reponse


def _en_entier(texte):
    """Le `Last-Event-ID` en entier, ou `None` s'il ne l'est pas.

    L'en-tête vient du navigateur : il peut être vide — c'est ce qu'envoie un `EventSource` qui
    n'a encore rien reçu — ou n'importe quoi. Un `None` fait simplement renvoyer l'état complet.
    """
    try:
        return int(texte)
    except ValueError:
        return None


@jeu.route("/deplacements")
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


@jeu.route("/deplacer", methods=["POST"])
@camp_actif_requis
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
    autorise = not hors_phase and PLATEAU.deplacer(depart, arrivee, pion)
    if autorise:
        sauvegarder_la_partie()
    # Le carton repris en main s'est recouché : c'est le plateau qui a tiré l'angle, et le
    # navigateur le reçoit plutôt que d'en tirer un de son côté — sans quoi le pion se
    # recoucherait encore au premier rechargement de la page.
    return decrit | {"autorise": autorise, "arrivee": arrivee.en_dict(),
                     "inclinaison": PLATEAU.inclinaison_sur(arrivee)}


def decrire_un_deplacement(depart, pion):
    """Ce que le serveur sait de l'unité qui part : sa case, son pion, son camp, ses points."""
    pose = PLATEAU.pion_sur(depart) or pion
    return {
        "depart": depart.en_dict(),
        "pion": pose.cle if pose else None,
        "camp": pose.camp if pose else None,
        "mouvement": PLATEAU.mouvement_de(depart, pion),
    }


@jeu.route("/phase")
def phase_courante():
    """La phase en cours — le navigateur s'en sert pour son libellé et ses blocages."""
    return la_phase_courante()


@jeu.route("/phase/suivante", methods=["POST"])
@camp_actif_requis
def phase_suivante():
    """Passe à la phase suivante ; la magie est franchie d'elle-même.

    Le registre des combats est vidé au passage : chaque phase de combat repart avec toutes ses
    unités disponibles, celle des Ténèbres comme celle de l'Alliance, à ce tour-ci comme au suivant.
    """
    TOUR.suivante()
    SUIVI.reinitialiser()
    JOURNAL.info("Phase : %s (tour %s)", TOUR.libelle, TOUR.numero)
    sauvegarder_la_partie()
    faire_jouer_l_ia()
    return la_phase_courante()


def lire_un_hexagone_prefixe(prefixe, source):
    """Un `Hex` depuis `{prefixe}q`, `{prefixe}r`, `{prefixe}s` — pour deux hexagones dans l'URL."""
    return lire_un_hexagone({nom: source.get(f"{prefixe}{nom}") for nom in ("q", "r", "s")})


@jeu.route("/combat/portee")
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


@jeu.route("/combat/cible")
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


@jeu.route("/combat", methods=["POST"])
@camp_actif_requis
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
    # Le calcul d'abord, l'issue ensuite : la colonne du navigateur se lit à l'envers du fichier,
    # et l'issue s'y retrouve donc en tête, son détail juste dessous.
    if resultat.detail is not None:
        JOURNAL.info(detailler_le_rapport(resultat))
    JOURNAL.info(message)
    sauvegarder_la_partie()
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


@jeu.route("/admin/map_fix")
@administrateur_requis
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


@jeu.route("/admin/map_fix", methods=["POST"])
@administrateur_requis
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


@jeu.route("/carte.jpg")
def image_de_la_carte():
    return send_from_directory(BOITE, "map.jpg")


@jeu.route("/pions/<path:chemin>")
def image_de_pion(chemin):
    if not est_un_pion(chemin):
        abort(404)
    return send_from_directory(PIONS, chemin)


def create_app(config=None):
    """Construit l'application : la configuration, la persistance, puis les routes.

    Tout Flask naît ici — le module n'a plus d'app globale, seulement le blueprint `jeu` et
    l'état de jeu. La persistance est branchée sous forme de dépôt (voir `moteur/depots/`), accroché
    aux extensions de l'app : les routes le retrouvent par `le_depot()` et ne savent rien de
    MongoDB. Les imports de la branche Mongo sont faits ici, et pas en tête de fichier, pour
    qu'une app sans persistance — celle des tests — se construise sans mongoengine.
    """
    application = Flask(__name__)
    application.config.from_object(config or Config)

    # Échec franc au démarrage plutôt qu'une erreur de Flask au premier `session[...]`, c'est-à-dire
    # au premier clic sur « se connecter ».
    if not application.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY manquante : sans elle, aucune session ne peut être signée. En poser une "
            "dans .env — python3 -c \"import secrets; print(secrets.token_hex(32))\"")

    if application.config["PERSISTANCE"] == "mongo":
        from depots.vue import DepotDeVuesMongo
        from extensions import db
        from moteur.depots.joueur import DepotDeJoueursMongo
        from moteur.depots.partie import DepotDePartieMongo
        db.init_app(application)  # avant les routes, et une seule fois : l'instance est partagée
        depot, joueurs, vues = DepotDePartieMongo(), DepotDeJoueursMongo(), DepotDeVuesMongo()
    else:
        from depots.vue import DepotDeVuesEnMemoire
        from moteur.depots.joueur import DepotDeJoueursEnMemoire
        from moteur.depots.partie import DepotDePartieNul
        depot, joueurs, vues = (DepotDePartieNul(), DepotDeJoueursEnMemoire(),
                                DepotDeVuesEnMemoire())
    application.extensions["depot_de_partie"] = depot
    application.extensions["depot_de_joueurs"] = joueurs
    # La vue de la carte n'est pas du jeu : son modèle et son dépôt sont à l'application
    # (`models/vue.py`, `depots/vue.py`), et non au moteur, qui ne sait pas qu'il existe une image.
    application.extensions["depot_de_vues"] = vues

    if application.config["AUTHENTIFICATION"] == "discord":
        from client_discord import ClientDiscord
        application.extensions["discord"] = ClientDiscord(
            application.config["DISCORD_CLIENT_ID"],
            application.config["DISCORD_CLIENT_SECRET"],
            application.config["DISCORD_REDIRECT_URI"])
    else:
        from client_discord import ClientDiscordFactice
        application.extensions["discord"] = ClientDiscordFactice()

    application.register_blueprint(jeu)
    return application


if __name__ == "__main__":
    create_app().run(debug=True)
