"""The holes, as a program of their own.

Engraving and drilling are two setups. The engraver has a cutter in it and
the plate is held down flat; the drilling is done with a drill in the same
spindle and the plate is usually still on the same fixture, but never at the
same time as the lettering, because a hole cut before the legend leaves a
burr the cutter picks up and a hole cut after it leaves swarf in the groove.

So the holes come out as a second file. It is a toolpath like any other and
goes through the same post processors, which is the whole reason drilling
lives here rather than in a writer of its own.

Pecking is not optional on laminate. A drill that goes straight through
2 mm of phenolic in one plunge melts the swarf into the flutes, and the next
hole is drilled by a drill with a plug of plastic on the end of it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.compiler.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.path.plan import Move, MoveKind, Toolpath
from dragpoint.spec.feature import Feature, FeatureKind
from dragpoint.spec.plate import PlateSpec
from dragpoint.tool.material import Material, material
from dragpoint.units import QUANTUM

__all__ = ["DEFAULT_PECK", "DrillPlan", "drill_plate", "drillable"]

DEFAULT_PECK = 0.5
"""Millimetres of depth per peck, before the drill comes out to clear."""

BREAKTHROUGH = 0.5
"""Millimetres past the back of the sheet, so every hole is through."""

DRILLED = (FeatureKind.HOLE, FeatureKind.BORE)
"""The feature kinds a drill makes. A keepout is not a hole."""


def drillable(spec: PlateSpec) -> tuple[Feature, ...]:
    """The features on a plate that actually get drilled, in schedule order."""
    return tuple(item for item in spec.features if item.kind in DRILLED)


@dataclass(frozen=True, slots=True)
class DrillPlan:
    """Every hole on one plate, and the program that makes them."""

    plate: PlateSpec
    stock: Material
    holes: tuple[Feature, ...]
    depth: float
    peck: float
    toolpath: Toolpath

    @property
    def name(self) -> str:
        """The plate these holes belong to."""
        return self.plate.name

    @property
    def pecks_per_hole(self) -> int:
        """How many times the drill goes in and comes out of each hole."""
        return max(1, math.ceil(self.depth / self.peck - QUANTUM))

    def diameters(self) -> tuple[float, ...]:
        """Every distinct diameter, smallest first.

        A plate with three diameters on it is three drills and two tool
        changes, which is the number the setter wants before anything else.
        """
        return tuple(sorted({hole.width for hole in self.holes}))

    def __len__(self) -> int:
        return len(self.holes)

    def __str__(self) -> str:
        if not self.holes:
            return f"{self.name}: nothing to drill"
        listed = ", ".join(f"{size:g}mm" for size in self.diameters())
        return f"{self.name}: {len(self.holes)} holes at {listed}, {self.depth:.2f}mm deep"


def _nearest_order(holes: tuple[Feature, ...], start: Point) -> list[Feature]:
    """The holes in the order the head would sensibly visit them.

    Nearest neighbour and nothing cleverer. A plate has four fixing holes on
    it, not four hundred, and the difference between this and the best
    possible order is a rapid move nobody would notice.
    """
    remaining = list(holes)
    ordered: list[Feature] = []
    here = start
    while remaining:
        nearest = min(remaining, key=lambda hole: here.distance_to(hole.centre))
        remaining.remove(nearest)
        ordered.append(nearest)
        here = nearest.centre
    return ordered


def _cycle(
    hole: Feature, depth: float, peck: float, setup: MachineSetup, feed: float
) -> list[Move]:
    """The moves for one hole: rapid over, peck down, come out."""
    moves = [Move(MoveKind.RAPID, hole.centre, setup.safe)]
    reached = 0.0
    while reached < depth - QUANTUM:
        reached = min(depth, reached + peck)
        moves.append(Move(MoveKind.PLUNGE, hole.centre, -reached, feed))
        moves.append(Move(MoveKind.LIFT, hole.centre, setup.clearance, feed))
    moves.append(Move(MoveKind.LIFT, hole.centre, setup.safe, feed))
    return moves


def drill_plate(
    spec: PlateSpec,
    *,
    stock: Material | None = None,
    setup: MachineSetup | None = None,
    peck: float = DEFAULT_PECK,
) -> DrillPlan:
    """Work out the drilling for one plate.

    The depth is the sheet plus a breakthrough, because a hole that stops a
    tenth short of the back leaves a disc of laminate that comes out on the
    panel and takes the edge of the hole with it.
    """
    if peck <= 0.0:
        raise OutOfRange("peck", peck, QUANTUM, float("inf"))
    machine = setup or MachineSetup()
    sheet = stock if stock is not None else material(spec.stock)
    holes = drillable(spec)
    depth = sheet.thickness + BREAKTHROUGH

    moves: list[Move] = []
    for hole in _nearest_order(holes, machine.origin):
        moves.extend(_cycle(hole, depth, peck, machine, sheet.plunge_feed))
    return DrillPlan(
        plate=spec,
        stock=sheet,
        holes=holes,
        depth=depth,
        peck=peck,
        toolpath=Toolpath(moves=tuple(moves), safe=machine.safe, clearance=machine.clearance),
    )
