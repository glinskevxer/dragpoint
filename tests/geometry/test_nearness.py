"""Closest approach, which is what the legibility rules ask about."""

from __future__ import annotations

import math

import pytest

from dragpoint.geometry.nearness import (
    closest_approach,
    meets_itself,
    point_to_segment,
    segment_to_segment,
    segments_cross,
    self_approach,
    stroke_to_stroke,
)
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke


def test_point_to_segment_falls_on_the_middle() -> None:
    assert point_to_segment(Point(5.0, 3.0), Point(0.0, 0.0), Point(10.0, 0.0)) == 3.0


def test_point_to_segment_clamps_past_the_end() -> None:
    assert point_to_segment(Point(20.0, 0.0), Point(0.0, 0.0), Point(10.0, 0.0)) == 10.0
    assert point_to_segment(Point(-5.0, 0.0), Point(0.0, 0.0), Point(10.0, 0.0)) == 5.0


def test_point_to_segment_is_not_the_distance_to_the_infinite_line() -> None:
    off_the_end = point_to_segment(Point(20.0, 3.0), Point(0.0, 0.0), Point(10.0, 0.0))
    assert off_the_end == pytest.approx(math.hypot(10.0, 3.0))


def test_point_to_a_collapsed_segment_is_the_distance_to_the_point() -> None:
    assert point_to_segment(Point(3.0, 4.0), Point(0.0, 0.0), Point(0.0, 0.0)) == 5.0


def test_segments_cross_in_an_x() -> None:
    assert segments_cross(Point(0.0, 0.0), Point(10.0, 10.0), Point(0.0, 10.0), Point(10.0, 0.0))


def test_segments_that_miss_do_not_cross() -> None:
    assert not segments_cross(Point(0.0, 0.0), Point(1.0, 0.0), Point(0.0, 5.0), Point(1.0, 5.0))


def test_a_touching_endpoint_counts_as_crossing() -> None:
    assert segments_cross(Point(0.0, 0.0), Point(5.0, 0.0), Point(5.0, 0.0), Point(5.0, 5.0))


def test_collinear_overlap_counts_as_crossing() -> None:
    assert segments_cross(Point(0.0, 0.0), Point(10.0, 0.0), Point(4.0, 0.0), Point(6.0, 0.0))


def test_collinear_but_apart_does_not_cross() -> None:
    assert not segments_cross(Point(0.0, 0.0), Point(1.0, 0.0), Point(4.0, 0.0), Point(6.0, 0.0))


def test_a_t_junction_crosses() -> None:
    assert segments_cross(Point(0.0, 0.0), Point(10.0, 0.0), Point(5.0, 0.0), Point(5.0, 9.0))


def test_segment_distance_of_parallel_rails() -> None:
    gap = segment_to_segment(Point(0.0, 0.0), Point(10.0, 0.0), Point(0.0, 2.0), Point(10.0, 2.0))
    assert gap == pytest.approx(2.0)


def test_segment_distance_is_zero_when_they_cross() -> None:
    gap = segment_to_segment(Point(0.0, 0.0), Point(10.0, 10.0), Point(0.0, 10.0), Point(10.0, 0.0))
    assert gap == 0.0


def test_segment_distance_between_diagonal_ends() -> None:
    gap = segment_to_segment(Point(0.0, 0.0), Point(1.0, 0.0), Point(4.0, 4.0), Point(5.0, 4.0))
    assert gap == pytest.approx(5.0)


def test_segment_distance_is_symmetric() -> None:
    a1, a2 = Point(0.0, 0.0), Point(3.0, 1.0)
    b1, b2 = Point(-2.0, 4.0), Point(7.0, 6.0)
    forward = segment_to_segment(a1, a2, b1, b2)
    backward = segment_to_segment(b1, b2, a1, a2)
    assert forward == pytest.approx(backward)


def test_stroke_to_stroke_finds_the_closest_pair_of_segments() -> None:
    left = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    right = Stroke.from_pairs([(0.0, 20.0), (12.0, 20.0), (12.0, 11.0)])
    assert stroke_to_stroke(left, right) == pytest.approx(math.hypot(2.0, 1.0))


def test_stroke_to_stroke_reports_zero_when_the_strokes_meet() -> None:
    stem = Stroke.from_pairs([(0.0, 0.0), (0.0, 10.0)])
    bar = Stroke.from_pairs([(0.0, 5.0), (8.0, 5.0)])
    assert stroke_to_stroke(stem, bar) == 0.0


