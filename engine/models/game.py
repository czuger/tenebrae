"""The saved game: the only game state that changes while playing, and that must outlive the run.

What goes into the base is what the board, the turn, the combat register and the seating table
hold in memory - the positions, the phase, what the combat phase has already consumed, who sits at
which side. The reference data is not there: the map, the piece catalogue and the scenarios live
in files under `game_box/` and `scenarios/`, which are the repository's source of truth (see the
root `CLAUDE.md`). Copying them in would make two truths for one.

A placed unit has no identity of its own: the engine designates it by its **square**, one counter
standing for all the units it represents (`orques-01-15-infanteries` is placed fifteen times in
scenario no. 4). The document follows that rule - it invents no unit identifier.

The MongoDB field names stay as they were, pinned by `db_field`: renaming a stored field would
orphan the games already saved, and the `parties` collection is not renamed either.
"""

from mongoengine import (DateTimeField, Document, FloatField, IntField, ListField, MapField,
                         StringField)

from engine.phase import COMBAT, MOVEMENT


class Game(Document):
    """A saved game: enough to reopen the board where it was left.

    `placement` is the engine's format, "q,r,s" -> piece key - that of `Board.to_dict()` and of
    `Scenario.placement`. The keys of a `MapField` become Mongo document keys, which forbid a
    leading dot or dollar; cube coordinates use only digits, commas and the minus sign, so they
    pass as they are.

    Eliminated pieces simply disappear from the placement: the engine keeps no graveyard.
    """

    scenario = IntField(required=True)
    placement = MapField(StringField(), required=True)

    # The angle each counter lies at, "q,r,s" -> degrees (see `engine/board.py`). It is not a
    # rule, it is appearance - but an appearance that must hold: without it in base, the piece
    # would lie down differently at every page reload. Same keys as `placement`, and the field is
    # not required: games saved before we started keeping them have none, and their pieces lie
    # down once when the game resumes.
    tilts = MapField(FloatField(), db_field="inclinaisons")

    # The current phase. The (side, type) pair is enough to put the turn back in its sequence;
    # magic does not appear, the server always steps over it.
    active_side = StringField(required=True, db_field="camp_actif")
    phase_type = StringField(required=True, choices=(MOVEMENT, COMBAT), db_field="type_de_phase")
    turn_number = IntField(required=True, min_value=1, db_field="numero_de_tour")

    # What the current combat phase has consumed: squares, not pieces. Emptied as soon as the
    # phase changes.
    engaged_attackers = ListField(StringField(), db_field="attaquants_engages")
    engaged_targets = ListField(StringField(), db_field="cibles_engagees")

    # Who holds which side: "alliance" or "tenebres" -> Discord identifier. A free side has no
    # key. It is an identifier and not a `ReferenceField` to `Player` because the repositories
    # only exchange state dicts: a reference would force a document out of `engine/repositories/`,
    # or make a DBRef travel around. The game thus stays readable on its own.
    #
    # The field is not required: games saved before players existed have none, and they must stay
    # resumable - the table is then simply empty.
    seats = MapField(StringField(), db_field="places")

    created_at = DateTimeField(required=True, db_field="creee_le")
    updated_at = DateTimeField(required=True, db_field="modifiee_le")

    # `ordering` makes the most recent game the first one found: that is the one the server
    # resumes when "/" is loaded. The identifier breaks ties: two games opened in the same clock
    # tick carry the same date, and the order would otherwise be undecided - a "restart" followed
    # by a reload could resume the abandoned game. ObjectIds grow with time, so the greatest is
    # the most recent.
    meta = {"collection": "parties", "indexes": ["-updated_at"],
            "ordering": ["-updated_at", "-id"]}

    def __repr__(self):
        return (f"Game(scenario {self.scenario}, turn {self.turn_number}, "
                f"{len(self.placement)} pieces placed)")
