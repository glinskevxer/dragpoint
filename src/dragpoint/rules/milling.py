"""Can the windows actually be milled, and will the plate survive it.

The fitment rules ask whether a window is on the plate and whether the
lettering keeps clear of it. These ask the questions the milling setup asks,
which are different and only come up once somebody has to cut it.

A window narrower than the cutter cannot be cut at all. A window that leaves
a two millimetre rail along the edge of the blank can be cut and the rail
snaps on the way off the fixture. Two windows a cutter's width apart are one
window with a whisker of laminate in the middle of it, and the whisker ends
up in the spindle.

None of these look at the engraving. A blank with a window in it and nothing
written on it is a real order, it goes through this package the same way,
and it can be wrong for every reason in here.
"""

from __future__ import annotations

from collections.abc import Iterator

from dragpoint.rules.check import PlateCheck, rule
from dragpoint.rules.report import Severity, Violation
from dragpoint.spec.feature import milled_features
from dragpoint.tool.cutter import DEFAULT_PROFILE_CUTTER, catalogue_cutter

__all__: list[str] = []
"""Nothing here is called by name. The rules run out of the register."""

MIN_RAIL = 4.0
"""Millimetres of blank that must be left between a window and the edge.

Under this the rail flexes while it is being cut and the window comes out
bowed, and on the thin stock it snaps. Four is what this shop has settled
on for 1.6 mm laminate and it is generous for 3 mm.
"""

MIN_WEB = 3.0
"""Millimetres of blank that must be left between two windows.

The same problem between two windows instead of a window and the edge. Less
than a web here and the strip between them is a spring.
"""


@rule(
    "window-narrower-than-the-cutter",
    "a window smaller than the cutter that has to go round it",
    severity=Severity.ERROR,
)
def window_narrower_than_the_cutter(check: PlateCheck) -> Iterator[Violation]:
    """Windows the milling cutter will not fit inside.

    The path is the window less the cutter radius on both sides, so a window
    narrower than the cutter has no path at all. The compiler refuses it and
    the refusal is an exception, which is the wrong way for a schedule to
    find out: this says it on the report with the rest of the plate.
    """
    cutter = catalogue_cutter(DEFAULT_PROFILE_CUTTER)
    for window in milled_features(check.plate.features):
        smallest = min(window.width, window.height)
        if smallest <= cutter.tip_width:
            yield Violation(
                rule="",
                severity=Severity.ERROR,
                message=(
                    f"{window.name} is {smallest:g}mm across and the cutter is "
                    f"{cutter.tip_width:g}mm"
                ),
                where=window.centre,
                measured=smallest,
                limit=cutter.tip_width,
                subject=window.name,
            )


@rule(
    "window-rail-too-thin",
    "a window that leaves too little blank between it and the edge",
    severity=Severity.WARNING,
)
def window_rail_too_thin(check: PlateCheck) -> Iterator[Violation]:
    """Windows that leave a fragile rail along one side of the plate."""
    blank = check.plate.outline()
    for window in milled_features(check.plate.features):
        box = window.bounds()
        rail = min(
            box.min_x - blank.min_x,
            blank.max_x - box.max_x,
            box.min_y - blank.min_y,
            blank.max_y - box.max_y,
        )
        if rail < MIN_RAIL:
            yield Violation(
                rule="",
                severity=Severity.WARNING,
                message=f"{window.name} leaves a {rail:.1f}mm rail at the edge of the blank",
                where=window.centre,
                measured=rail,
                limit=MIN_RAIL,
                subject=window.name,
            )


@rule(
    "windows-too-close-together",
    "two windows with a whisker of blank between them",
    severity=Severity.WARNING,
)
def windows_too_close_together(check: PlateCheck) -> Iterator[Violation]:
    """Pairs of windows with too little between them to hold together.

    Measured box to box, which is the web before the cutter takes its own
    width off each side. What is left after milling is thinner than this
    says, and that is the direction to be wrong in.
    """
    windows = milled_features(check.plate.features)
    for index, first in enumerate(windows):
        for second in windows[index + 1 :]:
            web = first.bounds().gap_to(second.bounds())
            if web < MIN_WEB:
                yield Violation(
                    rule="",
                    severity=Severity.WARNING,
                    message=(
                        f"{first.name} and {second.name} are {web:.1f}mm apart, which is not a web"
                    ),
                    where=first.centre,
                    measured=web,
                    limit=MIN_WEB,
                    subject=first.name,
                )


@rule(
    "window-over-the-lettering",
    "a window that would mill away what has just been engraved",
    severity=Severity.ERROR,
)
def window_over_the_lettering(check: PlateCheck) -> Iterator[Violation]:
    """Lettering inside a window, which is lettering that ends up in the bin.

    The clearance rule already keeps the legend a distance from a feature.
    This is the blunter question underneath it: is any of the legend inside
    the hole rather than near it. Kept apart because the answers are
    different jobs, one is move the legend and the other is the schedule has
    the wrong window on the wrong plate.
    """
    for window in milled_features(check.plate.features):
        box = window.bounds()
        inside = [
            stroke
            for stroke in check.text_strokes
            if any(box.contains(point) for point in stroke.points)
        ]
        if inside:
            yield Violation(
                rule="",
                severity=Severity.ERROR,
                message=f"{len(inside)} strokes of the legend are inside {window.name}",
                where=window.centre,
                measured=float(len(inside)),
                limit=0.0,
                unit=" strokes",
                subject=window.name,
            )
