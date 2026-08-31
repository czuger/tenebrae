"""Ce que le navigateur affiche : les pions posés, centrés et inclinés sur la carte.

Ces tests demandent Chromium (`python3 -m playwright install chromium`).
"""

import math

import pytest

import app
from moteur.hexagone import CARTE, Hex
from moteur.pion import ADVERSAIRES, CATALOGUE


@pytest.fixture
def plateau(page, serveur):
    """Ouvre la page et attend que la carte et les unités du scénario soient chargées."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(serveur)
    page.wait_for_function(
        "document.querySelectorAll('img.pion').length === %d" % len(app.SCENARIO)
    )
    page.wait_for_function(
        "[...document.querySelectorAll('img.pion'), document.getElementById('carte')]"
        ".every((i) => i.complete && i.naturalWidth > 0)"
    )
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")
    return page


def centre_attendu(q, r):
    """centre(q, r) = origine + matrice · (q, r), en pixels de map.jpg (game_box/carte.md)."""
    origine, matrice = app.GRILLE_ORIGINE, app.GRILLE_MATRICE
    return (origine[0] + matrice[0][0] * q + matrice[0][1] * r,
            origine[1] + matrice[1][0] * q + matrice[1][1] * r)


def geometrie_des_pions(page, selecteur="img.pion:not(.fantome)"):
    """Rend, pour chaque image de `selecteur`, sa position rendue en pixels de map.jpg."""
    return page.evaluate("""(selecteur) => {
        const carte = document.getElementById('carte');
        const cadreCarte = carte.getBoundingClientRect();
        const echelle = cadreCarte.width / carte.naturalWidth;
        return [...document.querySelectorAll(selecteur)].map((pion) => {
            const cadre = pion.getBoundingClientRect();
            const matrice = new DOMMatrix(getComputedStyle(pion).transform);
            return {
                q: Number(pion.dataset.q),
                r: Number(pion.dataset.r),
                s: Number(pion.dataset.s),
                x: (cadre.x + cadre.width / 2 - cadreCarte.x) / echelle,
                y: (cadre.y + cadre.height / 2 - cadreCarte.y) / echelle,
                angle: Math.atan2(matrice.b, matrice.a) * 180 / Math.PI,
                largeur: pion.offsetWidth,
                echelle: echelle,
                opacite: Number(getComputedStyle(pion).opacity),
            };
        });
    }""", selecteur)


def test_la_carte_est_affichee(plateau):
    carte = plateau.evaluate(
        "() => { const c = document.getElementById('carte');"
        " return {l: c.naturalWidth, h: c.naturalHeight}; }"
    )
    assert (carte["l"], carte["h"]) == (6173, 5102)


def test_les_unites_du_scenario_sont_posees(plateau):
    assert plateau.locator("img.pion").count() == len(app.SCENARIO)


def test_les_images_de_pions_se_chargent(plateau):
    assert plateau.evaluate(
        "() => [...document.querySelectorAll('img.pion')].every((i) => i.naturalWidth > 0)"
    )


def test_chaque_pion_est_centre_sur_son_hexagone(plateau):
    """Le centre rendu du pion tombe sur le centre de l'hexagone, à moins d'un pixel près."""
    for pion in geometrie_des_pions(plateau):
        x, y = centre_attendu(pion["q"], pion["r"])
        assert math.isclose(pion["x"], x, abs_tol=1.0), pion
        assert math.isclose(pion["y"], y, abs_tol=1.0), pion


def test_chaque_pion_est_incline_de_moins_de_cinq_degres(plateau):
    for pion in geometrie_des_pions(plateau):
        assert abs(pion["angle"]) <= 5.0, pion


def test_les_inclinaisons_sont_tirees_au_hasard(plateau):
    """Des pions tous à la même inclinaison trahiraient une rotation figée."""
    angles = [round(pion["angle"], 3) for pion in geometrie_des_pions(plateau)]
    # Deux inclinaisons sur cinquante-deux peuvent coïncider au millième de degré près ; une
    # rotation figée, elle, les rendrait toutes égales.
    assert len(set(angles)) >= len(angles) - 3
    assert any(angle < 0 for angle in angles) and any(angle > 0 for angle in angles)


def test_les_pions_ont_la_taille_prevue(plateau):
    for pion in geometrie_des_pions(plateau):
        assert pion["largeur"] == app.PION_TAILLE


def test_le_plateau_tient_dans_la_fenetre(plateau):
    debordement = plateau.evaluate(
        "() => ({ l: document.documentElement.scrollWidth - window.innerWidth,"
        "         h: document.documentElement.scrollHeight - window.innerHeight })"
    )
    assert debordement["l"] <= 0 and debordement["h"] <= 0


def test_le_plateau_suit_le_redimensionnement(plateau):
    """Après un redimensionnement, la carte reste à l'échelle et les pions à leur place."""
    avant = geometrie_des_pions(plateau)[0]["echelle"]
    plateau.set_viewport_size({"width": 900, "height": 600})
    plateau.wait_for_function("() => window.innerWidth === 900 && window.innerHeight === 600")
    plateau.evaluate("() => new Promise(requestAnimationFrame)")
    apres = geometrie_des_pions(plateau)
    assert apres[0]["echelle"] < avant
    for pion in apres:
        x, y = centre_attendu(pion["q"], pion["r"])
        assert math.isclose(pion["x"], x, abs_tol=1.0), pion
        assert math.isclose(pion["y"], y, abs_tol=1.0), pion


