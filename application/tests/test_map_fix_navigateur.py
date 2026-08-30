"""La page de correction dans le navigateur : survol, dialogue, zoom.

Ces tests demandent Chromium (`python3 -m playwright install chromium`). Comme ceux du client,
ils détournent le chemin du fichier de corrections : rien n'est écrit dans `game_box/`.
"""

import json

import pytest

import app
from moteur import hexagone as moteur_hexagone
from moteur.hexagone import CARTE_TRANSCRITE, Hex

from test_map_fix import corrections, relire  # noqa: F401  (fixture réutilisée)
from test_plateau import centre_attendu, cliquer_l_hexagone

# Un hexagone de plaine, loin des bords, et le terrain qu'on lui donnera.
PLAINE = Hex.depuis_cle("10,20,-30")
CORRECTION = "colline"


@pytest.fixture
def page_de_correction(page, serveur, corrections, monkeypatch):  # noqa: F811
    """Ouvre /admin/map_fix et attend que la carte soit chargée et mise à l'échelle.

    Le moteur est présenté comme démarré sans correction, pour partir d'une page cohérente : ni
    correction relevée, ni correction en vigueur.
    """
    monkeypatch.setattr(moteur_hexagone, "CORRECTIONS_APPLIQUEES", {})
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{serveur}/admin/map_fix")
    page.wait_for_function(
        "() => { const c = document.getElementById('carte');"
        " return c.complete && c.naturalWidth > 0; }")
    page.wait_for_function("document.getElementById('echelle').textContent !== '—'")
    return page


def survoler(page, hexagone):
    """Amène le pointeur au centre de l'hexagone."""
    x, y = centre_attendu(hexagone.q, hexagone.r)
    point = page.evaluate("""([x, y]) => {
        const carte = document.getElementById('carte');
        const cadre = carte.getBoundingClientRect();
        const echelle = cadre.width / carte.naturalWidth;
        return [cadre.x + x * echelle, cadre.y + y * echelle];
    }""", [x, y])
    page.mouse.move(point[0], point[1])


def test_la_carte_tient_dans_la_fenetre(page_de_correction):
    mesures = page_de_correction.evaluate("""() => {
        const carte = document.getElementById('carte');
        return { largeur: carte.getBoundingClientRect().width,
                 naturelle: carte.naturalWidth,
                 hauteur: carte.getBoundingClientRect().height };
    }""")
    assert mesures["largeur"] <= 1400 + 1
    assert mesures["hauteur"] <= 900 + 1
    assert mesures["largeur"] < mesures["naturelle"]


def test_le_survol_dit_le_terrain(page_de_correction):
    survoler(page_de_correction, PLAINE)
    infobulle = page_de_correction.locator("#infobulle")
    infobulle.wait_for(state="visible")
    assert infobulle.text_content() == f"{PLAINE.cle} — {CARTE_TRANSCRITE[PLAINE.cle][0]}"


def test_le_survol_surligne_l_hexagone(page_de_correction):
    survoler(page_de_correction, PLAINE)
    page_de_correction.wait_for_function("document.querySelectorAll('#surlignage .vise').length === 1")


def test_le_clic_ouvre_le_dialogue(page_de_correction):
    cliquer_l_hexagone(page_de_correction, PLAINE)
    page_de_correction.locator("#choix[open]").wait_for()
    assert page_de_correction.locator("#choix-titre").text_content() == f"Hexagone {PLAINE.cle}"
    assert CARTE_TRANSCRITE[PLAINE.cle][0] in page_de_correction.locator("#choix-etat").text_content()
    assert page_de_correction.locator("#choix-terrains button").count() == len(app.TERRAINS)


def test_choisir_un_terrain_enregistre_la_correction(page_de_correction, corrections):  # noqa: F811
    cliquer_l_hexagone(page_de_correction, PLAINE)
    page_de_correction.locator("#choix[open]").wait_for()
    page_de_correction.locator(f"#choix-terrains button:text-is('{CORRECTION}')").click()

    page_de_correction.wait_for_function(
        "document.getElementById('compteur').textContent === '1 correction'")
    assert relire(corrections) == {PLAINE.cle: CORRECTION}
    assert page_de_correction.locator("#surlignage .corrige").count() == 1


def test_retablir_efface_la_correction(page_de_correction, corrections):  # noqa: F811
    cliquer_l_hexagone(page_de_correction, PLAINE)
    page_de_correction.locator("#choix[open]").wait_for()
    page_de_correction.locator(f"#choix-terrains button:text-is('{CORRECTION}')").click()
    page_de_correction.wait_for_function(
        "document.getElementById('compteur').textContent === '1 correction'")

    cliquer_l_hexagone(page_de_correction, PLAINE)
    page_de_correction.locator("#choix[open]").wait_for()
    page_de_correction.locator("#choix-retablir").click()

    page_de_correction.wait_for_function(
        "document.getElementById('compteur').textContent === 'aucune correction'")
    assert relire(corrections) == {}


def test_la_correction_survit_au_rechargement(page_de_correction, corrections):  # noqa: F811
    corrections.write_text(json.dumps({PLAINE.cle: CORRECTION}), encoding="utf-8")
    page_de_correction.reload()
    page_de_correction.wait_for_function(
        "document.getElementById('compteur').textContent === '1 correction'")
    assert page_de_correction.locator("#surlignage .corrige").count() == 1


def test_les_boutons_de_zoom_changent_l_echelle(page_de_correction):
    echelle = page_de_correction.locator("#echelle")
    ajustee = echelle.text_content()
    page_de_correction.locator("#zoomer").click()
    page_de_correction.wait_for_function(
        "(depart) => document.getElementById('echelle').textContent !== depart", arg=ajustee)
    page_de_correction.locator("#ajuster").click()
    page_de_correction.wait_for_function(
        "(depart) => document.getElementById('echelle').textContent === depart", arg=ajustee)


def test_le_redemarrage_est_annonce_apres_une_correction(page_de_correction):
    """Le moteur ne relit map_fix.json qu'au démarrage : la page doit le dire."""
    redemarrage = page_de_correction.locator("#redemarrage")
    assert redemarrage.is_hidden()

    cliquer_l_hexagone(page_de_correction, PLAINE)
    page_de_correction.locator("#choix[open]").wait_for()
    page_de_correction.locator(f"#choix-terrains button:text-is('{CORRECTION}')").click()
    redemarrage.wait_for(state="visible")

    # Revenir au terrain transcrit remet la page d'accord avec le moteur.
    cliquer_l_hexagone(page_de_correction, PLAINE)
    page_de_correction.locator("#choix[open]").wait_for()
    page_de_correction.locator("#choix-retablir").click()
    redemarrage.wait_for(state="hidden")
