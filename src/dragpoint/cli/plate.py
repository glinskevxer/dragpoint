"""Commands about one plate, given on the command line rather than in a file.

This is the quick path: somebody at the machine wants one plate, now, and
writing a schedule for it would take longer than cutting it. Everything a
schedule can say has an option here, and the options are named the same.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import click

from dragpoint.cli.common import (
    echo_json,
    echo_report,
    exit_code_for,
    handled,
    plate_json,
    write_out,
)
from dragpoint.cli.options import (
    parse_size,
    plate_from_options,
    plate_options,
    setup_from_options,
)
from dragpoint.compiler.cutout import DEFAULT_TAB_WIDTH, cutout_plate
from dragpoint.compiler.drill import DEFAULT_PECK, drill_plate
from dragpoint.compiler.plate import compile_plate
from dragpoint.draw.dxf import render_dxf
from dragpoint.draw.svg import render_svg
from dragpoint.estimate.cycle import estimate_plate
from dragpoint.geometry.point import Point
from dragpoint.post.base import PostOptions, post_names, render
from dragpoint.spec.feature import Feature
from dragpoint.units import parse_length

__all__ = ["plate"]


@click.group()
def plate() -> None:
    """Compile one plate."""


@plate.command("check")
@plate_options
@click.option("--quiet", is_flag=True, help="Say nothing, just set the exit code.")
@click.option("--json", "as_json", is_flag=True, help="Print the whole thing as JSON.")
@click.pass_context
def check(context: click.Context, /, quiet: bool, as_json: bool, **options: object) -> None:
    """Compile a plate and print what the rules say about it."""
    with handled():
        made = compile_plate(plate_from_options(options), setup=setup_from_options(options))
    if as_json:
        echo_json(plate_json(made))
    elif not quiet:
        click.echo(str(made))
        echo_report(made.report)
    context.exit(exit_code_for(made.report))


@plate.command("post")
@plate_options
@click.option(
    "--post",
    "post_name",
    type=click.Choice(list(post_names())),
    default="iso",
    show_default=True,
)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--program-number", default=1000, show_default=True)
@click.option("--line-numbers", is_flag=True, help="Number the blocks.")
@click.option("--repeats", default=1, show_default=True, help="Blanks on the fixture.")
@click.option("--pitch", default="0mm", show_default=True, help="Step between blanks in x.")
@click.option("--pitch-y", default="0mm", show_default=True, help="Step between blanks in y.")
@click.option("--force", is_flag=True, help="Post it even if the rules found an error.")
@click.pass_context
def post_plate(
    context: click.Context,
    /,
    post_name: str,
    out: Path | None,
    program_number: int,
    line_numbers: bool,
    repeats: int,
    pitch: str,
    pitch_y: str,
    force: bool,
    **options: object,
) -> None:
    """Post one plate to a machine program.

    A plate that failed the rules is not posted unless asked for twice. The
    program would cut, and what it cut would be scrap.
    """
    with handled():
        spec = plate_from_options(options)
        made = compile_plate(spec, setup=setup_from_options(options))
    if not made.ok and not force:
        echo_report(made.report)
        raise click.ClickException("the plate has errors, pass --force to post it anyway")
    with handled():
        settings = PostOptions(
            program=spec.name,
            number=program_number,
            spindle=made.stock.spindle,
            line_numbers=line_numbers,
            repeats=repeats,
            pitch_x=parse_length(pitch),
            pitch_y=parse_length(pitch_y),
            notes=(f"{made.cutter.name} in {made.stock.name} at {made.depth:.3f}mm",),
        )
    text = render(post_name, made.toolpath, settings)
    write_out(text, out)
    context.exit(exit_code_for(made.report))


@plate.command("draw")
@plate_options
@click.option(
    "--format",
    "shape",
    type=click.Choice(["svg", "dxf"]),
    default="svg",
    show_default=True,
)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--scale", default=4.0, show_default=True, help="Pixels per mm, SVG only.")
@click.option("--travel", is_flag=True, help="Draw the rapid moves too, SVG only.")
def draw(shape: str, out: Path | None, scale: float, travel: bool, **options: object) -> None:
    """Draw one plate as an SVG preview or a DXF."""
    with handled():
        made = compile_plate(plate_from_options(options), setup=setup_from_options(options))
        text = (
            render_svg(made, scale=scale, show_travel=travel)
            if shape == "svg"
            else render_dxf(made)
        )
    write_out(text, out)


@plate.command("time")
@plate_options
def time_plate(**options: object) -> None:
    """Estimate how long one plate takes."""
    with handled():
        setup = setup_from_options(options)
        made = compile_plate(plate_from_options(options), setup=setup)
        estimate = estimate_plate(made, setup=setup)
    click.echo(str(estimate))
    click.echo(
        f"  cut {made.cuts.cut_length():.1f}mm over {made.passes.cutting_passes} passes, "
        f"travel {made.order.after:.1f}mm"
    )


@plate.command("cutout")
@plate_options
@click.option(
    "--post",
    "post_name",
    type=click.Choice(list(post_names())),
    default="iso",
    show_default=True,
)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--tab", default=f"{DEFAULT_TAB_WIDTH}mm", show_default=True, help="Width of a tab.")
@click.option("--no-tabs", is_flag=True, help="Cut the window right out, holding nothing.")
@click.option(
    "--window",
    "windows",
    multiple=True,
    metavar="WxH@X,Y",
    help="A window this size at this centre. May be given more than once.",
)
def cutout(
    post_name: str,
    out: Path | None,
    tab: str,
    no_tabs: bool,
    windows: tuple[str, ...],
    **options: object,
) -> None:
    """Post the window milling for one plate as a program of its own.

    Tabs are on unless they are turned off. A window cut with no tabs at all
    is a piece of laminate loose under a spinning cutter, which is a decision
    somebody can make and not one to arrive at by leaving an option out.
    """
    with handled():
        spec = plate_from_options(options)
        spec = replace(spec, features=spec.features + tuple(_window(text) for text in windows))
        plan = cutout_plate(
            spec,
            setup=setup_from_options(options),
            tab_width=0.0 if no_tabs else parse_length(tab),
        )
    click.echo(str(plan), err=True)
    text = render(
        post_name,
        plan.toolpath,
        PostOptions(
            program=f"{spec.name} CUTOUT",
            spindle=plan.stock.spindle,
            notes=(
                f"{len(plan)} windows {plan.depth:.2f}mm deep with {plan.cutter.name}",
                f"{plan.tabs_per_window} tabs a window at {plan.tab_height:g}mm",
            ),
        ),
    )
    write_out(text, out)


def _window(text: str) -> Feature:
    """One ``--window`` argument, which is a size and a centre.

    Written the way a size is written everywhere else in this package, with
    an at sign and the centre after it: ``40x20mm@60,30mm``.
    """
    size, _, centre = text.partition("@")
    if not centre:
        raise click.BadParameter(f"{text!r} does not say where the window goes")
    width, height = parse_size(size)
    across, _, up = centre.partition(",")
    return Feature.rectangle(
        f"window-{across.strip()}-{up.strip()}",
        Point(parse_length(across), parse_length(up)),
        width,
        height,
    )


@plate.command("drill")
@plate_options
@click.option(
    "--post",
    "post_name",
    type=click.Choice(list(post_names())),
    default="iso",
    show_default=True,
)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--peck", default=f"{DEFAULT_PECK}mm", show_default=True, help="Depth per peck.")
def drill(post_name: str, out: Path | None, peck: str, **options: object) -> None:
    """Post the drilling for one plate as a program of its own.

    A plate with no holes on it posts an empty program rather than nothing,
    so a job that drills some plates and not others still has a file for
    every plate and the operator does not have to work out which.
    """
    with handled():
        spec = plate_from_options(options)
        plan = drill_plate(spec, setup=setup_from_options(options), peck=parse_length(peck))
    click.echo(str(plan), err=True)
    text = render(
        post_name,
        plan.toolpath,
        PostOptions(
            program=f"{spec.name} DRILL",
            spindle=plan.stock.spindle,
            notes=(f"{len(plan)} holes {plan.depth:.2f}mm deep in {plan.stock.name}",),
        ),
    )
    write_out(text, out)
