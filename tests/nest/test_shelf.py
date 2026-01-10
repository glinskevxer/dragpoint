"""Shelf nesting."""

from __future__ import annotations

import pytest

from dragpoint.nest.shelf import nest_job, nest_pieces
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.load import load_job
from dragpoint.spec.plate import PlateSpec

from ..compiler.conftest import EXAMPLE


def sheet(**overrides: float) -> Sheet:
    values: dict[str, object] = {
        "stock": "LAM16-BW",
        "width": 300.0,
        "height": 200.0,
        "margin": 5.0,
        "kerf": 1.5,
    }
    values.update(overrides)
    return Sheet(**values)  # type: ignore[arg-type]


def test_one_piece_goes_in_the_corner() -> None:
    result = nest_pieces([("A", 60.0, 20.0)], sheet())
    assert len(result) == 1
    assert result.placements[0].origin.x == 5.0
    assert result.placements[0].origin.y == 5.0


def test_pieces_fill_a_row_before_starting_another() -> None:
    result = nest_pieces([("A", 60.0, 20.0)] * 4, sheet())
    assert result.rows() == 1
    assert result.placed == 4


def test_a_row_that_is_full_starts_a_new_one() -> None:
    result = nest_pieces([("A", 100.0, 20.0)] * 4, sheet())
    assert result.rows() == 2
    assert result.placed == 4


def test_the_kerf_sits_between_pieces_in_a_row() -> None:
    result = nest_pieces([("A", 60.0, 20.0)] * 2, sheet(kerf=2.0))
    first, second = result.placements
    assert second.origin.x - (first.origin.x + first.width) == pytest.approx(2.0)


def test_the_kerf_sits_between_rows_as_well() -> None:
    result = nest_pieces([("A", 100.0, 20.0)] * 4, sheet(kerf=2.0))
    bottoms = sorted({item.origin.y for item in result.placements})
    assert bottoms[1] - bottoms[0] == pytest.approx(22.0)


def test_nothing_is_placed_on_the_clamp_margin() -> None:
    result = nest_pieces([("A", 60.0, 20.0)] * 20, sheet(margin=8.0))
    for item in result.placements:
        box = item.bounds()
        assert box.min_x >= 8.0 - 1e-9
        assert box.min_y >= 8.0 - 1e-9
        assert box.max_x <= 292.0 + 1e-9
        assert box.max_y <= 192.0 + 1e-9


def test_the_tallest_pieces_go_down_first() -> None:
    result = nest_pieces([("short", 40.0, 10.0), ("tall", 40.0, 60.0)], sheet())
    assert result.placements[0].plate == "tall"


def test_a_piece_may_be_turned_to_fit() -> None:
    result = nest_pieces([("A", 250.0, 20.0)], sheet(width=100.0, height=400.0))
    assert result.placed == 1
    assert result.placements[0].rotated


def test_rotation_can_be_forbidden() -> None:
    result = nest_pieces(
        [("A", 250.0, 20.0)], sheet(width=100.0, height=400.0), allow_rotation=False
    )
    assert result.placed == 0
    assert result.left_over == (("A", 1),)


def test_a_square_piece_is_never_reported_as_turned() -> None:
    result = nest_pieces([("A", 20.0, 20.0)], sheet())
    assert not result.placements[0].rotated


def test_a_piece_too_big_for_the_sheet_is_left_over() -> None:
    result = nest_pieces([("A", 500.0, 500.0)], sheet())
    assert result.placed == 0
    assert not result.complete
    assert result.missed == 1
    assert result.left_over == (("A", 1),)


def test_the_pieces_that_do_fit_still_go_on() -> None:
    result = nest_pieces([("big", 500.0, 500.0), ("small", 20.0, 20.0)], sheet())
    assert result.placed == 1
    assert result.placements[0].plate == "small"
    assert result.left_over == (("big", 1),)


def test_pieces_are_numbered_from_one_within_a_plate() -> None:
    result = nest_pieces([("A", 20.0, 20.0), ("A", 20.0, 20.0), ("B", 20.0, 20.0)], sheet())
    numbers = sorted(item.piece for item in result.for_plate("A"))
    assert numbers == [1, 2]
    assert [item.piece for item in result.for_plate("B")] == [1]


def test_no_two_pieces_overlap() -> None:
    result = nest_pieces([("A", 37.0, 23.0)] * 24, sheet())
    boxes = [item.bounds() for item in result.placements]
    for index, left in enumerate(boxes):
        for right in boxes[index + 1 :]:
            assert not left.overlaps(right, tolerance=-1e-6)


def test_the_utilisation_is_the_area_over_the_usable_sheet() -> None:
    result = nest_pieces([("A", 60.0, 20.0)] * 4, sheet())
    assert result.used_area() == pytest.approx(4 * 60.0 * 20.0)
    assert result.utilisation() == pytest.approx(4 * 1200.0 / sheet().usable_area)


def test_an_empty_nest_measures_nothing() -> None:
    result = nest_pieces([], sheet())
    assert result.placed == 0
    assert result.complete
    assert result.used_area() == 0.0
    assert result.utilisation() == 0.0
    assert result.rows() == 0
    assert result.bounds() is None


