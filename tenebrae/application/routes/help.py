"""The help page: what a player needs to know to sit down and play, and who is owed thanks.

`/aide` is a page for the player and nothing else: how a game is opened and joined, what the board
shows, how a turn goes, how one moves and fights, and what the game does not play yet. Nothing of
the server appears on it. It is **public**, like the list and the board: a visitor reads it before
having an account.

It closes on the credits - the author of the game, the blog whose photographs the counters come
from, and the game-icons.net contributors whose drawings the counters wear. That last list is not
written by hand: it is **read from `static/pawn_icons.json`**, so that a counter given a new drawing
credits its author the moment the file is saved. What the hand keeps is `ICON_AUTHORS`, the name a
contributor signs with and where they publish, and a test holds that every contributor the file
uses has a row there.
"""

import json
from collections import Counter
from typing import Optional

from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue

from tenebrae.application.config import ROOT
from tenebrae.application.pieces import PIECE_CATALOGUE, PieceEntry

blueprint = Blueprint("help", __name__)

CORRESPONDENCES = ROOT / "tenebrae" / "application" / "static" / "pawn_icons.json"

# The game-icons.net contributors, by the directory the set files their drawings under: the name
# they sign with, and where they publish (`None` where the set names no site). Taken from the set's
# own `license.txt` and from https://game-icons.net/about.html#authors.
ICON_AUTHORS: dict[str, tuple[str, Optional[str]]] = {
    "lorc": ("Lorc", "https://lorcblog.blogspot.com"),
    "delapouite": ("Delapouite", "https://delapouite.com"),
    "skoll": ("Skoll", None),
    "heavenly-dog": ("HeavenlyDog", "http://www.gnomosygoblins.blogspot.com"),
    "caro-asercion": ("Caro Asercion", None),
    "carl-olsen": ("Carl Olsen", "https://twitter.com/unstoppableCarl"),
    "cathelineau": ("Cathelineau", None),
    "kier-heyl": ("Kier Heyl", None),
    "darkzaitzev": ("DarkZaitzev", "http://darkzaitzev.deviantart.com"),
    "faithtoken": ("Faithtoken", "http://www.faithtoken.com"),
    "sbed": ("sbed", "http://opengameart.org/content/95-game-icons"),
}

# The counter the page shows in both faces: the dwarves' infantry, the first unit of the scenario
# the game opened on for a long time.
EXAMPLE_COUNTER = "nains-01-5-infanteries.jpg"


@blueprint.route("/aide")
def help_page() -> ResponseReturnValue:
    """Serves the player's help page.

    Returns:
        The rendered `help.html`.
    """
    icons = drawn_icons()
    return render_template("help.html", credits=icon_credits(icons), example=example_counter(icons))


def drawn_icons() -> dict[str, str]:
    """Reads which counter wears which drawing, as the browser reads it.

    Returns:
        Photograph -> icon path under the set (`"lorc/barbute"`), the counters with no drawing
        left out.
    """
    rows = json.loads(CORRESPONDENCES.read_text(encoding="utf-8"))
    return {photograph: icon for photograph, icon in rows if icon}


def icon_credits(icons: dict[str, str]) -> list[dict[str, object]]:
    """Lists the contributors whose drawings the counters wear, the most used first.

    Args:
        icons: Photograph -> icon path, from `drawn_icons`.

    Returns:
        One entry per contributor: `slug`, `name`, `url`, how many `drawings` of theirs are used,
        and one `example` icon path to show beside the name. A contributor `ICON_AUTHORS` does not
        name is credited under their directory name, with no link.
    """
    drawings = Counter(author_of(icon) for icon in icons.values())
    examples: dict[str, str] = {}
    for icon in icons.values():
        examples.setdefault(author_of(icon), icon)
    return [{"slug": slug, "name": ICON_AUTHORS.get(slug, (slug, None))[0],
             "url": ICON_AUTHORS.get(slug, (slug, None))[1],
             "drawings": count, "example": examples[slug]}
            for slug, count in sorted(drawings.items(), key=lambda item: (-item[1], item[0]))]


def author_of(icon: str) -> str:
    """The directory an icon is filed under, which is its contributor's.

    Args:
        icon: The icon path under the set, `"lorc/barbute"`.

    Returns:
        `"lorc"`.
    """
    return icon.split("/", 1)[0]


def example_counter(icons: dict[str, str]) -> dict[str, object]:
    """The counter shown in both faces at the top of the section on the pawns.

    Args:
        icons: Photograph -> icon path, from `drawn_icons`.

    Returns:
        `name`, the `photograph` path for `/pieces/`, and the `icon` path under the set.
    """
    piece: PieceEntry = next(entry for entry in PIECE_CATALOGUE
                             if str(entry["path"]).endswith(EXAMPLE_COUNTER))
    return {"name": piece["name"], "photograph": piece["path"],
            "icon": icons.get(EXAMPLE_COUNTER, "")}
