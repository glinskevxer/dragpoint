"""A point on the plate, and the handful of things worth doing to one."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from dragpoint.units import QUANTUM, quantise

__all__ = ["Point", "centroid", "polyline_length"]


@dataclass(frozen=True, slots=True)
class Point:
    """A position in millimetres, x to the right and y up.

    Y up is the drafting convention and the one the DXF export wants. The
    controllers all agree. Screen coordinates are the odd one out and the SVG
    writer is the only place that flips.
    """

    x: float
    y: float

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, factor: float) -> Point:
        return Point(self.x * factor, self.y * factor)

    __rmul__ = __mul__

    def __neg__(self) -> Point:
        return Point(-self.x, -self.y)

    def distance_to(self, other: Point) -> float:
        """Straight line distance, which is the only kind a rapid move makes."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def norm(self) -> float:
        """Distance from the origin."""
        return math.hypot(self.x, self.y)

    def dot(self, other: Point) -> float:
        """Scalar product, used by the corner tests in the path planner."""
        return self.x * other.x + self.y * other.y

    def cross(self, other: Point) -> float:
        """Signed area of the parallelogram, so positive means a left turn."""
        return self.x * other.y - self.y * other.x

    def unit(self) -> Point:
        """This point as a direction of length one.

        A zero length vector has no direction and returning ``(0, 0)`` here
        would let a degenerate stroke travel silently through the lead in
        code, so it raises instead.
        """
        length = self.norm()
        if length < QUANTUM:
            raise ValueError("a zero length vector has no direction")
        return Point(self.x / length, self.y / length)

    def perpendicular(self) -> Point:
        """Rotated a quarter turn to the left, which is the offset direction."""
        return Point(-self.y, self.x)

    def lerp(self, other: Point, t: float) -> Point:
        """The point ``t`` of the way from here to ``other``."""
        return Point(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)

    def quantised(self, quantum: float = QUANTUM) -> Point:
        """Both coordinates snapped, for output and for dictionary keys."""
        return Point(quantise(self.x, quantum), quantise(self.y, quantum))

    def is_close(self, other: Point, tolerance: float = QUANTUM) -> bool:
        """True when the machine could not tell these two apart."""
        return abs(self.x - other.x) < tolerance and abs(self.y - other.y) < tolerance

    def __str__(self) -> str:
        return f"({self.x:.4f}, {self.y:.4f})"


ORIGIN = Point(0.0, 0.0)


def centroid(points: Iterable[Point]) -> Point:
    """Arithmetic mean of the points, which is not the area centroid.

    The path planner wants a cheap representative position for a stroke and
    this is it. Nothing here treats it as a centre of mass.
    """
    total_x = 0.0
    total_y = 0.0
    count = 0
    for point in points:
        total_x += point.x
        total_y += point.y
        count += 1
    if count == 0:
        raise ValueError("no points to average")
    return Point(total_x / count, total_y / count)


def polyline_length(points: Iterable[Point]) -> float:
    """Total length walked along the points in order."""
    total = 0.0
    previous: Point | None = None
    for point in points:
        if previous is not None:
            total += previous.distance_to(point)
        previous = point
    return total
