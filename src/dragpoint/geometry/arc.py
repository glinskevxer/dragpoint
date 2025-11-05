"""Bending a straight baseline round a circle.

Every rotary switch on a panel has a legend round it: OFF at eight o'clock,
HAND at twelve, AUTO at four. The lettering follows the bore, and a shop
without a way to do that sets each word as its own little plate and glues
them on, which looks exactly as bad as it sounds.

The map is one idea. Distance along the straight baseline becomes angle
round the circle, and height above the baseline becomes distance out from
it. Everything else follows: a glyph bends, its stems fan out, and the
lettering stands off the bore by whatever the baseline was above zero.

Bending is not an affine transform and cannot be one. A straight line comes
out curved, so a stroke has to be broken into enough pieces that the flats
between them are inside a tolerance, and the tolerance is a real number on
the plate rather than a screen resolution. :func:`chord_spacing` is where
that number turns into a step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.units import QUANTUM

__all__ = ["ArcMap", "bend", "chord_spacing"]

DEFAULT_TOLERANCE = 0.01
"""Millimetres of flat allowed between two points of a bent stroke."""


def chord_spacing(radius: float, tolerance: float = DEFAULT_TOLERANCE) -> float:
    """How far apart points may be on a circle of ``radius``.

    The gap between a chord and the arc it cuts off is the sagitta, and for
    a small one the chord is about ``2 * sqrt(2 * radius * sagitta)``. Read
    backwards, that is the longest step that keeps the flat inside the
    tolerance, which is what the caller actually wants to know.
    """
    if radius <= 0.0:
        raise OutOfRange("radius", radius, QUANTUM, math.inf)
    if tolerance <= 0.0:
        raise OutOfRange("tolerance", tolerance, QUANTUM, math.inf)
    if tolerance >= radius:
        return 2.0 * radius
    return 2.0 * math.sqrt(2.0 * radius * tolerance)


@dataclass(frozen=True, slots=True)
class ArcMap:
    """Where a point on a straight baseline lands on a circle.

    ``start`` is the angle, in degrees anticlockwise from three o'clock,
    that x zero maps to. ``clockwise`` reverses the direction the text runs
    in, which is what a legend below a switch needs: above the bore the
    words read left to right going anticlockwise, and below it they read
    left to right going clockwise, or they come out upside down.

    ``outward`` says which side of the baseline the lettering stands on.
    Outward is a legend outside the bore reading from outside, which is the
    usual case; inward is a legend inside a ring, reading from the middle.
    """

    centre: Point
    radius: float
    start: float = 90.0
    clockwise: bool = False
    outward: bool = True

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise OutOfRange("radius", self.radius, QUANTUM, math.inf)

    @property
    def circumference(self) -> float:
        """All the way round, in millimetres."""
        return 2.0 * math.pi * self.radius

    def angle_at(self, along: float) -> float:
        """The angle in degrees that ``along`` millimetres of baseline reaches."""
        sweep = math.degrees(along / self.radius)
        return self.start - sweep if self.clockwise else self.start + sweep

    def sweep_for(self, width: float) -> float:
        """How many degrees a run of ``width`` millimetres takes up."""
        return math.degrees(width / self.radius)

    def apply(self, point: Point) -> Point:
        """Map one point off the baseline onto the arc.

        A point below the baseline maps inside the circle when the lettering
        stands outward, which is what a descender should do.
        """
        angle = math.radians(self.angle_at(point.x))
        reach = self.radius + (point.y if self.outward else -point.y)
        return Point(
            self.centre.x + reach * math.cos(angle),
            self.centre.y + reach * math.sin(angle),
        )

    def fits(self, width: float) -> bool:
        """True when a run of ``width`` goes round without meeting itself."""
        return width < self.circumference

    def __str__(self) -> str:
        way = "clockwise" if self.clockwise else "anticlockwise"
        side = "outward" if self.outward else "inward"
        return f"r{self.radius:g}mm at {self.centre}, from {self.start:g} deg {way}, {side}"


def bend(stroke: Stroke, arc: ArcMap, *, tolerance: float = DEFAULT_TOLERANCE) -> Stroke:
    """Bend one stroke round the arc, subdividing it enough to stay smooth.

    The subdivision is worked out at the radius the stroke actually sits at,
    not at the baseline radius. A cap height above the baseline is a bigger
    circle and needs slightly longer steps, and using the baseline for
    everything would break a tall letter into more pieces than the tolerance
    asks for and the control has room for.
    """
    reach = max(arc.radius + (point.y if arc.outward else -point.y) for point in stroke.points)
    spacing = chord_spacing(max(reach, QUANTUM), tolerance)
    dense = stroke.resampled(spacing)
    return Stroke(tuple(arc.apply(point) for point in dense.points))
