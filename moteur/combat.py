"""La résolution des combats d'Ave Tenebrae : le Tableau I du fascicule, et rien de plus.

Le fascicule (`game_box/ave_tenebrae_regles.md`, § « Combats ») donne une table à double entrée —
le rapport de force en colonnes, le jet de dé en lignes — dont chaque case dit l'issue de la
bataille : attaquant éliminé, défenseur éliminé, échange, ou l'un des deux reculs. Ce module
transcrit cette table, calcule le rapport de force (« toujours arrondi en faveur du défenseur »)
et applique les modificateurs de terrain du *Tableau des terrains*.

Les reculs ne sont pas joués : `AR` et `DR` laissent le plateau intact. `EX` retire toutes les
unités engagées, sans le tri « attaquants totalisant une force au moins égale » du fascicule. Les
facultés spéciales, la charge de cavalerie, les phalanges et l'alternance jour/nuit sont hors de
portée — voir `moteur/README.md`.

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


def portee_de_combat(pion):
    """La distance à laquelle ce pion peut engager : sa portée de tir s'il tire, 1 sinon."""
    if pion.tir and pion.portee:
        return pion.portee
    return 1


def a_portee(hex_attaquant, pion_attaquant, hex_cible):
    """Dit si l'attaquant est assez près de la cible pour l'engager (distance à vol d'oiseau)."""
    return hex_attaquant.distance(hex_cible) <= portee_de_combat(pion_attaquant)


def resoudre(forces_attaquantes, pion_defenseur, hexagone_defenseur, jet):
    """L'issue d'un combat : une des chaînes `AE`, `DE`, `EX`, `AR`, `DR`.

    `jet` est le résultat du dé (1 à 6), passé en argument pour que le hasard reste au bord du
    moteur. Il est modifié par le terrain puis ramené dans l'intervalle du tableau.
    """
    de = min(6, max(1, jet + bonus_de_terrain(hexagone_defenseur)))
    force_defensive = pion_defenseur.force * multiplicateur_de_defense(hexagone_defenseur,
                                                                       pion_defenseur)
    return TABLEAU_I[de][colonne_du_rapport(sum(forces_attaquantes), force_defensive)]


class ResultatDeCombat:
    """Ce qu'un combat a donné : son issue, les cases vidées, le rapport de force et le dé joué.

    `resultat` vaut `None` quand le combat n'a pas pu être résolu (cible absente, force illisible) ;
    `elimines` est alors vide.
    """

    __slots__ = ("resultat", "elimines", "rapport", "de")

    def __init__(self, resultat, elimines, rapport, de):
        self.resultat = resultat
        self.elimines = list(elimines)
        self.rapport = rapport
        self.de = de

    def __repr__(self):
        return f"ResultatDeCombat({self.resultat!r}, {len(self.elimines)} éliminés)"


def livrer_combat(plateau, hexagone_cible, hexagones_attaquants, jet):
    """Résout un combat sur le plateau et **retire** les pions éliminés.

    Les attaquants sont réputés valides — à portée, du bon camp : c'est à l'appelant de les avoir
    filtrés. Un attaquant sans force lisible est ignoré dans le calcul mais suit le sort du groupe.
    `AE` retire les attaquants, `DE` la cible, `EX` les deux ; `AR` et `DR` ne changent rien.
    """
    pion_cible = plateau.pion_sur(hexagone_cible)
    forces = [plateau.pion_sur(hexagone).force
              for hexagone in hexagones_attaquants
              if plateau.pion_sur(hexagone) and plateau.pion_sur(hexagone).force is not None]
    if pion_cible is None or pion_cible.force is None or not forces:
        return ResultatDeCombat(None, [], None, None)

    de = min(6, max(1, jet + bonus_de_terrain(hexagone_cible)))
    force_defensive = pion_cible.force * multiplicateur_de_defense(hexagone_cible, pion_cible)
    colonne = colonne_du_rapport(sum(forces), force_defensive)
    resultat = TABLEAU_I[de][colonne]

    elimines = []
    if resultat in (AE, EX):
        elimines.extend(hexagones_attaquants)
    if resultat in (DE, EX):
        elimines.append(hexagone_cible)
    for hexagone in elimines:
        plateau.retirer(hexagone)

    return ResultatDeCombat(resultat, elimines, COLONNES[colonne], de)


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
