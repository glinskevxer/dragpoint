"""Holes, bores and cutouts, and the ground the engraving has to keep off.

A legend plate is rarely a plain rectangle. It has fixing holes at the
corners, a bore for the switch it sits behind, sometimes a rectangular window
for a meter. Every one of those is a place the cutter must not go, and every
one of them takes a clearance ring on top of its own size, because a groove
that runs into the edge of a hole chips the laminate on the way past.

Clearance is measured from the edge of the feature, not from its centre.
That is the only reading that makes sense for a rectangular cutout and it is
the reading a fitter would use with a rule.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from dragpoint.errors import OutOfRange
from dragpoint.geometry.box import Box
from dragpoint.geometry.nearness import point_to_segment, segment_to_segment
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.units import QUANTUM

__all__ = ["Feature", "FeatureKind", "milled_features"]


class FeatureKind(StrEnum):
    """What the feature is, for the benefit of the drilling list.

    The geometry does not care which of these a feature is. The drilling
    list does, because a HOLE gets a drill and a BORE gets a boring head,
    and a KEEPOUT gets neither because it is not a hole at all.
    """

    HOLE = "hole"
    BORE = "bore"
    CUTOUT = "cutout"
    KEEPOUT = "keepout"


@dataclass(frozen=True, slots=True)
class Feature:
    """One thing on the plate the engraving must stay clear of.

    Round features carry their diameter in both size fields, so a rule that
    only wants a bounding box never has to ask which shape it is holding.
    """

    name: str
    kind: FeatureKind
    centre: Point
    width: float
    height: float
    is_round: bool = False
    clearance: float = 0.5

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a feature needs a name")
        if self.width <= 0.0:
            raise OutOfRange(f"{self.name} width", self.width, QUANTUM, math.inf)
        if self.height <= 0.0:
            raise OutOfRange(f"{self.name} height", self.height, QUANTUM, math.inf)
        if self.clearance < 0.0:
            raise OutOfRange(f"{self.name} clearance", self.clearance, 0.0, math.inf)
        if self.is_round and abs(self.width - self.height) > QUANTUM:
            raise ValueError(f"round feature {self.name} is {self.width} by {self.height}")

    @classmethod
    def round_hole(
        cls,
        name: str,
        centre: Point,
        diameter: float,
        *,
        kind: FeatureKind = FeatureKind.HOLE,
        clearance: float = 0.5,
    ) -> Feature:
        """A drilled hole or a bore."""
        return cls(
            name=name,
            kind=kind,
            centre=centre,
            width=diameter,
            height=diameter,
            is_round=True,
            clearance=clearance,
        )

    @classmethod
    def rectangle(
        cls,
        name: str,
        centre: Point,
        width: float,
        height: float,
        *,
        kind: FeatureKind = FeatureKind.CUTOUT,
        clearance: float = 0.5,
    ) -> Feature:
        """A rectangular cutout or a keepout zone."""
        return cls(
            name=name,
            kind=kind,
            centre=centre,
            width=width,
            height=height,
            is_round=False,
            clearance=clearance,
        )

    @property
    def diameter(self) -> float | None:
        """The diameter, or ``None`` when the feature is not round."""
        return self.width if self.is_round else None

    @property
    def radius(self) -> float:
        """Half the width. Only meaningful for a round feature."""
        return self.width / 2.0

    def bounds(self) -> Box:
        """The box round the feature itself, without any clearance."""
        return Box(
            self.centre.x - self.width / 2.0,
            self.centre.y - self.height / 2.0,
            self.centre.x + self.width / 2.0,
            self.centre.y + self.height / 2.0,
        )

    def keepout_bounds(self) -> Box:
        """The box round the feature grown by its clearance."""
        return self.bounds().grown(self.clearance)

    def distance_to(self, point: Point) -> float:
        """Distance from ``point`` to the edge of the feature.

        Negative inside. A rule that wants to know whether a stroke runs
        through a hole is asking whether this ever goes below zero, and a
        rule about clearance is asking whether it goes below the clearance.
        """
        if self.is_round:
            return self.centre.distance_to(point) - self.radius
        box = self.bounds()
        dx = max(box.min_x - point.x, 0.0, point.x - box.max_x)
        dy = max(box.min_y - point.y, 0.0, point.y - box.max_y)
        if dx == 0.0 and dy == 0.0:
            return -min(
                point.x - box.min_x,
                box.max_x - point.x,
                point.y - box.min_y,
                box.max_y - point.y,
            )
        return math.hypot(dx, dy)

    def distance_to_stroke(self, stroke: Stroke) -> float:
        """The closest any part of ``stroke`` comes to the feature edge.

        Negative when the stroke is inside the feature, which happens when a
        legend has been laid over a cutout, and zero when it crosses the
        edge. Both are the same fault to a rule but they read differently in
        a message, so the sign is kept.
        """
        if self.is_round:
            closest = min(
                point_to_segment(self.centre, first, second) for first, second in stroke.segments
            )
            return closest - self.radius
        box = self.bounds()
        corners = box.corners
        edges = [(corners[index], corners[(index + 1) % 4]) for index in range(4)]
        gap = min(
            segment_to_segment(first, second, edge_start, edge_end)
            for first, second in stroke.segments
            for edge_start, edge_end in edges
        )
        if gap <= QUANTUM:
            return 0.0
        if box.contains(stroke.start):
            return -gap
        return gap

    def clears(self, stroke: Stroke) -> bool:
        """True when ``stroke`` keeps its clearance from this feature."""
        return self.distance_to_stroke(stroke) >= self.clearance - QUANTUM

    def __str__(self) -> str:
        shape = f"{self.width:g}mm dia" if self.is_round else f"{self.width:g} by {self.height:g}mm"
        return f"{self.name} ({self.kind}, {shape} at {self.centre})"


def milled_features(features: Iterable[Feature]) -> tuple[Feature, ...]:
    """The features a profile cutter goes round, in the order they came.

    A rectangular cutout is milled. A hole is drilled, a bore is bored, and
    a keepout is not a thing at all, so none of those are here.
    """
    return tuple(item for item in features if item.kind is FeatureKind.CUTOUT and not item.is_round)
