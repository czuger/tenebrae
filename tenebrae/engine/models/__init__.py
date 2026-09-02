"""The game entities, **one file per model**.

This directory holds everything that *is* the game and that must outlive a request: the saved
game, the player holding it, the seating table. Nothing of the web enters here - no Flask, no
session, no request: the engine ignores that an application serves it, and lets itself be played
from a plain interpreter.

The link with the *connected* player runs the other way: it is the application that holds a
connection entity (`tenebrae/application/models/connection.py`) and that designates the engine's
player by its Discord identifier. The engine never has to know about sessions or cookies.

This file re-exports nothing, and that is deliberate: `Seats` only needs the standard library,
while `Game` and `Player` require mongoengine. Re-exporting all three here would make anyone who
only wants a seating register pay for mongoengine - and so would the application mounted without
persistence, which is built today without it. Each caller therefore imports the module it needs:

    from tenebrae.engine.models.seats import Seats
    from tenebrae.engine.models.game import Game
    from tenebrae.engine.models.player import Player
"""
