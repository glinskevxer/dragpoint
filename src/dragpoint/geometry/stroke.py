"""A stroke is an open polyline the cutter follows from end to end.

There are no closed contours anywhere in dragpoint. A rotary engraver cuts
centrelines, so the letter O is one stroke that happens to come back near
where it started, and treating it as closed would invite fill logic that has
nowhere to go. If a glyph wants the ends joined it repeats the first point.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.transform import Transform
from dragpoint.units import QUANTUM

__all__ = ["Stroke", "join_runs"]


@dataclass(frozen=True, slots=True)
class Stroke:
    """An ordered run of points with at least two of them.

    A single point is not a stroke. The machine would plunge and lift without
    moving, which leaves a dimple rather than a line, and every rule that
    measures a direction would have to special case it. Glyphs that really
    want a dot, like the one over an i, carry a short segment instead.
    """

    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError(f"a stroke needs at least two points, got {len(self.points)}")

    @classmethod
    def of(cls, *points: Point) -> Stroke:
        """Build from positional points, which reads well in a glyph table."""
        return cls(tuple(points))

    @classmethod
    def from_pairs(cls, pairs: Iterable[tuple[float, float]]) -> Stroke:
        """Build from ``(x, y)`` tuples, which is what the font parser has."""
        return cls(tuple(Point(x, y) for x, y in pairs))

    @classmethod
    def line(cls, start: Point, end: Point) -> Stroke:
        """The common case, two points."""
        return cls((start, end))

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterator[Point]:
        return iter(self.points)

    def __getitem__(self, index: int) -> Point:
        return self.points[index]

    @property
    def start(self) -> Point:
        """The end the cutter enters from."""
        return self.points[0]

    @property
    def end(self) -> Point:
        """The end the cutter leaves from."""
        return self.points[-1]

    @property
    def segments(self) -> tuple[tuple[Point, Point], ...]:
        """Consecutive point pairs, which is what the distance tests want."""
        return tuple(zip(self.points, self.points[1:], strict=False))

    def length(self) -> float:
        """Cut length, which the cycle time estimate bills at feed rate."""
        total = 0.0
        for first, second in self.segments:
            total += first.distance_to(second)
        return total

    def bounds(self) -> Box:
        """The bounding box. Never ``None``, a stroke always has two points."""
        box = Box.around(self.points)
        assert box is not None
        return box

    def transformed(self, transform: Transform) -> Stroke:
        """This stroke mapped through ``transform``."""
        return Stroke(tuple(transform.apply(point) for point in self.points))

    def reversed(self) -> Stroke:
        """Same geometry, cut the other way.

        The travel optimiser flips strokes freely. Nothing downstream may
        depend on which end came first, and the tests say so.
        """
        return Stroke(tuple(reversed(self.points)))

    def is_closed(self, tolerance: float = QUANTUM) -> bool:
        """True when the last point lands back on the first."""
        return len(self.points) > 2 and self.start.is_close(self.end, tolerance)

    def dedupe(self, tolerance: float = QUANTUM) -> Stroke | None:
        """Drop points the machine could not distinguish from the one before.

        Returns ``None`` when nothing is left but a single position, because a
        stroke that collapses is not a stroke and the caller has to decide
        whether that is an error or a glyph that simply had a stray point.
        """
        kept: list[Point] = [self.points[0]]
        for point in self.points[1:]:
            if not point.is_close(kept[-1], tolerance):
                kept.append(point)
        if len(kept) < 2:
            return None
        return Stroke(tuple(kept))

    def simplified(self, tolerance: float) -> Stroke:
        """Douglas Peucker, to drop points a curve does not need.

        Arc mapped text arrives with far more points than the controller has
        block memory for, and the tolerance is chosen against the cutter, not
        against the screen.
        """
        if tolerance <= 0.0 or len(self.points) <= 2:
            return self
        kept = _douglas_peucker(self.points, tolerance)
        return Stroke(tuple(kept))

    def resampled(self, spacing: float) -> Stroke:
        """Subdivide every segment until no step is longer than ``spacing``.

        Used before arc mapping, where a long straight has to bend and a two
        point segment cannot. Corners survive: each segment is divided on its
        own, so an existing vertex is always still a vertex afterwards. That
        matters because a corner smoothed away by resampling comes back as a
        chamfer on the plate and nobody asked for one.
        """
        if spacing <= 0.0:
            raise ValueError(f"resample spacing must be positive, got {spacing}")
        out: list[Point] = [self.start]
        for first, second in self.segments:
            span = first.distance_to(second)
            if span < QUANTUM:
                continue
            steps = max(1, math.ceil(span / spacing))
            for step in range(1, steps + 1):
                out.append(first.lerp(second, step / steps))
        if len(out) < 2:
            return self
        return Stroke(tuple(out))

    def __str__(self) -> str:
        return " ".join(f"{point.x:g},{point.y:g}" for point in self.points)


def _douglas_peucker(points: Sequence[Point], tolerance: float) -> list[Point]:
    """The recursive half of :meth:`Stroke.simplified`."""
    if len(points) <= 2:
        return list(points)
    first = points[0]
    last = points[-1]
    worst = 0.0
    index = 0
    for position in range(1, len(points) - 1):
        offset = _point_line_distance(points[position], first, last)
        if offset > worst:
            worst = offset
            index = position
    if worst <= tolerance:
        return [first, last]
    left = _douglas_peucker(points[: index + 1], tolerance)
    right = _douglas_peucker(points[index:], tolerance)
    return left[:-1] + right


def _point_line_distance(point: Point, start: Point, end: Point) -> float:
    """Perpendicular distance to the infinite line, or to the point if degenerate."""
    span = end - start
    length = span.norm()
    if length < QUANTUM:
        return point.distance_to(start)
    return abs(span.cross(point - start)) / length


def join_runs(strokes: Iterable[Stroke], tolerance: float = QUANTUM) -> list[Stroke]:
    """Glue strokes that meet end to start into single runs.

    A glyph drawn as separate segments cuts badly, because every joint is a
    lift and a plunge and the plunge marks show. This is run before the
    travel optimiser so the optimiser only ever sees real breaks.
    """
    remaining = list(strokes)
    out: list[Stroke] = []
    while remaining:
        current = remaining.pop(0)
        merged = True
        while merged:
            merged = False
            for index, candidate in enumerate(remaining):
                if current.end.is_close(candidate.start, tolerance):
                    current = Stroke(current.points + candidate.points[1:])
                elif current.end.is_close(candidate.end, tolerance):
                    current = Stroke(current.points + candidate.reversed().points[1:])
                elif current.start.is_close(candidate.end, tolerance):
                    current = Stroke(candidate.points + current.points[1:])
                elif current.start.is_close(candidate.start, tolerance):
                    current = Stroke(candidate.reversed().points + current.points[1:])
                else:
                    continue
                remaining.pop(index)
                merged = True
                break
        out.append(current)
    return out
