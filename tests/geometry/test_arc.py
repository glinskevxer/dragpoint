"""Bending a baseline round a circle."""

from __future__ import annotations

import math

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.geometry.arc import ArcMap, bend, chord_spacing
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke


def arc(**overrides: object) -> ArcMap:
    values: dict[str, object] = {"centre": Point(0.0, 0.0), "radius": 20.0}
    values.update(overrides)
    return ArcMap(**values)  # type: ignore[arg-type]


def test_a_spacing_keeps_the_flat_inside_the_tolerance() -> None:
    radius = 20.0
    tolerance = 0.01
    step = chord_spacing(radius, tolerance)
    sagitta = radius - math.sqrt(radius**2 - (step / 2.0) ** 2)
    assert sagitta == pytest.approx(tolerance, rel=0.01)


def test_a_bigger_radius_takes_longer_steps() -> None:
    assert chord_spacing(100.0) > chord_spacing(10.0)


def test_a_tighter_tolerance_takes_shorter_steps() -> None:
    assert chord_spacing(20.0, 0.001) < chord_spacing(20.0, 0.05)


def test_a_tolerance_bigger_than_the_circle_gives_up_and_uses_the_diameter() -> None:
    assert chord_spacing(1.0, 5.0) == 2.0


@pytest.mark.parametrize(("radius", "tolerance"), [(0.0, 0.01), (-1.0, 0.01), (10.0, 0.0)])
def test_an_impossible_spacing_is_refused(radius: float, tolerance: float) -> None:
    with pytest.raises(OutOfRange):
        chord_spacing(radius, tolerance)


def test_a_radius_of_zero_is_not_an_arc() -> None:
    with pytest.raises(OutOfRange, match="radius"):
        ArcMap(centre=Point(0.0, 0.0), radius=0.0)


def test_the_origin_of_the_baseline_lands_at_the_start_angle() -> None:
    landed = arc(start=90.0).apply(Point(0.0, 0.0))
    assert landed.x == pytest.approx(0.0, abs=1e-9)
    assert landed.y == pytest.approx(20.0)


def test_a_start_of_zero_lands_at_three_o_clock() -> None:
    landed = arc(start=0.0).apply(Point(0.0, 0.0))
    assert landed == Point(20.0, 0.0)


def test_going_along_the_baseline_goes_anticlockwise_by_default() -> None:
    quarter = arc(start=0.0).apply(Point(20.0 * math.pi / 2.0, 0.0))
    assert quarter.x == pytest.approx(0.0, abs=1e-9)
    assert quarter.y == pytest.approx(20.0)


def test_clockwise_goes_the_other_way() -> None:
    quarter = arc(start=0.0, clockwise=True).apply(Point(20.0 * math.pi / 2.0, 0.0))
    assert quarter.y == pytest.approx(-20.0)


def test_the_angle_at_a_distance_is_the_arc_length() -> None:
    mapped = arc(start=0.0)
    assert mapped.angle_at(mapped.radius * math.pi) == pytest.approx(180.0)


def test_a_sweep_is_the_width_over_the_radius() -> None:
    assert arc(radius=20.0).sweep_for(20.0 * math.pi) == pytest.approx(180.0)


def test_height_above_the_baseline_stands_out_from_the_circle() -> None:
    landed = arc(start=0.0).apply(Point(0.0, 3.0))
    assert landed == Point(23.0, 0.0)


def test_a_descender_goes_inside_the_circle() -> None:
    landed = arc(start=0.0).apply(Point(0.0, -2.0))
    assert landed == Point(18.0, 0.0)


def test_lettering_can_stand_inward_instead() -> None:
    landed = arc(start=0.0, outward=False).apply(Point(0.0, 3.0))
    assert landed == Point(17.0, 0.0)


def test_the_circumference_is_the_room_there_is() -> None:
    mapped = arc(radius=20.0)
    assert mapped.circumference == pytest.approx(2.0 * math.pi * 20.0)
    assert mapped.fits(mapped.circumference - 1.0)
    assert not mapped.fits(mapped.circumference)


def test_the_centre_moves_everything_with_it() -> None:
    landed = arc(centre=Point(100.0, 50.0), start=0.0).apply(Point(0.0, 0.0))
    assert landed == Point(120.0, 50.0)


def test_a_bent_straight_line_is_no_longer_straight() -> None:
    straight = Stroke.from_pairs([(0.0, 0.0), (30.0, 0.0)])
    bent = bend(straight, arc())
    assert len(bent) > 2
    assert not all(point.y == bent.start.y for point in bent.points)


def test_every_point_of_a_bent_baseline_sits_on_the_circle() -> None:
    straight = Stroke.from_pairs([(0.0, 0.0), (30.0, 0.0)])
    mapped = arc()
    for point in bend(straight, mapped).points:
        assert mapped.centre.distance_to(point) == pytest.approx(mapped.radius)


def test_a_bent_stroke_keeps_its_length_along_the_arc() -> None:
    straight = Stroke.from_pairs([(0.0, 0.0), (30.0, 0.0)])
    bent = bend(straight, arc(), tolerance=0.0005)
    assert bent.length() == pytest.approx(30.0, rel=0.001)


def test_a_tighter_tolerance_makes_more_points() -> None:
    straight = Stroke.from_pairs([(0.0, 0.0), (30.0, 0.0)])
    assert len(bend(straight, arc(), tolerance=0.0005)) > len(bend(straight, arc(), tolerance=0.05))


def test_the_ends_of_a_bent_stroke_are_where_the_map_puts_them() -> None:
    straight = Stroke.from_pairs([(0.0, 0.0), (30.0, 0.0)])
    mapped = arc()
    bent = bend(straight, mapped)
    assert bent.start.is_close(mapped.apply(Point(0.0, 0.0)))
    assert bent.end.is_close(mapped.apply(Point(30.0, 0.0)))


def test_a_tall_stroke_is_subdivided_at_its_own_radius() -> None:
    tall = Stroke.from_pairs([(0.0, 10.0), (30.0, 10.0)])
    low = Stroke.from_pairs([(0.0, 0.0), (30.0, 0.0)])
    assert len(bend(tall, arc())) <= len(bend(low, arc()))


def test_str_reads_like_a_note_on_a_drawing() -> None:
    text = str(arc(start=45.0, clockwise=True))
    assert "r20mm" in text
    assert "clockwise" in text
    assert "outward" in text
