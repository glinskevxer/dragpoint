"""How close two bits of geometry come to each other.

This is the measurement the legibility rules are built on. A conical cutter
leaves a groove as wide as the depth makes it, so two centrelines that pass
within that width merge into one blob on the plate. Deciding whether that has
happened is a segment to segment distance problem and nothing more exotic.

Everything here is exact. There is no sampling, because a sampled minimum
distance misses exactly the case that matters, which is two strokes that touch
at one point and are far apart everywhere else.

Exact does not mean measuring everything. A glyph is a few dozen strokes and
a plate is a few hundred, which is tens of thousands of segment pairs, and
almost all of them are nowhere near each other. Every pair is offered a box
first: two boxes further apart than the closest thing found so far cannot
contain anything closer, so the segments inside them are never touched. The
answer is the same one and there is a great deal less of it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.units import QUANTUM

__all__ = [
    "closest_approach",
    "point_to_segment",
    "segment_to_segment",
    "meets_itself",
    "segments_cross",
    "self_approach",
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

    Zero means they meet. Nothing here decides what meeting means; that is
    :func:`closest_approach`, which throws the pair away.
    """
    best = float("inf")
    left_segments = [(a1, a2, _segment_box(a1, a2)) for a1, a2 in left.segments]
    for b1, b2 in right.segments:
        box = _segment_box(b1, b2)
        for a1, a2, other in left_segments:
            if other.gap_to(box) >= best:
                continue
            gap = segment_to_segment(a1, a2, b1, b2)
            if gap >= best:
                continue
            best = gap
            if cutoff is not None and best < cutoff:
                return best
    return best


def _segment_box(start: Point, end: Point) -> Box:
    """The box round one segment, which is its two ends."""
    return Box(
        min(start.x, end.x),
        min(start.y, end.y),
        max(start.x, end.x),
        max(start.y, end.y),
    )


def self_approach(
    stroke: Stroke,
    *,
    min_arc: float,
    fold_ratio: float = 1.0,
    cutoff: float | None = None,
    touch: float = QUANTUM,
    step: float | None = None,
) -> float:
    """How close a stroke comes to a part of itself far away along the path.

    Two places on a smooth curve are always close together in space when
    they are close together along the curve, and that is the curve rather
    than a fault. ``min_arc`` is how far apart two places have to be
    measured along the stroke before their distance in space means anything.

    Without that gate the measurement is dominated by the sampling: a circle
    drawn with twenty chords reports the length of one chord, and reports it
    more tightly the more finely the circle was drawn. With it, what comes
    back is what the rule is asking about, which is a stroke that has come
    back on ground it already covered.

    The stroke is walked as points rather than as segments, because a fold
    is only a fold away from the turn. At the turn itself the two sides are
    as close along the path as they are in space, and it is at the far end,
    where the path between them is the whole fold, that they are a fault.
    ``step`` is the walking distance and defaults to a quarter of
    ``min_arc``, which puts the answer within an eighth of that of exact.

    A stroke that meets itself is a junction the face drew on purpose, such
    as the waist of an eight or the crossing of an ampersand. Nothing useful
    can be said about one, because every measurement near the crossing is
    small for the same reason the crossing is there, so it returns infinity
    and is left to the eye.

    On a closed stroke the path distance wraps, since the two ends of a
    closed run are the same place.

    ``min_arc`` has no default. It is the sampling gate and should be a
    small multiple of the step, not a real limit.

    ``fold_ratio`` is what separates a fold from a bend. Two places on a
    straight stroke are as far apart in space as they are along it, so the
    ratio is one; a right angle gives about one and a half; a circle coming
    back on itself gives pi over two, and a sharp point gives more the
    sharper it is. Asking for a ratio above one and a half therefore means a
    stem is never a fold, a square corner never is, and a closed counter or
    a spike always is. Both of those last two fill in under a wide cutter,
    which is the whole question.

    Returns infinity when no two places on the stroke are far enough apart
    along it to compare.
    """
    if meets_itself(stroke):
        return float("inf")
    samples = _walk(stroke, step if step is not None else _default_step(stroke, min_arc))
    if len(samples) < 2:
        return float("inf")
    total = samples[-1][0]
    closed = stroke.is_closed()
    best = float("inf")
    for index, (arc, point) in enumerate(samples):
        for other in range(index + 1, len(samples)):
            along = samples[other][0] - arc
            if closed:
                along = min(along, total - along)
            if along < min_arc:
                continue
            gap = point.distance_to(samples[other][1])
            if gap <= touch:
                return float("inf")
            if gap >= best or gap * fold_ratio > along:
                continue
            best = gap
            if cutoff is not None and best < cutoff:
                return best
    return best


def meets_itself(stroke: Stroke) -> bool:
    """True when the stroke crosses or touches a non neighbouring part of itself.

    Exact, and separate from the walk on purpose. A crossing is a single
    point, and a walk with any step at all can step straight over one: the
    four is drawn as one run whose bar goes through its own stem, and
    sampled at anything coarser than nothing it reads as a near miss of
    whatever the step happened to leave either side of the crossing.
    """
    segments = stroke.segments
    count = len(segments)
    closed = stroke.is_closed()
    for index in range(count):
        for other in range(index + 2, count):
            if closed and index == 0 and other == count - 1:
                continue
            if segments_cross(*segments[index], *segments[other]):
                return True
    return False


def _default_step(stroke: Stroke, min_arc: float) -> float:
    """How finely to walk a stroke that did not say."""
    if min_arc > 0.0:
        return min_arc / 4.0
    return max(stroke.length() / 64.0, QUANTUM)


def _walk(stroke: Stroke, step: float) -> list[tuple[float, Point]]:
    """Points along the stroke with the distance walked to each."""
    if step <= 0.0:
        raise ValueError(f"a walking step must be positive, got {step}")
    samples: list[tuple[float, Point]] = [(0.0, stroke.start)]
    walked = 0.0
    for first, second in stroke.segments:
        span = first.distance_to(second)
        if span < QUANTUM:
            continue
        pieces = max(1, math.ceil(span / step))
        for piece in range(1, pieces + 1):
            samples.append((walked + span * piece / pieces, first.lerp(second, piece / pieces)))
        walked += span
    return samples


def closest_approach(
    strokes: Iterable[Stroke],
    *,
    cutoff: float | None = None,
    touch: float = QUANTUM,
) -> float:
    """The smallest gap between any two strokes that do not meet.

    A pair that meets anywhere is thrown away whole, not just at the point
    where it meets. The bar of an A lands on both diagonals on purpose, and
    every measurement within a bar's length of that landing is small for the
    same reason: it is one junction, drawn deliberately, and the cutter
    filling it in is what makes an A. Keeping the pair and measuring the
    near parts of it would report that junction as a fault, in every A, on
    every plate, for ever.

    Returns infinity for fewer than two strokes, and for a group where every
    pair meets. A stroke is never compared with itself; that is
    :func:`self_approach`.
    """
    ordered = [(stroke, stroke.bounds()) for stroke in strokes]
    best = float("inf")
    for index, (left, left_box) in enumerate(ordered):
        for right, right_box in ordered[index + 1 :]:
            if left_box.gap_to(right_box) >= best:
                continue
            gap = stroke_to_stroke(left, right)
            if gap <= touch or gap >= best:
                continue
            best = gap
            if cutoff is not None and best < cutoff:
                return best
    return best
