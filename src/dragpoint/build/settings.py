"""The machine settings that are not in the job and not in the plate.

A job says what to cut. A plate says what it says. Neither of them says how
high the head lifts between letters, and neither should: those are properties
of the machine and the fixture, they change when the vice is moved, and they
are the same for every plate cut in that setup.

Feeds are the exception and they are not here. A feed rate belongs to the
material, comes off the stock table, and changes with the plate rather than
with the machine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.path.cut import PassOrder
from dragpoint.units import QUANTUM

__all__ = ["MachineSetup"]


@dataclass(frozen=True, slots=True)
class MachineSetup:
    """How the machine is set up for this run.

    ``origin`` is where the head sits at the start and where it is expected
    to be at the end. It matters to the travel figures and to nothing else,
    which is why it is a machine setting rather than something the plate
    knows about.
    """

    safe: float = 5.0
    clearance: float = 0.5
    hop_limit: float = 25.0
    pass_order: PassOrder = PassOrder.BY_PASS
    allow_reverse: bool = True
    optimise_rounds: int = 2
    spring_pass: bool = False
    origin: Point = Point(0.0, 0.0)
    rapid_rate: float = 6000.0

    def __post_init__(self) -> None:
        if self.clearance <= 0.0:
            raise OutOfRange("clearance", self.clearance, QUANTUM, math.inf)
        if self.safe <= self.clearance:
            raise OutOfRange("safe height", self.safe, self.clearance, math.inf)
        if self.hop_limit < 0.0:
            raise OutOfRange("hop limit", self.hop_limit, 0.0, math.inf)
        if self.optimise_rounds < 0:
            raise OutOfRange("optimise rounds", self.optimise_rounds, 0, math.inf)
        if self.rapid_rate <= 0.0:
            raise OutOfRange("rapid rate", self.rapid_rate, QUANTUM, math.inf)

    @property
    def optimises(self) -> bool:
        """True when the travel optimiser will do anything at all."""
        return self.optimise_rounds > 0

    def without_optimising(self) -> MachineSetup:
        """A copy with the travel optimiser turned off.

        Used to measure what the optimiser was worth, and by anyone who
        needs the cuts in the order the plate was laid out in.
        """
        return replace(self, optimise_rounds=0)

    def at_origin(self, origin: Point) -> MachineSetup:
        """A copy starting somewhere else."""
        return replace(self, origin=origin)

    def __str__(self) -> str:
        parts = [
            f"safe {self.safe:g}mm",
            f"clearance {self.clearance:g}mm",
            f"hop over {self.hop_limit:g}mm",
            str(self.pass_order),
        ]
        if not self.allow_reverse:
            parts.append("no reversing")
        if self.spring_pass:
            parts.append("spring pass")
        return ", ".join(parts)