# --- Zoom -----------------------------------------------------------------------------------


def echelle_rendue(page):
    """L'échelle à laquelle la carte est rendue, lue sur l'image elle-même."""
    return page.evaluate(
        "() => { const c = document.getElementById('carte');"
        " return c.getBoundingClientRect().width / c.naturalWidth; }")


def approcher(page, crans=1):
    """Clique « + » et attend que l'échelle affichée change."""
    for _ in range(crans):
        avant = page.locator("#echelle").text_content()
        page.locator("#zoomer").click()
        page.wait_for_function(
            "(depart) => document.getElementById('echelle').textContent !== depart", arg=avant)


def test_les_boutons_de_zoom_changent_l_echelle(plateau):
    ajustee = echelle_rendue(plateau)
    approcher(plateau)
    assert echelle_rendue(plateau) > ajustee

    plateau.locator("#ajuster").click()
    plateau.wait_for_function(
        "(ajustee) => { const c = document.getElementById('carte');"
        " return Math.abs(c.getBoundingClientRect().width / c.naturalWidth - ajustee) < 1e-6; }",
        arg=ajustee)


def test_la_molette_approche_la_carte(plateau):
    """Approcher à la molette garde sous le pointeur le point de carte qu'il désignait."""
    x, y = centre_attendu(28, 15)
    pointeur = plateau.evaluate("""([x, y]) => {
        const carte = document.getElementById('carte');
        const cadre = carte.getBoundingClientRect();
        const echelle = cadre.width / carte.naturalWidth;
        return [cadre.x + x * echelle, cadre.y + y * echelle];
    }""", [x, y])

    ajustee = echelle_rendue(plateau)
    plateau.mouse.move(*pointeur)
    plateau.mouse.wheel(0, -300)
    plateau.wait_for_function(
        "(ajustee) => { const c = document.getElementById('carte');"
        " return c.getBoundingClientRect().width / c.naturalWidth > ajustee; }", arg=ajustee)

    # Le point de map.jpg désormais sous le pointeur : à quelques pixels d'écran près, le même.
    vise = plateau.evaluate("""([cx, cy]) => {
        const carte = document.getElementById('carte');
        const cadre = carte.getBoundingClientRect();
        const echelle = cadre.width / carte.naturalWidth;
        return [(cx - cadre.x) / echelle, (cy - cadre.y) / echelle];
    }""", list(pointeur))
    assert math.isclose(vise[0], x, abs_tol=30), vise
    assert math.isclose(vise[1], y, abs_tol=30), vise


def test_les_pions_restent_sur_leur_hexagone_une_fois_approche(plateau):
    """Le zoom ne touche qu'à l'échelle : les pions sont posés en pixels de map.jpg."""
    approcher(plateau, crans=3)
    poses = geometrie_des_pions(plateau)
    assert poses[0]["echelle"] > 0

    for pion in poses:
        x, y = centre_attendu(pion["q"], pion["r"])
        assert math.isclose(pion["x"], x, abs_tol=1.0), pion
        assert math.isclose(pion["y"], y, abs_tol=1.0), pion


def test_le_redimensionnement_ne_defait_pas_le_zoom(plateau):
    """La carte suit la fenêtre tant qu'on n'a pas réglé l'échelle soi-même."""
    approcher(plateau)
    approchee = echelle_rendue(plateau)

    plateau.set_viewport_size({"width": 900, "height": 600})
    plateau.wait_for_function("() => window.innerWidth === 900 && window.innerHeight === 600")
    plateau.evaluate("() => new Promise(requestAnimationFrame)")

    assert math.isclose(echelle_rendue(plateau), approchee, rel_tol=1e-6)


# --- Fantômes et déplacement ----------------------------------------------------------------


def pions_qui_peuvent_bouger(page, convient=lambda pion: True):
    """Les pions de la page qui ont des cases où aller, et que `convient` accepte.

    La portée est celle que le **plateau du serveur** calcule : le mouvement du carton, moins ce
    que les adversaires posés autour lui interdisent. Le serveur de test tourne dans ce processus,
    son plateau se lit donc directement.
    """
    for indice in range(len(app.SCENARIO)):
        pion = page.locator("img.pion:not(.fantome)").nth(indice)
        position = pion.evaluate(
            "p => [Number(p.dataset.q), Number(p.dataset.r), Number(p.dataset.s)]")
        depart = Hex(*position)
        atteignables = app.PLATEAU.deplacements(depart)
        if atteignables and convient(app.PLATEAU.pion_sur(depart)):
            yield pion, depart, atteignables


