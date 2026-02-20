"""The setup sheet: one page that goes to the machine with the job.

Everything on it is something the operator has to know before pressing
start, and nothing on it is anything else. What cutter, how deep, how many
passes, which sheet, how many pieces, and roughly how long. A sheet with
more than that on it does not get read; a sheet with less than that on it
gets ignored and the setter works it out again from the schedule.

It is plain text on purpose. It gets printed on a dot matrix printer next to
a machine from 1998 and it gets written on in pencil.
"""

from __future__ import annotations

from collections.abc import Sequence

from dragpoint.compiler.drill import drill_plate
from dragpoint.compiler.job import EngravedJob
from dragpoint.compiler.plate import EngravedPlate
from dragpoint.estimate.cycle import JobTime, estimate_job
from dragpoint.nest.shelf import NestResult
from dragpoint.rules.report import Severity

__all__ = ["setup_sheet"]

WIDTH = 78
"""Characters across. Eighty minus the two a fanfold printer eats."""


def _rule(character: str = "-") -> str:
    """A line across the page."""
    return character * WIDTH


def _row(columns: Sequence[str], widths: Sequence[int]) -> str:
    """One row of a fixed width table."""
    return "  ".join(text[:width].ljust(width) for text, width in zip(columns, widths, strict=True))


PLATE_COLUMNS = ("plate", "qty", "size", "stock", "depth", "pass", "cap", "min")
"""The columns of the plate table, in the order they are read."""

PLATE_WIDTHS = (10, 4, 13, 10, 7, 5, 6, 6)
"""How wide each of those columns is, in characters."""


def _plate_row(plate: EngravedPlate, time: JobTime) -> str:
    """One plate as a line of the table."""
    spec = plate.spec
    return _row(
        (
            spec.name,
            str(spec.quantity),
            f"{spec.width:g}x{spec.height:g}",
            spec.stock,
            f"{plate.depth:.2f}",
            str(plate.passes.cutting_passes),
            f"{plate.style.cap_height:g}",
            f"{time.for_plate(spec.name).minutes:.1f}",
        ),
        PLATE_WIDTHS,
    )


def _heading(job: EngravedJob) -> list[str]:
    """The block at the top that says what setup this is."""
    spec = job.spec
    lines = [
        _rule("="),
        f"SETUP SHEET   {spec.name}",
        _rule("="),
        f"cutter    {', '.join(spec.cutter_codes())}",
        f"post      {spec.post}",
        f"plates    {len(job)} drawings, {job.piece_count()} pieces",
    ]
    if spec.sheet is not None:
        lines.append(f"sheet     {spec.sheet}")
    if spec.spring_pass:
        lines.append("note      spring pass on every plate")
    if spec.notes:
        lines.append(f"note      {spec.notes}")
    return lines


def _drilling(job: EngravedJob) -> list[str]:
    """The drilling, as its own block, or nothing when there are no holes.

    Drilling is a second setup with a drill in the spindle, so it is set
    apart on the sheet rather than mixed into the plate rows. A sheet that
    listed the holes in the engraving table would have somebody drilling
    with a cutter in the machine.
    """
    plans = [drill_plate(plate.spec) for plate in job]
    with_holes = [plan for plan in plans if len(plan)]
    if not with_holes:
        return []
    lines = ["", _rule(), "DRILLING (second setup, drill in the spindle)", _rule()]
    lines.extend(f"{plan.name:<10}  {plan}" for plan in with_holes)
    sizes = sorted({size for plan in with_holes for size in plan.diameters()})
    lines.append(f"{'drills':<10}  {', '.join(f'{size:g}mm' for size in sizes)}")
    return lines


def _tips(job: EngravedJob) -> list[str]:
    """What the job asks of each cutter, and whether one tip covers it.

    Only the cutters that want more than one tip get a line of their own.
    A setup sheet that says every cutter is fine is a setup sheet with four
    lines on it that nobody reads, and then the fifth one is missed.
    """
    lives = job.tip_lives()
    hungry = [life for life in lives if not life.within_one_tip]
    if not hungry:
        return []
    lines = ["", "tips"]
    for life in hungry:
        lines.append(f"  {life}")
    return lines


def _violations(job: EngravedJob) -> list[str]:
    """What the rules said, worst first, or a line saying they said nothing."""
    report = job.report().sorted_worst_first()
    if report.clean:
        return ["", "checks    nothing to report"]
    lines = ["", _rule(), "CHECKS", _rule()]
    for violation in report:
        where = violation.subject or ""
        lines.append(f"{str(violation.severity):>7}  {where:<12} {violation.message}")
    if not report.ok:
        lines.append("")
        lines.append("DO NOT CUT. The errors above have to be dealt with first.")
    return lines


def setup_sheet(
    job: EngravedJob,
    *,
    time: JobTime | None = None,
    nest: NestResult | None = None,
) -> str:
    """Write the setup sheet for a compiled job.

    ``time`` and ``nest`` are worked out here when they are not handed in,
    so a caller that already has them does not pay for them twice and a
    caller that does not have them still gets a complete sheet.
    """
    estimate = time if time is not None else estimate_job(job)
    lines = _heading(job)
    lines.extend(["", _rule(), _row(PLATE_COLUMNS, PLATE_WIDTHS), _rule()])
    for plate in job:
        lines.append(_plate_row(plate, estimate))
    lines.append(_rule())
    lines.append(f"{'total':<10}  {job.piece_count():<4}  cutting {job.cut_length() / 1000:.2f}m")
    lines.append(f"{'':<10}  {'':<4}  {estimate.minutes:.0f} minutes including tool changes")

    for stock, count in job.stock_usage().items():
        lines.append(f"{'stock':<10}  {count:<4}  {stock}")

    if nest is not None:
        lines.extend(["", f"nest      {nest}"])
        if not nest.complete:
            for name, count in nest.left_over:
                lines.append(f"          {count} of {name} did not fit")

    lines.extend(_tips(job))
    lines.extend(_drilling(job))
    lines.extend(_violations(job))
    lines.append("")
    return "\n".join(lines) + "\n"


def worst_severity(job: EngravedJob) -> Severity | None:
    """The worst thing the rules found anywhere in the job.

    On the sheet for the reason it is here in the code: an operator reads
    the top of the page and stops there, so the sheet has to be able to say
    one word about the whole job.
    """
    return job.report().worst
