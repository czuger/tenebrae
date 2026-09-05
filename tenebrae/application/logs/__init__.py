"""The logs: three of them, three files, and the sentences the game log carries.

- `battle_log.py` configures the game log once, at import, and serves its last lines to the page;
- `rotating_log.py` opens a log file that rotates - the standard handler, on a directory it makes -
  and `in_memory_log.py` is the bounded queue the browser's column shows;
- `movement_log.py` gives the engine's movement trace a file of its own, away from the game log;
- `general_log.py` is everything that is neither a combat nor a movement - the server's own trace,
  at DEBUG, in `general.log` - and `request_trace.py` writes every request and its answer there;
- `combat_sentences.py` composes the French lines a combat writes.

This file re-exports nothing, like every `__init__.py` of the project:

    from tenebrae.application.logs.battle_log import LOG, log_lines
    from tenebrae.application.logs.general_log import event, note
"""
