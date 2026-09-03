"""The guards on the routes: logged in, seated, holding the side whose phase it is, administrator.

The map stays public, but everything that changes the state requires being logged in and holding
the side whose phase it is: that is what `login_required`, `seat_required` and
`active_side_required` set out. `administrator_required` reserves the map-fixing page to the
accounts in `ADMIN_DISCORD_IDS`. Each refusal is a French message, with the status the browser
reads: 401 for the anonymous, 403 for everyone else.
"""

from collections.abc import Callable
from functools import wraps

from flask.typing import ResponseReturnValue

from tenebrae.application.current_game import SEATS, TURN
from tenebrae.application.players import current_player, is_administrator, logged_in_player

# A Flask view, as the guards wrap it.
RouteFunction = Callable[..., ResponseReturnValue]


def login_required(view: RouteFunction) -> RouteFunction:
    """Refuses the route to anyone who has not opened a session.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 401 to anonymous visitors.
    """
    @wraps(view)
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 401, or lets the route through."""
        if current_player() is None:
            return {"allowed": False, "message": "Connectez-vous pour jouer."}, 401
        return view(*args, **kwargs)
    return wrapper


def seat_required(view: RouteFunction) -> RouteFunction:
    """Refuses the route to anyone holding no side.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 403 to spectators.
    """
    @wraps(view)
    @login_required
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 403 to a spectator, or lets the route through."""
        if not SEATS.sides_of(logged_in_player()["discord_id"]):
            return {"allowed": False, "message": "Prenez place à un camp pour jouer."}, 403
        return view(*args, **kwargs)
    return wrapper


def active_side_required(view: RouteFunction) -> RouteFunction:
    """Refuses the route to anyone not holding the side whose phase it is.

    The decorator looks only at the **seat**. The phase type and the side of the piece aimed at
    are still checked in the routes: a move outside the movement phase goes on returning 200 and
    `allowed: false`.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 403 when it is not the requester's turn.
    """
    @wraps(view)
    @login_required
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 403 out of turn, or lets the route through."""
        if not SEATS.holds(logged_in_player()["discord_id"], TURN.active_side):
            return {"allowed": False,
                    "message": f"C'est au camp {TURN.active_army} de jouer."}, 403
        return view(*args, **kwargs)
    return wrapper


def administrator_required(view: RouteFunction) -> RouteFunction:
    """Reserves the route to the accounts declared in `ADMIN_DISCORD_IDS`.

    An empty list admits nobody, and the refusal says how to declare oneself in it.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 403 to everyone else.
    """
    @wraps(view)
    @login_required
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 403 to a non-administrator, or lets the route through."""
        if not is_administrator(current_player()):
            return {"allowed": False,
                    "message": "Corriger la carte demande un compte déclaré dans "
                               "ADMIN_DISCORD_IDS."}, 403
        return view(*args, **kwargs)
    return wrapper
