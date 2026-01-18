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

The rack itself is a file rather than a table in here. Stock is bought, and
the shop that buys it is the one that knows what it cut at: a new colour of
laminate arriving on a Tuesday should not need anybody to edit Python. The
shipped file is what this shop runs, and ``load_rack`` reads somebody
else's.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dragpoint.errors import OutOfRange, StockError
from dragpoint.units import QUANTUM

__all__ = ["MATERIALS", "Material", "load_rack", "material", "parse_rack"]

RACK_FILE = Path(__file__).resolve().parent / "stock" / "rack.toml"
"""The rack this shop runs, shipped inside the package."""

REQUIRED = ("description", "thickness", "nominal", "per_pass", "feed", "plunge", "spindle")
"""What every entry in a rack file has to say. ``cap`` is the only option."""

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


def parse_rack(text: str, *, source: str = "rack") -> dict[str, Material]:
    """Read a rack out of the text of a rack file.

    Every table in the file is one stock code, and the code is the table
    name. A file with nothing in it is refused rather than treated as an
    empty rack: an empty rack means every plate in every job fails on stock
    it cannot find, which is a confusing way to be told a file is wrong.
    """
    try:
        loaded = tomllib.loads(text)
    except tomllib.TOMLDecodeError as bad:
        raise StockError(source, "", f"this is not a rack file: {bad}") from bad
    if not loaded:
        raise StockError(source, "", "there is no stock in this file")
    rack: dict[str, Material] = {}
    for code, entry in loaded.items():
        if not isinstance(entry, dict):
            raise StockError(source, code, "this should be a table of numbers")
        rack[code] = _sheet(source, code, entry)
    return rack


def load_rack(path: Path | str) -> dict[str, Material]:
    """Read a rack from a file on disk."""
    resolved = Path(path)
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as bad:
        raise StockError(str(resolved), "", f"cannot read the file: {bad}") from bad
    return parse_rack(text, source=str(resolved))


def _sheet(source: str, code: str, entry: dict[str, Any]) -> Material:
    """One entry, checked and turned into a sheet."""
    missing = [key for key in REQUIRED if key not in entry]
    if missing:
        raise StockError(source, code, f"nothing says {', '.join(missing)}")
    extra = set(entry) - set(REQUIRED) - {"cap"}
    if extra:
        raise StockError(source, code, f"nothing here uses {', '.join(sorted(extra))}")
    try:
        sheet = Material(
            name=code,
            description=str(entry["description"]),
            thickness=float(entry["thickness"]),
            cap=None if entry.get("cap") is None else float(entry["cap"]),
            nominal_depth=float(entry["nominal"]),
            max_depth_per_pass=float(entry["per_pass"]),
            feed=float(entry["feed"]),
            plunge_feed=float(entry["plunge"]),
            spindle=int(entry["spindle"]),
        )
    except (TypeError, ValueError) as bad:
        raise StockError(source, code, f"one of these is not a number: {bad}") from bad
    except OutOfRange as bad:
        raise StockError(source, code, str(bad)) from bad
    return sheet


MATERIALS: dict[str, Material] = load_rack(RACK_FILE)
"""What the rack holds. Names are the ones on the stock label."""


def material(name: str) -> Material:
    """Look a sheet up by its stock code."""
    try:
        return MATERIALS[name]
    except KeyError:
        known = ", ".join(sorted(MATERIALS))
        raise KeyError(f"no stock called {name!r}, the rack holds {known}") from None
