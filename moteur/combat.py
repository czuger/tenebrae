"""La résolution des combats d'Ave Tenebrae : le Tableau I du fascicule, et rien de plus.

Le fascicule (`game_box/ave_tenebrae_regles.md`, § « Combats ») donne une table à double entrée —
le rapport de force en colonnes, le jet de dé en lignes — dont chaque case dit l'issue de la
bataille : attaquant éliminé, défenseur éliminé, échange, ou l'un des deux reculs. Ce module
transcrit cette table, calcule le rapport de force (« toujours arrondi en faveur du défenseur »)
et applique les modificateurs de terrain du *Tableau des terrains*.

Les reculs ne sont pas joués : `AR` et `DR` laissent le plateau intact. `EX` retire les unités
engagées, sans le tri « attaquants totalisant une force au moins égale » du fascicule — mais
**les tireurs y échappent** : « une unité tirant des missiles ne peut en aucun cas subir un
résultat de retraite ou d'échange ». Les facultés spéciales, la charge de cavalerie, les phalanges
et l'alternance jour/nuit sont hors de portée — voir `moteur/README.md`.

`SuiviDeCombat` tient à part ce qu'une phase de combat a déjà consommé : une unité n'attaque
qu'une fois, une unité n'est attaquée qu'une fois. C'est un registre, pas une résolution — il ne
touche ni au plateau ni au tour, et se vide à chaque nouvelle phase de combat.
"""

# Les cinq issues possibles. Seules `AE`, `DE` et `EX` changent quelque chose au plateau ; `AR` et
# `DR` — les reculs — sont lus mais laissés sans effet, faute de règle de retraite.
AE, DE, EX, AR, DR = "AE", "DE", "EX", "AR", "DR"

# Les dix rapports de force du Tableau I, de 1 contre 5 à 6 contre 1, attaquant au numérateur.
COLONNES = ((1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1))

# Tableau I, transcrit tel quel : jet de dé (1 à 6) → issue pour chacune des dix colonnes.
TABLEAU_I = {
    1: (AR, AR, DR, DR, DR, DR, DR, DE, DE, DE),
    2: (AE, AR, AR, DR, DR, DR, DR, DR, DE, DE),
    3: (AE, AE, AR, AR, DR, DR, DR, DR, DE, DE),
    4: (AE, AE, AR, AR, AR, DR, DR, DR, DR, DE),
    5: (AE, AE, AE, AR, AR, AR, DR, DR, DR, EX),
    6: (AE, AE, AE, AR, AR, AR, AR, EX, EX, EX),
}

# Colonne « Combat » du *Tableau des terrains* : le terrain du défenseur multiplie sa force.
DEFENSE_MULTIPLIEE = {"montagne": 3, "fort": 3, "chateau": 3,
                      "riviere": 2, "lac": 2, "ruines": 2, "village": 2}

# Le fascicule réserve le « × 2 en défense » du bois aux seuls Elfes.
FACTION_DES_ELFES = "09-elfes"

# Bois et collines ajoutent 2 au dé de l'attaquant, quel que soit le défenseur.
BONUS_AU_DE = {"bois", "colline"}