def pion_qui_peut_bouger(page, convient=lambda pion: True):
    """Le premier pion de la page qui a des cases où aller."""
    for candidat in pions_qui_peuvent_bouger(page, convient):
        return candidat
    raise AssertionError("aucune unité du scénario ne peut se déplacer")


def fantomes(page):
    return geometrie_des_pions(page, "img.fantome")


def montrer_les_fantomes(page, pion):
    """Clique le pion et attend ses fantômes."""
    pion.click()
    page.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    return fantomes(page)


def test_cliquer_un_pion_montre_ses_deplacements(plateau):
    pion, depart, atteignables = pion_qui_peut_bouger(plateau)
    poses = montrer_les_fantomes(plateau, pion)

    assert len(poses) == len(atteignables)
    assert {(f["q"], f["r"], f["s"]) for f in poses} == {(h.q, h.r, h.s) for h in atteignables}
    assert (depart.q, depart.r, depart.s) not in {(f["q"], f["r"], f["s"]) for f in poses}


def test_les_fantomes_suivent_le_mouvement_du_carton(plateau):
    """Le nombre de fantômes est celui du mouvement du pion, pas d'un forfait commun."""
    pion, depart, _ = pion_qui_peut_bouger(plateau)
    mouvement = app.PLATEAU.pion_sur(depart).points_de_mouvement
    poses = montrer_les_fantomes(plateau, pion)

    assert len(poses) == len(app.PLATEAU.deplacements(depart))
    assert len(poses) <= len(depart.deplacements(mouvement))


def contact_avec_un_adversaire(page):
    """Pose un adversaire au contact d'un pion de la page, et rend la figure obtenue.

    L'ennemi est posé sur le plateau du serveur sans image sur la carte : ce qu'on veut éprouver
    est la chaîne du clic à la règle, pas l'affichage de ce pion-là. On cherche une figure où il
    reste quelque chose à montrer — un pion acculé n'aurait aucun fantôme, et il n'y aurait rien
    à comparer. Une unité prise au milieu de son armée n'a aucune case voisine libre : elle ne
    fait pas l'affaire non plus, et on passe à la suivante.
    """
    for pion, depart, seul in pions_qui_peuvent_bouger(page, engage):
        voisine = next((voisin for voisin in depart.voisins() if voisin in seul), None)
        if voisine is None:
            continue
        app.PLATEAU.poser(voisine, adversaire_de(app.PLATEAU.pion_sur(depart)))
        au_contact = app.PLATEAU.deplacements(depart)
        if 0 < len(au_contact) < len(seul):
            return pion, depart, seul, voisine
        app.PLATEAU.retirer(voisine)
    pytest.skip("aucune unité du scénario n'a de voisin où poser un adversaire")


def test_les_fantomes_s_arretent_devant_l_adversaire(plateau):
    """Un adversaire posé au contact réduit ce que le clic affiche."""
    pion, _, seul, voisine = contact_avec_un_adversaire(plateau)

    poses = montrer_les_fantomes(plateau, pion)
    assert len(poses) < len(seul)
    assert (voisine.q, voisine.r, voisine.s) not in {(f["q"], f["r"], f["s"]) for f in poses}


def engage(pion):
    """Dit si le pion appartient à un camp : un neutre n'a pas d'adversaire à lui opposer."""
    return pion.camp in ADVERSAIRES


def adversaire_de(pion):
    """Un pion du camp opposé, pris au catalogue."""
    return next(autre for autre in CATALOGUE.values()
                if autre.camp == ADVERSAIRES[pion.camp] and autre.est_une_unite)


# --- La fiche de l'unité survolée ---------------------------------------------------------------


def fiche_lue(page):
    """Ce que la fiche montre en ce moment : son état, ses textes et ses valeurs."""
    return page.evaluate("""() => {
        const paires = [...document.getElementById('fiche-valeurs').children];
        const valeurs = {};
        for (let i = 0; i < paires.length; i += 2) {
            valeurs[paires[i].textContent] = paires[i + 1].textContent;
        }
        const image = document.getElementById('fiche-image');
        const remarques = document.getElementById('fiche-remarques');
        return {
            cachee: document.getElementById('fiche').hidden,
            nom: document.getElementById('fiche-nom').textContent,
            appoint: document.getElementById('fiche-appoint').textContent,
            symbole: document.getElementById('fiche-symbole').textContent,
            valeurs: valeurs,
            remarques: remarques.hidden ? null : remarques.textContent,
            source: image.src,
            chargee: image.complete && image.naturalWidth > 0,
        };
    }""")


