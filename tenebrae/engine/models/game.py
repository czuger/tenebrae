"""The saved game: the only game state that changes while playing, and that must outlive the run.

What goes into the base is what the board, the turn, the combat register and the seating table hold
in memory - the positions, the phase, what the combat phase has already consumed, who sits at which
side. The reference data is not there: the map, the piece catalogue and the scenarios live in files
under `tenebrae/game_box/` and `tenebrae/scenarios/`, which are the repository's source of truth
(see the root `CLAUDE.md`). Copying them in would make two truths for one.

A placed unit has no identity of its own: the engine designates it by its **square**, one counter
standing for all the units it represents (`orques-01-15-infanteries` is placed fifteen times in
scenario no. 4). The document follows that rule - it invents no unit identifier.

The MongoDB field names stay as they were, pinned by `db_field`: renaming a stored field would
orphan the games already saved, and the `parties` collection is not renamed either.
"""

from mongoengine import (DateTimeField, Document, FloatField, IntField, ListField, MapField,
                         StringField)

from tenebrae.engine.phase import COMBAT, MOVEMENT


class Game(Document):
    """A saved game: enough to reopen the board where it was left.

    `placement` is the engine's format, "q,r,s" -> piece key - that of `Board.to_dict()` and of
    `Scenario.placement`. Cube coordinates use only digits, commas and the minus sign, so they pass
    as Mongo document keys. Eliminated pieces simply disappear from the placement: the engine keeps
    no graveyard.
    """

    scenario = IntField(required=True)
    placement = MapField(StringField(), required=True)

    # Same keys as `placement`. Not required: games saved before tilts were kept have none, and
    # their pieces lie down once when the game resumes.
    tilts = MapField(FloatField(), db_field="inclinaisons")

    # The (side, type) pair is enough to put the turn back in its sequence; magic never appears.
    active_side = StringField(required=True, db_field="camp_actif")
    phase_type = StringField(required=True, choices=(MOVEMENT, COMBAT), db_field="type_de_phase")
    turn_number = IntField(required=True, min_value=1, db_field="numero_de_tour")

    # What the current combat phase has consumed: squares, not pieces.
    engaged_attackers = ListField(StringField(), db_field="attaquants_engages")
    engaged_targets = ListField(StringField(), db_field="cibles_engagees")

    # Side -> Discord identifier; a free side has no key. An identifier rather than a
    # `ReferenceField`: the repositories exchange state dicts, and the game stays readable on its
    # own. Not required: games saved before players existed must stay resumable.
    seats = MapField(StringField(), db_field="places")

    created_at = DateTimeField(required=True, db_field="creee_le")
    updated_at = DateTimeField(required=True, db_field="modifiee_le")

    # Most recent first, the identifier breaking ties between two games saved in the same clock
    # tick: ObjectIds grow with time.
    meta = {"collection": "parties", "indexes": ["-updated_at"],
            "ordering": ["-updated_at", "-id"]}

    def __repr__(self) -> str:
        """The scenario, the turn and the number of pieces placed."""
        return (f"Game(scenario {self.scenario}, turn {self.turn_number}, "
                f"{len(self.placement)} pieces placed)")
