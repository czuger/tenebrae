"""Le diffuseur seul, sans Flask ni navigateur : boîte à une place, registre, radiation.

C'est la pièce sur laquelle repose tout le flux SSE, et elle se laisse éprouver sans serveur —
elle ne connaît ni le jeu ni le web. Ce qui se voit dans une page est éprouvé à part, dans
`test_flux.py` (Flask) et `test_flux_navigateur.py` (Chromium).
"""

import threading

from flux import Diffuseur

# De quoi ne pas attendre une seconde pour constater qu'une boîte est vide.
INSTANT = 0.05
# La marge laissée à un fil pour se réveiller sur une machine chargée.
PATIENCE = 2.0


def test_un_abonne_recoit_ce_qui_est_publie():
    diffuseur = Diffuseur()
    with diffuseur.abonnement() as abonne:
        diffuseur.publier({"version": 7})
        assert abonne.attendre(PATIENCE) == {"version": 7}


def test_une_boite_vide_rend_none_apres_le_delai():
    """C'est ce `None` qui déclenche le battement de cœur du flux."""
    diffuseur = Diffuseur()
    with diffuseur.abonnement() as abonne:
        assert abonne.attendre(INSTANT) is None


def test_tous_les_abonnes_recoivent_la_meme_publication():
    """Deux joueurs, deux onglets : un seul coup joué les réveille tous les deux."""
    diffuseur = Diffuseur()
    with diffuseur.abonnement() as premier, diffuseur.abonnement() as second:
        assert diffuseur.publier({"version": 1}) == 2
        assert premier.attendre(PATIENCE) == {"version": 1}
        assert second.attendre(PATIENCE) == {"version": 1}


def test_la_boite_ne_garde_que_le_dernier_etat():
    """La coalescence : `/partie/nouvelle` fait monter la version trois fois en une requête.

    L'abonné n'a que faire des états intermédiaires — il repose la scène entière à chaque
    réveil. Il ne doit donc être réveillé qu'une fois, et sur le dernier.
    """
    diffuseur = Diffuseur()
    with diffuseur.abonnement() as abonne:
        diffuseur.publier({"version": 1})
        diffuseur.publier({"version": 2})
        diffuseur.publier({"version": 3})

        assert abonne.attendre(PATIENCE) == {"version": 3}
        assert abonne.attendre(INSTANT) is None, "un état intermédiaire est resté en attente"


def test_publier_sans_personne_ne_fait_rien():
    assert Diffuseur().publier({"version": 1}) == 0


def test_le_registre_se_vide_a_la_sortie_du_with():
    """La fuite qu'on veut prendre : un onglet refermé qui laisse sa boîte derrière lui."""
    diffuseur = Diffuseur()
    with diffuseur.abonnement():
        assert len(diffuseur) == 1
    assert len(diffuseur) == 0


def test_le_registre_se_vide_meme_sur_une_erreur():
    """Une coupure réseau lève dans le générateur du flux : l'abonné doit partir quand même."""
    diffuseur = Diffuseur()
    try:
        with diffuseur.abonnement():
            raise BrokenPipeError("le navigateur est parti")
    except BrokenPipeError:
        pass
    assert len(diffuseur) == 0


def test_un_generateur_abandonne_radie_son_abonne():
    """Le cas réel : le navigateur ferme l'onglet, le générateur est fermé, `GeneratorExit`
    traverse le `with`. C'est ce que fait werkzeug quand la connexion tombe."""
    diffuseur = Diffuseur()

    def flux():
        with diffuseur.abonnement() as abonne:
            while True:
                yield abonne.attendre(INSTANT)

    generateur = flux()
    next(generateur)
    assert len(diffuseur) == 1

    generateur.close()
    assert len(diffuseur) == 0


def test_radier_deux_fois_ne_fait_rien_de_plus():
    diffuseur = Diffuseur()
    abonne = diffuseur.abonner()
    diffuseur.radier(abonne)
    diffuseur.radier(abonne)
    assert len(diffuseur) == 0


def test_un_abonne_endormi_est_reveille_par_une_publication():
    """Le cœur du sujet : le flux **attend**, il ne redemande rien. Publier le réveille.

    Sans cela on aurait un sondage déguisé côté serveur — une boucle qui relit l'état à
    intervalle fixe pour voir s'il a bougé —, ce qui n'aurait déplacé le problème que d'un cran.
    """
    diffuseur = Diffuseur()
    recu = []
    pret = threading.Event()

    def ecouter():
        with diffuseur.abonnement() as abonne:
            pret.set()
            recu.append(abonne.attendre(PATIENCE))

    fil = threading.Thread(target=ecouter, daemon=True)
    fil.start()
    assert pret.wait(PATIENCE), "le fil d'écoute n'a pas démarré"

    diffuseur.publier({"version": 42})
    fil.join(PATIENCE)

    assert recu == [{"version": 42}]
    assert len(diffuseur) == 0, "le fil parti, son abonnement doit l'être aussi"