def survoler(page, pion):
    """Survole le pion et attend que sa fiche paraisse ; rend ce qu'elle montre."""
    pion.hover()
    page.wait_for_function("() => !document.getElementById('fiche').hidden")
    return fiche_lue(page)


def quitter_le_pion(page):
    """Éloigne le pointeur de tout pion, et attend que la fiche se referme."""
    page.mouse.move(1, 1)
    page.wait_for_function("() => document.getElementById('fiche').hidden")


def portee_sur_le_carton(valeur):
    """La valeur telle que la fiche l'écrit : ce que le carton ne porte pas devient un tiret."""
    return "—" if valeur is None else str(valeur)


def test_la_fiche_est_cachee_tant_qu_on_ne_survole_rien(plateau):
    assert fiche_lue(plateau)["cachee"]


def test_survoler_un_pion_montre_les_valeurs_de_son_carton(plateau):
    """Toute unité posée montre, au survol, ce que son carton porte — et rien d'inventé."""
    for indice in range(len(app.SCENARIO)):
        pion = plateau.locator("img.pion:not(.fantome)").nth(indice)
        cle = pion.evaluate("p => p.pion.cle")
        pose = CATALOGUE[cle]

        fiche = survoler(plateau, pion)
        assert fiche["valeurs"] == {
            "Force": portee_sur_le_carton(pose.force),
            "Mouvement": str(pose.points_de_mouvement),
            "Tir": portee_sur_le_carton(pose.tir),
            "Portée": portee_sur_le_carton(pose.portee),
            "Vol": portee_sur_le_carton(pose.mouvement_vol),
            "Facultés": portee_sur_le_carton(pose.facultes_speciales),
        }, cle
        assert fiche["symbole"] == portee_sur_le_carton(pose.symbole), cle
        # Une remarque est ce que la photo laisse en suspens : pas de remarque, pas de ligne.
        assert fiche["remarques"] == pose.remarques, cle
        quitter_le_pion(plateau)


def test_les_deux_pions_sans_remarque_n_en_montrent_pas_la_ligne(plateau):
    """La ligne des remarques ne paraît que s'il y a quelque chose à dire."""
    sans, avec = 0, 0
    for indice in range(len(app.SCENARIO)):
        pion = plateau.locator("img.pion:not(.fantome)").nth(indice)
        remarque = CATALOGUE[pion.evaluate("p => p.pion.cle")].remarques
        lue = survoler(plateau, pion)["remarques"]
        if remarque is None:
            assert lue is None
            sans += 1
        else:
            assert lue == remarque
            avec += 1
        quitter_le_pion(plateau)
    assert sans and avec, "le scénario doit porter les deux cas pour que le test vaille"


def test_la_fiche_dit_le_nom_le_camp_et_la_case_du_pion(plateau):
    pion = plateau.locator("img.pion:not(.fantome)").first
    cle, case = pion.evaluate(
        "p => [p.pion.cle, `${p.dataset.q},${p.dataset.r},${p.dataset.s}`]")

    fiche = survoler(plateau, pion)
    assert fiche["nom"] == app.PIONS_PAR_CLE[cle]["nom"]
    assert fiche["appoint"] == f"{CATALOGUE[cle].camp} — {case}"


def test_la_fiche_montre_la_photo_du_pion(plateau):
    """C'est là qu'on lit le carton : la carte ajustée n'en montre qu'une quinzaine de pixels."""
    pion = plateau.locator("img.pion:not(.fantome)").first
    source = pion.evaluate("p => p.src")

    fiche = survoler(plateau, pion)
    assert fiche["source"] == source
    assert fiche["chargee"]


def test_quitter_le_pion_referme_la_fiche(plateau):
    pion = plateau.locator("img.pion:not(.fantome)").first
    survoler(plateau, pion)
    quitter_le_pion(plateau)
    assert fiche_lue(plateau)["cachee"]


def test_survoler_un_fantome_ne_montre_pas_de_fiche(plateau):
    """Un fantôme répète l'unité sélectionnée : sa fiche n'apprendrait rien."""
    pion, _, _ = pion_qui_peut_bouger(plateau)
    montrer_les_fantomes(plateau, pion)
    quitter_le_pion(plateau)

    plateau.locator("img.fantome").last.hover()
    assert fiche_lue(plateau)["cachee"]


def test_la_fiche_dit_la_case_ou_le_pion_vient_d_arriver(plateau):
    """Le pion déplacé, sa fiche doit donner sa nouvelle case, pas celle du scénario."""
    pion, depart, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    plateau.locator("img.fantome").last.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    case = pion.evaluate("p => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`")
    assert case != depart.cle
    assert survoler(plateau, pion)["appoint"].endswith(f"— {case}")


