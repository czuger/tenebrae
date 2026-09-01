"""L'adversaire artificiel : un joueur de plus, sans navigateur ni compte Discord.

Le fascicule suppose deux joueurs autour de la carte ; ce module tient la place du second. Il ne
sait rien des règles — il **choisit**, et laisse le moteur juger : chaque déplacement passe par
`Plateau.deplacer`, chaque combat par `combat.livrer_combat`, chaque disponibilité par
`SuiviDeCombat`. Une décision illégale est simplement refusée, comme elle le serait à un humain.

La stratégie est courte et assumée. Chaque unité choisit sa cible — l'adversaire le plus proche,
le plus faible à distance égale — et marche jusqu'à l'avoir à portée d'engagement : au contact
pour l'infanterie, à portée de tir pour ce qui tire. Au combat, les attaques se concentrent :
toutes les unités disponibles à portée d'une cible l'engagent ensemble, en un seul combat — la
règle « une attaque par cible et par phase » interdit de toute façon d'y revenir. L'IA n'attaque
pas sous la parité : le Tableau I ne pardonne rien sous la colonne 1-1.

Les limites, elles aussi, sont assumées : la marche vise à vol d'oiseau, pas au coût de chemin —
une unité peut donc longer un lac au lieu de le contourner au plus court ; la magie n'est pas
jouée, le moteur la sautant déjà ; et il n'y a ni repli, ni garnison, ni défense de terrain — l'IA
avance, toujours.

Tous les départages sont déterministes : les unités jouent dans l'ordre de leurs clés de case, et
toute clé de tri finit par une clé de case. À dé égal, deux parties identiques se rejouent à
l'identique — c'est ce qui rend l'IA testable. Le dé, lui, reste au bord du moteur : `jet` est un
appelable fourni par l'appelant, un tirage par combat.
"""

from moteur import combat
from moteur.hexagone import Hex
from moteur.phase import MOUVEMENT

# L'occupant d'une place tenue par l'IA. Aucun humain ne peut le porter : les identifiants
# Discord sont des chaînes de chiffres.
JOUEUR_IA = "ia"

# Le nom que l'interface affiche pour cette place.
NOM_IA = "IA"

# La colonne du Tableau I en dessous de laquelle l'IA renonce à attaquer : la parité. C'est le
# seul bouton de difficulté — l'abaisser rend l'IA téméraire, le monter la rend timorée.
RAPPORT_MINIMAL = combat.COLONNES.index((1, 1))


def priorite_des_cibles(plateau, depuis, camp):
    """Les cases adverses par ordre de priorité, vues de `depuis` : la plus proche d'abord, la
    plus faible ensuite.

    Le tri se fait sur (distance à vol d'oiseau, force défensive effective — la force du carton
    multipliée par le terrain occupé —, clé de case) : viser près, frapper faible, départager
    pareil d'une partie à l'autre. Les adversaires sans force lisible sont écartés : ni cibles de
    combat, ni objectifs de marche.

    C'est ici que se règlerait une difficulté future : changer ce tri change toute l'IA,
    mouvement et combat visant par la même fonction.
    """
    cibles = []
    for cle in plateau.adversaires_de(camp):
        hexagone = Hex.depuis_cle(cle)
        pion = plateau.pion_sur(hexagone)
        if pion.force is None:
            continue
        defense = pion.force * combat.multiplicateur_de_defense(hexagone, pion)
        cibles.append((depuis.distance(hexagone), defense, cle, hexagone))
    return [hexagone for _, _, _, hexagone in sorted(cibles, key=lambda c: c[:3])]


def choisir_la_cible(plateau, depuis, camp):
    """La case adverse à viser depuis `depuis`, ou `None` s'il n'y a plus d'adversaire."""
    cibles = priorite_des_cibles(plateau, depuis, camp)
    return cibles[0] if cibles else None


