"""L'accès en base aux entités de l'application : un dépôt par sujet, à côté du modèle qu'il écrit.

Le pendant de `moteur/depots/`, pour ce qui n'est pas du jeu. Mêmes règles, et pour les mêmes
raisons : un dépôt échange des **dicts**, jamais un Document MongoEngine, et chaque sujet en a
deux — le vrai, sur MongoDB, et son homologue sans base que la configuration de test branche.
C'est ce qui tient Mongo hors des routes.

Comme partout ailleurs dans le projet, ce fichier ne réexporte rien : une application montée sans
persistance ne doit pas charger mongoengine pour autant.

    from depots.vue import DepotDeVuesMongo, DepotDeVuesEnMemoire
"""
