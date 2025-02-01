"""Bounding boxes, and the shrink that must not invert."""

from __future__ import annotations

import pytest

from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point


def test_around_finds_the_tightest_box() -> None:
    box = Box.around([Point(1.0, 5.0), Point(-2.0, 3.0), Point(0.0, 9.0)])
    assert box == Box(-2.0, 3.0, 1.0, 9.0)


def test_around_nothing_is_none_and_not_a_box_of_infinities() -> None:
    assert Box.around([]) is None


def test_from_size_places_the_lower_left_corner() -> None:
    box = Box.from_size(10.0, 4.0, Point(2.0, 3.0))
    assert box == Box(2.0, 3.0, 12.0, 7.0)
    assert Box.from_size(10.0, 4.0) == Box(0.0, 0.0, 10.0, 4.0)


def test_a_negative_size_is_refused() -> None:
    with pytest.raises(ValueError, match="negative box size"):
        Box.from_size(-1.0, 4.0)


def test_an_inverted_box_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="inverted box"):
        Box(5.0, 0.0, 1.0, 1.0)


def test_a_degenerate_box_is_allowed_because_a_single_stroke_makes_one() -> None:
    box = Box(1.0, 1.0, 1.0, 5.0)
    assert box.width == 0.0
    assert box.height == 4.0


def test_measurements() -> None:
    box = Box(1.0, 2.0, 5.0, 10.0)
    assert box.width == 4.0
    assert box.height == 8.0
    assert box.centre == Point(3.0, 6.0)


def test_corners_run_anticlockwise_from_the_lower_left() -> None:
    box = Box(0.0, 0.0, 2.0, 1.0)
    assert box.corners == (
        Point(0.0, 0.0),
        Point(2.0, 0.0),
        Point(2.0, 1.0),
        Point(0.0, 1.0),
    )


def test_contains_includes_the_edge() -> None:
    box = Box(0.0, 0.0, 10.0, 10.0)
    assert box.contains(Point(0.0, 0.0))
    assert box.contains(Point(10.0, 10.0))
    assert not box.contains(Point(10.001, 5.0))
    assert box.contains(Point(10.001, 5.0), tolerance=0.01)


def test_contains_box() -> None:
    outer = Box(0.0, 0.0, 10.0, 10.0)
    assert outer.contains_box(Box(1.0, 1.0, 2.0, 2.0))
    assert outer.contains_box(outer)
    assert not outer.contains_box(Box(-1.0, 1.0, 2.0, 2.0))
    assert outer.contains_box(Box(-0.001, 1.0, 2.0, 2.0), tolerance=0.01)


def test_overlaps_counts_a_shared_edge() -> None:
    left = Box(0.0, 0.0, 5.0, 5.0)
    assert left.overlaps(Box(5.0, 0.0, 9.0, 5.0))
    assert not left.overlaps(Box(5.1, 0.0, 9.0, 5.0))
    assert left.overlaps(Box(5.1, 0.0, 9.0, 5.0), tolerance=0.2)


def test_overlap_is_symmetric() -> None:
    a = Box(0.0, 0.0, 5.0, 5.0)
    b = Box(3.0, 3.0, 9.0, 9.0)
    assert a.overlaps(b) == b.overlaps(a)


def test_union() -> None:
    assert Box(0.0, 0.0, 1.0, 1.0).union(Box(4.0, -2.0, 5.0, 0.0)) == Box(0.0, -2.0, 5.0, 1.0)


def test_grown_moves_every_side_out() -> None:
    assert Box(1.0, 1.0, 3.0, 3.0).grown(1.0) == Box(0.0, 0.0, 4.0, 4.0)


def test_shrinking_past_the_centre_collapses_instead_of_inverting() -> None:
    box = Box(0.0, 0.0, 4.0, 10.0).grown(-3.0)
    assert box.width == 0.0
    assert box.min_x == pytest.approx(2.0)
    assert box.height == pytest.approx(4.0)


def test_moved() -> None:
    assert Box(0.0, 0.0, 1.0, 1.0).moved(Point(2.0, -3.0)) == Box(2.0, -3.0, 3.0, -2.0)


def test_str_is_readable_in_a_failure_message() -> None:
    assert str(Box(0.0, 0.0, 1.5, 2.0)) == "[0.000,0.000 1.500,2.000]"