def jouer_le_mouvement(plateau, camp):
    """Joue la phase de mouvement du camp : chaque unité marche vers sa cible.

    Une unité déjà à portée d'engagement de sa cible ne bouge pas — un archer en position tient
    sa position, une infanterie au contact y reste. Les autres prennent, parmi leurs déplacements
    permis, la case la moins hors de portée ; à écart égal, la moins éloignée de leur position —
    un tireur s'arrête donc à portée au lieu de coller à sa cible, et personne ne se déplace pour
    rien. Le moteur revalide chaque pas : terrain, zones de contrôle, cases occupées.

    Le plateau change sous l'itération, mais une seule passe sur les cases figées au départ
    suffit à donner une action par unité : une case occupée n'est jamais une destination, donc
    chaque case de la liste garde son occupant jusqu'à son propre tour, et une case libérée ne
    peut être reprise que par une unité jouée après elle — quand elle est déjà passée.

    Rend la liste des couples `(départ, arrivée)` joués — de quoi journaliser.
    """
    deplacements_joues = []
    for cle in sorted(plateau.cases_tenues_par(camp)):
        depart = Hex.depuis_cle(cle)
        pion = plateau.pion_sur(depart)
        if not pion.est_une_unite or pion.points_de_mouvement == 0:
            continue
        cible = choisir_la_cible(plateau, depart, camp)
        if cible is None:
            continue
        objectif = combat.portee_de_combat(pion)
        if depart.distance(cible) <= objectif:
            continue

        def rang(hexagone, depart=depart, cible=cible, objectif=objectif):
            ecart = max(0, hexagone.distance(cible) - objectif)
            return (ecart, depart.distance(hexagone), hexagone.cle)

        candidates = plateau.deplacements(depart)
        if not candidates:
            continue
        arrivee = min(candidates, key=rang)
        if rang(arrivee) >= rang(depart):
            continue
        if plateau.deplacer(depart, arrivee):
            deplacements_joues.append((depart, arrivee))
    return deplacements_joues


def jouer_le_combat(plateau, camp, suivi, jet):
    """Joue la phase de combat du camp : les attaques se concentrent sur les cibles prioritaires.

    Chaque unité encore disponible cherche, dans l'ordre de ses priorités, une cible à portée et
    pas encore engagée ; toutes les unités du camp disponibles et à portée de cette cible s'y
    joignent alors, en un seul combat — c'est la concentration que permet le moteur, plusieurs
    attaquants pour un `livrer_combat`. Sous la parité (`RAPPORT_MINIMAL`), l'unité renonce et
    reste disponible : elle rejoindra peut-être un groupe plus fourni sur une autre cible.

    Le registre `suivi` — le même que pour les humains — tient les deux règles du fascicule : une
    attaque par unité et par phase, une attaque par cible et par phase. `jet` est appelé une fois
    par combat livré.

    Rend la liste des combats livrés : `(cible, attaquants, ResultatDeCombat)`.
    """
    combats_livres = []
    for cle in sorted(plateau.cases_tenues_par(camp)):
        depart = Hex.depuis_cle(cle)
        pion = plateau.pion_sur(depart)
        if pion is None or pion.camp != camp:
            continue  # éliminée dans un échange plus tôt dans la phase
        if not pion.est_une_unite or pion.force is None or not suivi.peut_attaquer(cle):
            continue

        cible = next((candidate for candidate in priorite_des_cibles(plateau, depart, camp)
                      if suivi.peut_etre_cible(candidate.cle)
                      and combat.a_portee(depart, pion, candidate)), None)
        if cible is None:
            continue

        attaquants = []
        for cle_amie in sorted(plateau.cases_tenues_par(camp)):
            hexagone = Hex.depuis_cle(cle_amie)
            pion_ami = plateau.pion_sur(hexagone)
            if (pion_ami.est_une_unite and pion_ami.force is not None
                    and suivi.peut_attaquer(cle_amie)
                    and combat.a_portee(hexagone, pion_ami, cible)):
                attaquants.append(hexagone)

        pion_cible = plateau.pion_sur(cible)
        force_defensive = pion_cible.force * combat.multiplicateur_de_defense(cible, pion_cible)
        forces = sum(plateau.pion_sur(hexagone).force for hexagone in attaquants)
        if combat.colonne_du_rapport(forces, force_defensive) < RAPPORT_MINIMAL:
            continue

        resultat = combat.livrer_combat(plateau, cible, attaquants, jet())
        suivi.enregistrer([hexagone.cle for hexagone in attaquants], cible.cle)
        combats_livres.append((cible, attaquants, resultat))
    return combats_livres


def jouer_le_tour(plateau, tour, suivi, jet):
    """Joue le tour complet du camp actif — mouvement puis combat — et rend la main.

    À l'entrée, la phase courante doit être la phase de mouvement du camp de l'IA ; à la sortie,
    c'est la phase de mouvement du camp suivant. Entre les deux, le passage de phase est celui de
    tout le monde : `Tour.suivante()` et un registre de combat remis à neuf — exactement ce que
    fait un joueur humain qui clique « phase suivante ».

    Rend `(deplacements, combats)`, ce que les deux phases ont joué.
    """
    if tour.type_de_phase != MOUVEMENT:
        raise ValueError("l'IA entre en jeu à sa phase de mouvement, pas ailleurs")
    camp = tour.camp_actif
    deplacements = jouer_le_mouvement(plateau, camp)
    tour.suivante()
    suivi.reinitialiser()
    combats = jouer_le_combat(plateau, camp, suivi, jet)
    tour.suivante()
    suivi.reinitialiser()
    return deplacements, combats
