"""Database access for the application's entities: one repository per subject, beside the model it
writes.

The counterpart of `tenebrae/engine/repositories/`, for what is not the game. Same rule, and for
the same reason: a repository exchanges **dicts**, never a MongoEngine Document. That is what keeps
Mongo out of the routes.

As everywhere else in the project, this file re-exports nothing:

    from tenebrae.application.repositories.view import MongoViewRepository
"""
