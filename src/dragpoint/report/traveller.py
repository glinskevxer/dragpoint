"""The traveller: the card that goes round the shop with one plate.

The setup sheet is for the machine and covers the whole job. This is for the
piece, and it goes with the piece: into the machine, onto the bench for
deburring, to the inspection table, into the bag that gets posted. When a
plate comes back six weeks later with a complaint, the traveller is the only
document that says what was actually cut and who signed for it.

So it says the legend twice. Once as the drawing office wrote it, and once
as it will come out after wrapping, fitting and condensing, because those
are not the same thing and the difference is exactly what a customer rings
up about. A line that was condensed to eighty per cent is a line somebody
should look at before two hundred of them are cut.

The boxes at the bottom are empty on purpose. They get a pencil tick and a
pair of initials, and that is the whole quality system in a shop this size.
"""

from __future__ import annotations

from dragpoint.compiler.plate import EngravedPlate
from dragpoint.estimate.cycle import CycleTime, estimate_plate
from dragpoint.rules.report import Severity

__all__ = ["traveller_card", "travellers"]

WIDTH = 78
"""Characters across, the same as the setup sheet, for the same printer."""

SIGN_OFF = ("first off checked", "quantity complete", "deburred", "packed")
"""The four things somebody has to put their initials against."""


def traveller_card(plate: EngravedPlate, *, time: CycleTime | None = None) -> str:
    """Write the card that travels with one compiled plate."""
    spent = time if time is not None else estimate_plate(plate)
    lines = [
        "=" * WIDTH,
        f"TRAVELLER   {plate.name}",
        "=" * WIDTH,
    ]
    lines.extend(_what(plate))
    lines.extend(_legend(plate))
    lines.extend(_cutting(plate, spent))
    lines.extend(_drilling(plate))
    lines.extend(_warnings(plate))
    lines.extend(_boxes())
    return "\n".join(lines) + "\n"


def travellers(plates: tuple[EngravedPlate, ...]) -> str:
    """One card per plate, separated by a page break.

    The break is a form feed because these get printed as a stack and torn
    apart at the perforation, and a card that runs onto the back of the one
    before it is a card that ends up on the wrong bench.
    """
    return "\f".join(traveller_card(plate) for plate in plates)


def _what(plate: EngravedPlate) -> list[str]:
    """The block that says which plate this is and what it is cut from."""
    spec = plate.spec
    lines = [
        f"blank     {spec.width:g} x {spec.height:g} mm, {spec.stock}",
        f"quantity  {spec.quantity}",
        f"face      {plate.face.name} at {plate.style.cap_height:g} mm cap",
    ]
    if spec.notes:
        lines.append(f"note      {spec.notes}")
    if spec.tags:
        lines.append(f"tags      {', '.join(sorted(spec.tags))}")
    return lines


def _legend(plate: EngravedPlate) -> list[str]:
    """What it says, as asked for and as it will read."""
    lines = ["", "-" * WIDTH, "legend", "-" * WIDTH]
    asked = plate.spec.lines
    cut = plate.lines
    for index, line in enumerate(cut):
        source = asked[index] if index < len(asked) else ""
        note = "" if source == line else f"   (asked for {source!r})"
        lines.append(f"  {index + 1}  {line}{note}")
    if not cut:
        lines.append("  nothing is engraved on this plate")
    settled = plate.fit.style
    if settled.condense < 1.0:
        lines.append(f"  condensed to {settled.condense:.0%} to make it fit")
    if settled.cap_height != plate.spec.cap_height:
        lines.append(f"  cap height dropped to {settled.cap_height:g} mm")
    if not plate.fit.fits:
        lines.append(f"  still over the line by {plate.fit.overrun:.2f} mm")
    return lines


def _cutting(plate: EngravedPlate, time: CycleTime) -> list[str]:
    """The numbers the setter needs and the operator checks against."""
    whole = time.minutes * plate.spec.quantity
    return [
        "",
        "-" * WIDTH,
        "cutting",
        "-" * WIDTH,
        f"cutter    {plate.cutter}",
        f"depth     {plate.depth:.2f} mm in {plate.passes.cutting_passes} passes",
        f"groove    {plate.cutter.width_at_depth(plate.depth):.2f} mm wide at depth",
        f"feed      {plate.stock.feed:g} mm/min, plunge {plate.stock.plunge_feed:g} mm/min",
        f"spindle   {plate.stock.spindle} rpm",
        f"cutting   {plate.cuts.cut_length() / 1000.0:.2f} m in {len(plate.cuts)} cuts",
        f"time      {time.minutes:.1f} minutes each, {whole:.0f} for the quantity",
    ]


def _drilling(plate: EngravedPlate) -> list[str]:
    """The holes, if there are any."""
    holes = [item for item in plate.spec.features if item.is_round]
    if not holes:
        return []
    lines = ["", "-" * WIDTH, "drilling", "-" * WIDTH]
    for hole in holes:
        lines.append(f"  {hole.width:.1f} mm at {hole.centre}")
    return lines


def _warnings(plate: EngravedPlate) -> list[str]:
    """Anything the rules said, worst first, or one line saying they passed."""
    violations = plate.report.violations
    if not violations:
        return ["", "checks    all passed"]
    lines = ["", "-" * WIDTH, "checks", "-" * WIDTH]
    for violation in sorted(violations, key=lambda item: -item.severity):
        lines.append(f"  {str(violation.severity):>7}  {violation.message}")
    if plate.report.worst is not None and plate.report.worst >= Severity.ERROR:
        lines.append("  DO NOT CUT until this is settled with the drawing office")
    return lines


def _boxes() -> list[str]:
    """The part somebody signs."""
    lines = ["", "-" * WIDTH]
    for label in SIGN_OFF:
        lines.append(f"  [    ]  {label:<28} initials ______  date ______")
    lines.append("-" * WIDTH)
    lines.append("")
    return lines
