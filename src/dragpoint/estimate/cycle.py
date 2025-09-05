"""How long the job will actually take, which is not distance over feed.

A legend plate is thousands of moves of under a millimetre each. On a job
like that the controller spends more time reading blocks than the axes spend
moving, and an estimate built only from distance and feed rate comes out at
half the real figure. Every shop that quotes off one loses money on lettering
and makes it back on the big stuff without ever finding out why.

So there is a block time: a fixed cost per move, whatever its length. It is
the number to argue about when an estimate is wrong, and it is the only one
in here that is a property of the control rather than of the cut.

Acceleration is not modelled. Over moves this short the axes never reach the
programmed feed at all, and pretending otherwise with a trapezoid would give
a worse answer with more arithmetic. The block time absorbs it, which is why
the number that comes out of a real machine is the one to set it from.
"""

from __future__ import annotations

from dataclasses import dataclass

from dragpoint.compiler.job import EngravedJob
from dragpoint.compiler.plate import EngravedPlate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.path.plan import MoveKind, Toolpath

__all__ = ["CycleTime", "JobTime", "estimate_job", "estimate_plate"]

DEFAULT_BLOCK_TIME = 0.004
"""Seconds the control spends on a move whatever its length."""

DEFAULT_TOOL_CHANGE = 45.0
"""Seconds to change the cutter and reset the depth nose."""

DEFAULT_LOAD_TIME = 25.0
"""Seconds to take one plate off the fixture and put the next one on."""


@dataclass(frozen=True, slots=True)
class CycleTime:
    """Where the seconds go on one plate."""

    cutting: float
    plunging: float
    rapid: float
    blocks: float
    loading: float

    @property
    def total(self) -> float:
        """Every second of it."""
        return self.cutting + self.plunging + self.rapid + self.blocks + self.loading

    @property
    def minutes(self) -> float:
        """The total in minutes, which is what a quote is written in."""
        return self.total / 60.0

    @property
    def in_the_air(self) -> float:
        """Seconds not cutting, which is what there is to save."""
        return self.rapid + self.blocks + self.loading

    @property
    def cutting_fraction(self) -> float:
        """How much of the cycle is actually removing material."""
        if self.total <= 0.0:
            return 0.0
        return self.cutting / self.total

    def __str__(self) -> str:
        return (
            f"{self.minutes:.2f} min, {self.cutting_fraction:.0%} cutting "
            f"({self.cutting:.1f}s cut, {self.rapid:.1f}s rapid, {self.blocks:.1f}s blocks)"
        )


@dataclass(frozen=True, slots=True)
class JobTime:
    """The whole job, plate by plate and added up."""

    per_plate: tuple[tuple[str, int, CycleTime], ...]
    tool_changes: int
    tool_change_time: float

    @property
    def machining(self) -> float:
        """Seconds cutting pieces, quantities counted."""
        return sum(time.total * quantity for _, quantity, time in self.per_plate)

    @property
    def total(self) -> float:
        """Everything, including changing cutters."""
        return self.machining + self.tool_changes * self.tool_change_time

    @property
    def minutes(self) -> float:
        """The total in minutes."""
        return self.total / 60.0

    def for_plate(self, name: str) -> CycleTime:
        """One plate's cycle time by name."""
        for plate_name, _, time in self.per_plate:
            if plate_name == name:
                return time
        known = ", ".join(plate for plate, _, _ in self.per_plate) or "none"
        raise KeyError(f"no plate {name!r} in this estimate, there is {known}")

    def slowest(self) -> str | None:
        """The plate that takes longest for one piece."""
        if not self.per_plate:
            return None
        return max(self.per_plate, key=lambda entry: entry[2].total)[0]

    def __str__(self) -> str:
        return (
            f"{self.minutes:.1f} min for {len(self.per_plate)} plates "
            f"and {self.tool_changes} tool changes"
        )


def _seconds(distance: float, rate: float) -> float:
    """Seconds to move ``distance`` millimetres at ``rate`` per minute."""
    if rate <= 0.0:
        raise OutOfRange("rate", rate, 1e-6, float("inf"))
    return distance / rate * 60.0


def _plunge_distance(path: Toolpath) -> float:
    """How far the Z axis travels under feed, both ways."""
    total = 0.0
    here = 0.0
    for move in path:
        if move.kind in (MoveKind.PLUNGE, MoveKind.LIFT):
            total += abs(move.z - here)
        here = move.z
    return total


def estimate_plate(
    plate: EngravedPlate,
    *,
    setup: MachineSetup | None = None,
    block_time: float = DEFAULT_BLOCK_TIME,
    load_time: float = DEFAULT_LOAD_TIME,
) -> CycleTime:
    """Work out how long one plate takes."""
    if block_time < 0.0:
        raise OutOfRange("block time", block_time, 0.0, float("inf"))
    if load_time < 0.0:
        raise OutOfRange("load time", load_time, 0.0, float("inf"))
    machine = setup or MachineSetup()
    path = plate.toolpath
    return CycleTime(
        cutting=_seconds(path.cut_length(machine.origin), plate.stock.feed),
        plunging=_seconds(_plunge_distance(path), plate.stock.plunge_feed),
        rapid=_seconds(path.rapid_length(machine.origin), machine.rapid_rate),
        blocks=len(path) * block_time,
        loading=load_time,
    )


def estimate_job(
    job: EngravedJob,
    *,
    setup: MachineSetup | None = None,
    block_time: float = DEFAULT_BLOCK_TIME,
    load_time: float = DEFAULT_LOAD_TIME,
    tool_change_time: float = DEFAULT_TOOL_CHANGE,
) -> JobTime:
    """Work out how long the whole job takes.

    A tool change is counted for every cutter after the first. The order the
    plates are cut in decides how many that really is, and this assumes the
    sensible one, which is all the plates on a cutter before it comes out.
    """
    per_plate = tuple(
        (
            plate.name,
            plate.spec.quantity,
            estimate_plate(plate, setup=setup, block_time=block_time, load_time=load_time),
        )
        for plate in job
    )
    cutters = len(job.spec.cutter_codes()) if len(job) else 0
    return JobTime(
        per_plate=per_plate,
        tool_changes=max(0, cutters - 1),
        tool_change_time=tool_change_time,
    )
