"""How long the whole plate takes, not just the lettering.

The cycle estimate answers the question the engraving setup asks: how long
does this plate take with a cutter in the spindle. That was the only setup
this package knew about for a long time and it is no longer the only one.

A plate with four fixing holes and a meter window in it goes across the
machine three times. It is engraved, then the drill goes in and it is
drilled, then the profile cutter goes in and the window is milled, and each
of those has its own loading, its own tool change and its own program. A
quote built on the engraving alone is out by more than the engraving on the
plates that pay best.

So this adds the two other setups up in the same units and says what each of
them costs. Nothing here re-derives a toolpath: it asks the drilling and the
milling for theirs, which is the whole reason those two produce a toolpath
rather than a list of holes.
"""

from __future__ import annotations

from dataclasses import dataclass

from dragpoint.compiler.cutout import CutoutPlan, cutout_plate
from dragpoint.compiler.drill import DrillPlan, drill_plate
from dragpoint.compiler.job import EngravedJob
from dragpoint.compiler.plate import EngravedPlate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.estimate.cycle import (
    DEFAULT_BLOCK_TIME,
    DEFAULT_LOAD_TIME,
    DEFAULT_TOOL_CHANGE,
    CycleTime,
    estimate_plate,
)
from dragpoint.path.plan import MoveKind, Toolpath

__all__ = ["PlateWork", "job_work", "plate_work"]


@dataclass(frozen=True, slots=True)
class PlateWork:
    """The three setups one plate goes through, in seconds each."""

    name: str
    quantity: int
    engraving: CycleTime
    drilling: CycleTime | None
    milling: CycleTime | None

    @property
    def setups(self) -> int:
        """How many times the plate goes on the machine."""
        return 1 + (self.drilling is not None) + (self.milling is not None)

    @property
    def each(self) -> float:
        """Seconds for one piece through every setup it needs."""
        total = self.engraving.total
        if self.drilling is not None:
            total += self.drilling.total
        if self.milling is not None:
            total += self.milling.total
        return total

    @property
    def total(self) -> float:
        """Seconds for the quantity, tool changes not counted."""
        return self.each * self.quantity

    @property
    def minutes(self) -> float:
        """The total in minutes, which is what a quote is written in."""
        return self.total / 60.0

    def __str__(self) -> str:
        return f"{self.name} x{self.quantity}: {self.minutes:.1f} min over {self.setups} setup" + (
            "" if self.setups == 1 else "s"
        )


def plate_work(
    plate: EngravedPlate,
    *,
    setup: MachineSetup | None = None,
    block_time: float = DEFAULT_BLOCK_TIME,
    load_time: float = DEFAULT_LOAD_TIME,
) -> PlateWork:
    """Every setup one compiled plate needs, timed.

    A plate with no holes has no drilling setup rather than a drilling setup
    that takes no time. The difference matters to the count of setups, which
    is what the tool changes are worked out from.
    """
    machine = setup or MachineSetup()
    holes = drill_plate(plate.spec, setup=machine)
    windows = cutout_plate(plate.spec, setup=machine)
    return PlateWork(
        name=plate.name,
        quantity=plate.spec.quantity,
        engraving=estimate_plate(plate, setup=machine, block_time=block_time, load_time=load_time),
        drilling=_drilling_time(holes, machine, block_time, load_time),
        milling=_milling_time(windows, machine, block_time, load_time),
    )


def job_work(
    job: EngravedJob,
    *,
    setup: MachineSetup | None = None,
    block_time: float = DEFAULT_BLOCK_TIME,
    load_time: float = DEFAULT_LOAD_TIME,
    tool_change_time: float = DEFAULT_TOOL_CHANGE,
) -> tuple[tuple[PlateWork, ...], float]:
    """Every plate in a job, timed, with the shop total in seconds.

    The total counts one tool change for every setup on every plate that
    needs one, which is the pessimistic reading and the true one in a shop
    with a single spindle and no changer.
    """
    work = tuple(
        plate_work(plate, setup=setup, block_time=block_time, load_time=load_time) for plate in job
    )
    changes = sum(item.setups - 1 for item in work)
    return work, sum(item.total for item in work) + changes * tool_change_time


def _drilling_time(
    plan: DrillPlan, machine: MachineSetup, block_time: float, load_time: float
) -> CycleTime | None:
    """The drilling setup, or nothing when there is nothing to drill."""
    if not len(plan):
        return None
    return _path_time(plan.toolpath, plan.stock.plunge_feed, machine, block_time, load_time)


def _milling_time(
    plan: CutoutPlan, machine: MachineSetup, block_time: float, load_time: float
) -> CycleTime | None:
    """The milling setup, or nothing when there are no windows."""
    if not len(plan):
        return None
    return _path_time(plan.toolpath, plan.stock.feed, machine, block_time, load_time)


def _path_time(
    path: Toolpath,
    feed: float,
    machine: MachineSetup,
    block_time: float,
    load_time: float,
) -> CycleTime:
    """One toolpath timed the same way the engraving is timed."""
    return CycleTime(
        cutting=_seconds(path.cut_length(machine.origin), feed),
        plunging=_seconds(_plunge_distance(path), feed),
        rapid=_seconds(path.rapid_length(machine.origin), machine.rapid_rate),
        blocks=len(path) * block_time,
        loading=load_time,
    )


def _seconds(distance: float, rate: float) -> float:
    """Seconds to move ``distance`` millimetres at ``rate`` per minute."""
    return 0.0 if rate <= 0.0 else distance / rate * 60.0


def _plunge_distance(path: Toolpath) -> float:
    """How far the Z axis travels under feed, both ways.

    Worth more here than in the engraving. A drilled hole is nearly all Z
    travel and a pecked one goes up and down five times, so a drilling
    estimate that ignored it would come out at almost nothing.
    """
    total = 0.0
    here = 0.0
    for move in path:
        if move.kind in (MoveKind.PLUNGE, MoveKind.LIFT):
            total += abs(move.z - here)
        here = move.z
    return total
