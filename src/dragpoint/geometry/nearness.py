"""How close two bits of geometry come to each other.

This is the measurement the legibility rules are built on. A conical cutter
leaves a groove as wide as the depth makes it, so two centrelines that pass
within that width merge into one blob on the plate. Deciding whether that has
happened is a segment to segment distance problem and nothing more exotic.

Everything here is exact. There is no sampling, because a sampled minimum
distance misses exactly the case that matters, which is two strokes that touch
at one point and are far apart everywhere else.
"""

from __future__ import annotations

from collections.abc import Iterable

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.units import QUANTUM

__all__ = [
    "closest_approach",
    "point_to_segment",
    "segment_to_segment",
    "segments_cross",
    "stroke_to_stroke",
]


def point_to_segment(point: Point, start: Point, end: Point) -> float:
    """Distance from ``point`` to the segment, not to the infinite line."""
    span = end - start
    length_squared = span.dot(span)
    if length_squared < QUANTUM * QUANTUM:
        return point.distance_to(start)
    t = (point - start).dot(span) / length_squared
    t = min(1.0, max(0.0, t))
    return point.distance_to(start.lerp(end, t))


def segments_cross(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """True when two segments properly intersect or touch.

    Collinear overlap counts as crossing. The rule that uses this is asking
    whether the cutter goes over ground it has already cut, and it has,
    whether the crossing is a clean X or a segment lying along another.
    """
    d1 = (a2 - a1).cross(b1 - a1)
    d2 = (a2 - a1).cross(b2 - a1)
    d3 = (b2 - b1).cross(a1 - b1)
    d4 = (b2 - b1).cross(a2 - b1)
    if ((d1 > 0.0) != (d2 > 0.0)) and ((d3 > 0.0) != (d4 > 0.0)):
        return True
    for point, start, end in (
        (b1, a1, a2),
        (b2, a1, a2),
        (a1, b1, b2),
        (a2, b1, b2),
    ):
        if point_to_segment(point, start, end) < QUANTUM:
            return True
    return False


def segment_to_segment(a1: Point, a2: Point, b1: Point, b2: Point) -> float:
    """Shortest distance between two segments, zero when they cross."""
    if segments_cross(a1, a2, b1, b2):
        return 0.0
    return min(
        point_to_segment(a1, b1, b2),
        point_to_segment(a2, b1, b2),
        point_to_segment(b1, a1, a2),
        point_to_segment(b2, a1, a2),
    )


def stroke_to_stroke(left: Stroke, right: Stroke, *, cutoff: float | None = None) -> float:
    """Shortest distance between any part of two strokes.

    ``cutoff`` stops the search as soon as something closer than it is found.
    A plate with three hundred strokes is fifty thousand segment pairs, and
    the legibility rule only ever asks whether anything is closer than one
    number, so the exact value below that number is not worth computing.
    """
    best = float("inf")
    left_boxes = [(first, second) for first, second in left.segments]
    for b1, b2 in right.segments:
        for a1, a2 in left_boxes:
            gap = segment_to_segment(a1, a2, b1, b2)
            if gap < best:
                best = gap
                if cutoff is not None and best < cutoff:
                    return best
    return best


def closest_approach(strokes: Iterable[Stroke], *, cutoff: float | None = None) -> float:
    """The smallest gap between any two different strokes in the group.

    Returns infinity for fewer than two strokes, which reads correctly in the
    rules: nothing is too close to anything when there is nothing to be close
    to. A stroke is never compared with itself, so a glyph whose own stroke
    doubles back does not trip a neighbour rule. That case belongs to the
    self overlap rule and is measured separately.
    """
    ordered = list(strokes)
    best = float("inf")
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            gap = stroke_to_stroke(left, right, cutoff=cutoff)
            if gap < best:
                best = gap
                if cutoff is not None and best < cutoff:
                    return best
    return best
