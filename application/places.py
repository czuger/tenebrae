"""Qui tient quel camp à la table : le registre des places.

Le fascicule fait jouer deux joueurs, un par camp. Le moteur, lui, ne connaît que des camps —
`moteur.pion` range chaque faction sous « alliance » ou « ténèbres », `moteur.phase` fait tourner
les phases de l'un à l'autre — et il n'a jamais eu à savoir *qui* les jouait. Ce fichier tient ce
lien-là, et c'est pourquoi il est ici et non dans `moteur/` : une partie de plateau se joue très
bien sans compte Discord, et le moteur doit pouvoir continuer à l'ignorer.

Un joueur est désigné par son identifiant Discord, une chaîne. Le registre n'en sait rien d'autre :
ni pseudo, ni avatar — cela vit dans le dépôt de joueurs, et le registre resterait juste si Discord
disparaissait demain.

    places = Places()
    places.asseoir("alliance", "100000000000000001")
    places.tient("100000000000000001", "alliance")   # True
    places.est_libre("tenebres")                     # True

**Le registre ne garde qu'un invariant : un camp a au plus un occupant**, et `asseoir` refuse d'en
déloger un. La règle sociale — un joueur ne tient qu'un camp — n'est pas ici mais dans la route
qui fait asseoir, comme la légalité d'un mouvement est dans le serveur et non dans le navigateur.
La séparation n'est pas gratuite : la suite de tests assied un même joueur des deux côtés pour
jouer une partie à elle seule, ce que la route refuse et que le registre permet.

Comme `moteur.combat.SuiviDeCombat`, il se sérialise en dict et se restaure d'une sauvegarde :
qui tient l'Alliance fait partie de l'état de la partie, au même titre que le camp actif, et un
redémarrage du serveur ne doit pas vider la table.
"""


class Places:
    """Les camps de la partie et leur occupant, par identifiant Discord."""

    __slots__ = ("_par_camp",)

    def __init__(self):
        # Un camp libre n'a pas de clé : « absent » se lit mieux que « nul », et c'est aussi ce
        # que MapField enregistre.
        self._par_camp = {}

    def occupant(self, camp):
        """L'identifiant Discord de qui tient ce camp, ou `None` s'il est libre."""
        return self._par_camp.get(camp)

    def est_libre(self, camp):
        """Dit si personne ne tient ce camp."""
        return camp not in self._par_camp

    def camps_de(self, joueur):
        """Les camps que ce joueur tient, dans l'ordre où ils ont été pris — vide s'il regarde."""
        return [camp for camp, occupant in self._par_camp.items() if occupant == joueur]

    def tient(self, joueur, camp):
        """Dit si ce joueur est bien l'occupant de ce camp."""
        return joueur is not None and self._par_camp.get(camp) == joueur

    def asseoir(self, camp, joueur):
        """Assied un joueur à un camp libre — ou au sien, ce qui ne change rien.

        Lève `ValueError` si le camp est tenu par quelqu'un d'autre : une place ne se prend pas à
        son occupant. C'est le seul invariant que le registre défend lui-même.
        """
        occupant = self._par_camp.get(camp)
        if occupant is not None and occupant != joueur:
            raise ValueError(f"le camp {camp} est déjà tenu")
        self._par_camp[camp] = joueur
        return self

    def liberer(self, camp):
        """Rend le camp libre. Un camp qui l'était déjà ne fait pas d'histoire."""
        self._par_camp.pop(camp, None)
        return self

    def vider(self):
        """Lève toute la table — personne ne tient plus rien."""
        self._par_camp.clear()
        return self

    def en_dict(self):
        """Les places sous une forme sérialisable, prête à rejoindre l'état de la partie."""
        return {"places": dict(self._par_camp)}

    def restaurer(self, places):
        """Remplace les places par celles d'une sauvegarde."""
        self._par_camp = dict(places or {})
        return self

    def __repr__(self):
        return f"Places({self._par_camp!r})"