def test_la_fiche_se_pose_sous_la_barre_des_boutons_de_zoom(plateau):
    """La fiche n'est pas un encadré posé n'importe où sur la carte : elle est sous la barre.

    Elle a été dans la barre, à la suite des boutons ; il lui fallait pour cela rester minuscule
    sous peine de l'allonger. Descendue d'un cran, elle a la place de se lire, et le panneau la
    tient toujours dans le coin que la barre occupe déjà.
    """
    assert plateau.locator("#panneau > #outils").count() == 1
    assert plateau.locator("#panneau > #fiche").count() == 1

    pion = plateau.locator("img.pion:not(.fantome)").first
    survoler(plateau, pion)
    places = plateau.evaluate("""() => {
        const cadre = (id) => document.getElementById(id).getBoundingClientRect();
        const outils = cadre('outils');
        const fiche = cadre('fiche');
        return { barre: [outils.bottom, outils.left], fiche: [fiche.top, fiche.left] };
    }""")
    assert places["fiche"][0] >= places["barre"][0], places  # sous la barre
    assert places["fiche"][1] == places["barre"][1], places  # alignée sur son bord gauche


def test_la_fiche_se_lit_a_la_taille_de_la_barre(plateau):
    """L'encart reprend la taille de police de la barre d'outils : les deux se lisent d'un même œil.

    C'est la correction du 0.1875rem — trois pixels — auquel la fiche avait été réduite pour tenir
    dans la barre sans l'agrandir.
    """
    survoler(plateau, plateau.locator("img.pion:not(.fantome)").first)
    tailles = plateau.evaluate("""() => ['outils', 'fiche'].map(
        (id) => getComputedStyle(document.getElementById(id)).fontSize)""")
    assert tailles[0] == tailles[1], tailles
    assert float(tailles[1].removesuffix("px")) >= 12, tailles


def test_la_fiche_ne_bouge_pas_d_un_pion_a_l_autre(plateau):
    """La barre est en place fixe : survoler une autre unité ne la déplace pas."""
    coins = set()
    for indice in range(len(app.SCENARIO)):
        pion = plateau.locator("img.pion:not(.fantome)").nth(indice)
        survoler(plateau, pion)
        coins.add(tuple(plateau.evaluate(
            "() => { const c = document.getElementById('outils').getBoundingClientRect();"
            "        return [Math.round(c.x), Math.round(c.y)]; }")))
    assert len(coins) == 1, coins


def test_les_elements_de_la_fiche_sont_empiles(plateau):
    """Un élément par ligne, du nom aux remarques : chacun commence sous le précédent.

    La vignette, elle, reste à côté de la pile — le carton se reconnaît d'un coup d'œil pendant
    qu'on lit ses valeurs.
    """
    pion = plateau.locator("img.pion:not(.fantome)").first
    survoler(plateau, pion)

    places = plateau.evaluate("""() => {
        const cadre = (id) => {
            const c = document.getElementById(id).getBoundingClientRect();
            return { haut: c.top, gauche: c.left, bas: c.bottom, droite: c.right };
        };
        return {
            empiles: ['fiche-nom', 'fiche-appoint', 'fiche-symbole', 'fiche-valeurs'].map(cadre),
            vignette: cadre('fiche-image'),
            texte: cadre('fiche-texte'),
        };
    }""")

    for precedent, suivant in zip(places["empiles"], places["empiles"][1:]):
        assert suivant["haut"] >= precedent["bas"], places["empiles"]
        assert suivant["gauche"] == precedent["gauche"], places["empiles"]

    assert places["vignette"]["droite"] <= places["texte"]["gauche"]


def hauteur_de_la_barre(page):
    return page.evaluate(
        "() => Math.round(document.getElementById('outils').getBoundingClientRect().height)")


def test_la_barre_garde_sa_taille_quand_la_fiche_parait(plateau):
    """La barre d'outils garde la taille de référence que carte.css documente : même hauteur,
    fiche ouverte ou non, et à toute largeur de fenêtre.

    C'est ce que le todo demandait de préserver. La fiche est désormais sous la barre plutôt que
    dedans, elle ne peut donc plus l'allonger ; reste que la barre, elle, ne se replie toujours pas
    — un repli la ferait doubler de hauteur —, elle se laisse rogner par la droite. Le survol est
    ici simulé plutôt que joué à la souris : une fois la fenêtre rétrécie, le pion visé peut se
    retrouver sous la barre, hors d'atteinte du pointeur, et ce qu'on éprouve est la mise en page,
    pas le pointage.
    """
    # Le pion au libellé le plus long : c'est lui qui allonge le plus la barre.
    indice = plateau.evaluate("""() => {
        const pions = [...document.querySelectorAll('img.pion:not(.fantome)')];
        const large = pions.slice().sort((a, b) =>
            (b.pion.nom + (b.pion.remarques ?? '')).length
            - (a.pion.nom + (a.pion.remarques ?? '')).length)[0];
        return pions.indexOf(large);
    }""")
    survol = """([indice, evenement]) => {
        const pion = document.querySelectorAll('img.pion:not(.fantome)')[indice];
        pion.dispatchEvent(new MouseEvent(evenement, { bubbles: true }));
    }"""

    for largeur in (1400, 800):
        plateau.set_viewport_size({"width": largeur, "height": 900})
        plateau.wait_for_function("(l) => window.innerWidth === l", arg=largeur)
        plateau.evaluate(survol, [indice, "mouseout"])
        nue = hauteur_de_la_barre(plateau)

        plateau.evaluate(survol, [indice, "mouseover"])
        assert not fiche_lue(plateau)["cachee"]
        assert hauteur_de_la_barre(plateau) == nue, largeur


