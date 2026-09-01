"""Le diffuseur : qui suit la partie, et comment un coup joué leur parvient.

Avant, chaque navigateur redemandait l'état toutes les trois secondes (`GET /partie/etat`) et
s'entendait répondre « rien n'a bougé » vingt fois sur vingt et une. Maintenant il tient un
**flux ouvert** (`GET /flux`, du Server-Sent Events) et le serveur lui pousse la partie au moment
où elle change — pas avant, pas après.

Le mécanisme tient en trois pièces :

- un **abonné** par flux ouvert, c'est-à-dire par onglet qui regarde la partie ;
- une **boîte à une place** par abonné : un `Queue(maxsize=1)` dont le contenu est *remplacé*
  plutôt qu'empilé. Personne n'a besoin d'un état périmé — seul le dernier compte —, et une
  requête qui fait monter la version trois fois (c'est le cas de `/partie/nouvelle`, qui repose
  le scénario puis laisse l'IA jouer son tour) ne réveille l'abonné qu'une fois, sur le dernier
  état. C'est cette boîte qui fait la coalescence, et non le navigateur ;
- `publier`, appelé par le thread qui vient de jouer le coup, avec l'instantané **déjà pris**.

Ce dernier point est ce qui écarte les conflits d'accès à l'état du jeu : le plateau, le tour et
le registre des combats sont des module-globaux d'`app.py`, et rien ne les protège. Si le
générateur d'un flux allait les relire lui-même au réveil, il les lirait depuis le fil du serveur
qui sert *son* flux, pendant qu'un autre fil est peut-être en train de déplacer un pion. On ne
lui laisse donc rien à relire : la photo est prise une fois, dans le fil qui vient d'écrire, et
c'est elle qui voyage. Le seul état partagé qui reste est le registre des abonnés, et il a son
verrou.

Ce module ne connaît ni Flask, ni le jeu : il ne transporte que des objets qu'on lui donne. La
mise en forme SSE et la route sont dans `app.py`.

TODO: PRODUCTION — le registre est en mémoire, dans le processus. Tant qu'il n'y a qu'un worker
(`gunicorn -w 1`, et le serveur de développement), tous les joueurs sont abonnés au même
diffuseur et tout va bien. Au-delà, chaque worker aurait le sien et ne diffuserait qu'à ses
propres abonnés : un joueur servi par le worker 2 ne verrait jamais le coup joué sur le worker 1.
Il faudra alors un pub/sub externe — Redis — entre `publier` et les boîtes. Voir `DEPLOIEMENT.md`.
"""

import queue
import threading


class Abonne:
    """Un flux ouvert : sa boîte à une place, et de quoi y attendre le prochain état.

    L'abonné ne sait pas *qui* regarde — le diffuseur non plus. C'est la route qui sait quel
    joueur est derrière quel flux, et qui compose ce qu'elle lui envoie.
    """

    __slots__ = ("_boite",)

    def __init__(self):
        self._boite = queue.Queue(maxsize=1)

    def deposer(self, etat):
        """Y met le dernier état connu, en remplaçant celui qui n'a pas encore été lu.

        Le retrait puis le dépôt ne sont pas atomiques ensemble, et c'est sans conséquence : le
        seul lecteur de cette boîte est le générateur de *ce* flux-là, et deux dépôts concurrents
        laisseraient de toute façon l'un des deux états — le plus récent à quelques microsecondes
        près. Un état de retard se rattrape au dépôt suivant ; le navigateur, lui, ne verrait
        même pas la différence.
        """
        try:
            self._boite.get_nowait()
        except queue.Empty:
            pass
        try:
            self._boite.put_nowait(etat)
        except queue.Full:  # pragma: no cover - un autre dépôt vient de la remplir
            pass

    def attendre(self, delai):
        """Le prochain état, ou `None` si rien n'est venu avant `delai` secondes.

        Le `None` n'est pas une panne : c'est ce qui déclenche le battement de cœur, sans lequel
        un intermédiaire — ou le navigateur lui-même — finirait par refermer une connexion qu'il
        croit morte.
        """
        try:
            return self._boite.get(timeout=delai)
        except queue.Empty:
            return None


class Diffuseur:
    """Le registre des flux ouverts, et l'envoi d'un état à tous.

    Une seule instance par processus (`DIFFUSEUR` dans `app.py`), comme le plateau et le tour :
    il n'y a qu'une partie, et tous ceux qui la regardent la regardent ensemble.
    """

    def __init__(self):
        self._abonnes = set()
        self._verrou = threading.Lock()

    def __len__(self):
        """Le nombre de flux ouverts. Les tests s'en servent pour constater qu'il n'en reste
        aucun une fois les pages refermées."""
        with self._verrou:
            return len(self._abonnes)

    def abonner(self):
        """Ouvre un abonnement et rend l'abonné.

        Préférer `abonnement()`, qui garantit la radiation ; celui-ci est là pour les tests et
        pour qui a besoin des deux temps séparément.
        """
        abonne = Abonne()
        with self._verrou:
            self._abonnes.add(abonne)
        return abonne

    def radier(self, abonne):
        """Retire un abonné du registre. Radier deux fois ne fait rien de plus."""
        with self._verrou:
            self._abonnes.discard(abonne)

    def abonnement(self):
        """L'abonnement en context manager : `with DIFFUSEUR.abonnement() as abonne:`.

        C'est **la** façon de s'abonner depuis un générateur de flux. Un navigateur qui ferme son
        onglet, une coupure réseau, un serveur qu'on arrête : dans tous les cas le générateur est
        fermé, `GeneratorExit` traverse le `with`, et l'abonné est radié. Sans cela, chaque page
        refermée laisserait une boîte derrière elle, à qui le serveur continuerait de déposer
        l'état de chaque coup joué — une fuite à la fois de mémoire et de travail.
        """
        return _Abonnement(self, self.abonner())

    def publier(self, etat):
        """Dépose cet état chez tous les abonnés, et rend leur nombre.

        L'appelant est le fil qui vient de jouer le coup, et `etat` la photo qu'il a prise
        lui-même : le diffuseur ne va rien relire.

        La copie du registre est prise sous le verrou, mais les dépôts se font en dehors : un
        abonné qui s'abonne ou se radie pendant l'envoi n'a pas à attendre qu'il finisse. Celui
        qui arrive une microseconde trop tard rattrape de toute façon l'état courant à
        l'ouverture de son flux, que la route lui envoie d'emblée.
        """
        with self._verrou:
            abonnes = list(self._abonnes)
        for abonne in abonnes:
            abonne.deposer(etat)
        return len(abonnes)


class _Abonnement:
    """Ce que rend `Diffuseur.abonnement()` : un abonné, radié quoi qu'il arrive en sortant."""

    __slots__ = ("_diffuseur", "_abonne")

    def __init__(self, diffuseur, abonne):
        self._diffuseur = diffuseur
        self._abonne = abonne

    def __enter__(self):
        return self._abonne

    def __exit__(self, *_):
        self._diffuseur.radier(self._abonne)
        return False
