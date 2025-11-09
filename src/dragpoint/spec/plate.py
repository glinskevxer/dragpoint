"""One plate as the drawing office specified it.

This is the whole work order for a single plate: how big it is, what it says,
what it is cut from and what has to be drilled in it. It is inert. Nothing
here shapes text, measures a groove or decides a depth, because a spec that
worked things out would be a spec that could disagree with the compiler about
what was asked for.

The engraving area is the plate less its margin. Everything the cutter does
happens inside that box, and the margin exists because the guillotine that
cut the blank is not accurate to a tenth and the edge of a laminate sheet
chips if a groove runs into it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from dragpoint.errors import OutOfRange
from dragpoint.geometry.arc import ArcMap
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign, VAlign
from dragpoint.text.style import TextStyle
from dragpoint.units import QUANTUM

__all__ = ["PlateSpec"]

DEFAULT_FACE = "panelgothic"
"""The house face, used unless a plate names another."""

DEFAULT_MARGIN = 2.0
"""Millimetres round the plate that nothing is engraved in."""

DEFAULT_CAP_HEIGHT = 3.0
"""Millimetres of capital height, which is most of the legend work."""

DEFAULT_ARC_SWEEP = 180.0
"""Degrees a legend on an arc may take up before it is too far round."""


@dataclass(frozen=True, slots=True)
class PlateSpec:
    """A plate, as ordered.

    ``depth`` and ``cutter`` are optional because most orders do not name
    them. Left out, the depth comes from the stock and the cutter comes from
    whatever the job says is in the spindle, and both of those decisions are
    made downstream where the stock and the machine are both known.
    """

    name: str
    width: float
    height: float
    stock: str
    lines: tuple[str, ...] = ()
    face: str = DEFAULT_FACE
    cap_height: float = DEFAULT_CAP_HEIGHT
    tracking: float = 0.0
    condense: float = 1.0
    slant: float = 0.0
    word_space: float | None = None
    line_pitch: float | None = None
    kerning: bool = True
    mirror: bool = False
    margin: float = DEFAULT_MARGIN
    halign: HAlign = HAlign.CENTRE
    valign: VAlign = VAlign.MIDDLE
    fit: FitPolicy = FitPolicy.CONDENSE
    features: tuple[Feature, ...] = ()
    depth: float | None = None
    cutter: str | None = None
    quantity: int = 1
    border: float | None = None
    wrap: bool = False
    arc_radius: float | None = None
    arc_centre: Point | None = None
    arc_start: float = 90.0
    arc_sweep: float = DEFAULT_ARC_SWEEP
    arc_clockwise: bool = False
    arc_inward: bool = False
    notes: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a plate needs a name")
        if self.width <= 0.0:
            raise OutOfRange(f"{self.name} width", self.width, QUANTUM, math.inf)
        if self.height <= 0.0:
            raise OutOfRange(f"{self.name} height", self.height, QUANTUM, math.inf)
        if self.margin < 0.0:
            raise OutOfRange(f"{self.name} margin", self.margin, 0.0, math.inf)
        if self.quantity < 1:
            raise OutOfRange(f"{self.name} quantity", self.quantity, 1, math.inf)
        if self.depth is not None and self.depth <= 0.0:
            raise OutOfRange(f"{self.name} depth", self.depth, QUANTUM, math.inf)
        if 2.0 * self.margin >= min(self.width, self.height):
            raise OutOfRange(
                f"{self.name} margin",
                self.margin,
                0.0,
                min(self.width, self.height) / 2.0,
            )
        if self.border is not None:
            if self.border < 0.0:
                raise OutOfRange(f"{self.name} border", self.border, 0.0, math.inf)
            if 2.0 * self.border >= min(self.width, self.height):
                raise OutOfRange(
                    f"{self.name} border",
                    self.border,
                    0.0,
                    min(self.width, self.height) / 2.0,
                )
        if self.arc_radius is not None and self.arc_radius <= 0.0:
            raise OutOfRange(f"{self.name} arc radius", self.arc_radius, QUANTUM, math.inf)
        if not 0.0 < self.arc_sweep <= 360.0:
            raise OutOfRange(f"{self.name} arc sweep", self.arc_sweep, QUANTUM, 360.0)
        for line in self.lines:
            if "\n" in line:
                raise ValueError(f"{self.name} has a line with a newline in it")

    def outline(self) -> Box:
        """The blank, with its lower left corner on the origin."""
        return Box(0.0, 0.0, self.width, self.height)

    def area(self) -> Box:
        """The box the engraving has to stay inside."""
        return self.outline().grown(-self.margin)

    def border_box(self) -> Box | None:
        """The engraved border, or ``None`` when the plate has none."""
        if self.border is None:
            return None
        return self.outline().grown(-self.border)

    def arc(self) -> ArcMap | None:
        """The arc the legend is set round, or ``None`` for straight text.

        With no centre given the arc is centred on the plate, which is what
        a rotary switch legend wants: the bore is in the middle and the
        words go round it.
        """
        if self.arc_radius is None:
            return None
        centre = self.arc_centre if self.arc_centre is not None else self.outline().centre
        return ArcMap(
            centre=centre,
            radius=self.arc_radius,
            start=self.arc_start,
            clockwise=self.arc_clockwise,
            outward=not self.arc_inward,
        )

    def fit_limit(self) -> float:
        """How wide the legend may be before the fitter has to do something.

        Straight text is limited by the engraving area. Text on an arc is
        limited by how far round it is allowed to go, which is a length on
        the arc and has nothing to do with how wide the plate is.
        """
        arc = self.arc()
        if arc is None:
            return self.area().width
        return arc.radius * math.radians(self.arc_sweep)

    def style(self) -> TextStyle:
        """The text style this plate asks for, before any fitting."""
        return TextStyle(
            cap_height=self.cap_height,
            tracking=self.tracking,
            word_space=self.word_space,
            slant=self.slant,
            condense=self.condense,
            kerning=self.kerning,
            mirror=self.mirror,
            line_pitch=self.line_pitch,
        )

    def feature(self, name: str) -> Feature:
        """Look up one feature by name."""
        for item in self.features:
            if item.name == name:
                return item
        known = ", ".join(item.name for item in self.features) or "none"
        raise KeyError(f"plate {self.name} has no feature {name!r}, it has {known}")

    def features_outside_the_blank(self) -> tuple[Feature, ...]:
        """Features that do not fit on the plate they were put on.

        Reported rather than refused. A spec that came out of a schedule
        with a transposed coordinate should say which feature is wrong, and
        raising at construction time would name only the first one.
        """
        outline = self.outline()
        return tuple(
            item for item in self.features if not outline.contains_box(item.bounds(), QUANTUM)
        )

    @property
    def is_blank_plate(self) -> bool:
        """True when nothing at all is engraved on it."""
        return not any(line.strip() for line in self.lines) and self.border is None

    def has_tag(self, tag: str) -> bool:
        """True when the plate carries ``tag``.

        Tags come off the schedule and are how a job says a plate is urgent,
        or is a remake, or belongs to a particular panel.
        """
        return tag in self.tags

    def __str__(self) -> str:
        text = " / ".join(line for line in self.lines if line) or "blank"
        return f"{self.name} {self.width:g}x{self.height:g}mm {self.stock}: {text}"