def test_the_bounds_cover_everything_placed() -> None:
    result = nest_pieces([("A", 60.0, 20.0)] * 4, sheet())
    box = result.bounds()
    assert box is not None
    assert box.min_x == 5.0


def test_a_job_nests_every_piece_it_asks_for() -> None:
    job = JobSpec(
        name="J1",
        sheet=sheet(),
        plates=(
            PlateSpec(name="P-1", width=60.0, height=20.0, stock="LAM16-BW", quantity=3),
            PlateSpec(name="P-2", width=40.0, height=15.0, stock="LAM16-BW", quantity=2),
        ),
    )
    result = nest_job(job)
    assert result.placed == 5
    assert result.complete
    assert len(result.for_plate("P-1")) == 3


def test_a_job_with_no_sheet_cannot_be_nested() -> None:
    job = JobSpec(name="J1", plates=(PlateSpec(name="P", width=10.0, height=10.0, stock="X"),))
    with pytest.raises(ValueError, match="does not say what sheet"):
        nest_job(job)


def test_the_shipped_example_nests_onto_its_own_sheet() -> None:
    result = nest_job(load_job(EXAMPLE))
    assert result.complete
    assert result.placed == 15
    assert result.utilisation() > 0.0


def test_str_reads_like_a_line_on_a_cutting_list() -> None:
    text = str(nest_pieces([("A", 60.0, 20.0)] * 4, sheet()))
    assert "pieces in" in text
    assert text.endswith("all on")


def three_rows() -> list[tuple[str, float, float]]:
    """A tall row, a shorter row, then a piece that belongs in the shorter one.

    The names are in the order the nest will take them, because pieces of
    the same size are sorted by name and the point of the fixture is which
    row is open when the last piece arrives.
    """
    return [
        ("a-tall", 50.0, 40.0),
        ("b-short", 50.0, 22.0),
        ("c-fill", 30.0, 21.0),
    ]


def test_best_fit_puts_a_piece_in_the_row_that_suits_it() -> None:
    narrow = sheet(width=100.0, height=200.0)
    result = nest_pieces(three_rows(), narrow, allow_rotation=False)
    rows = {item.plate: item.origin.y for item in result}
    assert rows["c-fill"] == rows["b-short"]


def test_first_fit_puts_the_same_piece_in_the_first_row_that_takes_it() -> None:
    narrow = sheet(width=100.0, height=200.0)
    result = nest_pieces(three_rows(), narrow, allow_rotation=False, best_fit=False)
    rows = {item.plate: item.origin.y for item in result}
    assert rows["c-fill"] == rows["a-tall"]


def test_best_fit_wastes_less_row_height_than_first_fit() -> None:
    narrow = sheet(width=100.0, height=200.0)
    best = nest_pieces(three_rows(), narrow, allow_rotation=False)
    first = nest_pieces(three_rows(), narrow, allow_rotation=False, best_fit=False)
    assert best.row_waste() < first.row_waste()


def test_both_ways_round_place_the_same_pieces() -> None:
    narrow = sheet(width=100.0, height=200.0)
    best = nest_pieces(three_rows(), narrow, allow_rotation=False)
    first = nest_pieces(three_rows(), narrow, allow_rotation=False, best_fit=False)
    assert {item.plate for item in best} == {item.plate for item in first}
    assert best.used_area() == first.used_area()


def test_a_tie_on_height_goes_to_the_row_with_the_least_room_left() -> None:
    narrow = sheet(width=100.0, height=200.0, kerf=0.0)
    pieces = [("a", 50.0, 30.0), ("b", 60.0, 30.0), ("c", 25.0, 30.0)]
    result = nest_pieces(pieces, narrow, allow_rotation=False)
    rows = {item.plate: item.origin.y for item in result}
    assert rows["c"] == rows["b"]
    assert rows["c"] != rows["a"]


def test_a_nest_where_nothing_stands_short_wastes_no_row_height() -> None:
    result = nest_pieces([("A", 40.0, 20.0), ("B", 40.0, 20.0)], sheet(), allow_rotation=False)
    assert result.row_waste() == 0.0


def test_row_waste_counts_the_area_above_a_short_piece() -> None:
    result = nest_pieces([("A", 40.0, 30.0), ("B", 40.0, 20.0)], sheet(), allow_rotation=False)
    assert result.row_waste() == pytest.approx(40.0 * 10.0)


def test_an_empty_nest_wastes_nothing() -> None:
    assert nest_pieces([], sheet()).row_waste() == 0.0


def test_a_job_can_ask_for_the_plain_first_fit_nest() -> None:
    spec = JobSpec(
        name="J",
        plates=tuple(
            PlateSpec(name=name, width=width, height=height, stock="LAM16-BW", lines=("A",))
            for name, width, height in three_rows()
        ),
        sheet=sheet(width=100.0, height=200.0),
    )
    best = nest_job(spec, allow_rotation=False)
    first = nest_job(spec, allow_rotation=False, best_fit=False)
    assert best.row_waste() < first.row_waste()
