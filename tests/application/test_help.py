"""The help page: what it says to the player, and whom it credits.

`/aide` is a public page of text. What a test can hold of it is that it is served, that it carries
the sections a player is sent to, that the two other pages lead to it, and above all that the
credits are **true**: every game-icons.net contributor whose drawing a counter wears is named, with
a drawing of theirs that lies where the page fetches it, and none is named that the counters do
not use.
"""

import json
import re

from tenebrae.application.routes.help import CORRESPONDENCES, ICON_AUTHORS, icon_credits
from tests.application.test_pawn_icons import ICONS
from tests.application.test_server import the_board

SECTIONS = ("start", "board", "turn", "movement", "combat", "end", "keys", "not-played", "credits")
SHORTCUTS = "AZEQSD"


def the_help(client):
    """The page as an anonymous visitor receives it: the help asks for no account."""
    answer = client.get("/aide")
    assert answer.status_code == 200
    return answer.get_data(as_text=True)


def authors_used():
    """The contributors the counters wear drawings of, read from the file the browser reads."""
    rows = json.loads(CORRESPONDENCES.read_text(encoding="utf-8"))
    return {icon.split("/", 1)[0] for _, icon in rows if icon}


def credited(page):
    """The contributors the page names, by the directory slug each row carries."""
    return set(re.findall(r'data-author="([^"]+)"', page))


# --- The page ---


def test_the_help_is_public_and_in_french(anonymous_client):
    page = the_help(anonymous_client)
    assert "<title>Ave Tenebrae — aide</title>" in page
    assert 'lang="fr"' in page


def test_the_help_carries_every_section_its_summary_points_to(anonymous_client):
    page = the_help(anonymous_client)
    for section in SECTIONS:
        assert f'<section id="{section}">' in page, section
        assert f'href="#{section}"' in page, section


def test_the_help_explains_the_three_choices_of_a_new_game(anonymous_client):
    page = the_help(anonymous_client)
    for field in ("Scénario", "Votre camp", "Jouer contre l'IA", "Commencer"):
        assert field in page, field


def test_the_help_names_the_six_keys(anonymous_client):
    page = the_help(anonymous_client)
    assert sorted(re.findall(r"<kbd>(\w)</kbd>", page)) == sorted(SHORTCUTS)


def test_the_help_shows_the_example_counter_in_both_faces(anonymous_client):
    page = the_help(anonymous_client)
    photograph, = re.findall(r'src="/pieces/([^"]+)"', page)
    assert anonymous_client.get(f"/pieces/{photograph}").status_code == 200
    icons = re.findall(r'src="/static/icons/000000/ffffff/1x1/([^"]+)\.svg"', page)
    assert icons, "no icon on the page"
    for icon in icons:
        assert (ICONS / f"{icon}.svg").is_file(), icon


# --- The credits ---


def test_the_author_of_the_game_and_the_blog_are_thanked(anonymous_client):
    page = the_help(anonymous_client)
    assert "François Marcela-Froideval" in page
    assert "irlboardgames.blogspot.com/2017/07/vintageboard-1-ave-tenebrae.html" in page
    assert "https://game-icons.net/" in page


def test_every_contributor_the_counters_use_is_credited(anonymous_client):
    """A counter given a new drawing credits its author the moment the file is saved."""
    assert credited(the_help(anonymous_client)) == authors_used()


def test_every_contributor_used_has_a_name_and_a_link_written_by_hand():
    """`ICON_AUTHORS` is the one thing the page cannot read from the set: a contributor used and
    not named there would be credited under a directory name."""
    assert authors_used() - set(ICON_AUTHORS) == set()


def test_the_credits_name_each_contributor_as_they_sign(anonymous_client):
    page = the_help(anonymous_client)
    for slug in authors_used():
        name, url = ICON_AUTHORS[slug]
        assert name in page, slug
        if url:
            assert f'href="{url}"' in page, slug


def test_the_most_used_contributors_come_first():
    credits = icon_credits({"a.jpg": "lorc/ace", "b.jpg": "lorc/acorn", "c.jpg": "skoll/bat",
                            "d.jpg": "delapouite/rat", "e.jpg": "delapouite/fog"})
    assert [entry["slug"] for entry in credits] == ["delapouite", "lorc", "skoll"]
    assert [entry["drawings"] for entry in credits] == [2, 2, 1]
    assert credits[0]["example"] == "delapouite/rat"


def test_a_contributor_the_hand_has_not_named_is_still_credited():
    entry, = icon_credits({"a.jpg": "someone-new/drawing"})
    assert entry["name"] == "someone-new" and entry["url"] is None


# --- The ways to it ---


def test_the_list_of_games_leads_to_the_help(anonymous_client):
    page = anonymous_client.get("/").get_data(as_text=True)
    assert 'id="help-link"' in page and 'href="/aide"' in page


def test_the_board_leads_to_the_help_from_the_table_dialog(client):
    page = the_board(client).get_data(as_text=True)
    assert 'id="table-help"' in page
