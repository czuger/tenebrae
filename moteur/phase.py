"""Le déroulement d'un tour d'Ave Tenebrae : une machine à états des phases.

Le fascicule (`game_box/ave_tenebrae_regles.md`, § « Phases de jeu ») fixe l'ordre : chaque joueur
enchaîne mouvement, magie puis combat, et l'on repart au joueur suivant, en boucle. Le moteur
n'en connaissait rien jusqu'ici — un scénario n'était qu'une position de départ.

`Tour` tient le camp actif et le type de phase courante, et sait passer à la suivante. La phase de
magie n'est pas implémentée : `suivante()` la franchit d'elle-même, elle n'est jamais courante.
"""

MOUVEMENT, MAGIE, COMBAT = "mouvement", "magie", "combat"

# L'ordre des phases d'un même joueur. La magie y figure pour être sautée au bon moment.
ORDRE = (MOUVEMENT, MAGIE, COMBAT)

LIBELLES = {MOUVEMENT: "Phase de mouvement", MAGIE: "Phase de magie", COMBAT: "Phase de combat"}


class Tour:
    """La phase courante d'une partie : quel camp joue, et à quoi.

        tour = Tour(("alliance", "tenebres"), {"alliance": "Nains", "tenebres": "Orques"})
        tour.libelle          # « Phase de mouvement — Nains »
        tour.suivante()       # passe au combat (la magie est sautée)
    """

    __slots__ = ("_camps", "_noms", "_i", "numero")

    def __init__(self, camps, noms=None):
        self._camps = tuple(camps)
        self._noms = dict(noms or {})
        # La séquence complète d'un tour : chaque camp, chaque type de phase, dans l'ordre.
        self._i = 0
        self.numero = 1

    @property
    def _sequence(self):
        return [(camp, type_) for camp in self._camps for type_ in ORDRE]

    @property
    def camp_actif(self):
        """Le camp dont c'est la phase — « alliance » ou « tenebres »."""
        return self._sequence[self._i][0]

    @property
    def type_de_phase(self):
        """Le type de la phase courante : « mouvement » ou « combat » (jamais « magie »)."""
        return self._sequence[self._i][1]

    @property
    def armee_active(self):
        """Le nom lisible de l'armée qui joue — « Nains », « Orques » —, à défaut son camp."""
        return self._noms.get(self.camp_actif, self.camp_actif)

    @property
    def libelle(self):
        """Ce que l'interface affiche : « Phase de mouvement — Nains »."""
        return f"{LIBELLES[self.type_de_phase]} — {self.armee_active}"

    def recommencer(self):
        """Ramène la partie à la première phase du premier tour."""
        self._i = 0
        self.numero = 1
        return self

    def suivante(self):
        """Passe à la phase suivante, en franchissant la magie et en comptant les tours."""
        sequence = self._sequence
        self._i += 1
        if self._i >= len(sequence):
            self._i = 0
            self.numero += 1
        if sequence[self._i][1] == MAGIE:
            self.suivante()
        return self

    def autorise_mouvement(self, camp):
        """Dit si `camp` peut déplacer ses unités maintenant."""
        return self.type_de_phase == MOUVEMENT and camp == self.camp_actif

    def autorise_combat(self, camp):
        """Dit si `camp` peut déclarer un combat maintenant."""
        return self.type_de_phase == COMBAT and camp == self.camp_actif

    def en_dict(self):
        """La phase courante sous une forme prête pour le JSON du navigateur."""
        return {"camp": self.camp_actif, "type": self.type_de_phase,
                "armee": self.armee_active, "libelle": self.libelle, "numero": self.numero}

    def __repr__(self):
        return f"Tour({self.numero}, {self.libelle!r})"