def test_le_panneau_ne_deborde_pas_de_la_fenetre(plateau):
    """À toute largeur, le panneau tient dans la fenêtre et la page ne défile pas de côté.

    Descendre la fiche sous la barre lui a rendu de la place, mais elle en prend maintenant en
    hauteur comme en largeur : elle ne doit pour autant ni sortir de l'écran ni pousser la carte.
    """
    indice = plateau.evaluate("""() => {
        const pions = [...document.querySelectorAll('img.pion:not(.fantome)')];
        const large = pions.slice().sort((a, b) =>
            (b.pion.nom + (b.pion.remarques ?? '')).length
            - (a.pion.nom + (a.pion.remarques ?? '')).length)[0];
        return pions.indexOf(large);
    }""")
    survol = """(indice) => {
        const pion = document.querySelectorAll('img.pion:not(.fantome)')[indice];
        pion.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    }"""

    for largeur in (1400, 800, 480):
        plateau.set_viewport_size({"width": largeur, "height": 900})
        plateau.wait_for_function("(l) => window.innerWidth === l", arg=largeur)
        plateau.evaluate(survol, indice)
        assert not fiche_lue(plateau)["cachee"]

        mesures = plateau.evaluate("""() => {
            const panneau = document.getElementById('panneau').getBoundingClientRect();
            return { droite: panneau.right, bas: panneau.bottom,
                     largeur: window.innerWidth, hauteur: window.innerHeight,
                     defile: document.documentElement.scrollWidth > window.innerWidth };
        }""")
        assert mesures["droite"] <= mesures["largeur"], (largeur, mesures)
        assert mesures["bas"] <= mesures["hauteur"], (largeur, mesures)
        assert not mesures["defile"], (largeur, mesures)


def test_la_carte_reste_entiere_sous_le_panneau(plateau):
    """Le panneau se pose par-dessus la carte ; il ne la rétrécit ni ne la déplace.

    Il est en place fixe, hors du flux : la carte occupe la fenêtre comme s'il n'existait pas,
    fiche ouverte ou non.
    """
    cadre = "() => { const c = document.getElementById('carte').getBoundingClientRect();"\
            "        return [Math.round(c.x), Math.round(c.y),"\
            "                Math.round(c.width), Math.round(c.height)]; }"
    nue = plateau.evaluate(cadre)
    survoler(plateau, plateau.locator("img.pion:not(.fantome)").first)
    assert plateau.evaluate(cadre) == nue


def test_la_fiche_ne_capte_pas_les_clics(plateau):
    """La barre porte des boutons, mais la fiche, elle, laisse le clic filer vers la carte :
    sans quoi elle rendrait injouable la bande de carte qu'elle recouvre."""
    pion = plateau.locator("img.pion:not(.fantome)").first
    survoler(plateau, pion)
    assert plateau.evaluate("""() => {
        const fiche = document.getElementById('fiche');
        const cadre = fiche.getBoundingClientRect();
        const vise = document.elementFromPoint(cadre.x + cadre.width / 2,
                                               cadre.y + cadre.height / 2);
        return vise === null || !fiche.contains(vise);
    }""")


