"""Closest approach, which is what the legibility rules ask about."""

from __future__ import annotations

import math

import pytest

from dragpoint.geometry.nearness import (
    closest_approach,
    point_to_segment,
    segment_to_segment,
    segments_cross,
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
