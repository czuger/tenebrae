"""The routes, one module per subject, each on a blueprint of its own.

Every module that serves URLs defines a `blueprint`, which `create_app` registers
(`tenebrae/application/app.py`); the endpoint names carry the blueprint's -
`url_for("home.games")`, `url_for("game.board", identifier=...)`, `url_for("images.map_image")`.
Two modules serve no URL and are what the routes share: `authorization.py`, the guards that turn
the anonymous, the unseated or the out-of-turn away, and `reading.py`, the request's parameters
read into engine objects.

Nothing is re-exported: each caller imports the module it needs.

    from tenebrae.application.routes import combat
    application.register_blueprint(combat.blueprint)
"""
