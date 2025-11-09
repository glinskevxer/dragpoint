"""The options that describe a plate, in one place.

Three commands take the same twenty options and every one of them has to map
onto a plate spec the same way. Written out three times they would drift, and
the drift would be silent: a plate drawn with one command and posted with
another would come out different and nothing would say so.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import click

from dragpoint.compiler.settings import MachineSetup
from dragpoint.geometry.point import Point
from dragpoint.path.cut import PassOrder
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign, VAlign
from dragpoint.units import parse_length

__all__ = ["plate_from_options", "plate_options", "setup_from_options"]

Command = TypeVar("Command", bound=Callable[..., Any])


def plate_options(command: Command) -> Command:
    """Attach every option that describes a plate.

    Applied bottom up, the way click stacks decorators, so the list reads
    backwards here and forwards in the help.
    """
    options = [
        click.option("--rapid-rate", default=6000.0, show_default=True, help="Rapid mm/min."),
        click.option(
            "--pass-order",
            type=click.Choice([order.value for order in PassOrder]),
            default=PassOrder.BY_PASS.value,
            show_default=True,
        ),
        click.option("--no-optimise", is_flag=True, help="Leave the travel order alone."),
        click.option("--hop", default="25mm", show_default=True, help="Lift high above this move."),
        click.option("--clearance", default="0.5mm", show_default=True, help="Hop height."),
        click.option("--safe", default="5mm", show_default=True, help="Full retract height."),
        click.option("--arc-inward", is_flag=True, help="Letters face the middle."),
        click.option("--arc-clockwise", is_flag=True, help="Run the legend the other way."),
        click.option("--arc-sweep", default=180.0, show_default=True, help="Degrees allowed."),
        click.option("--arc-start", default=90.0, show_default=True, help="Degrees at the middle."),
        click.option("--arc", "arc_radius", default=None, help="Set the legend round this radius."),
        click.option("--cutter", default=None, help="Cutter name, else the shop default."),
        click.option("--depth", default=None, help="Cut depth, else the stock nominal."),
        click.option("--border", default=None, help="Engraved border inset."),
        click.option("--margin", default="2mm", show_default=True, help="Engraving margin."),
        click.option(
            "--valign",
            type=click.Choice([align.value for align in VAlign]),
            default=VAlign.MIDDLE.value,
            show_default=True,
        ),
        click.option(
            "--halign",
            type=click.Choice([align.value for align in HAlign]),
            default=HAlign.CENTRE.value,
            show_default=True,
        ),
        click.option(
            "--fit",
            type=click.Choice([policy.value for policy in FitPolicy]),
            default=FitPolicy.CONDENSE.value,
            show_default=True,
        ),
        click.option("--wrap", is_flag=True, help="Break long lines to fit."),
        click.option("--mirror", is_flag=True, help="Cut it back to front."),
        click.option("--slant", default=0.0, show_default=True, help="Oblique, in degrees."),
        click.option("--condense", default=1.0, show_default=True, help="Horizontal squeeze."),
        click.option("--tracking", default="0mm", show_default=True, help="Space per glyph."),
        click.option("--cap-height", default="3mm", show_default=True, help="Lettering height."),
        click.option("--face", default="panelgothic", show_default=True),
        click.option("--stock", default="LAM16-BW", show_default=True, help="Stock code."),
        click.option("--size", default="60x20mm", show_default=True, help="Plate size, WxH."),
        click.option("--name", default="PLATE", show_default=True, help="Plate name."),
        click.argument("lines", nargs=-1),
    ]
    for option in options:
        command = option(command)
    return command


def _size(text: str) -> tuple[float, float]:
    """Read ``60x20mm`` into a width and a height.

    A unit on the whole thing applies to both, which is how everybody
    writes a plate size down.
    """
    parts = text.lower().replace("*", "x").split("x")
    if len(parts) != 2:
        raise ValueError(f"{text!r} is not a size, write it as 60x20mm")
    unit = "".join(character for character in parts[1] if character.isalpha())
    first = parts[0] if any(character.isalpha() for character in parts[0]) else parts[0] + unit
    return parse_length(first), parse_length(parts[1])


def plate_from_options(options: dict[str, Any]) -> PlateSpec:
    """Build a plate spec from the parsed options."""
    width, height = _size(str(options["size"]))
    return PlateSpec(
        name=str(options["name"]),
        width=width,
        height=height,
        stock=str(options["stock"]),
        lines=tuple(str(line) for line in options["lines"]),
        face=str(options["face"]),
        cap_height=parse_length(str(options["cap_height"])),
        tracking=parse_length(str(options["tracking"])),
        condense=float(options["condense"]),
        slant=float(options["slant"]),
        mirror=bool(options["mirror"]),
        wrap=bool(options["wrap"]),
        margin=parse_length(str(options["margin"])),
        halign=HAlign(str(options["halign"])),
        valign=VAlign(str(options["valign"])),
        fit=FitPolicy(str(options["fit"])),
        border=None if options["border"] is None else parse_length(str(options["border"])),
        depth=None if options["depth"] is None else parse_length(str(options["depth"])),
        cutter=None if options["cutter"] is None else str(options["cutter"]),
        arc_radius=(
            None if options["arc_radius"] is None else parse_length(str(options["arc_radius"]))
        ),
        arc_start=float(options["arc_start"]),
        arc_sweep=float(options["arc_sweep"]),
        arc_clockwise=bool(options["arc_clockwise"]),
        arc_inward=bool(options["arc_inward"]),
    )


def setup_from_options(options: dict[str, Any]) -> MachineSetup:
    """Build a machine setup from the parsed options."""
    return MachineSetup(
        safe=parse_length(str(options["safe"])),
        clearance=parse_length(str(options["clearance"])),
        hop_limit=parse_length(str(options["hop"])),
        pass_order=PassOrder(str(options["pass_order"])),
        optimise_rounds=0 if options["no_optimise"] else 2,
        rapid_rate=float(options["rapid_rate"]),
        origin=Point(0.0, 0.0),
    )
