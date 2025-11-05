"""Does everything land where it is allowed to land.

These are the rules about position rather than about legibility. A plate can
be perfectly readable and still be scrap because a groove runs into a fixing
hole, and a legend can be inside the engraving area and still be wrong
because the face could not draw half of it.

Nothing here needs the cutter, with one exception: clearance from a feature
is measured to the edge of the groove and not to its centreline, because
what runs into the hole is the groove.
"""

from __future__ import annotations

from collections.abc import Iterator

from dragpoint.rules.check import PlateCheck, rule
from dragpoint.rules.report import Severity, Violation

__all__: list[str] = []
"""Nothing here is called by name. The rules run out of the register."""


@rule(
    "legend-missing-glyph",
    "the face cannot draw something the legend asks for",
    severity=Severity.ERROR,
)
def legend_missing_glyph(check: PlateCheck) -> Iterator[Violation]:
    """Characters the face has no glyph for.

    Reported per line, naming every offender on that line in the order they
    appear. A legend with a degree sign the face does not carry comes back
    from the machine with a question mark on it, and the operator does not
    find out until the plate is on the panel.
    """
    for number, line in enumerate(check.plate.lines, start=1):
        missing = check.face.missing(line)
        if not missing:
            continue
        listed = " ".join(repr(character) for character in missing)
        yield Violation(
            rule="",
            severity=Severity.ERROR,
            message=f"{check.face.name} cannot draw {listed}",
            subject=f"{check.plate.name} line {number}",
        )


@rule(
    "legend-overrun",
    "the legend is wider than the engraving area even after fitting",
    severity=Severity.ERROR,
)
def legend_overrun(check: PlateCheck) -> Iterator[Violation]:
    """The fitter could not get the legend inside the area.

    The fitter reports rather than raises, so this is where an overlong
    legend becomes a decision. What it was stopped by comes through in the
    message, because that is what the drawing office has to change.
    """
    if check.fit.fits:
        return
    stopped = check.fit.stopped_at or "the fit policy"
    yield Violation(
        rule="",
        severity=Severity.ERROR,
        message=f"the legend will not fit, stopped by {stopped}",
        measured=check.fit.width,
        limit=check.fit.limit,
        subject=check.plate.name,
    )


@rule(
    "engraving-inside-area",
    "every mark has to be inside the engraving area",
    severity=Severity.ERROR,
)
def engraving_inside_area(check: PlateCheck) -> Iterator[Violation]:
    """Lettering outside the margin.

    Measured to the edge of the groove. A centreline exactly on the margin
    puts half a groove into it, and the margin exists because that is where
    the guillotine and the chipping are.

    Only the lettering. The border is engraving too and it lives outside the
    text margin on purpose, so it is checked against the plate instead, by
    :func:`border_on_plate`. The lettering is taken from the check rather
    than from the layout, because a legend set round an arc has been bent
    since the layout was made.
    """
    reach = check.groove_width / 2.0
    area = check.area
    for stroke in check.text_strokes:
        box = stroke.bounds().grown(reach)
        if area.contains_box(box):
            continue
        overhang = max(
            area.min_x - box.min_x,
            area.min_y - box.min_y,
            box.max_x - area.max_x,
            box.max_y - area.max_y,
        )
        yield Violation(
            rule="",
            severity=Severity.ERROR,
            message="a mark reaches outside the engraving area",
            where=stroke.bounds().centre,
            measured=overhang,
            limit=0.0,
            subject=check.plate.name,
        )


@rule(
    "feature-clearance",
    "engraving has to keep its distance from holes and cutouts",
    severity=Severity.ERROR,
)
def feature_clearance(check: PlateCheck) -> Iterator[Violation]:
    """Strokes that come inside a feature's clearance ring.

    One violation per feature, at the worst stroke. A legend laid across a
    switch bore is wrong once, not once per letter.
    """
    reach = check.groove_width / 2.0
    for feature in check.plate.features:
        worst = min(
            (feature.distance_to_stroke(stroke) - reach for stroke in check.strokes),
            default=float("inf"),
        )
        if worst >= feature.clearance:
            continue
        yield Violation(
            rule="",
            severity=Severity.ERROR,
            message=f"engraving comes inside the clearance on {feature.name}",
            where=feature.centre,
            measured=worst,
            limit=feature.clearance,
            subject=check.plate.name,
        )


@rule(
    "feature-on-plate",
    "a hole or cutout that is not on the plate it belongs to",
    severity=Severity.ERROR,
)
def feature_on_plate(check: PlateCheck) -> Iterator[Violation]:
    """Features whose own outline falls off the blank.

    Almost always a transposed coordinate in the schedule. Named one by one
    because the schedule has to be corrected one by one.
    """
    for feature in check.plate.features_outside_the_blank():
        yield Violation(
            rule="",
            severity=Severity.ERROR,
            message=f"{feature.name} is not on the plate",
            where=feature.centre,
            subject=check.plate.name,
        )


@rule(
    "border-on-plate",
    "the border groove has to be on the plate with room to spare",
    severity=Severity.ERROR,
)
def border_on_plate(check: PlateCheck) -> Iterator[Violation]:
    """The border ring, groove and all, against the edge of the blank.

    The border sits outside the text margin, so the margin says nothing
    about it. What it must not do is run off the edge, where the groove
    would break out of the side of the laminate.
    """
    border = check.plate.border_box()
    if border is None:
        return
    reach = check.groove_width / 2.0
    outline = check.plate.outline()
    grown = border.grown(reach)
    if outline.contains_box(grown):
        return
    overhang = max(
        outline.min_x - grown.min_x,
        outline.min_y - grown.min_y,
        grown.max_x - outline.max_x,
        grown.max_y - outline.max_y,
    )
    yield Violation(
        rule="",
        severity=Severity.ERROR,
        message="the border groove runs off the edge of the plate",
        measured=overhang,
        limit=0.0,
        subject=check.plate.name,
    )


@rule(
    "border-clearance",
    "the legend has to stay off the engraved border",
    severity=Severity.WARNING,
)
def border_clearance(check: PlateCheck) -> Iterator[Violation]:
    """Marks that touch or cross the border groove.

    A warning rather than an error. Lettering that runs into the border
    looks wrong and still reads, and there are plates where the drawing
    office meant it.
    """
    border = check.plate.border_box()
    if border is None:
        return
    reach = check.groove_width
    inner = border.grown(-reach)
    for stroke in check.text_strokes:
        if inner.contains_box(stroke.bounds()):
            continue
        yield Violation(
            rule="",
            severity=Severity.WARNING,
            message="a mark runs into the border",
            where=stroke.bounds().centre,
            measured=reach,
            limit=reach,
            subject=check.plate.name,
        )
