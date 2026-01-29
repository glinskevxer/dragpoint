"""Rules about a whole job, which is a different question from a plate.

Every rule in the other three modules looks at one plate and asks whether it
can be cut. These look at the schedule and ask whether it can be run, which
nothing else in the package is in a position to ask: a plate compiled on its
own knows nothing about the plate before it, and the mistakes that cost a
morning are all about the relationship between two of them.

Two plates called the same thing overwrite each other's program. Two plates
on the same stock at different depths mean resetting the depth nose halfway
through a run. Two identical legends on a schedule of thirty is a copy and
paste that nobody read back. None of these stop a plate being cut; all of
them stop the job being run the way the schedule implies.

The severities say so. Only the repeated name is an error, because that one
loses work rather than costing time.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from dragpoint.rules.check import PlateCheck, RuleSelection
from dragpoint.rules.report import Report, Severity, Violation
from dragpoint.spec.job import JobSpec

__all__ = [
    "JOB_REGISTRY",
    "JobCheck",
    "JobRuleDef",
    "job_rule",
    "job_rule_names",
    "run_job_rules",
]


@dataclass(frozen=True, slots=True)
class JobCheck:
    """One schedule and every plate on it, compiled.

    The plates are the same checks the plate rules were handed, so a job
    rule sees the settled depth and the settled cutter rather than what the
    schedule asked for. That matters: two plates that both say nothing about
    depth can still end up at two different depths.
    """

    job: JobSpec
    plates: tuple[PlateCheck, ...]

    def names(self) -> tuple[str, ...]:
        """Every plate name, in schedule order and repeats included."""
        return tuple(check.plate.name for check in self.plates)

    def stocks(self) -> tuple[str, ...]:
        """Every stock code used, in the order it first appears."""
        seen: list[str] = []
        for check in self.plates:
            if check.stock.name not in seen:
                seen.append(check.stock.name)
        return tuple(seen)

    def cutters(self) -> tuple[str, ...]:
        """Every cutter used, in the order it first appears."""
        seen: list[str] = []
        for check in self.plates:
            if check.cutter.name not in seen:
                seen.append(check.cutter.name)
        return tuple(seen)

    def piece_area(self) -> float:
        """Square millimetres of blank the job needs, quantities counted."""
        return sum(
            check.plate.width * check.plate.height * check.plate.quantity for check in self.plates
        )

    def __str__(self) -> str:
        return f"{self.job.name}: {len(self.plates)} plates on {len(self.stocks())} stocks"


JobRuleFunction = Callable[["JobCheck"], Iterable[Violation]]


@dataclass(frozen=True, slots=True)
class JobRuleDef:
    """One registered job rule."""

    name: str
    description: str
    severity: Severity
    check: JobRuleFunction

    def __str__(self) -> str:
        return f"{self.name} ({self.severity}): {self.description}"


JOB_REGISTRY: dict[str, JobRuleDef] = {}
"""Every job rule, in registration order."""


def job_rule(
    name: str,
    description: str,
    severity: Severity = Severity.WARNING,
) -> Callable[[JobRuleFunction], JobRuleFunction]:
    """Register a job rule under ``name``.

    Job rules and plate rules share one namespace on purpose. A report puts
    them side by side, and two rules called the same thing in one report is
    a report nobody can act on.
    """

    def register(function: JobRuleFunction) -> JobRuleFunction:
        """Put the function in the register and hand it back."""
        if name in JOB_REGISTRY:
            raise ValueError(f"a job rule called {name!r} is already registered")
        JOB_REGISTRY[name] = JobRuleDef(
            name=name,
            description=description,
            severity=severity,
            check=function,
        )
        return function

    return register


def job_rule_names() -> tuple[str, ...]:
    """Every registered job rule name, in registration order."""
    return tuple(JOB_REGISTRY)


def run_job_rules(check: JobCheck, selection: RuleSelection | None = None) -> Report:
    """Run the job rules over one compiled schedule."""
    wanted = selection or RuleSelection()
    found: list[Violation] = []
    for definition in JOB_REGISTRY.values():
        if not wanted.wants(definition.name):
            continue
        level = wanted.severity.get(definition.name, definition.severity)
        for violation in definition.check(check):
            found.append(
                Violation(
                    rule=definition.name,
                    severity=level,
                    message=violation.message,
                    where=violation.where,
                    measured=violation.measured,
                    limit=violation.limit,
                    unit=violation.unit,
                    subject=violation.subject,
                )
            )
    return Report.of(found)


@job_rule(
    "plate-name-repeated",
    "two plates on one schedule with the same name",
    Severity.ERROR,
)
def plate_name_repeated(check: JobCheck) -> Iterable[Violation]:
    """A repeated name means one program file overwrites another.

    A schedule cannot hold two plates of one name, so the way this happens
    is a numbered run: a run called TAG makes TAG-1, TAG-2 and TAG-3, and a
    plate somebody already called TAG-2 is now two plates.
    """
    counted: dict[str, int] = {}
    for name in check.names():
        counted[name] = counted.get(name, 0) + 1
    for name, count in sorted(counted.items()):
        if count > 1:
            yield Violation(
                rule="",
                severity=Severity.ERROR,
                message=f"{count} plates are called {name}, so their programs collide",
                measured=float(count),
                limit=1.0,
                unit=" plates",
                subject=name,
            )


@job_rule("legend-repeated", "two plates that say exactly the same thing")
def legend_repeated(check: JobCheck) -> Iterable[Violation]:
    """Two different plates with the same legend on them.

    Nearly always a schedule that was copied down a spreadsheet and one cell
    left unedited. Occasionally deliberate, which is why it is a warning and
    why the message names both plates rather than guessing which is wrong.
    """
    seen: dict[tuple[str, ...], str] = {}
    for plate in check.plates:
        if not plate.lines or not any(line.strip() for line in plate.lines):
            continue
        first = seen.get(plate.lines)
        if first is not None and first != plate.plate.name:
            yield Violation(
                rule="",
                severity=Severity.WARNING,
                message=f"{plate.plate.name} says the same as {first}",
                subject=plate.plate.name,
            )
            continue
        seen.setdefault(plate.lines, plate.plate.name)


@job_rule("stock-changes", "more than one stock in one setup")
def stock_changes(check: JobCheck) -> Iterable[Violation]:
    """Every stock past the first is a sheet change in the middle of a run."""
    stocks = check.stocks()
    if len(stocks) > 1:
        yield Violation(
            rule="",
            severity=Severity.WARNING,
            message=f"the job runs on {len(stocks)} stocks: {', '.join(stocks)}",
            measured=float(len(stocks)),
            limit=1.0,
            unit=" stocks",
        )


@job_rule("cutter-changes", "more than one cutter in one setup")
def cutter_changes(check: JobCheck) -> Iterable[Violation]:
    """Every cutter past the first is a tool change and a new depth setting."""
    cutters = check.cutters()
    if len(cutters) > 1:
        yield Violation(
            rule="",
            severity=Severity.WARNING,
            message=f"the job needs {len(cutters)} cutters: {', '.join(cutters)}",
            measured=float(len(cutters)),
            limit=1.0,
            unit=" cutters",
        )


@job_rule("depth-varies-on-one-stock", "the same stock cut at two depths")
def depth_varies_on_one_stock(check: JobCheck) -> Iterable[Violation]:
    """The depth nose gets reset partway through a run of one material.

    Which is fine when it was asked for and expensive when it was not, so
    the message names the two depths and leaves the decision alone.
    """
    depths: dict[str, dict[float, str]] = {}
    for plate in check.plates:
        depths.setdefault(plate.stock.name, {}).setdefault(round(plate.depth, 4), plate.plate.name)
    for stock, seen in sorted(depths.items()):
        if len(seen) > 1:
            written = ", ".join(f"{depth:g}mm on {name}" for depth, name in sorted(seen.items()))
            yield Violation(
                rule="",
                severity=Severity.WARNING,
                message=f"{stock} is cut at {len(seen)} depths: {written}",
                measured=float(len(seen)),
                limit=1.0,
                unit=" depths",
                subject=stock,
            )


@job_rule("sheet-too-small", "more blank than the sheet the job names holds")
def sheet_too_small(check: JobCheck) -> Iterable[Violation]:
    """The pieces will not come off the sheet even before the kerf.

    Area is not a nest and a job that passes this can still fail to nest.
    It is here because a job that fails it cannot possibly nest, and that is
    worth knowing on the schedule rather than at the guillotine.
    """
    sheet = check.job.sheet
    if sheet is None:
        return
    wanted = check.piece_area()
    if wanted > sheet.usable_area:
        yield Violation(
            rule="",
            severity=Severity.WARNING,
            message=(
                f"the pieces come to {wanted / 100.0:.0f}cm2 and the sheet holds "
                f"{sheet.usable_area / 100.0:.0f}cm2 inside the clamps"
            ),
            measured=wanted,
            limit=sheet.usable_area,
            unit=" square millimetres",
        )