def colonne_du_rapport(force_attaquante, force_defensive):
    """L'indice, dans `COLONNES`, du rapport de force attaquant / défenseur.

    Le rapport va de 1-5 à 6-1 et est « toujours arrondi en faveur du défenseur » : 10 contre 4
    vaut 2 contre 1, 4 contre 10 vaut 1 contre 3.
    """
    if force_attaquante <= 0:
        return 0
    if force_defensive <= 0:
        return len(COLONNES) - 1
    if force_attaquante >= force_defensive:
        return COLONNES.index((min(force_attaquante // force_defensive, 6), 1))
    return COLONNES.index((1, min(-(-force_defensive // force_attaquante), 5)))


def multiplicateur_de_defense(hexagone, pion_defenseur):
    """Le facteur qui multiplie la force du défenseur d'après le terrain qu'il occupe."""
    terrain = hexagone.terrain
    if terrain == "bois":
        return 2 if pion_defenseur.faction == FACTION_DES_ELFES else 1
    return DEFENSE_MULTIPLIEE.get(terrain, 1)


def bonus_de_terrain(hexagone):
    """Ce que le terrain du défenseur ajoute au dé de l'attaquant : 2 en bois ou colline, 0 sinon."""
    return 2 if hexagone.terrain in BONUS_AU_DE else 0


def tire_des_missiles(pion):
    """Dit si ce pion engage par le tir : il porte une force de tir **et** une portée.

    C'est la seule façon d'engager qu'on lui connaisse — le moteur ne lui donne pas le choix entre
    le tir et le corps à corps, et sa portée couvre la case au contact. Un pion qui tire est donc
    réputé tirer à chaque combat qu'il livre, quelle que soit la distance.
    """
    if pion is None:
        return False
    return bool(pion.tir and pion.portee)


def portee_de_combat(pion):
    """La distance à laquelle ce pion peut engager : sa portée de tir s'il tire, 1 sinon."""
    if tire_des_missiles(pion):
        return pion.portee
    return 1


def a_portee(hex_attaquant, pion_attaquant, hex_cible):
    """Dit si l'attaquant est assez près de la cible pour l'engager (distance à vol d'oiseau)."""
    return hex_attaquant.distance(hex_cible) <= portee_de_combat(pion_attaquant)


class DetailDuRapport:
    """Le calcul qui mène au rapport de force, pièce par pièce : de quoi le raconter.

    Le rapport ne se lit pas sur le plateau. Entre la force inscrite sur les cartons et la
    colonne du Tableau I, il y a le **terrain du défenseur**, qui multiplie sa force et ajoute au
    dé de l'attaquant — deux effets d'une même case, et rien ne les montre une fois le combat
    résolu. Cet objet les retient tous.

    Il ne fabrique aucune phrase : il rend des nombres et un nom de terrain, et c'est
    l'application qui les met en français (voir `detailler_le_rapport` dans `application/app.py`).
    Le moteur, lui, n'a pas à savoir qu'un journal existe.
    """

    __slots__ = ("forces", "force_de_la_cible", "terrain", "multiplicateur", "bonus_au_de", "jet")

    def __init__(self, forces, force_de_la_cible, terrain, multiplicateur, bonus_au_de, jet):
        self.forces = list(forces)
        self.force_de_la_cible = force_de_la_cible
        self.terrain = terrain
        self.multiplicateur = multiplicateur
        self.bonus_au_de = bonus_au_de
        self.jet = jet

    @property
    def force_attaquante(self):
        """Ce que le groupe d'attaquants totalise. Le terrain ne joue pas de ce côté-ci."""
        return sum(self.forces)

    @property
    def force_defensive(self):
        """La force du défenseur, son terrain compté."""
        return self.force_de_la_cible * self.multiplicateur

    @property
    def de(self):
        """Le dé tel que le tableau le lit : le jet, le terrain ajouté, ramené entre 1 et 6."""
        return min(6, max(1, self.jet + self.bonus_au_de))

    @property
    def colonne(self):
        """L'indice de la colonne du Tableau I où le combat se lit."""
        return colonne_du_rapport(self.force_attaquante, self.force_defensive)

    @property
    def rapport(self):
        """Le rapport de force tel que le fascicule l'écrit : un couple, attaquant au numérateur."""
        return COLONNES[self.colonne]

    @property
    def issue(self):
        """Ce que le Tableau I dit de ce rapport et de ce dé."""
        return TABLEAU_I[self.de][self.colonne]

    def __repr__(self):
        return (f"DetailDuRapport({self.force_attaquante} contre {self.force_defensive} "
                f"en {self.terrain}, dé {self.de})")


def detailler(forces_attaquantes, pion_defenseur, hexagone_defenseur, jet):
    """Le calcul du rapport de force, avant qu'on n'en lise l'issue.

    C'est le seul endroit où le terrain du défenseur est consulté : les deux entrées du combat —
    `resoudre` et `livrer_combat` — passent par ici, et ne peuvent donc pas en dire deux choses
    différentes.
    """
    return DetailDuRapport(
        forces=forces_attaquantes,
        force_de_la_cible=pion_defenseur.force,
        terrain=hexagone_defenseur.terrain,
        multiplicateur=multiplicateur_de_defense(hexagone_defenseur, pion_defenseur),
        bonus_au_de=bonus_de_terrain(hexagone_defenseur),
        jet=jet,
    )


def resoudre(forces_attaquantes, pion_defenseur, hexagone_defenseur, jet):
    """L'issue d'un combat : une des chaînes `AE`, `DE`, `EX`, `AR`, `DR`.

    `jet` est le résultat du dé (1 à 6), passé en argument pour que le hasard reste au bord du
    moteur. Il est modifié par le terrain puis ramené dans l'intervalle du tableau.
    """
    return detailler(forces_attaquantes, pion_defenseur, hexagone_defenseur, jet).issue


class ResultatDeCombat:
    """Ce qu'un combat a donné : son issue, les cases vidées, le rapport de force et le dé joué.

    `resultat` vaut `None` quand le combat n'a pas pu être résolu (cible absente, force illisible) ;
    `elimines` est alors vide, et `detail` aussi — il n'y a pas eu de calcul à détailler.

    `rapport` et `de` sont ceux de `detail` : ils restent des attributs à eux, la moitié du projet
    les lisant déjà ainsi.
    """

    __slots__ = ("resultat", "elimines", "rapport", "de", "detail")

    def __init__(self, resultat, elimines, rapport, de, detail=None):
        self.resultat = resultat
        self.elimines = list(elimines)
        self.rapport = rapport
        self.de = de
        self.detail = detail

    def __repr__(self):
        return f"ResultatDeCombat({self.resultat!r}, {len(self.elimines)} éliminés)"


def livrer_combat(plateau, hexagone_cible, hexagones_attaquants, jet):
    """Résout un combat sur le plateau et **retire** les pions éliminés.

    Les attaquants sont réputés valides — à portée, du bon camp : c'est à l'appelant de les avoir
    filtrés. Un attaquant sans force lisible est ignoré dans le calcul mais suit le sort du groupe.
    `AE` retire les attaquants, `DE` la cible, `EX` les deux ; `AR` et `DR` ne changent rien.

    Une exception, et elle vient du fascicule : sur un échange, **les attaquants qui tirent des
    missiles ne sont pas retirés** — ils ont frappé de loin, l'échange ne les atteint pas. Ils
    comptent en revanche dans le rapport de force, et un `AE` les élimine comme les autres : le
    fascicule ne les dispense que de la retraite et de l'échange.
    """
    pion_cible = plateau.pion_sur(hexagone_cible)
    forces = [plateau.pion_sur(hexagone).force
              for hexagone in hexagones_attaquants
              if plateau.pion_sur(hexagone) and plateau.pion_sur(hexagone).force is not None]
    if pion_cible is None or pion_cible.force is None or not forces:
        return ResultatDeCombat(None, [], None, None)

    detail = detailler(forces, pion_cible, hexagone_cible, jet)
    resultat = detail.issue

    elimines = []
    if resultat == AE:
        elimines.extend(hexagones_attaquants)
    elif resultat == EX:
        elimines.extend(hexagone for hexagone in hexagones_attaquants
                        if not tire_des_missiles(plateau.pion_sur(hexagone)))
    if resultat in (DE, EX):
        elimines.append(hexagone_cible)
    for hexagone in elimines:
        plateau.retirer(hexagone)

    return ResultatDeCombat(resultat, elimines, detail.rapport, detail.de, detail)


class SuiviDeCombat:
    """Ce qu'une phase de combat a déjà consommé : quelles cases ont attaqué, lesquelles ont été
    attaquées.

    Le fascicule veut qu'une unité ne livre qu'un combat par phase — seule ou dans un groupe
    d'attaquants — et qu'une unité ne soit prise pour cible qu'une fois.

    Le registre retient des **cases**, en clés « q,r,s », et non des clés de pion : un carton vaut
    pour toutes les unités qu'il représente — `orques-01-15-infanteries` est posé quinze fois dans
    le scénario n° 4 —, et le moteur ne donne pas d'identité à l'unité. La case, elle, en désigne
    une seule, et rien ne bouge pendant une phase de combat : le déplacement a sa phase à lui.
    C'est ce qui rend l'assimilation exacte le temps où le registre vit.

        suivi = SuiviDeCombat()
        suivi.peut_attaquer("1,26,-27")           # True
        suivi.enregistrer(["1,26,-27"], "2,26,-28")
        suivi.peut_attaquer("1,26,-27")           # False

    Le combat compte dès qu'il est livré : une issue que le moteur laisse sans effet — un recul —
    engage les unités tout autant qu'une élimination.
    """

    __slots__ = ("attaquants_engages", "cibles_engagees")

    def __init__(self):
        self.attaquants_engages = set()
        self.cibles_engagees = set()

    def peut_attaquer(self, case):
        """Dit si l'unité de cette case n'a pas encore attaqué durant la phase en cours."""
        return case not in self.attaquants_engages

    def peut_etre_cible(self, case):
        """Dit si l'unité de cette case n'a pas encore été attaquée durant la phase en cours."""
        return case not in self.cibles_engagees

    def enregistrer(self, cases_attaquantes, case_cible):
        """Marque un combat livré : les attaquants ont attaqué, la cible a été attaquée."""
        self.attaquants_engages.update(cases_attaquantes)
        self.cibles_engagees.add(case_cible)
        return self

    def en_dict(self):
        """Le registre sous une forme sérialisable : deux listes de cases, triées.

        Le tri ne doit rien à la règle — un ensemble n'a pas d'ordre — mais rend la forme stable
        d'une sauvegarde à l'autre.
        """
        return {"attaquants_engages": sorted(self.attaquants_engages),
                "cibles_engagees": sorted(self.cibles_engagees)}

    def restaurer(self, attaquants_engages, cibles_engagees):
        """Remplace le contenu du registre par celui d'une sauvegarde."""
        self.attaquants_engages.clear()
        self.attaquants_engages.update(attaquants_engages)
        self.cibles_engagees.clear()
        self.cibles_engagees.update(cibles_engagees)
        return self

    def reinitialiser(self):
        """Vide le registre — une nouvelle phase de combat rend toutes les unités disponibles.

        C'est aussi ce qui empêche une case retenue de survivre à un déplacement : entre deux
        phases de combat il y a toujours une phase de mouvement, et le registre est déjà vide
        quand les unités changent de case.
        """
        self.attaquants_engages.clear()
        self.cibles_engagees.clear()
        return self

    def __repr__(self):
        return (f"SuiviDeCombat({len(self.attaquants_engages)} attaquants, "
                f"{len(self.cibles_engagees)} cibles)")
