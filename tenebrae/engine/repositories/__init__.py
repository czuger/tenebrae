"""Database access for the game entities: one repository per subject, beside the model it writes.

A repository exchanges **state dicts**, never a MongoEngine Document. That is what keeps Mongo out
of the routes: they call `load`, `save` and `new_game` through
`tenebrae/application/persistence.py`, and never see a document. The tests go through the same
repositories, on the base `make test` brings up.

As in `tenebrae/engine/models/`, this file re-exports nothing:

    from tenebrae.engine.repositories.game import MongoGameRepository
    from tenebrae.engine.repositories.player import MongoPlayerRepository
"""
