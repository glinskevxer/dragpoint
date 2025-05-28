"""Will the plate be readable once the groove is as wide as it is going to be.

Every rule in here is the same question asked in a different place: the
centrelines were drawn as lines with no width, the cutter gives them a width,
and the width depends on the depth. Nothing in this module can be decided
from the geometry alone, and nothing in it can be decided from the tool
alone. That is why the rules live here and not with either.

The limit is the groove width itself rather than half of it. Two centrelines
one groove width apart leave two grooves whose edges just touch, and touching
is the point at which a reader stops seeing two strokes.

A hit is not a near miss. The bar of an A lands on both diagonals on purpose,
and the letter would be wrong if it did not, so two strokes that meet are one
junction and are not measured against each other at all. The fault is the gap
in between: close enough for the cutter to bridge, far enough that nobody drew
a joint there.
"""

from __future__ import annotations

from collections.abc import Iterator

from dragpoint.geometry.nearness import closest_approach, self_approach, stroke_to_stroke
from dragpoint.geometry.point import Point
from dragpoint.rules.check import PlateCheck, rule
from dragpoint.rules.report import Severity, Violation

__all__ = ["FOLD_ARC_FRACTION", "JOINT_FRACTION", "MAX_WEIGHT_RATIO", "MIN_STUB_FACTOR"]

JOINT_FRACTION = 0.02
"""Contacts within this fraction of the cap height are junctions.

Not a fraction of the groove. A face draws its junctions on the design grid,
so how nearly they land on each other scales with the lettering and not with
whatever cutter happens to be in the spindle.
"""

FOLD_ARC_FRACTION = 0.25
"""How far apart along a stroke two places have to be before they are compared.

A quarter of the cap height. This is a sampling gate and not a limit: what
decides whether an approach is a fold is :data:`FOLD_RATIO`.
"""

FOLD_RATIO = 1.5
"""How much further apart along the stroke than across it a fold has to be.

A stem gives one, a square corner about one and a half, a closed counter
pi over two, and a spike more the sharper it is. Asking for more than one
and a half means stems and square corners are left alone and the two shapes
that actually fill in are not.
"""

MIN_STUB_FACTOR = 1.0
"""A stroke shorter than this many groove widths is a dot, not a line."""

MAX_WEIGHT_RATIO = 0.25
"""Groove width as a fraction of cap height, past which letters fill in."""


@rule(
    "stroke-merge",
    "two strokes come closer than the groove they cut, so they run together",
    severity=Severity.ERROR,
)
def stroke_merge(check: PlateCheck) -> Iterator[Violation]:
    """Any two different strokes closer than one groove width.

    Reported once per plate, at the worst pair, because a legend that is too
    tight is too tight everywhere and forty violations saying so is not
    forty pieces of information.
    """
    limit = check.groove_width
    gap = closest_approach(check.strokes, touch=_joint(check))
    if gap >= limit:
        return
    yield Violation(
        rule="",
        severity=Severity.ERROR,
        message="strokes closer than the groove width will merge",
        where=_where_of_worst_pair(check, gap),
        measured=gap,
        limit=limit,
        subject=check.plate.name,
    )


def _where_of_worst_pair(check: PlateCheck, gap: float) -> Point | None:
    """The midpoint of the closest pair, for the message.

    Recomputed rather than carried out of the search, because the search
    stops early when it is given a cutoff and the pair it stopped on is not
    always the closest one.
    """
    strokes = check.strokes
    for index, left in enumerate(strokes):
        for right in strokes[index + 1 :]:
            if abs(stroke_to_stroke(left, right) - gap) < 1e-9:
                return left.bounds().centre.lerp(right.bounds().centre, 0.5)
    return None


def _joint(check: PlateCheck) -> float:
    """How close two strokes have to be before they count as joined."""
    return check.style.cap_height * JOINT_FRACTION


@rule(
    "stroke-self-merge",
    "a stroke comes back on itself closer than the groove it cuts",
    severity=Severity.ERROR,
)
def stroke_self_merge(check: PlateCheck) -> Iterator[Violation]:
    """A single stroke whose own bowl closes up at this depth.

    This is the one that catches a filled in counter. The bowl of an e is
    one stroke that comes round to within a fraction of the bar it started
    from, and the letter is fine until the groove is wide enough to bridge
    the gap.
    """
    limit = check.groove_width
    min_arc = check.style.cap_height * FOLD_ARC_FRACTION
    for stroke in check.strokes:
        gap = self_approach(
            stroke,
            min_arc=min_arc,
            fold_ratio=FOLD_RATIO,
            touch=_joint(check),
        )
        if gap < limit:
            yield Violation(
                rule="",
                severity=Severity.ERROR,
                message="a stroke closes on itself and the counter will fill",
                where=stroke.bounds().centre,
                measured=gap,
                limit=limit,
                subject=check.plate.name,
            )


@rule(
    "stroke-stub",
    "a stroke too short to be anything but a dimple",
    severity=Severity.WARNING,
)
def stroke_stub(check: PlateCheck) -> Iterator[Violation]:
    """Strokes shorter than the groove they would cut.

    A full stop is meant to be one of these. Anything else that comes out
    this short is a glyph that has been condensed past the point where its
    shortest stroke says anything, and it will read as a speck of dirt.
    """
    limit = check.groove_width * MIN_STUB_FACTOR
    for stroke in check.strokes:
        length = stroke.length()
        if length < limit:
            yield Violation(
                rule="",
                severity=Severity.WARNING,
                message="a stroke is shorter than the groove it cuts",
                where=stroke.start,
                measured=length,
                limit=limit,
                subject=check.plate.name,
            )


@rule(
    "letter-weight",
    "the groove is too wide for the size of the lettering",
    severity=Severity.WARNING,
)
def letter_weight(check: PlateCheck) -> Iterator[Violation]:
    """Groove width against cap height.

    A quarter is the number the shop settled on. Past it the letters stop
    being strokes and start being shapes, and the small counters go first.
    This catches the case the merge rules cannot: lettering that is legal
    everywhere and simply looks like a smudge.
    """
    limit = check.style.cap_height * MAX_WEIGHT_RATIO
    width = check.groove_width
    if width <= limit:
        return
    yield Violation(
        rule="",
        severity=Severity.WARNING,
        message="the groove is wide for this lettering height",
        measured=width,
        limit=limit,
        subject=check.plate.name,
    )