def test_les_fantomes_sont_a_moitie_transparents(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    for fantome in fantomes(plateau):
        assert fantome["opacite"] == 0.5


def test_les_fantomes_reprennent_l_image_du_pion(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    source = pion.evaluate("p => p.src")
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    assert plateau.evaluate(
        "(src) => [...document.querySelectorAll('img.fantome')].every((f) => f.src === src)", source
    )


def test_chaque_fantome_est_centre_et_incline(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    for fantome in fantomes(plateau):
        x, y = centre_attendu(fantome["q"], fantome["r"])
        assert math.isclose(fantome["x"], x, abs_tol=1.0), fantome
        assert math.isclose(fantome["y"], y, abs_tol=1.0), fantome
        assert abs(fantome["angle"]) <= 5.0, fantome


def test_cliquer_un_pion_approche_montre_ses_deplacements(plateau):
    """Le clic vise le bon hexagone quelle que soit l'échelle."""
    pion, _, atteignables = pion_qui_peut_bouger(plateau)
    approcher(plateau, crans=2)
    pion.scroll_into_view_if_needed()

    poses = montrer_les_fantomes(plateau, pion)
    assert {(f["q"], f["r"], f["s"]) for f in poses} == {(h.q, h.r, h.s) for h in atteignables}


def test_cliquer_un_fantome_deplace_le_pion(plateau):
    pion, depart, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    cible = plateau.locator("img.fantome").last
    arrivee = cible.evaluate("f => [Number(f.dataset.q), Number(f.dataset.r), Number(f.dataset.s)]")
    cible.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    assert pion.evaluate(
        "p => [Number(p.dataset.q), Number(p.dataset.r), Number(p.dataset.s)]") == arrivee
    assert arrivee != [depart.q, depart.r, depart.s]

    pose = next(p for p in geometrie_des_pions(plateau) if [p["q"], p["r"], p["s"]] == arrivee)
    x, y = centre_attendu(*arrivee[:2])
    assert math.isclose(pose["x"], x, abs_tol=1.0) and math.isclose(pose["y"], y, abs_tol=1.0)
    assert abs(pose["angle"]) <= 5.0


def test_le_nombre_d_unites_ne_change_pas_apres_un_deplacement(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    plateau.locator("img.fantome").last.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    assert plateau.locator("img.pion:not(.fantome)").count() == len(app.SCENARIO)


def test_recliquer_le_pion_efface_les_fantomes(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")


def test_cliquer_ailleurs_efface_les_fantomes(plateau):
    """Un clic sur une case sans pion ni fantôme repose la sélection."""
    pion, depart, atteignables = pion_qui_peut_bouger(plateau)
    pion.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")

    occupes = set(plateau.evaluate(
        "() => [...document.querySelectorAll('img.pion:not(.fantome)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))
    interdits = {hexagone.cle for hexagone in atteignables} | {depart.cle} | occupes
    cliquer_l_hexagone(plateau, hexagone_decouvert(plateau, interdits))
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")


def point_de_l_hexagone(page, hexagone):
    """Le centre de l'hexagone en pixels d'écran, à l'échelle où la carte est rendue."""
    x, y = centre_attendu(hexagone.q, hexagone.r)
    return page.evaluate("""([x, y]) => {
        const carte = document.getElementById('carte');
        const cadre = carte.getBoundingClientRect();
        const echelle = cadre.width / carte.naturalWidth;
        return [cadre.x + x * echelle, cadre.y + y * echelle];
    }""", [x, y])


def cliquer_l_hexagone(page, hexagone):
    """Clique au centre de l'hexagone, en pixels d'écran."""
    page.mouse.click(*point_de_l_hexagone(page, hexagone))


def hexagone_decouvert(page, interdits):
    """Le premier hexagone hors `interdits` qu'un clic atteint vraiment.

    La barre d'outils est posée par-dessus le coin haut-gauche de la carte, et la fenêtre n'en
    montre qu'une partie une fois qu'on a approché : un clic qui tombe là n'arriverait jamais au
    plateau.
    """
    for cle in CARTE:
        if cle in interdits:
            continue
        hexagone = Hex.depuis_cle(cle)
        x, y = point_de_l_hexagone(page, hexagone)
        if page.evaluate("([x, y]) => document.getElementById('plateau')"
                         ".contains(document.elementFromPoint(x, y))", [x, y]):
            return hexagone
    raise AssertionError("aucun hexagone libre n'est cliquable")


# --- Phases de jeu et combat --------------------------------------------------------------------


def phase_lue(page):
    return page.locator("#phase-libelle").inner_text()


def passer_en_phase_de_combat(page):
    """Clique « Phase suivante » et attend la phase de combat des Nains (la magie est sautée)."""
    page.locator("#phase-suivante").click()
    page.wait_for_function(
        "document.getElementById('phase-libelle').textContent === 'Phase de combat — Nains'")


def test_le_libelle_annonce_la_phase(plateau):
    assert phase_lue(plateau) == "Phase de mouvement — Nains"


def test_phase_suivante_saute_la_magie(plateau):
    passer_en_phase_de_combat(plateau)
    assert phase_lue(plateau) == "Phase de combat — Nains"


def test_en_phase_de_combat_le_mouvement_ne_repond_plus(plateau):
    pion, _, _ = pion_qui_peut_bouger(plateau, lambda p: p.camp == "alliance")
    passer_en_phase_de_combat(plateau)
    pion.click()
    plateau.wait_for_timeout(150)
    assert plateau.locator("img.fantome").count() == 0


def test_cliquer_une_unite_adverse_la_surligne_en_rouge(plateau):
    passer_en_phase_de_combat(plateau)
    orque = Hex.depuis_cle(next(cle for cle, p in app.PLATEAU.pions.items()
                                if p.camp == "tenebres"))
    cliquer_l_hexagone(plateau, orque)
    plateau.wait_for_selector("img.pion.cible")
    assert plateau.locator("img.pion.cible").count() == 1


def couple_pour_le_combat(page):
    """Un Nain qui peut rejoindre le contact d'une Orque, la case de contact, et l'Orque."""
    contacts = {voisin.cle: orque
                for cle, p in app.PLATEAU.pions.items() if p.camp == "tenebres"
                for orque in [Hex.depuis_cle(cle)] for voisin in orque.voisins()}
    for pion, _, atteignables in pions_qui_peuvent_bouger(page, lambda p: p.camp == "alliance"):
        for arrivee in atteignables:
            if arrivee.cle in contacts:
                return pion, arrivee, contacts[arrivee.cle]
    pytest.skip("aucun Nain ne peut rejoindre le contact d'une Orque")


def test_le_cycle_de_combat_surligne_les_unites_puis_les_libere(plateau, monkeypatch):
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    nain, contact, orque = couple_pour_le_combat(plateau)

    nain.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    cliquer_l_hexagone(plateau, contact)
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    passer_en_phase_de_combat(plateau)

    cliquer_l_hexagone(plateau, orque)
    plateau.wait_for_selector("img.pion.cible")
    cliquer_l_hexagone(plateau, contact)
    plateau.wait_for_selector("img.pion.attaquant")
    plateau.wait_for_selector("#attaquer", state="visible")

    plateau.locator("#attaquer").click()
    plateau.wait_for_function(
        "!document.querySelector('img.pion.cible') && !document.querySelector('img.pion.attaquant')")
    plateau.wait_for_selector("#attaquer", state="hidden")


def test_les_unites_qui_ont_combattu_sont_grisees_et_refusent_le_clic(plateau, monkeypatch):
    """Une unité ne combat qu'une fois par phase : la carte le montre, et le clic le refuse.

    Le résultat du combat n'est pas connu d'avance — le dé est fixé, pas le couple d'unités que
    la mise en place offre —, on interroge donc le registre du serveur pour savoir qui doit être
    grisé, plutôt que de parier sur une issue.
    """
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    nain, contact, orque = couple_pour_le_combat(plateau)

    nain.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    cliquer_l_hexagone(plateau, contact)
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    passer_en_phase_de_combat(plateau)
    cliquer_l_hexagone(plateau, orque)
    plateau.wait_for_selector("img.pion.cible")
    cliquer_l_hexagone(plateau, contact)
    plateau.wait_for_selector("img.pion.attaquant")
    plateau.locator("#attaquer").click()
    plateau.wait_for_selector("#attaquer", state="hidden")

    # Ce que le serveur a inscrit, moins les cases que le combat a vidées : c'est ce qui se grise.
    engagees = {cle for cle in app.SUIVI.attaquants_engages | app.SUIVI.cibles_engagees
                if cle in app.PLATEAU.pions}
    assert engagees, "le combat n'a engagé personne"
    plateau.wait_for_function(
        "(n) => document.querySelectorAll('img.pion.indisponible').length === n",
        arg=len(engagees))
    grisees = set(plateau.evaluate(
        "() => [...document.querySelectorAll('img.pion.indisponible')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))
    assert grisees == engagees

    # Et le clic ne les reprend pas : rien ne se resurligne, ni en rouge ni en or.
    for cle in engagees:
        cliquer_l_hexagone(plateau, Hex.depuis_cle(cle))
    plateau.wait_for_timeout(200)
    assert plateau.locator("img.pion.cible").count() == 0
    assert plateau.locator("img.pion.attaquant").count() == 0


def test_la_phase_suivante_efface_le_grisage(plateau, monkeypatch):
    """Chaque phase de combat repart avec toutes ses unités : plus rien n'est grisé."""
    monkeypatch.setattr(app, "lancer_le_de", lambda: 1)
    nain, contact, orque = couple_pour_le_combat(plateau)

    nain.click()
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length > 0")
    cliquer_l_hexagone(plateau, contact)
    plateau.wait_for_function("document.querySelectorAll('img.fantome').length === 0")

    passer_en_phase_de_combat(plateau)
    cliquer_l_hexagone(plateau, orque)
    plateau.wait_for_selector("img.pion.cible")
    cliquer_l_hexagone(plateau, contact)
    plateau.wait_for_selector("img.pion.attaquant")
    plateau.locator("#attaquer").click()
    plateau.wait_for_selector("img.pion.indisponible")

    plateau.locator("#phase-suivante").click()  # mouvement des Orques
    plateau.wait_for_function("!document.querySelector('img.pion.indisponible')")


def test_annuler_retire_les_surlignages_de_combat(plateau):
    passer_en_phase_de_combat(plateau)
    orque = Hex.depuis_cle(next(cle for cle, p in app.PLATEAU.pions.items()
                                if p.camp == "tenebres"))
    cliquer_l_hexagone(plateau, orque)
    plateau.wait_for_selector("img.pion.cible")
    plateau.locator("#annuler-combat").click()
    plateau.wait_for_function("!document.querySelector('img.pion.cible')")
