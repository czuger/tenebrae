"""The register of units removed from play: what it keeps, and the two totals it can give."""

from tenebrae.engine.casualties import Casualties
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import piece

DWARF = "nains-01-5-infanteries"     # alliance, strength 12
ORC = "orques-01-15-infanteries"     # darkness, strength 8
MARKER = "marqueurs-03-paralysie"    # neutral, no strength printed

SQUARE = Hex(1, 26, -27)
ELSEWHERE = Hex(2, 26, -28)


def test_it_opens_empty():
    assert len(Casualties()) == 0
    assert Casualties().losses == []


def test_an_entry_says_the_piece_the_square_and_both_sides():
    casualties = Casualties()
    entry = casualties.record(SQUARE, piece(DWARF), "tenebres")

    assert entry == {"square": SQUARE.key, "piece": DWARF,
                     "side": "alliance", "taken_by": "tenebres"}
    assert casualties.losses == [entry]


def test_a_unit_nobody_claims_is_recorded_all_the_same():
    """A neutral piece has no opponent: it falls without anyone to count it."""
    casualties = Casualties()
    assert casualties.record(SQUARE, piece(MARKER), None)["taken_by"] == ""


def test_the_fallen_are_sorted_by_the_side_that_lost_them_and_by_the_taker():
    casualties = Casualties()
    casualties.record(SQUARE, piece(DWARF), "tenebres")
    casualties.record(ELSEWHERE, piece(ORC), "alliance")

    assert [loss["piece"] for loss in casualties.lost_by("alliance")] == [DWARF]
    assert [loss["piece"] for loss in casualties.taken_by("tenebres")] == [DWARF]
    assert [loss["piece"] for loss in casualties.lost_by("tenebres")] == [ORC]


def test_the_totals_count_the_counters_strengths():
    """"Eliminated units are kept by the player who eliminated them, to establish their total of
    points at the end of the game" - and the same entries say what each side left on the field."""
    casualties = Casualties()
    casualties.record(SQUARE, piece(DWARF), "tenebres")
    casualties.record(ELSEWHERE, piece(DWARF), "tenebres")

    assert casualties.points_taken_by("tenebres") == 24
    assert casualties.points_lost_by("alliance") == 24
    assert casualties.points_taken_by("alliance") == 0


def test_a_counter_with_no_legible_strength_counts_nothing():
    casualties = Casualties()
    casualties.record(SQUARE, piece(MARKER), "alliance")
    assert casualties.points_taken_by("alliance") == 0


def test_two_units_of_the_same_counter_make_two_entries():
    """One counter stands for all the units it represents: the register counts them, not it."""
    casualties = Casualties()
    casualties.record(SQUARE, piece(ORC), "alliance")
    casualties.record(SQUARE, piece(ORC), "alliance")
    assert len(casualties) == 2
    assert casualties.points_taken_by("alliance") == 16


def test_it_is_serialised_and_read_back_as_it_was():
    casualties = Casualties()
    casualties.record(SQUARE, piece(DWARF), "tenebres")
    saved = casualties.to_dict()

    resumed = Casualties()
    resumed.restore(saved["casualties"])
    assert resumed.losses == casualties.losses


def test_a_game_saved_before_the_register_existed_reads_as_empty():
    casualties = Casualties()
    casualties.record(SQUARE, piece(DWARF), "tenebres")
    casualties.restore(None)
    assert len(casualties) == 0


def test_an_entry_missing_a_field_is_read_with_it_empty():
    casualties = Casualties()
    casualties.restore([{"square": SQUARE.key, "piece": DWARF}])
    assert casualties.losses == [{"square": SQUARE.key, "piece": DWARF,
                                  "side": "", "taken_by": ""}]


def test_a_new_game_starts_with_nobody_fallen():
    casualties = Casualties()
    casualties.record(SQUARE, piece(DWARF), "tenebres")
    casualties.reset()
    assert len(casualties) == 0
