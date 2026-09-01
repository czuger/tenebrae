"""La colonne du journal, dans le navigateur : où elle est, ce qu'elle montre, et quand.

Ces tests demandent Chromium (`python3 -m playwright install chromium`).
"""

import pytest

import app
from moteur.hexagone import Hex
from moteur.pion import CATALOGUE

PLAINE = {"q": 1, "r": 26, "s": -27}    # deux cases libres du scénario n° 4, au contact
VOISINE = {"q": 2, "r": 26, "s": -28}

NAIN = "nains-01-5-infanteries"   # alliance, force 12
ARCHER = "yzent-03-8-archers"     # ténèbres, force 2 → rapport 6-1, dé 1 → DE


@pytest.fixture
def plateau(page, serveur, application, installer_le_joueur, carte_deserte):
    """Ouvre la page **connectée**, le journal vidé.

    Le journal du serveur est un module-global, et le serveur des tests tourne dans ce même
    processus : on le vide pour que la colonne ne montre que ce que le test y écrit. Il faut pour
    cela le vider **entre** la connexion et la page — se connecter écrit sa propre ligne, et elle
    fausserait les comptes.
    """
    installer_le_joueur(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{serveur}/connexion")
    app.MEMOIRE_DU_JOURNAL.lignes.clear()
    page.goto(f"{serveur}/")
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")
    yield page
    app.MEMOIRE_DU_JOURNAL.lignes.clear()


def lignes_lues(page):
    """Ce que la colonne montre, de haut en bas : une paire (heure, texte) par ligne."""
    return page.evaluate("""() => [...document.querySelectorAll('#journal-lignes li')]
        .map((ligne) => [ligne.querySelector('time').textContent,
                         ligne.querySelector('.texte').textContent])""")


def passer_une_phase(page, attendues):
    """Passe à la phase suivante, et attend que la colonne compte `attendues` lignes.

    C'est le **flux** qu'on attend là : la réponse du bouton ne porte que la phase, et la ligne
    du journal arrive par le canal qui pousse la partie (voir `reprendreLaPartie`).
    """
    page.locator("#phase-suivante").click()
    page.wait_for_function(
        "(n) => document.querySelectorAll('#journal-lignes li').length === n", arg=attendues)


def test_la_colonne_est_vide_et_cachee_tant_que_rien_n_est_arrive(plateau):
    """Rien à raconter, rien à encadrer."""
    assert plateau.locator("#journal").is_hidden()
    assert lignes_lues(plateau) == []


def test_la_colonne_montre_ce_que_le_serveur_journalise(plateau):
    passer_une_phase(plateau, 1)
    assert plateau.locator("#journal").is_visible()
    heure, texte = lignes_lues(plateau)[0]
    assert texte == "Phase : Phase de combat — Nains (tour 1)"
    assert len(heure.split(":")) == 3


def test_la_derniere_ligne_est_en_haut(plateau):
    """La colonne se lit à l'envers du fichier : ce qui vient d'arriver est sous la fiche."""
    passer_une_phase(plateau, 1)
    passer_une_phase(plateau, 2)
    assert [texte for _, texte in lignes_lues(plateau)] == [
        "Phase : Phase de mouvement — Orques (tour 1)",
        "Phase : Phase de combat — Nains (tour 1)",
    ]


def test_la_colonne_se_pose_sous_la_fiche(plateau):
    """Le placement demandé : une colonne juste en dessous de la zone de la fiche.

    La fiche étant cachée tant qu'on ne survole rien, on la montre à la main le temps de la
    mesure — c'est l'ordre des deux encadrés dans le panneau qu'on vérifie, pas le survol.
    """
    assert plateau.locator("#panneau > #journal").count() == 1
    passer_une_phase(plateau, 1)
    places = plateau.evaluate("""() => {
        const fiche = document.getElementById('fiche');
        fiche.hidden = false;
        const cadre = (id) => document.getElementById(id).getBoundingClientRect();
        const mesures = { fiche: cadre('fiche'), journal: cadre('journal') };
        fiche.hidden = true;
        return { fiche: [mesures.fiche.bottom, mesures.fiche.left],
                 journal: [mesures.journal.top, mesures.journal.left] };
    }""")
    assert places["journal"][0] >= places["fiche"][0], places   # sous la fiche
    assert places["journal"][1] == places["fiche"][1], places   # aligné sur son bord gauche


def cliquer(page, case):
    """Clique le pion posé sur cette case, quel que soit le zoom."""
    page.locator(f"img.pion[data-q='{case['q']}'][data-r='{case['r']}'][data-s='{case['s']}']") \
        .click()


def test_le_combat_montre_le_detail_de_son_calcul(plateau, monkeypatch):
    """Ce que le joueur voit d'un combat livré : son issue, et dessous le calcul qui l'a donnée.

    Les deux unités sont posées sur le plateau du serveur avant le changement de phase : c'est
    lui qui repose la scène, et elles y arrivent avec le reste.
    """
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    app.PLATEAU.poser(Hex(**PLAINE), CATALOGUE[NAIN])
    app.PLATEAU.poser(Hex(**VOISINE), CATALOGUE[ARCHER])
    passer_une_phase(plateau, 1)  # phase de combat des Nains, et la scène reposée avec les deux

    cliquer(plateau, VOISINE)  # la cible
    cliquer(plateau, PLAINE)   # l'attaquant
    plateau.locator("#attaquer").click()
    plateau.wait_for_function(
        "() => document.querySelectorAll('#journal-lignes li').length === 3")

    assert [texte for _, texte in lignes_lues(plateau)] == [
        "Combat résolu : Défenseur Éliminé",
        "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1",
        "Phase : Phase de combat — Nains (tour 1)",
    ]


def test_une_ligne_longue_reste_dans_la_colonne(plateau, monkeypatch):
    """Le détail est long : il doit se replier dans la colonne, pas la faire déborder."""
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    app.PLATEAU.poser(Hex(**PLAINE), CATALOGUE[NAIN])
    app.PLATEAU.poser(Hex(**VOISINE), CATALOGUE[ARCHER])
    passer_une_phase(plateau, 1)
    cliquer(plateau, VOISINE)
    cliquer(plateau, PLAINE)
    plateau.locator("#attaquer").click()
    plateau.wait_for_function(
        "() => document.querySelectorAll('#journal-lignes li').length === 3")

    mesures = plateau.evaluate("""() => {
        const colonne = document.getElementById('journal');
        const detail = [...document.querySelectorAll('#journal-lignes li')][1];
        return { debordement: colonne.scrollWidth - colonne.clientWidth,
                 largeur: colonne.getBoundingClientRect().width,
                 hauteur: detail.getBoundingClientRect().height,
                 ligne: parseFloat(getComputedStyle(detail).fontSize) };
    }""")
    assert mesures["debordement"] <= 1, mesures          # rien ne dépasse par la droite
    assert mesures["hauteur"] > mesures["ligne"], mesures  # la ligne s'est bien repliée
