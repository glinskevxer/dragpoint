"""Axis aligned bounding boxes.

Everything that has to fit inside something else on a plate gets compared as a
box first: the text block against the engraving area, the plate against the
stock sheet, a stroke against a keepout. The exact geometry only comes out
when the box test is inconclusive.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from dragpoint.geometry.point import Point

__all__ = ["Box"]


@dataclass(frozen=True, slots=True)
class Box:
    """A rectangle with sides parallel to the axes.

    An empty box is not representable. Code that might have nothing to bound
    returns ``None`` and the caller deals with it, because a sentinel box of
    infinities silently unions into every result it touches.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError(f"inverted box {self.min_x},{self.min_y} to {self.max_x},{self.max_y}")

    @classmethod
    def around(cls, points: Iterable[Point]) -> Box | None:
        """The tightest box containing every point, or ``None`` for no points."""
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        seen = False
        for point in points:
            seen = True
            min_x = min(min_x, point.x)
            min_y = min(min_y, point.y)
            max_x = max(max_x, point.x)
            max_y = max(max_y, point.y)
        if not seen:
            return None
        return cls(min_x, min_y, max_x, max_y)

    @classmethod
    def from_size(cls, width: float, height: float, origin: Point | None = None) -> Box:
        """A box of the given size with its lower left corner at ``origin``."""
        corner = origin if origin is not None else Point(0.0, 0.0)
        if width < 0.0 or height < 0.0:
            raise ValueError(f"negative box size {width} by {height}")
        return cls(corner.x, corner.y, corner.x + width, corner.y + height)

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def centre(self) -> Point:
        return Point((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    @property
    def corners(self) -> tuple[Point, Point, Point, Point]:
        """Anticlockwise from the lower left."""
        return (
            Point(self.min_x, self.min_y),
            Point(self.max_x, self.min_y),
            Point(self.max_x, self.max_y),
            Point(self.min_x, self.max_y),
        )

    def contains(self, point: Point, tolerance: float = 0.0) -> bool:
        """True when ``point`` is inside, grown by ``tolerance`` on every side."""
        return (
            self.min_x - tolerance <= point.x <= self.max_x + tolerance
            and self.min_y - tolerance <= point.y <= self.max_y + tolerance
        )

    def contains_box(self, other: Box, tolerance: float = 0.0) -> bool:
        """True when ``other`` sits entirely inside this one."""
        return (
            other.min_x >= self.min_x - tolerance
            and other.min_y >= self.min_y - tolerance
            and other.max_x <= self.max_x + tolerance
            and other.max_y <= self.max_y + tolerance
        )

    def overlaps(self, other: Box, tolerance: float = 0.0) -> bool:
        """True when the two boxes share any area, edges counting as shared."""
        return not (
            other.min_x > self.max_x + tolerance
            or other.max_x < self.min_x - tolerance
            or other.min_y > self.max_y + tolerance
            or other.max_y < self.min_y - tolerance
        )

    def union(self, other: Box) -> Box:
        """The smallest box containing both."""
        return Box(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )

    def grown(self, margin: float) -> Box:
        """This box with every side moved out by ``margin``.

        A negative margin shrinks, and shrinking past the centre collapses the
        box onto its centre line rather than inverting it. Callers use this to
        take a keepout clearance off an engraving area and an inverted box
        there would read as an area that accepts nothing, which is wrong in a
        way nothing downstream would notice.
        """
        min_x = self.min_x - margin
        max_x = self.max_x + margin
        min_y = self.min_y - margin
        max_y = self.max_y + margin
        if min_x > max_x:
            min_x = max_x = (self.min_x + self.max_x) / 2.0
        if min_y > max_y:
            min_y = max_y = (self.min_y + self.max_y) / 2.0
        return Box(min_x, min_y, max_x, max_y)

    def moved(self, delta: Point) -> Box:
        """This box translated by ``delta``."""
        return Box(
            self.min_x + delta.x,
            self.min_y + delta.y,
            self.max_x + delta.x,
            self.max_y + delta.y,
        )

    def __str__(self) -> str:
        return f"[{self.min_x:.3f},{self.min_y:.3f} {self.max_x:.3f},{self.max_y:.3f}]"
