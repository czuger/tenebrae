"""L'état de partie, réduit à l'essentiel : quels pions sont posés, où, et dans quel camp.

La carte ne change pas, les cartons non plus ; les positions, si. C'est le seul objet mutable du
moteur, et c'est lui qui rend les zones de contrôle calculables : sans savoir qui occupe quelle
case, la règle des six cases environnantes n'a personne à qui s'appliquer.

Le plateau ne juge ni l'empilement, ni les scénarios, ni les tours de jeu : il porte des positions
et sait en tirer les déplacements permis.
"""

from moteur.hexagone import MOUVEMENT_PAR_DEFAUT, Hex, zone_de_controle
from moteur.pion import ADVERSAIRES, CATALOGUE


class Plateau:
    """Les pions posés sur la carte, une case au plus par pion.

    S'initialise vide, ou avec des couples `(hexagone, pion)` :

        plateau = Plateau([(Hex(1, 26, -27), pion("elfes-01-5-infanteries"))])
    """

    def __init__(self, positions=()):
        self._pions = {}
        for hexagone, pion in positions:
            self.poser(hexagone, pion)

    @property
    def pions(self):
        """« q,r,s » → `Pion` pour tout ce qui est posé, dans l'ordre où on l'a posé."""
        return dict(self._pions)

    def poser(self, hexagone, pion):
        """Pose un pion sur une case, en remplaçant celui qui s'y trouvait."""
        self._exiger_la_carte(hexagone)
        self._pions[hexagone.cle] = pion

    def retirer(self, hexagone):
        """Retire le pion de la case et le rend ; `None` si elle était vide."""
        return self._pions.pop(hexagone.cle, None)

    def vider(self):
        """Retire tous les pions : le plateau redevient une carte nue."""
        self._pions.clear()

    def pion_sur(self, hexagone):
        """Le pion posé sur cette case, ou `None`."""
        return self._pions.get(hexagone.cle)

    def cases_tenues_par(self, camp):
        """Les cases qu'occupe ce camp, en clés « q,r,s »."""
        return frozenset(cle for cle, pion in self._pions.items() if pion.camp == camp)

    def adversaires_de(self, camp):
        """Les cases tenues par le camp opposé.

        Le neutre — volants, conjurations, marqueurs — n'a pas d'adversaire : il ne gêne personne
        et personne ne le gêne.
        """
        oppose = ADVERSAIRES.get(camp)
        return self.cases_tenues_par(oppose) if oppose else frozenset()

    def zones_de_controle_contre(self, camp):
        """Les cases que les zones de contrôle adverses couvrent, en clés « q,r,s ».

        Seules les unités adverses qui exercent une zone de contrôle comptent : les marqueurs
        n'en exercent pas.
        """
        exercantes = [Hex.depuis_cle(cle) for cle in self.adversaires_de(camp)
                      if self._pions[cle].exerce_une_zone_de_controle]
        return zone_de_controle(exercantes)

    def deplacements(self, depart, pion=None):
        """Les cases où le pion posé sur `depart` peut aller, zones de contrôle comprises.

        Le pion **posé** fait foi ; `pion` ne sert qu'à interroger une case vide, pour savoir où
        telle unité irait si on l'y mettait. Sans pion du tout, la question est celle d'un
        déplacement sans unité : le forfait de mouvement s'applique et, faute de camp, personne
        n'est un adversaire.

        Une case occupée par un ami se traverse — le fascicule l'autorise — mais ne se prend pas :
        « il n'est pas possible de placer plus d'une unité dans la même case ». Elle est donc
        écartée des destinations, pas du parcours.
        """
        pion = self.pion_sur(depart) or pion
        if pion is None:
            atteignables = depart.deplacements()
        else:
            atteignables = depart.deplacements(
                pion.points_de_mouvement,
                ennemis=self.adversaires_de(pion.camp),
                sous_controle=self.zones_de_controle_contre(pion.camp),
            )
        return [hexagone for hexagone in atteignables if hexagone.cle not in self._pions]

    def mouvement_de(self, depart, pion=None):
        """Les points du pion posé sur `depart` — le forfait si la case est vide."""
        pion = self.pion_sur(depart) or pion
        return pion.points_de_mouvement if pion else MOUVEMENT_PAR_DEFAUT

    def deplacer(self, depart, arrivee, pion=None):
        """Déplace le pion de `depart` vers `arrivee` si la règle le permet ; dit si c'est fait.

        Le déplacement est recalculé ici, jamais reçu tout fait — la case d'arrivée est donc
        libre par construction. Une case vide au départ ne déplace rien mais répond quand même :
        c'est ainsi qu'on interroge la règle à la main.
        """
        if arrivee not in self.deplacements(depart, pion):
            return False
        pose = self.retirer(depart)
        if pose is not None:
            self.poser(arrivee, pose)
        return True

    def en_dict(self):
        """« q,r,s » → clé de pion, dans l'ordre de pose — le format de `Scenario.placement`.

        C'est toute la partie qui tient là : un pion posé n'a pas d'autre état que sa case et son
        carton, et le carton se retrouve au catalogue par sa clé.
        """
        return {cle: pion.cle for cle, pion in self._pions.items()}

    def restaurer(self, placement):
        """Vide le plateau et repose chaque pion d'un dict « case → clé de pion ».

        L'inverse d'`en_dict` : les cartons sont repris au catalogue, les cases revérifiées —
        une sauvegarde qui cite une case hors carte ou un pion inconnu est refusée, pas rafistolée.
        Tout est vérifié avant de toucher au plateau : refusé veut dire laissé tel quel.
        """
        poses = []
        for cle, cle_de_pion in placement.items():
            hexagone = Hex.depuis_cle(cle)
            self._exiger_la_carte(hexagone)
            poses.append((hexagone, CATALOGUE[cle_de_pion]))
        self.vider()
        for hexagone, pion in poses:
            self.poser(hexagone, pion)
        return self

    @staticmethod
    def _exiger_la_carte(hexagone):
        if not hexagone.est_sur_la_carte:
            raise ValueError(f"l'hexagone {hexagone!r} n'est pas sur la carte")

    def __len__(self):
        return len(self._pions)

    def __repr__(self):
        return f"Plateau({len(self._pions)} pions posés)"
