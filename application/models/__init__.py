"""Les modèles de l'application, **un fichier par modèle**.

Il n'y en a qu'un, et c'est voulu : l'application ne modélise que la **connexion** — le lien
entre une session Flask et le joueur du moteur. Tout le reste — la partie, le joueur, la table
des places — est du jeu, et vit dans `moteur/models/`.

Le sens de la dépendance ne s'inverse jamais : `models/connexion.py` désigne le joueur du moteur
par son identifiant Discord, et le moteur, lui, n'importe rien d'ici.

    from models.connexion import Connexion
"""
