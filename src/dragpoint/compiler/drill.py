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

Holes are grouped by diameter and each group is a program of its own. There
is one drill in the spindle at a time, so a plate with a 3.2 and two 6 mm
holes on it is a 3.2 program, a drill change and a 6 mm program. Walking the
holes in the order they sit on the plate would be the shortest path and
would also mean changing the drill at every hole, which is the sort of
optimisation that only looks like one.

The small drill goes first. A small drill dropped into a hole a big one has
already opened has nothing to centre it and wanders off across the plate,
and the other way round the big one just opens the small one out.
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

__all__ = ["DEFAULT_PECK", "DrillPlan", "DrillRun", "drill_plate", "drillable"]

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
class DrillRun:
    """Every hole of one diameter, and the program that makes them.

    One run is one drill. What the operator does between runs is change it,
    which is why they are kept apart rather than merged into one program
    that would be shorter and unrunnable.
    """

    diameter: float
    holes: tuple[Feature, ...]
    toolpath: Toolpath

    def __len__(self) -> int:
        return len(self.holes)

    def __str__(self) -> str:
        return f"{self.diameter:g}mm: {len(self.holes)} holes"


@dataclass(frozen=True, slots=True)
class DrillPlan:
    """Every hole on one plate, drill by drill."""

    plate: PlateSpec
    stock: Material
    holes: tuple[Feature, ...]
    depth: float
    peck: float
    runs: tuple[DrillRun, ...]

    @property
    def name(self) -> str:
        """The plate these holes belong to."""
        return self.plate.name

    @property
    def toolpath(self) -> Toolpath:
        """Every run's moves end to end, for a caller that wants one path.

        Useful for measuring and for drawing. Not useful for cutting, since
        it runs three drills without stopping to change any of them, and a
        caller posting a file wants :attr:`runs`.
        """
        moves = tuple(move for run in self.runs for move in run.toolpath.moves)
        first = self.runs[0].toolpath if self.runs else None
        return Toolpath(
            moves=moves,
            safe=first.safe if first else Toolpath().safe,
            clearance=first.clearance if first else Toolpath().clearance,
        )

    @property
    def tool_changes(self) -> int:
        """How many times the drill comes out and another goes in."""
        return max(0, len(self.runs) - 1)

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

    def run_for(self, diameter: float) -> DrillRun:
        """The run for one diameter."""
        for run in self.runs:
            if abs(run.diameter - diameter) < QUANTUM:
                return run
        listed = ", ".join(f"{size:g}" for size in self.diameters()) or "none"
        raise KeyError(f"{self.name} has no {diameter:g}mm holes, it has {listed}")

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

    runs: list[DrillRun] = []
    here = machine.origin
    for diameter in sorted({hole.width for hole in holes}):
        group = tuple(hole for hole in holes if abs(hole.width - diameter) < QUANTUM)
        ordered = _nearest_order(group, here)
        moves: list[Move] = []
        for hole in ordered:
            moves.extend(_cycle(hole, depth, peck, machine, sheet.plunge_feed))
        here = ordered[-1].centre if ordered else here
        runs.append(
            DrillRun(
                diameter=diameter,
                holes=tuple(ordered),
                toolpath=Toolpath(
                    moves=tuple(moves), safe=machine.safe, clearance=machine.clearance
                ),
            )
        )
    return DrillPlan(
        plate=spec,
        stock=sheet,
        holes=holes,
        depth=depth,
        peck=peck,
        runs=tuple(runs),
    )
