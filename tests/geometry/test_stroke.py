"""Strokes: the polyline the cutter actually follows."""

from __future__ import annotations

import pytest

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke, join_runs
from dragpoint.geometry.transform import Transform


def square_corner() -> Stroke:
    return Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])


def test_a_stroke_needs_two_points() -> None:
    with pytest.raises(ValueError, match="at least two points"):
        Stroke((Point(0.0, 0.0),))
    with pytest.raises(ValueError):
        Stroke(())


def test_constructors_agree() -> None:
    from_points = Stroke.of(Point(0.0, 0.0), Point(1.0, 1.0))
    from_pairs = Stroke.from_pairs([(0.0, 0.0), (1.0, 1.0)])
    from_line = Stroke.line(Point(0.0, 0.0), Point(1.0, 1.0))
    assert from_points == from_pairs == from_line


def test_sequence_behaviour() -> None:
    stroke = square_corner()
    assert len(stroke) == 3
    assert stroke[0] == Point(0.0, 0.0)
    assert list(stroke)[-1] == Point(10.0, 10.0)
    assert stroke.start == Point(0.0, 0.0)
    assert stroke.end == Point(10.0, 10.0)


def test_segments_are_consecutive_pairs() -> None:
    assert square_corner().segments == (
        (Point(0.0, 0.0), Point(10.0, 0.0)),
        (Point(10.0, 0.0), Point(10.0, 10.0)),
    )


def test_length_and_bounds() -> None:
    stroke = square_corner()
    assert stroke.length() == pytest.approx(20.0)
    assert stroke.bounds().width == 10.0
    assert stroke.bounds().height == 10.0


def test_transformed_maps_every_point() -> None:
    moved = square_corner().transformed(Transform.translation(1.0, 2.0))
    assert moved.start == Point(1.0, 2.0)
    assert moved.length() == pytest.approx(20.0)


def test_reversed_keeps_the_geometry() -> None:
    stroke = square_corner()
    back = stroke.reversed()
    assert back.start == stroke.end
    assert back.length() == pytest.approx(stroke.length())
    assert back.reversed() == stroke


def test_is_closed_needs_more_than_two_points() -> None:
    assert not Stroke.from_pairs([(0.0, 0.0), (0.0, 0.0)]).is_closed()
    ring = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)])
    assert ring.is_closed()
    assert not square_corner().is_closed()


def test_dedupe_drops_points_the_machine_cannot_see() -> None:
    stroke = Stroke.from_pairs([(0.0, 0.0), (0.000001, 0.0), (5.0, 0.0)])
    cleaned = stroke.dedupe()
    assert cleaned is not None
    assert len(cleaned) == 2


def test_dedupe_returns_none_when_the_stroke_collapses() -> None:
    assert Stroke.from_pairs([(1.0, 1.0), (1.0, 1.0)]).dedupe() is None


def test_simplify_removes_a_point_on_the_line() -> None:
    stroke = Stroke.from_pairs([(0.0, 0.0), (5.0, 0.001), (10.0, 0.0)])
    assert len(stroke.simplified(0.01)) == 2
    assert len(stroke.simplified(0.0001)) == 3


def test_simplify_keeps_a_real_corner() -> None:
    assert len(square_corner().simplified(0.5)) == 3


def test_simplify_is_a_no_op_below_two_segments_or_zero_tolerance() -> None:
    line = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)])
    assert line.simplified(1.0) == line
    assert square_corner().simplified(0.0) == square_corner()


def test_simplify_keeps_the_end_points() -> None:
    stroke = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.2), (2.0, 0.1), (3.0, 0.0)])
    simple = stroke.simplified(1.0)
    assert simple.start == stroke.start
    assert simple.end == stroke.end


def test_resample_divides_a_segment_evenly() -> None:
    stroke = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0)])
    resampled = stroke.resampled(2.5)
    assert len(resampled) == 5
    assert resampled[1].x == pytest.approx(2.5)
    assert resampled.end == stroke.end


def test_resample_keeps_the_corner_it_was_given() -> None:
    resampled = square_corner().resampled(3.0)
    assert Point(10.0, 0.0) in resampled.points
    assert resampled.length() == pytest.approx(20.0)


def test_resample_never_leaves_a_step_longer_than_asked_for() -> None:
    resampled = square_corner().resampled(3.0)
    for first, second in resampled.segments:
        assert first.distance_to(second) <= 3.0 + 1e-9


def test_resample_refuses_a_non_positive_spacing() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        square_corner().resampled(0.0)


def test_resample_skips_a_zero_length_segment() -> None:
    stroke = Stroke.from_pairs([(0.0, 0.0), (0.0, 0.0), (4.0, 0.0)])
    assert stroke.resampled(2.0).length() == pytest.approx(4.0)


def test_join_runs_glues_head_to_tail() -> None:
    first = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)])
    second = Stroke.from_pairs([(1.0, 0.0), (2.0, 0.0)])
    joined = join_runs([first, second])
    assert len(joined) == 1
    assert len(joined[0]) == 3


def test_join_runs_flips_a_stroke_that_meets_the_wrong_way_round() -> None:
    first = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)])
    second = Stroke.from_pairs([(2.0, 0.0), (1.0, 0.0)])
    joined = join_runs([first, second])
    assert len(joined) == 1
    assert joined[0].end == Point(2.0, 0.0)


def test_join_runs_extends_backwards_too() -> None:
    middle = Stroke.from_pairs([(1.0, 0.0), (2.0, 0.0)])
    before = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)])
    joined = join_runs([middle, before])
    assert len(joined) == 1
    assert joined[0].start == Point(0.0, 0.0)


def test_join_runs_glues_two_starts_together() -> None:
    left = Stroke.from_pairs([(1.0, 0.0), (2.0, 0.0)])
    right = Stroke.from_pairs([(1.0, 0.0), (0.0, 0.0)])
    joined = join_runs([left, right])
    assert len(joined) == 1
    assert joined[0].length() == pytest.approx(2.0)


def test_join_runs_leaves_real_breaks_alone() -> None:
    apart = [
        Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)]),
        Stroke.from_pairs([(5.0, 0.0), (6.0, 0.0)]),
    ]
    assert len(join_runs(apart)) == 2


def test_join_runs_of_nothing_is_nothing() -> None:
    assert join_runs([]) == []


def test_str_is_a_readable_point_list() -> None:
    assert str(Stroke.from_pairs([(0.0, 0.0), (1.5, 2.0)])) == "0,0 1.5,2"
