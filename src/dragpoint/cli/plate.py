"""Commands about one plate, given on the command line rather than in a file.

This is the quick path: somebody at the machine wants one plate, now, and
writing a schedule for it would take longer than cutting it. Everything a
schedule can say has an option here, and the options are named the same.
"""

from __future__ import annotations

from pathlib import Path

import click

from dragpoint.cli.common import echo_report, exit_code_for, handled, write_out
from dragpoint.cli.options import plate_from_options, plate_options, setup_from_options
from dragpoint.compiler.drill import DEFAULT_PECK, drill_plate
from dragpoint.compiler.plate import compile_plate
from dragpoint.draw.dxf import render_dxf
from dragpoint.draw.svg import render_svg
from dragpoint.estimate.cycle import estimate_plate
from dragpoint.post.base import PostOptions, post_names, render
from dragpoint.units import parse_length

__all__ = ["plate"]


@click.group()
def plate() -> None:
    """Compile one plate."""


@plate.command("check")
@plate_options
@click.option("--quiet", is_flag=True, help="Say nothing, just set the exit code.")
@click.pass_context
def check(context: click.Context, /, quiet: bool, **options: object) -> None:
    """Compile a plate and print what the rules say about it."""
    with handled():
        made = compile_plate(plate_from_options(options), setup=setup_from_options(options))
    if not quiet:
        click.echo(str(made))
    echo_report(made.report, quiet=quiet)
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
@click.option("--force", is_flag=True, help="Post it even if the rules found an error.")
@click.pass_context
def post_plate(
    context: click.Context,
    /,
    post_name: str,
    out: Path | None,
    program_number: int,
    line_numbers: bool,
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
    text = render(
        post_name,
        made.toolpath,
        PostOptions(
            program=spec.name,
            number=program_number,
            spindle=made.stock.spindle,
            line_numbers=line_numbers,
            notes=(f"{made.cutter.name} in {made.stock.name} at {made.depth:.3f}mm",),
        ),
    )
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
