"""Database access for the game entities: one repository per subject, beside the models it writes.

A repository exchanges **state dicts**, never a MongoEngine Document. That is what keeps Mongo out
of the routes: `application/app.py` imports neither `engine.models` nor `mongoengine`, it calls
`load`, `save` and `new_game`, and that is all.

Each subject has two: the real one, on MongoDB, and its base-less counterpart that the test
configuration plugs in. Both keep the same promise of `PERSISTENCE=none` - nothing outlives the
server - but not in the same way, and the nuance is explained in each module.

As in `engine/models/`, this file re-exports nothing: `application/app.py` imports a branch only
when its configuration asks for it, and an application mounted without persistence must not load
mongoengine for all that.

    from engine.repositories.game import MongoGameRepository, NullGameRepository
    from engine.repositories.player import MongoPlayerRepository, InMemoryPlayerRepository
"""