def test_stroke_to_stroke_cutoff_returns_early_with_a_number_below_it() -> None:
    left = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0)])
    right = Stroke.from_pairs([(0.0, 0.5), (10.0, 0.5)])
    assert stroke_to_stroke(left, right, cutoff=1.0) < 1.0


def test_closest_approach_of_a_group() -> None:
    strokes = [
        Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0)]),
        Stroke.from_pairs([(0.0, 3.0), (10.0, 3.0)]),
        Stroke.from_pairs([(0.0, 3.4), (10.0, 3.4)]),
    ]
    assert closest_approach(strokes) == pytest.approx(0.4)


def test_closest_approach_never_compares_a_stroke_with_itself() -> None:
    doubled_back = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 0.05), (0.0, 0.05)])
    assert closest_approach([doubled_back]) == math.inf


def test_closest_approach_of_nothing_is_infinite() -> None:
    assert closest_approach([]) == math.inf


def test_closest_approach_honours_the_cutoff() -> None:
    strokes = [
        Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)]),
        Stroke.from_pairs([(0.0, 0.1), (1.0, 0.1)]),
        Stroke.from_pairs([(0.0, 50.0), (1.0, 50.0)]),
    ]
    assert closest_approach(strokes, cutoff=0.5) < 0.5


def test_a_touching_pair_is_thrown_away_whole() -> None:
    stem = Stroke.from_pairs([(0.0, 0.0), (0.0, 10.0)])
    bar = Stroke.from_pairs([(0.0, 5.0), (8.0, 5.2)])
    assert stroke_to_stroke(stem, bar) == 0.0
    assert closest_approach([stem, bar]) == math.inf


def test_a_pair_that_only_nearly_touches_is_kept() -> None:
    stem = Stroke.from_pairs([(0.0, 0.0), (0.0, 10.0)])
    bar = Stroke.from_pairs([(0.3, 5.0), (8.0, 5.2)])
    assert closest_approach([stem, bar]) == pytest.approx(0.3)


def test_the_touch_tolerance_can_be_widened() -> None:
    stem = Stroke.from_pairs([(0.0, 0.0), (0.0, 10.0)])
    bar = Stroke.from_pairs([(0.3, 5.0), (8.0, 5.2)])
    assert closest_approach([stem, bar], touch=0.5) == math.inf


def test_a_group_where_every_pair_meets_has_no_approach() -> None:
    left = Stroke.from_pairs([(0.0, 0.0), (5.0, 5.0)])
    right = Stroke.from_pairs([(5.0, 5.0), (10.0, 0.0)])
    bar = Stroke.from_pairs([(2.5, 2.5), (7.5, 2.5)])
    assert closest_approach([left, right, bar]) == math.inf


def test_a_straight_stroke_reports_the_gate_it_was_given() -> None:
    line = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0)])
    assert self_approach(line, min_arc=5.0) == pytest.approx(5.0, abs=0.1)


def test_a_stroke_shorter_than_the_gate_has_nothing_to_compare() -> None:
    line = Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)])
    assert self_approach(line, min_arc=5.0) == math.inf


def test_self_approach_finds_a_stroke_folded_back_on_itself() -> None:
    folded = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 0.4), (0.0, 0.4)])
    assert self_approach(folded, min_arc=5.0) == pytest.approx(0.4, abs=0.2)


def test_a_right_angle_reports_less_than_the_gate_but_not_a_fold() -> None:
    corner = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    assert self_approach(corner, min_arc=4.0) == pytest.approx(4.0 * 0.7071, abs=0.2)


def test_a_gate_wider_than_the_stroke_finds_nothing() -> None:
    folded = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 0.4), (0.0, 0.4)])
    assert self_approach(folded, min_arc=50.0) == math.inf


def test_a_curve_leaving_a_long_straight_is_not_a_fold() -> None:
    hook = Stroke.from_pairs([(0.0, 100.0), (0.0, 10.0), (-2.0, 4.0), (-8.0, 0.0)])
    assert self_approach(hook, min_arc=20.0) == pytest.approx(20.0, abs=0.5)


def test_the_walking_step_can_be_set() -> None:
    folded = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 0.4), (0.0, 0.4)])
    assert self_approach(folded, min_arc=5.0, step=0.1) == pytest.approx(0.4, abs=0.05)


def test_a_walking_step_of_zero_is_refused() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        self_approach(
            Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]), min_arc=1.0, step=0.0
        )


