"""The cutter, and the one fact that drives the whole package.

A rotary engraving cutter is a cone with a flat on the end. The flat is the
tip width and it is the narrowest line the cutter can leave. Go deeper and
the cone is doing the cutting, so the groove gets wider::

    width(depth) = tip + 2 * depth * tan(included / 2)

Every legibility question in this package reduces to that expression. Two
centrelines 0.5 mm apart are two lines at 0.2 mm deep with a 0.3 mm 30 degree
cutter, and one filled in blob at 0.6 mm deep with the same cutter, and the
only thing that changed was a number on a setup sheet.

A parallel cutter, which the trade calls a flat or a burr, has an included
angle of zero and leaves the same width however deep it goes. That is not a
special case in the arithmetic, it falls out of ``tan(0)``, but it is a
special case in the depth rule, because there is no depth that makes it
narrower.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.units import QUANTUM

__all__ = ["CATALOGUE", "Cutter", "catalogue_cutter"]


@dataclass(frozen=True, slots=True)
class Cutter:
    """One cutter as it appears in the tool crib.

    ``max_depth`` is what the flute length and the cone geometry allow, not
    what the material allows. Material limits live with the material.
    """

    name: str
    tip_width: float
    included_angle: float
    shank: float = 3.175
    flutes: int = 1
    max_depth: float = 1.5

    def __post_init__(self) -> None:
        if self.tip_width <= 0.0:
            raise OutOfRange("tip width", self.tip_width, QUANTUM, math.inf)
        if not 0.0 <= self.included_angle < 180.0:
            raise OutOfRange("included angle", self.included_angle, 0.0, 180.0)
        if self.shank <= 0.0:
            raise OutOfRange("shank", self.shank, QUANTUM, math.inf)
        if self.flutes < 1:
            raise OutOfRange("flutes", self.flutes, 1, 4)
        if self.max_depth <= 0.0:
            raise OutOfRange("max depth", self.max_depth, QUANTUM, math.inf)

    @property
    def is_parallel(self) -> bool:
        """True when the cutter leaves the same width at any depth."""
        return self.included_angle == 0.0

    @property
    def taper(self) -> float:
        """Width gained per millimetre of depth. Zero for a parallel cutter."""
        return 2.0 * math.tan(math.radians(self.included_angle / 2.0))

    def width_at_depth(self, depth: float) -> float:
        """The groove width this cutter leaves at ``depth`` millimetres."""
        if depth < 0.0:
            raise OutOfRange("depth", depth, 0.0, self.max_depth)
        if depth > self.max_depth:
            raise OutOfRange("depth", depth, 0.0, self.max_depth)
        return self.tip_width + depth * self.taper

    def depth_for_width(self, width: float) -> float:
        """The depth that leaves a groove ``width`` millimetres wide.

        Raises when the cutter cannot leave a groove that narrow, which is
        anything under the tip, and when a parallel cutter is asked for any
        width but its own.
        """
        if width < self.tip_width - QUANTUM:
            raise OutOfRange("width", width, self.tip_width, math.inf)
        if self.is_parallel:
            if abs(width - self.tip_width) > QUANTUM:
                raise OutOfRange("width", width, self.tip_width, self.tip_width)
            return 0.0
        depth = (width - self.tip_width) / self.taper
        if depth > self.max_depth:
            raise OutOfRange("depth", depth, 0.0, self.max_depth)
        # A width inside the quantum of the tip got past the check above and
        # divides to a small negative depth. Zero is what that means.
        return max(0.0, depth)

    def widest_groove(self) -> float:
        """The widest groove this cutter can leave at all."""
        return self.width_at_depth(self.max_depth)

    def __str__(self) -> str:
        if self.is_parallel:
            return f"{self.name} (parallel, {self.tip_width:g}mm)"
        return f"{self.name} ({self.included_angle:g} deg, {self.tip_width:g}mm tip)"


CATALOGUE: dict[str, Cutter] = {
    cutter.name: cutter
    for cutter in (
        Cutter(name="V10-005", tip_width=0.127, included_angle=10.0, max_depth=1.0),
        Cutter(name="V20-010", tip_width=0.254, included_angle=20.0, max_depth=1.2),
        Cutter(name="V30-010", tip_width=0.254, included_angle=30.0, max_depth=1.5),
        Cutter(name="V30-015", tip_width=0.381, included_angle=30.0, max_depth=1.5),
        Cutter(name="V45-015", tip_width=0.381, included_angle=45.0, max_depth=1.5),
        Cutter(name="V60-020", tip_width=0.508, included_angle=60.0, max_depth=1.5),
        Cutter(name="V90-030", tip_width=0.762, included_angle=90.0, max_depth=1.0),
        Cutter(name="P-010", tip_width=0.254, included_angle=0.0, max_depth=2.0, flutes=2),
        Cutter(name="P-020", tip_width=0.508, included_angle=0.0, max_depth=3.0, flutes=2),
        Cutter(name="P-030", tip_width=0.794, included_angle=0.0, max_depth=4.0, flutes=2),
    )
}
"""The cutters the crib actually holds. Names are the ones on the tube."""


def catalogue_cutter(name: str) -> Cutter:
    """Look a cutter up by its catalogue name."""
    try:
        return CATALOGUE[name]
    except KeyError:
        known = ", ".join(sorted(CATALOGUE))
        raise KeyError(f"no cutter called {name!r}, the crib holds {known}") from None
