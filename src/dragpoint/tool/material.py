"""Engraving stock, and the depth window each sheet allows.

Two ply laminate is the stock most legend plates are cut from: a thin
coloured cap over a core of another colour. The engraving is only visible
where the cap has been cut through, so there is a floor on the depth as well
as a ceiling, and the window between them is often under half a millimetre.

    cap thickness + break through        <= depth <=  sheet - backing left

Solid stock has no floor. It shows because the groove catches the light, and
it will show at any depth the cutter can reach.

Getting the floor wrong is the expensive mistake. A plate cut a hundredth
short of the cap reads perfectly under the shop lights and disappears on the
panel, and by then it has been screwed down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.units import QUANTUM

__all__ = ["MATERIALS", "Material", "material"]

BREAK_THROUGH = 0.05
"""Millimetres past the cap that guarantees a clean colour change."""

BACKING_LEFT = 0.30
"""Millimetres of sheet that must stay under the groove so it holds together."""


@dataclass(frozen=True, slots=True)
class Material:
    """A sheet as it comes off the rack, with the numbers to cut it by.

    ``cap`` is ``None`` for solid stock. Everything else is millimetres
    except the spindle speed, which is revolutions per minute, and the feeds,
    which are millimetres per minute because that is what the controllers
    take.
    """

    name: str
    description: str
    thickness: float
    cap: float | None
    nominal_depth: float
    max_depth_per_pass: float
    feed: float
    plunge_feed: float
    spindle: int

    def __post_init__(self) -> None:
        if self.thickness <= 0.0:
            raise OutOfRange("thickness", self.thickness, QUANTUM, math.inf)
        if self.cap is not None and not 0.0 < self.cap < self.thickness:
            raise OutOfRange("cap", self.cap, QUANTUM, self.thickness)
        if self.max_depth_per_pass <= 0.0:
            raise OutOfRange("max depth per pass", self.max_depth_per_pass, QUANTUM, math.inf)
        if self.feed <= 0.0:
            raise OutOfRange("feed", self.feed, QUANTUM, math.inf)
        if self.plunge_feed <= 0.0:
            raise OutOfRange("plunge feed", self.plunge_feed, QUANTUM, math.inf)
        if self.spindle < 0:
            raise OutOfRange("spindle", self.spindle, 0, 30000)
        low, high = self.depth_window()
        if low > high:
            raise OutOfRange("nominal depth", self.nominal_depth, low, high)
        if not low <= self.nominal_depth <= high:
            raise OutOfRange("nominal depth", self.nominal_depth, low, high)

    @property
    def is_two_ply(self) -> bool:
        """True when the colour only appears once the cap is cut through."""
        return self.cap is not None

    def depth_window(self) -> tuple[float, float]:
        """The shallowest and deepest cut this sheet will take."""
        floor = 0.0 if self.cap is None else self.cap + BREAK_THROUGH
        ceiling = self.thickness - BACKING_LEFT
        return (floor, ceiling)

    def accepts_depth(self, depth: float) -> bool:
        """True when ``depth`` is inside the window, edges included."""
        low, high = self.depth_window()
        return low - QUANTUM <= depth <= high + QUANTUM

    def require_depth(self, depth: float) -> float:
        """Return ``depth`` if this sheet will take it, else raise."""
        low, high = self.depth_window()
        if not self.accepts_depth(depth):
            raise OutOfRange(f"depth in {self.name}", depth, low, high)
        return depth

    def passes_for(self, depth: float) -> int:
        """How many passes it takes to get to ``depth`` on this stock."""
        if depth <= 0.0:
            return 0
        return math.ceil(depth / self.max_depth_per_pass - QUANTUM)

    def __str__(self) -> str:
        kind = f"{self.cap:g}mm cap" if self.cap is not None else "solid"
        return f"{self.name} ({self.description}, {self.thickness:g}mm, {kind})"


MATERIALS: dict[str, Material] = {
    sheet.name: sheet
    for sheet in (
        Material(
            name="LAM16-BW",
            description="black on white laminate",
            thickness=1.6,
            cap=0.13,
            nominal_depth=0.25,
            max_depth_per_pass=0.35,
            feed=1200.0,
            plunge_feed=300.0,
            spindle=12000,
        ),
        Material(
            name="LAM16-WB",
            description="white on black laminate",
            thickness=1.6,
            cap=0.13,
            nominal_depth=0.25,
            max_depth_per_pass=0.35,
            feed=1200.0,
            plunge_feed=300.0,
            spindle=12000,
        ),
        Material(
            name="LAM32-RW",
            description="red on white laminate",
            thickness=3.2,
            cap=0.25,
            nominal_depth=0.40,
            max_depth_per_pass=0.35,
            feed=1000.0,
            plunge_feed=250.0,
            spindle=12000,
        ),
        Material(
            name="LAM32-YB",
            description="yellow on black laminate",
            thickness=3.2,
            cap=0.25,
            nominal_depth=0.40,
            max_depth_per_pass=0.35,
            feed=1000.0,
            plunge_feed=250.0,
            spindle=12000,
        ),
        Material(
            name="ANOD-10",
            description="anodised aluminium",
            thickness=1.0,
            cap=0.02,
            nominal_depth=0.10,
            max_depth_per_pass=0.10,
            feed=600.0,
            plunge_feed=120.0,
            spindle=15000,
        ),
        Material(
            name="ACRYL-30",
            description="clear acrylic",
            thickness=3.0,
            cap=None,
            nominal_depth=0.50,
            max_depth_per_pass=0.50,
            feed=900.0,
            plunge_feed=200.0,
            spindle=14000,
        ),
        Material(
            name="BRASS-15",
            description="half hard brass",
            thickness=1.5,
            cap=None,
            nominal_depth=0.15,
            max_depth_per_pass=0.08,
            feed=250.0,
            plunge_feed=60.0,
            spindle=8000,
        ),
        Material(
            name="STAIN-10",
            description="304 stainless",
            thickness=1.0,
            cap=None,
            nominal_depth=0.08,
            max_depth_per_pass=0.04,
            feed=120.0,
            plunge_feed=30.0,
            spindle=6000,
        ),
    )
}
"""What the rack holds. Names are the ones on the stock label."""


def material(name: str) -> Material:
    """Look a sheet up by its stock code."""
    try:
        return MATERIALS[name]
    except KeyError:
        known = ", ".join(sorted(MATERIALS))
        raise KeyError(f"no stock called {name!r}, the rack holds {known}") from None
