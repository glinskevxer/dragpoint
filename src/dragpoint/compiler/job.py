"""Compiling a whole job, and adding up what it comes to.

A job is compiled plate by plate and nothing is shared between plates except
the setup. That is deliberate: plates in one job can be on different stock at
different depths, and a compiler that cached anything derived from the first
plate would get the second one subtly wrong.

Quantities are counted here and nowhere else. A plate with a quantity of six
is compiled once, because the six are identical, and the six only exist in
the totals and in what the machine is told to repeat.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from dragpoint.compiler.plate import EngravedPlate, compile_plate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.rules.check import RuleSelection
from dragpoint.rules.report import Report, Severity
from dragpoint.spec.job import JobSpec

__all__ = ["EngravedJob", "compile_job"]


@dataclass(frozen=True, slots=True)
class EngravedJob:
    """Every plate in a job, compiled, with the job that asked for them."""

    spec: JobSpec
    plates: tuple[EngravedPlate, ...]

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def ok(self) -> bool:
        """True when no plate reported an error."""
        return all(plate.ok for plate in self.plates)

    def report(self) -> Report:
        """Every violation from every plate, plate order kept."""
        merged = Report()
        for plate in self.plates:
            merged = merged.merged(plate.report)
        return merged

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
        compile_plate(spec, job=job, setup=machine, selection=selection) for spec in job.plates
    )
    return EngravedJob(spec=job, plates=plates)
