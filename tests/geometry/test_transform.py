"""Transforms, and the composition order that reads left to right."""

from __future__ import annotations

import math

import pytest

from dragpoint.geometry.point import Point
from dragpoint.geometry.transform import Transform


def test_identity_leaves_a_point_alone() -> None:
    point = Point(3.0, -4.0)
    assert Transform.identity().apply(point) == point


def test_translation() -> None:
    assert Transform.translation(1.0, 2.0).apply(Point(0.0, 0.0)) == Point(1.0, 2.0)


def test_scaling_one_argument_scales_both_axes() -> None:
    assert Transform.scaling(2.0).apply(Point(1.0, 3.0)) == Point(2.0, 6.0)
    assert Transform.scaling(2.0, 0.5).apply(Point(1.0, 4.0)) == Point(2.0, 2.0)


def test_rotation_is_anticlockwise() -> None:
    turned = Transform.rotation(90.0).apply(Point(1.0, 0.0))
    assert turned.x == pytest.approx(0.0, abs=1e-12)
    assert turned.y == pytest.approx(1.0)


def test_rotation_of_a_full_turn_is_the_identity() -> None:
    turned = Transform.rotation(360.0).apply(Point(2.0, 5.0))
    assert turned.x == pytest.approx(2.0)
    assert turned.y == pytest.approx(5.0)


def test_slant_shears_along_x_and_leaves_the_baseline_alone() -> None:
    slant = Transform.slant(15.0)
    assert slant.apply(Point(0.0, 0.0)) == Point(0.0, 0.0)
    assert slant.apply(Point(0.0, 10.0)).x == pytest.approx(10.0 * math.tan(math.radians(15.0)))
    assert slant.apply(Point(0.0, 10.0)).y == 10.0


def test_a_right_angle_slant_has_no_meaning() -> None:
    with pytest.raises(ValueError, match="no shear"):
        Transform.slant(90.0)


def test_mirroring() -> None:
    assert Transform.mirror_x().apply(Point(2.0, 3.0)) == Point(-2.0, 3.0)
    assert Transform.mirror_y().apply(Point(2.0, 3.0)) == Point(2.0, -3.0)


def test_then_applies_the_receiver_first() -> None:
    move_then_scale = Transform.translation(1.0, 0.0).then(Transform.scaling(10.0))
    assert move_then_scale.apply(Point(0.0, 0.0)) == Point(10.0, 0.0)
    scale_then_move = Transform.scaling(10.0).then(Transform.translation(1.0, 0.0))
    assert scale_then_move.apply(Point(0.0, 0.0)) == Point(1.0, 0.0)


def test_composition_is_associative() -> None:
    a = Transform.rotation(20.0)
    b = Transform.scaling(2.0, 3.0)
    c = Transform.translation(-4.0, 7.0)
    point = Point(1.5, -2.5)
    left = a.then(b).then(c).apply(point)
    right = a.then(b.then(c)).apply(point)
    assert left.x == pytest.approx(right.x)
    assert left.y == pytest.approx(right.y)


def test_apply_vector_drops_the_translation() -> None:
    moved = Transform.translation(100.0, 100.0)
    assert moved.apply_vector(Point(1.0, 0.0)) == Point(1.0, 0.0)


def test_inverse_undoes() -> None:
    transform = Transform.rotation(33.0).then(Transform.scaling(2.0, 5.0))
    transform = transform.then(Transform.translation(9.0, -3.0))
    point = Point(1.0, 2.0)
    back = transform.inverse().apply(transform.apply(point))
    assert back.x == pytest.approx(1.0)
    assert back.y == pytest.approx(2.0)


def test_a_collapsed_transform_has_no_inverse() -> None:
    with pytest.raises(ValueError, match="no inverse"):
        Transform.scaling(1.0, 0.0).inverse()


def test_determinant_and_mirroring() -> None:
    assert Transform.scaling(2.0, 3.0).determinant == pytest.approx(6.0)
    assert not Transform.scaling(2.0, 3.0).is_mirrored
    assert Transform.mirror_x().is_mirrored
    assert Transform.mirror_x().then(Transform.mirror_y()).is_mirrored is False


def test_length_scale_is_exact_for_a_similarity() -> None:
    assert Transform.scaling(3.0).length_scale() == pytest.approx(3.0)
    assert Transform.rotation(41.0).length_scale() == pytest.approx(1.0)


def test_str_matches_what_an_svg_would_carry() -> None:
    assert str(Transform.translation(1.0, 2.0)) == "matrix(1 0 0 1 1 2)"
