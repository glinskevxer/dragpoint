"""A job: the plates, the sheet they come off, and the machine settings.

One job is one setup. The cutter goes in the spindle once, the sheet goes on
the bed once, and every plate in the job is cut without anybody touching the
machine in between. That is why the cutter lives on the job and not on the
plate: a plate that wanted a different cutter would be a different job, and
pretending otherwise produces a program that quietly cuts half the panel with
the wrong tool.

A plate may still override the depth, because depth is a property of the
stock and a job can hold plates cut from two different sheets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.spec.plate import PlateSpec
from dragpoint.units import QUANTUM

__all__ = ["JobSpec", "Sheet"]

DEFAULT_CUTTER = "V30-015"
"""What is in the spindle unless the job says otherwise."""

DEFAULT_SHEET_MARGIN = 5.0
"""Millimetres round the sheet the clamps sit on."""

DEFAULT_KERF = 1.5
"""Millimetres between nested pieces for the parting cut."""


@dataclass(frozen=True, slots=True)
class Sheet:
    """The blank the plates are cut out of.

    ``margin`` is the strip round the edge the clamps sit on, so nothing can
    be nested there. ``kerf`` is the gap left between plates for the parting
    cut, which on a rotary machine is the cutter diameter plus a little.
    """

    stock: str
    width: float
    height: float
    margin: float = DEFAULT_SHEET_MARGIN
    kerf: float = DEFAULT_KERF

    def __post_init__(self) -> None:
        if self.width <= 0.0:
            raise OutOfRange("sheet width", self.width, QUANTUM, math.inf)
        if self.height <= 0.0:
            raise OutOfRange("sheet height", self.height, QUANTUM, math.inf)
        if self.margin < 0.0:
            raise OutOfRange("sheet margin", self.margin, 0.0, math.inf)
        if self.kerf < 0.0:
            raise OutOfRange("kerf", self.kerf, 0.0, math.inf)
        if 2.0 * self.margin >= min(self.width, self.height):
            raise OutOfRange("sheet margin", self.margin, 0.0, min(self.width, self.height) / 2.0)

    @property
    def usable_width(self) -> float:
        """Width inside the clamp margins."""
        return self.width - 2.0 * self.margin

    @property
    def usable_height(self) -> float:
        """Height inside the clamp margins."""
        return self.height - 2.0 * self.margin

    @property
    def usable_area(self) -> float:
        """Square millimetres a plate could be nested on."""
        return self.usable_width * self.usable_height

    def __str__(self) -> str:
        return f"{self.stock} {self.width:g}x{self.height:g}mm"


@dataclass(frozen=True, slots=True)
class JobSpec:
    """Everything one setup needs."""

    name: str
    plates: tuple[PlateSpec, ...] = ()
    sheet: Sheet | None = None
    cutter: str = DEFAULT_CUTTER
    post: str = "iso"
    spring_pass: bool = False
    depth: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a job needs a name")
        if self.depth is not None and self.depth <= 0.0:
            raise OutOfRange(f"{self.name} depth", self.depth, QUANTUM, math.inf)
        seen: set[str] = set()
        for plate in self.plates:
            if plate.name in seen:
                raise ValueError(f"job {self.name} has two plates called {plate.name!r}")
            seen.add(plate.name)

    def plate(self, name: str) -> PlateSpec:
        """Look one plate up by name."""
        for item in self.plates:
            if item.name == name:
                return item
        known = ", ".join(item.name for item in self.plates) or "none"
        raise KeyError(f"job {self.name} has no plate {name!r}, it has {known}")

    def cutter_for(self, plate: PlateSpec) -> str:
        """The cutter a plate will actually be cut with."""
        return plate.cutter or self.cutter

    def depth_for(self, plate: PlateSpec) -> float | None:
        """The depth a plate asks for, or the job's, or nothing.

        Nothing means the stock decides, which is the usual case and the one
        the compiler resolves against the material table.
        """
        if plate.depth is not None:
            return plate.depth
        return self.depth

    def stock_codes(self) -> tuple[str, ...]:
        """Every stock code the job needs, sorted, once each."""
        codes = {plate.stock for plate in self.plates}
        if self.sheet is not None:
            codes.add(self.sheet.stock)
        return tuple(sorted(codes))

    def cutter_codes(self) -> tuple[str, ...]:
        """Every cutter the job would need, sorted, once each."""
        return tuple(sorted({self.cutter_for(plate) for plate in self.plates} or {self.cutter}))

    @property
    def piece_count(self) -> int:
        """How many pieces come off the machine, quantities counted."""
        return sum(plate.quantity for plate in self.plates)

    def __len__(self) -> int:
        return len(self.plates)

    def __str__(self) -> str:
        return f"{self.name}: {len(self.plates)} plates, {self.piece_count} pieces"
