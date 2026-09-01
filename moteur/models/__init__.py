"""Les entités du jeu, **un fichier par modèle**.

Ce répertoire tient tout ce qui *est* le jeu et qui doit survivre à une requête : la partie
sauvegardée, le joueur qui la tient, la table des places. Rien de web n'y entre — pas de Flask,
pas de session, pas de requête : le moteur ignore qu'une application le sert, et se laisse jouer
depuis un simple interpréteur.

Le lien avec le joueur *connecté* se fait dans l'autre sens : c'est l'application qui tient une
entité de connexion (`application/models/connexion.py`) et qui désigne le joueur du moteur par
son identifiant Discord. Le moteur n'a jamais à connaître ni session ni cookie.

Ce fichier ne réexporte rien, et c'est délibéré : `Places` n'a besoin que de la bibliothèque
standard, quand `Partie` et `Joueur` demandent mongoengine. Réexporter les trois ici ferait payer
mongoengine à qui ne veut qu'un registre de places — et à l'application montée sans persistance,
qui se construit aujourd'hui sans lui. Chacun importe donc le module qu'il lui faut :

    from moteur.models.places import Places
    from moteur.models.partie import Partie
    from moteur.models.joueur import Joueur
"""
