"""Compiling a whole job, and adding up what it comes to.

A job is compiled plate by plate and nothing is shared between plates except
the setup. That is deliberate: plates in one job can be on different stock at
different depths, and a compiler that cached anything derived from the first
plate would get the second one subtly wrong.

Quantities are counted here and nowhere else. A plate with a quantity of six
is compiled once, because the six are identical, and the six only exist in
the totals and in what the machine is told to repeat.

A numbered run is the exception and it is the reason this is not as simple as
it looks. Six plates that say VLV-001 to VLV-006 are six different programs,
so the spec is asked for its pieces first and each piece is compiled on its
own. Everything downstream then sees six plates of one, which is what they
are, and no total has to be adjusted afterwards to make up for it.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from dragpoint.compiler.plate import EngravedPlate, compile_plate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.rules.batch import JobCheck, run_job_rules
from dragpoint.rules.check import RuleSelection
from dragpoint.rules.report import Report, Severity
from dragpoint.spec.job import JobSpec
from dragpoint.tool.cutter import Cutter
from dragpoint.tool.life import TipLife, job_tip_life
from dragpoint.tool.material import Material

__all__ = ["EngravedJob", "compile_job"]


@dataclass(frozen=True, slots=True)
class EngravedJob:
    """Every plate in a job, compiled, with the job that asked for them."""

    spec: JobSpec
    plates: tuple[EngravedPlate, ...]
    batch: Report = Report()

    @property
    def name(self) -> str:
        """The job name off the schedule."""
        return self.spec.name

    @property
    def ok(self) -> bool:
        """True when nothing reported an error, on a plate or on the job."""
        return all(plate.ok for plate in self.plates) and self.batch.ok

    def report(self) -> Report:
        """Every violation from every plate, then the ones about the job.

        The job ones come last because they are read last: an operator works
        down the plates and then reads what is wrong with the schedule, and
        a repeated plate name at the top of a page of stroke separations is
        a repeated plate name nobody sees.
        """
        merged = Report()
        for plate in self.plates:
            merged = merged.merged(plate.report)
        return merged.merged(self.batch)

    def failed(self) -> tuple[EngravedPlate, ...]:
        """The plates that reported an error, in job order."""
        return tuple(plate for plate in self.plates if not plate.ok)

    def plate(self, name: str) -> EngravedPlate:
        """One compiled plate by name."""
        for plate in self.plates:
            if plate.name == name:
                return plate
        known = ", ".join(plate.name for plate in self.plates) or "none"
        raise KeyError(f"job {self.name} has no plate {name!r}, it has {known}")

    def cut_length(self) -> float:
        """Total cutting distance for the whole job, quantities counted."""
        return sum(plate.cuts.cut_length() * plate.spec.quantity for plate in self.plates)

    def travel_length(self) -> float:
        """Total rapid distance, quantities counted."""
        return sum(plate.order.after * plate.spec.quantity for plate in self.plates)

    def piece_count(self) -> int:
        """How many pieces come off the machine."""
        return self.spec.piece_count

    def stock_usage(self) -> dict[str, int]:
        """Pieces per stock code, sorted by code."""
        tally: dict[str, int] = {}
        for plate in self.plates:
            tally[plate.spec.stock] = tally.get(plate.spec.stock, 0) + plate.spec.quantity
        return dict(sorted(tally.items()))

    def tip_lives(self) -> tuple[TipLife, ...]:
        """What the job asks of each cutter it uses, sorted by cutter.

        Cutting length is counted per piece and multiplied by the quantity,
        because a tip does not know that six plates were the same drawing.
        """
        gathered: dict[str, dict[str, tuple[Material, float]]] = {}
        cutters: dict[str, Cutter] = {}
        for plate in self.plates:
            cutters[plate.cutter.name] = plate.cutter
            metres = plate.cuts.cut_length() * plate.spec.quantity / 1000.0
            by_stock = gathered.setdefault(plate.cutter.name, {})
            stock, so_far = by_stock.get(plate.stock.name, (plate.stock, 0.0))
            by_stock[plate.stock.name] = (stock, so_far + metres)
        return tuple(job_tip_life(cutters[name], gathered[name]) for name in sorted(gathered))

    def worst(self) -> Severity | None:
        """The worst severity anywhere in the job."""
        return self.report().worst

    def __len__(self) -> int:
        return len(self.plates)

    def __iter__(self) -> Iterator[EngravedPlate]:
        return iter(self.plates)

    def __str__(self) -> str:
        verdict = "ok" if self.ok else f"{len(self.failed())} plates not ok"
        return (
            f"{self.name}: {len(self.plates)} plates, {self.piece_count()} pieces, "
            f"{self.cut_length():.0f}mm cutting, {verdict}"
        )


def compile_job(
    job: JobSpec,
    *,
    setup: MachineSetup | None = None,
    selection: RuleSelection | None = None,
) -> EngravedJob:
    """Compile every plate in ``job``."""
    machine = setup or MachineSetup()
    plates = tuple(
        compile_plate(piece, job=job, setup=machine, selection=selection)
        for spec in job.plates
        for piece in spec.pieces()
    )
    batch = run_job_rules(
        JobCheck(job=job, plates=tuple(plate.check() for plate in plates)),
        selection,
    )
    return EngravedJob(spec=job, plates=plates, batch=batch)
