"""Database access for the game entities: one repository per subject, beside the models it writes.

A repository exchanges **state dicts**, never a MongoEngine Document. That is what keeps Mongo out
of the routes: the application (`tenebrae/application/persistence.py`) imports neither
`tenebrae.engine.models` nor `mongoengine`, it calls `load`, `save` and `new_game`, and that is all.

Each subject has two: the real one, on MongoDB, and its base-less counterpart that the test
configuration plugs in. Both keep the same promise of `PERSISTENCE=none` - nothing outlives the
server - but not in the same way, and the nuance is explained in each module.

As in `tenebrae/engine/models/`, this file re-exports nothing. Neither module loads mongoengine at
import - the Mongo repositories import their document lazily -, so
`tenebrae/application/persistence.py` imports both and an application mounted without persistence
still builds without mongoengine.

    from tenebrae.engine.repositories.game import MongoGameRepository, NullGameRepository
    from tenebrae.engine.repositories.player import MongoPlayerRepository, InMemoryPlayerRepository
"""
