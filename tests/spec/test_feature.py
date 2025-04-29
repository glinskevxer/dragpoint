"""Holes and cutouts, and how far a stroke stays off them."""

from __future__ import annotations

import math

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.spec.feature import Feature, FeatureKind


def hole() -> Feature:
    return Feature.round_hole("fix1", Point(10.0, 10.0), 4.0, clearance=1.0)


def window() -> Feature:
    return Feature.rectangle("meter", Point(20.0, 20.0), 10.0, 6.0, clearance=1.5)


def test_a_round_hole_carries_its_diameter_both_ways() -> None:
    feature = hole()
    assert feature.is_round
    assert feature.width == feature.height == 4.0
    assert feature.diameter == 4.0
    assert feature.radius == 2.0
    assert feature.kind is FeatureKind.HOLE


def test_a_rectangle_has_no_diameter() -> None:
    assert window().diameter is None
    assert window().kind is FeatureKind.CUTOUT


def test_a_keepout_is_a_rectangle_that_is_not_a_hole() -> None:
    zone = Feature.rectangle(
        "label", Point(0.0, 0.0), 5.0, 5.0, kind=FeatureKind.KEEPOUT, clearance=0.0
    )
    assert zone.kind is FeatureKind.KEEPOUT


def test_bounds_are_the_feature_and_keepout_bounds_add_the_clearance() -> None:
    assert hole().bounds() == Box(8.0, 8.0, 12.0, 12.0)
    assert hole().keepout_bounds() == Box(7.0, 7.0, 13.0, 13.0)


def test_a_feature_needs_a_name() -> None:
    with pytest.raises(ValueError, match="needs a name"):
        Feature.round_hole("", Point(0.0, 0.0), 4.0)


@pytest.mark.parametrize(
    ("width", "height", "clearance", "what"),
    [
        (0.0, 4.0, 0.5, "width"),
        (4.0, 0.0, 0.5, "height"),
        (4.0, 4.0, -0.1, "clearance"),
    ],
)
def test_an_impossible_feature_is_refused(
    width: float, height: float, clearance: float, what: str
) -> None:
    with pytest.raises(OutOfRange) as caught:
        Feature(
            name="bad",
            kind=FeatureKind.CUTOUT,
            centre=Point(0.0, 0.0),
            width=width,
            height=height,
            clearance=clearance,
        )
    assert what in str(caught.value)


def test_a_round_feature_that_is_not_square_is_refused() -> None:
    with pytest.raises(ValueError, match="round feature"):
        Feature(
            name="oval",
            kind=FeatureKind.BORE,
            centre=Point(0.0, 0.0),
            width=4.0,
            height=6.0,
            is_round=True,
        )


def test_distance_to_a_point_outside_a_hole() -> None:
    assert hole().distance_to(Point(16.0, 10.0)) == pytest.approx(4.0)


def test_distance_to_a_point_inside_a_hole_is_negative() -> None:
    assert hole().distance_to(Point(10.0, 10.0)) == pytest.approx(-2.0)


def test_distance_to_a_point_beside_a_rectangle() -> None:
    assert window().distance_to(Point(30.0, 20.0)) == pytest.approx(5.0)


def test_distance_to_a_point_off_a_rectangle_corner() -> None:
    corner = window().distance_to(Point(28.0, 26.0))
    assert corner == pytest.approx(math.hypot(3.0, 3.0))


def test_distance_to_a_point_inside_a_rectangle_is_negative() -> None:
    assert window().distance_to(Point(20.0, 20.0)) == pytest.approx(-3.0)


def test_a_stroke_that_passes_a_hole_measures_from_its_nearest_point() -> None:
    stroke = Stroke.from_pairs([(0.0, 16.0), (20.0, 16.0)])
    assert hole().distance_to_stroke(stroke) == pytest.approx(4.0)


def test_a_stroke_through_a_hole_measures_negative() -> None:
    stroke = Stroke.from_pairs([(0.0, 10.0), (20.0, 10.0)])
    assert hole().distance_to_stroke(stroke) == pytest.approx(-2.0)


def test_a_stroke_that_clears_a_hole_says_so() -> None:
    assert hole().clears(Stroke.from_pairs([(0.0, 16.0), (20.0, 16.0)]))
    assert not hole().clears(Stroke.from_pairs([(0.0, 12.5), (20.0, 12.5)]))


def test_a_stroke_exactly_on_the_clearance_still_clears() -> None:
    stroke = Stroke.from_pairs([(0.0, 13.0), (20.0, 13.0)])
    assert hole().distance_to_stroke(stroke) == pytest.approx(1.0)
    assert hole().clears(stroke)


def test_a_stroke_beside_a_rectangle() -> None:
    stroke = Stroke.from_pairs([(30.0, 10.0), (30.0, 30.0)])
    assert window().distance_to_stroke(stroke) == pytest.approx(5.0)


def test_a_stroke_crossing_a_rectangle_edge_measures_zero() -> None:
    stroke = Stroke.from_pairs([(10.0, 20.0), (30.0, 20.0)])
    assert window().distance_to_stroke(stroke) == 0.0


def test_a_stroke_wholly_inside_a_rectangle_measures_negative() -> None:
    stroke = Stroke.from_pairs([(19.0, 20.0), (21.0, 20.0)])
    assert window().distance_to_stroke(stroke) < 0.0


def test_a_rectangle_clearance_is_measured_from_the_edge() -> None:
    just_clear = Stroke.from_pairs([(26.5, 10.0), (26.5, 30.0)])
    just_inside = Stroke.from_pairs([(26.4, 10.0), (26.4, 30.0)])
    assert window().clears(just_clear)
    assert not window().clears(just_inside)


def test_a_bent_stroke_is_measured_at_its_closest_bend() -> None:
    stroke = Stroke.from_pairs([(0.0, 30.0), (10.0, 13.5), (20.0, 30.0)])
    assert hole().distance_to_stroke(stroke) == pytest.approx(1.5)
    ends_only = min(hole().distance_to(point) for point in (stroke.start, stroke.end))
    assert ends_only > 1.5


def test_str_reads_like_a_drilling_list_line() -> None:
    assert str(hole()) == "fix1 (hole, 4mm dia at (10.0000, 10.0000))"
    assert str(window()) == "meter (cutout, 10 by 6mm at (20.0000, 20.0000))"
