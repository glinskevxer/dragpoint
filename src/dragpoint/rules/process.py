"""Can the machine actually do what the plate asks for.

The geometry can be perfect and the plate still impossible: a depth the sheet
will not take, a cutter that does not reach that far, a cut that needs
fourteen passes and will take an hour a plate. These are the rules the
setter cares about rather than the drawing office.

Some of what is checked here has already been enforced by a constructor
somewhere. That is deliberate. A constructor raises and stops the job; a rule
reports and lets the report carry every other problem alongside it, which is
what an operator wants when a schedule is wrong in four places.
"""

from __future__ import annotations

from collections.abc import Iterator

from dragpoint.rules.check import PlateCheck, rule
from dragpoint.rules.report import Severity, Violation
from dragpoint.text.fit import PREFERRED_CAP_HEIGHTS

__all__: list[str] = []
"""Nothing here is called by name. The rules run out of the register."""

MAX_SENSIBLE_PASSES = 6
"""Past this the cut is slow enough that the setter should be asked."""

PLUNGE_RATIO = 1.0
"""Depth as a multiple of tip width, past which a parallel cutter is buried."""


@rule(
    "depth-window",
    "the depth has to be one the stock will take",
    severity=Severity.ERROR,
)
def depth_window(check: PlateCheck) -> Iterator[Violation]:
    """The cut depth against the window the sheet allows.

    Two ply stock has a floor as well as a ceiling: too shallow and the
    colour never appears, too deep and the sheet has nothing left holding
    it together.
    """
    low, high = check.stock.depth_window()
    if check.stock.accepts_depth(check.depth):
        return
    if check.depth < low:
        message = f"too shallow for {check.stock.name}, the cap will not break through"
        limit = low
    else:
        message = f"too deep for {check.stock.name}, it will cut through the backing"
        limit = high
    yield Violation(
        rule="",
        severity=Severity.ERROR,
        message=message,
        measured=check.depth,
        limit=limit,
        subject=check.plate.name,
    )


@rule(
    "cutter-reach",
    "the cutter has to reach the depth asked for",
    severity=Severity.ERROR,
)
def cutter_reach(check: PlateCheck) -> Iterator[Violation]:
    """Depth against what the cutter can physically do."""
    if check.depth <= check.cutter.max_depth:
        return
    yield Violation(
        rule="",
        severity=Severity.ERROR,
        message=f"{check.cutter.name} does not reach this depth",
        measured=check.depth,
        limit=check.cutter.max_depth,
        subject=check.plate.name,
    )


@rule(
    "pass-count",
    "a cut that needs a lot of passes is worth a second look",
    severity=Severity.WARNING,
)
def pass_count(check: PlateCheck) -> Iterator[Violation]:
    """How many passes the depth works out to.

    Not an error. Stainless at four hundredths a pass genuinely needs them.
    It is a warning because a laminate plate that needs eight passes is
    nearly always a depth somebody typed in inches.
    """
    passes = check.passes.cutting_passes
    if passes <= MAX_SENSIBLE_PASSES:
        return
    yield Violation(
        rule="",
        severity=Severity.WARNING,
        message=f"{passes} passes at {check.stock.max_depth_per_pass:g}mm a pass",
        measured=float(passes),
        limit=float(MAX_SENSIBLE_PASSES),
        unit=" passes",
        subject=check.plate.name,
    )


@rule(
    "parallel-cutter-buried",
    "a parallel cutter taken deeper than it is wide",
    severity=Severity.WARNING,
)
def parallel_cutter_buried(check: PlateCheck) -> Iterator[Violation]:
    """A flat cutter cutting deeper than its own width.

    A vee cutter opens out as it goes and clears its own chips. A parallel
    one does not, and past about its own width of depth the flute packs and
    the plastic melts back into the groove behind it.
    """
    if not check.cutter.is_parallel:
        return
    limit = check.cutter.tip_width * PLUNGE_RATIO
    if check.depth <= limit:
        return
    yield Violation(
        rule="",
        severity=Severity.WARNING,
        message=f"{check.cutter.name} is buried deeper than it is wide",
        measured=check.depth,
        limit=limit,
        subject=check.plate.name,
    )


@rule(
    "odd-lettering-height",
    "a lettering height that is not one the shop sets up for",
    severity=Severity.NOTE,
)
def odd_lettering_height(check: PlateCheck) -> Iterator[Violation]:
    """A cap height off the shop list.

    Only a note. It is legal and it will cut. It is worth saying because a
    plate at 2.7 next to a plate at 3 looks like a mistake even when it is
    exactly what was asked for.
    """
    height = check.style.cap_height
    if any(abs(height - listed) < 1e-9 for listed in PREFERRED_CAP_HEIGHTS):
        return
    nearest = min(PREFERRED_CAP_HEIGHTS, key=lambda listed: abs(listed - height))
    yield Violation(
        rule="",
        severity=Severity.NOTE,
        message=f"lettering is {height:g}mm, the nearest set up height is {nearest:g}mm",
        measured=height,
        limit=nearest,
        subject=check.plate.name,
    )
