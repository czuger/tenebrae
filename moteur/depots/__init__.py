"""L'accès en base aux entités du jeu : un dépôt par sujet, à côté des modèles qu'il écrit.

Un dépôt échange des **dicts d'état**, jamais un Document MongoEngine. C'est ce qui tient Mongo
hors des routes : `application/app.py` n'importe ni `moteur.models` ni `mongoengine`, il appelle
`charger`, `sauvegarder` et `nouvelle_partie`, point.

Chaque sujet en a deux : le vrai, sur MongoDB, et son homologue sans base que la configuration de
test branche. Les deux tiennent la même promesse de `PERSISTANCE=aucune` — rien ne survit au
serveur —, mais pas de la même façon, et la nuance est expliquée dans chaque module.

Comme pour `moteur/models/`, ce fichier ne réexporte rien : `application/app.py` n'importe une
branche qu'au moment où sa configuration la demande, et une application montée sans persistance ne
doit pas charger mongoengine pour autant.

    from moteur.depots.partie import DepotDePartieMongo, DepotDePartieNul
    from moteur.depots.joueur import DepotDeJoueursMongo, DepotDeJoueursEnMemoire
"""