def test_a_stroke_that_meets_itself_is_left_to_the_eye() -> None:
    figure_eight = Stroke.from_pairs(
        [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0), (0.0, 0.0)]
    )
    assert self_approach(figure_eight, min_arc=5.0) == math.inf


def test_a_closed_ring_measures_its_own_counter() -> None:
    ring = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)])
    assert self_approach(ring, min_arc=14.0) == pytest.approx(10.0, abs=0.3)


def test_a_closed_stroke_does_not_report_its_own_closure() -> None:
    ring = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)])
    assert self_approach(ring, min_arc=30.0) == math.inf


def test_self_approach_honours_its_cutoff() -> None:
    folded = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 0.4), (0.0, 0.4)])
    assert self_approach(folded, min_arc=5.0, cutoff=1.0) < 1.0


def test_a_stroke_that_crosses_itself_says_so() -> None:
    figure_four = Stroke.from_pairs([(4.0, 0.0), (4.0, 7.0), (0.7, 1.85), (5.3, 1.85)])
    assert meets_itself(figure_four)


def test_a_stroke_that_only_bends_does_not_meet_itself() -> None:
    corner = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    assert not meets_itself(corner)


def test_a_closed_stroke_does_not_meet_itself_at_its_closure() -> None:
    ring = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)])
    assert not meets_itself(ring)


def test_a_crossing_survives_a_coarse_walk() -> None:
    figure_four = Stroke.from_pairs([(4.0, 0.0), (4.0, 7.0), (0.7, 1.85), (5.3, 1.85)])
    assert self_approach(figure_four, min_arc=3.0, step=2.0) == math.inf


def test_the_fold_ratio_leaves_a_straight_stroke_alone() -> None:
    line = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0)])
    assert self_approach(line, min_arc=1.0, fold_ratio=1.5) == math.inf


def test_the_fold_ratio_leaves_a_right_angle_alone() -> None:
    corner = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    assert self_approach(corner, min_arc=1.0, fold_ratio=1.5) == math.inf


def test_the_fold_ratio_still_catches_a_fold() -> None:
    folded = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 0.4), (0.0, 0.4)])
    assert self_approach(folded, min_arc=1.0, fold_ratio=1.5) == pytest.approx(0.4, abs=0.2)


def test_the_fold_ratio_catches_a_closed_counter() -> None:
    ring = Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)])
    assert self_approach(ring, min_arc=1.0, fold_ratio=1.5) == pytest.approx(10.0, abs=0.5)


def test_the_fold_ratio_catches_a_sharp_spike() -> None:
    spike = Stroke.from_pairs([(0.0, 0.0), (10.0, 1.0), (0.0, 2.0)])
    assert self_approach(spike, min_arc=1.0, fold_ratio=1.5) < 2.0


def grid_of_strokes(across: int, up: int, pitch: float = 10.0) -> list[Stroke]:
    """A field of short strokes, none of them near each other."""
    return [
        Stroke.from_pairs([(x * pitch, y * pitch), (x * pitch + 2.0, y * pitch)])
        for x in range(across)
        for y in range(up)
    ]


def test_a_field_of_strokes_measures_the_pitch_between_rows() -> None:
    field = grid_of_strokes(6, 6)
    assert closest_approach(field) == pytest.approx(8.0)


def test_one_close_pair_in_a_field_is_still_found() -> None:
    field = grid_of_strokes(6, 6)
    field.append(Stroke.from_pairs([(0.0, 0.3), (2.0, 0.3)]))
    assert closest_approach(field) == pytest.approx(0.3)


def test_the_answer_does_not_change_with_the_order_the_strokes_come_in() -> None:
    field = grid_of_strokes(5, 5)
    field.append(Stroke.from_pairs([(0.0, 0.4), (2.0, 0.4)]))
    assert closest_approach(field) == pytest.approx(closest_approach(list(reversed(field))))


def test_two_long_strokes_far_apart_still_measure_exactly() -> None:
    left = Stroke.from_pairs([(0.0, 0.0), (100.0, 0.0)])
    right = Stroke.from_pairs([(0.0, 7.5), (100.0, 7.5)])
    assert stroke_to_stroke(left, right) == pytest.approx(7.5)


def test_a_stroke_that_doubles_back_near_another_is_measured_at_its_nearest() -> None:
    left = Stroke.from_pairs([(0.0, 0.0), (50.0, 0.0), (50.0, 20.0), (0.0, 20.0)])
    right = Stroke.from_pairs([(0.0, 22.0), (50.0, 22.0)])
    assert stroke_to_stroke(left, right) == pytest.approx(2.0)
