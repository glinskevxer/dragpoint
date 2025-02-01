"""Point arithmetic. Small surface, and every layer above stands on it."""

from __future__ import annotations

import math

import pytest

from dragpoint.geometry.point import Point, centroid, polyline_length


def test_addition_and_subtraction() -> None:
    assert Point(1.0, 2.0) + Point(3.0, 4.0) == Point(4.0, 6.0)
    assert Point(1.0, 2.0) - Point(3.0, 4.0) == Point(-2.0, -2.0)
    assert -Point(1.0, -2.0) == Point(-1.0, 2.0)


def test_scaling_works_from_either_side() -> None:
    assert Point(1.0, 2.0) * 3 == Point(3.0, 6.0)
    assert 3 * Point(1.0, 2.0) == Point(3.0, 6.0)


def test_distance_is_euclidean() -> None:
    assert Point(0.0, 0.0).distance_to(Point(3.0, 4.0)) == 5.0
    assert Point(3.0, 4.0).norm() == 5.0


def test_dot_and_cross_agree_with_the_angle() -> None:
    right = Point(1.0, 0.0)
    up = Point(0.0, 1.0)
    assert right.dot(up) == 0.0
    assert right.cross(up) == 1.0
    assert up.cross(right) == -1.0
    assert right.dot(right) == 1.0


def test_unit_gives_a_direction_of_length_one() -> None:
    unit = Point(3.0, 4.0).unit()
    assert unit.norm() == pytest.approx(1.0)
    assert unit.x == pytest.approx(0.6)


def test_a_zero_vector_has_no_direction() -> None:
    with pytest.raises(ValueError, match="no direction"):
        Point(0.0, 0.0).unit()


def test_a_vector_shorter_than_the_quantum_also_has_no_direction() -> None:
    with pytest.raises(ValueError):
        Point(1e-9, 1e-9).unit()


def test_perpendicular_turns_left() -> None:
    assert Point(1.0, 0.0).perpendicular() == Point(0.0, 1.0)
    assert Point(0.0, 1.0).perpendicular() == Point(-1.0, 0.0)


def test_perpendicular_four_times_is_the_identity() -> None:
    start = Point(2.0, -5.0)
    turned = start
    for _ in range(4):
        turned = turned.perpendicular()
    assert turned == start


def test_lerp_hits_both_ends() -> None:
    a = Point(0.0, 0.0)
    b = Point(10.0, 20.0)
    assert a.lerp(b, 0.0) == a
    assert a.lerp(b, 1.0) == b
    assert a.lerp(b, 0.5) == Point(5.0, 10.0)


def test_quantised_snaps_both_coordinates() -> None:
    snapped = Point(1.000049, 2.00006).quantised()
    assert snapped.x == pytest.approx(1.0)
    assert snapped.y == pytest.approx(2.0001)


def test_is_close_uses_the_machine_quantum() -> None:
    assert Point(1.0, 1.0).is_close(Point(1.00001, 1.00001))
    assert not Point(1.0, 1.0).is_close(Point(1.01, 1.0))


def test_points_are_hashable_so_they_can_key_a_lookup() -> None:
    assert len({Point(1.0, 1.0), Point(1.0, 1.0), Point(1.0, 2.0)}) == 2


def test_str_is_fixed_width_enough_to_read_in_a_diff() -> None:
    assert str(Point(1.0, -2.5)) == "(1.0000, -2.5000)"


def test_centroid_averages() -> None:
    assert centroid([Point(0.0, 0.0), Point(2.0, 0.0), Point(1.0, 3.0)]) == Point(1.0, 1.0)


def test_centroid_of_nothing_raises() -> None:
    with pytest.raises(ValueError, match="no points"):
        centroid([])


def test_polyline_length_walks_the_points_in_order() -> None:
    points = [Point(0.0, 0.0), Point(3.0, 4.0), Point(3.0, 0.0)]
    assert polyline_length(points) == pytest.approx(9.0)


def test_polyline_length_of_one_point_is_zero() -> None:
    assert polyline_length([Point(5.0, 5.0)]) == 0.0
    assert polyline_length([]) == 0.0


def test_a_diagonal_of_a_unit_square() -> None:
    assert Point(0.0, 0.0).distance_to(Point(1.0, 1.0)) == pytest.approx(math.sqrt(2.0))
