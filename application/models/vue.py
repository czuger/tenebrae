"""La vue de la carte : où un joueur en était, et de combien il l'avait approchée.

La carte fait 6173 × 5102 pixels, et l'on y joue approché. Jusqu'ici, chaque rechargement de la
page ramenait tout le monde à l'échelle d'ajustement, la carte entière dans la fenêtre : il
fallait refaire son zoom et retrouver l'endroit où l'on manœuvrait, à chaque fois. C'est ce que ce
document retient.

**Pourquoi ici, et non dans `moteur/models/` ?** Parce que ce n'est pas du jeu. Le moteur ne sait
pas qu'il existe une image, des pixels ou une fenêtre : une partie se joue depuis un interpréteur,
et le zoom n'y veut rien dire. L'inclinaison d'un pion, elle, est du plateau — le carton est
vraiment posé de travers, et les deux joueurs le voient pareil ; une vue de la carte n'appartient
qu'à **une** paire d'yeux. C'est donc le second modèle de l'application, à côté de la connexion,
et il désigne lui aussi le joueur du moteur par son seul `discord_id`.

Ce qui est retenu **n'est pas le défilement** : `x` et `y` sont le point de `map.jpg`, en pixels
de l'image, qui se trouvait au **centre** de la fenêtre. Un défilement en pixels d'écran ne
voudrait plus rien dire à l'échelle suivante, ni sur un autre écran ; ce point-là, si.

`ajustee` dit que la carte était encore réglée à la fenêtre — l'état d'ouverture, celui du bouton
« ajuster ». On ne fige alors aucune échelle : on réajuste, et une fenêtre de taille différente
retrouve son propre ajustement plutôt qu'un zoom hérité d'un autre écran.
"""

from mongoengine import BooleanField, DateTimeField, Document, FloatField, StringField


class Vue(Document):
    """Ce qu'un joueur voyait de la carte à son dernier réglage.

    Un document par joueur, écrasé à chaque changement : on ne garde pas d'historique de zoom.
    """

    discord_id = StringField(required=True, unique=True)

    # L'échelle de la carte, 1 étant la taille du scan (voir `ECHELLE_MIN`/`ECHELLE_MAX` dans
    # `static/zoom.js`, qui borne pour de bon).
    echelle = FloatField(required=True)

    # Le point de `map.jpg` qui était au centre de la fenêtre, en pixels de l'image.
    x = FloatField(required=True)
    y = FloatField(required=True)

    # La carte était-elle encore réglée à la fenêtre ? Si oui, on réajustera plutôt que de
    # reposer `echelle`.
    ajustee = BooleanField(default=False)

    modifiee_le = DateTimeField(required=True)

    meta = {"collection": "vues",
            "indexes": [{"fields": ["discord_id"], "unique": True}]}

    def __repr__(self):
        return (f"Vue(discord {self.discord_id}, {round(self.echelle * 100)} % "
                f"sur ({round(self.x)}, {round(self.y)}))")
