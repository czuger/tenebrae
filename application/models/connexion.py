"""La connexion : le lien entre une session Flask et le joueur du moteur.

C'est le seul modèle que l'application se garde. Il ne double pas `moteur.models.joueur` — il ne
retient ni pseudo, ni avatar, ni date : il ne retient qu'un **identifiant Discord**, celui que la
session porte, et va relire le joueur au dépôt chaque fois qu'on le lui demande. Un changement de
pseudo se voit ainsi dès la requête suivante, et il n'y a toujours qu'une notion d'identité dans
le projet.

Ce que la session porte : `joueur`, l'identifiant, et le temps d'un aller-retour `etat_oauth`.
**Rien d'autre, et surtout pas le jeton d'accès** — le cookie de session de Flask est signé, pas
chiffré, et son contenu se lit à qui le tient.

Rien de tout cela n'est persisté : la connexion n'est pas un document, elle n'a pas de collection.
Le cookie signé de Flask *est* son stockage, et il vit chez le joueur. La classe n'existe que pour
que ce savoir-là — quelles clés, dans quel ordre, avec quelle précaution — tienne en un seul
endroit plutôt qu'éparpillé dans les routes.

    connexion = Connexion(session, le_depot_de_joueurs())
    connexion.ouvrir(identite)          # après le retour de Discord
    connexion.joueur()                  # le dict du joueur, ou None
    connexion.fermer()                  # déconnexion
"""

import secrets

# Ce que la session porte, et rien de plus.
CLE_DU_JOUEUR = "joueur"
CLE_DE_L_ETAT_OAUTH = "etat_oauth"

# La longueur de l'état anti-CSRF de l'OAuth2, en octets avant encodage.
OCTETS_DE_L_ETAT = 32


class Connexion:
    """La session d'un visiteur, et le joueur du moteur qu'elle désigne.

    Elle se construit à chaque requête qui en a besoin : c'est un objet de passage, sans état
    propre — tout ce qu'elle sait est dans la session qu'on lui donne et dans le dépôt qu'elle
    interroge.

    `session` est la session de Flask (ou tout objet qui en offre l'interface : un mapping qui
    accepte aussi l'attribut `permanent`). `joueurs` est le dépôt de joueurs du moteur, celui que
    la factory accroche à l'application.
    """

    __slots__ = ("_session", "_joueurs")

    def __init__(self, session, joueurs):
        self._session = session
        self._joueurs = joueurs

    # --- Qui est là ---

    @property
    def identifiant(self):
        """L'identifiant Discord que porte la session, ou `None` si personne n'est connecté."""
        return self._session.get(CLE_DU_JOUEUR)

    def joueur(self):
        """Le joueur du moteur désigné par la session, ou `None`.

        Un identifiant qui ne correspond plus à personne — base vidée, dépôt de mémoire d'un
        serveur relancé — rend `None` sans faire d'histoire : le visiteur redevient anonyme.
        """
        identifiant = self.identifiant
        return self._joueurs.par_discord_id(identifiant) if identifiant else None

    # --- Ouvrir et fermer ---

    def ouvrir(self, identite):
        """Enregistre le joueur d'après ce que Discord vient d'en dire, et ouvre la session.

        On repart d'une session neuve : rien de ce qu'un anonyme y aurait laissé ne survit à
        l'ouverture d'un compte. Rend le dict du joueur enregistré.
        """
        joueur = self._joueurs.enregistrer(identite)
        self._session.clear()
        self._session[CLE_DU_JOUEUR] = joueur["discord_id"]
        self._session.permanent = True
        return joueur

    def fermer(self):
        """Ferme la session. La place tenue n'est pas rendue : on revient s'y asseoir."""
        self._session.clear()

    # --- L'aller-retour chez Discord ---

    def poser_un_etat_oauth(self):
        """Tire l'état à usage unique qui protège le flux du CSRF, le range, et le rend."""
        etat = secrets.token_urlsafe(OCTETS_DE_L_ETAT)
        self._session[CLE_DE_L_ETAT_OAUTH] = etat
        return etat

    def reprendre_l_etat_oauth(self):
        """Retire l'état de la session et le rend — `None` s'il n'y en avait pas.

        Il est **retiré**, et non lu : un retour rejoué ne trouvera plus rien à quoi se comparer.
        """
        return self._session.pop(CLE_DE_L_ETAT_OAUTH, None)

    def __repr__(self):
        identifiant = self.identifiant
        return f"Connexion({identifiant})" if identifiant else "Connexion(anonyme)"
