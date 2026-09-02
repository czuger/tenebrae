"""The phase state machine: the order, magic skipped, the turn count."""

import pytest

from tenebrae.engine.phase import COMBAT, MOVEMENT, Turn

SIDES = ("alliance", "tenebres")
NAMES = {"alliance": "Nains", "tenebres": "Orques"}


@pytest.fixture
def turn():
    return Turn(SIDES, NAMES)


class TestPhaseOrder:
    def test_the_turn_begins_with_the_first_players_movement_and_magic_is_skipped(self, turn):
        """Movement then combat, each side in turn, and never the magic phase the booklet has."""
        assert turn.number == 1
        seen = [(turn.active_side, turn.phase_type)]
        for _ in range(5):
            turn.advance()
            seen.append((turn.active_side, turn.phase_type))
        assert seen == [
            ("alliance", MOVEMENT),
            ("alliance", COMBAT),
            ("tenebres", MOVEMENT),
            ("tenebres", COMBAT),
            ("alliance", MOVEMENT),
            ("alliance", COMBAT),
        ]

    def test_a_full_turn_increments_the_number(self, turn):
        turn.advance()  # alliance combat
        turn.advance()  # darkness movement
        turn.advance()  # darkness combat
        assert turn.number == 1
        turn.advance()  # back to alliance movement
        assert turn.number == 2
        assert (turn.active_side, turn.phase_type) == ("alliance", MOVEMENT)


class TestLabel:
    def test_the_label_names_the_phase_and_the_army(self, turn):
        assert turn.label == "Phase de mouvement — Nains"
        turn.advance()
        assert turn.label == "Phase de combat — Nains"
        turn.advance()
        assert turn.label == "Phase de mouvement — Orques"

    def test_failing_a_name_the_side_will_do(self):
        assert Turn(SIDES).label == "Phase de mouvement — alliance"


class TestPermissions:
    def test_each_phase_opens_to_the_active_side_and_to_nothing_else(self, turn):
        """Movement, then combat: the side whose phase it is, and only what that phase allows."""
        assert turn.allows_movement("alliance")
        assert not turn.allows_movement("tenebres")
        assert not turn.allows_combat("alliance")

        turn.advance()
        assert turn.allows_combat("alliance")
        assert not turn.allows_combat("tenebres")
        assert not turn.allows_movement("alliance")


def test_to_dict_carries_the_essentials(turn):
    assert Turn(SIDES, NAMES).to_dict() == {
        "side": "alliance", "type": MOVEMENT, "army": "Nains",
        "label": "Phase de mouvement — Nains", "number": 1,
    }


class TestRestore:
    def test_restore_returns_to_the_saved_phase(self, turn):
        """In place, so that the module global the server holds is the one that moves."""
        assert turn.restore("tenebres", COMBAT, 7) is turn
        assert (turn.active_side, turn.phase_type, turn.number) == ("tenebres", COMBAT, 7)

    def test_the_round_trip_through_to_dict_lands_on_the_same_phase(self, turn):
        for _ in range(3):
            turn.advance()
        saved = turn.to_dict()
        resumed = Turn(SIDES, NAMES).restore(saved["side"], saved["type"], saved["number"])
        assert resumed.to_dict() == saved

    def test_a_phase_the_game_does_not_have_is_refused(self, turn):
        """Magic, which is never played, and a side that is not at the table."""
        with pytest.raises(ValueError):
            turn.restore("alliance", "magie", 1)
        with pytest.raises(ValueError):
            turn.restore("empire", MOVEMENT, 1)

    def test_the_resumed_game_carries_on_normally(self, turn):
        turn.restore("tenebres", COMBAT, 3)
        turn.advance()
        assert (turn.active_side, turn.phase_type, turn.number) == ("alliance", MOVEMENT, 4)
