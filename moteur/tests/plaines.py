"""Repères de terrain pour les tests du mouvement — pas de test ici, seulement de quoi en écrire.

Les hexagones de référence ne sont pas codés en dur : ils sont cherchés sur la carte du jeu, pour
que les tests survivent à une correction de terrain. Ce qu'on veut est un coin de plaine assez
large pour que chaque pas y coûte exactement 1 point, sans route ni chemin qui fausserait
l'arithmétique.
"""

from moteur.hexagone import CARTE, Hex

RAYON_DU_COIN = 2                     # le centre, sa couronne, et la couronne d'après
CASES_DU_COIN = 19                    # 1 + 6 + 12
BUDGET_MAXIMAL = 8                    # au-delà, c'est que le trajet cherché n'existe pas


def alentours(hexagone, rayon=RAYON_DU_COIN):
    """Les hexagones à `rayon` cases ou moins, l'hexagone lui-même compris."""
    atteints = {hexagone}
    bord = {hexagone}
    for _ in range(rayon):
        bord = {voisin for centre in bord for voisin in centre.voisins()} - atteints
        atteints |= bord
    return atteints


def plaine_bien_entouree():
    """Une plaine dont tout le voisinage à deux cases est de la plaine nue."""
    for cle, elements in CARTE.items():
        if elements != ("plaine",):
            continue
        hexagone = Hex.depuis_cle(cle)
        voisinage = alentours(hexagone)
        if (len(voisinage) == CASES_DU_COIN
                and all(CARTE.get(voisin.cle) == ("plaine",) for voisin in voisinage)):
            return hexagone
    raise AssertionError("aucun coin de plaine nue assez large sur la carte")


def couronne_de(centre):
    """Trois cases consécutives de la couronne de `centre`, et une case au large.

    C'est la figure de l'exemple du fascicule : **C**, **X1** et **X2** se suivent autour de
    l'unité **A**, et « au large » est la première case hors de sa zone de contrôle.
    """
    voisins = centre.voisins()
    c = voisins[0]
    x1 = next(voisin for voisin in voisins if voisin.distance(c) == 1)
    x2 = next(voisin for voisin in voisins if voisin.distance(x1) == 1 and voisin != c)
    large = next(voisin for voisin in c.voisins() if voisin.distance(centre) == 2)
    return c, x1, x2, large


def budget_minimal(depart, cible, **regles):
    """Le plus petit mouvement qui met `cible` à portée de `depart`, ou None au-delà du maximum."""
    for budget in range(1, BUDGET_MAXIMAL + 1):
        if cible in depart.deplacements(budget, **regles):
            return budget
    return None
