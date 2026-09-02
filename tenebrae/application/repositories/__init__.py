"""Database access for the application's entities: one repository per subject, beside the model it
writes.

The counterpart of `tenebrae/engine/repositories/`, for what is not the game. Same rules, and for
the same reasons: a repository exchanges **dicts**, never a MongoEngine Document, and each subject
has two
- the real one, on MongoDB, and its base-less counterpart that the test configuration plugs in.
That is what keeps Mongo out of the routes.

As everywhere else in the project, this file re-exports nothing: an application mounted without
persistence must not load mongoengine for all that.

    from tenebrae.application.repositories.view import MongoViewRepository, InMemoryViewRepository
"""
