"""Les modèles de l'application, **un fichier par modèle**.

Il y en a deux, et pas un de plus : l'application ne modélise que ce qui **n'est pas du jeu**.
Tout le reste — la partie, le joueur, la table des places — vit dans `moteur/models/`.

- `connexion.py` : le lien entre une session Flask et le joueur du moteur. Rien n'en est persisté,
  le cookie signé de Flask *est* son stockage ;
- `vue.py` : où un joueur en était sur la carte, et de combien il l'avait approchée. Un document
  Mongo, écrit par `depots/vue.py`. Il est ici et non dans le moteur parce que le moteur ne sait
  pas qu'il existe une image, des pixels ou une fenêtre : une partie se joue depuis un
  interpréteur, où le zoom ne veut rien dire.

Le sens de la dépendance ne s'inverse jamais : les deux désignent le joueur du moteur par son
identifiant Discord, et le moteur, lui, n'importe rien d'ici.

    from models.connexion import Connexion
    from models.vue import Vue
"""
