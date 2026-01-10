"""Commands about a whole job, read from a schedule.

The schedule is the thing that gets kept. A plate cut from the command line
is cut once and forgotten; a plate in a schedule is cut again in two years
when the panel is refurbished, and it comes out the same because the file
says everything.
"""

from __future__ import annotations

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
from dragpoint.compiler.drill import DEFAULT_PECK, drill_plate
from dragpoint.compiler.job import compile_job
from dragpoint.compiler.plate import rule_selection
from dragpoint.compiler.settings import MachineSetup
from dragpoint.draw.sheet import render_nest
from dragpoint.estimate.cycle import estimate_job
from dragpoint.nest.shelf import nest_job
from dragpoint.post.base import PostOptions, post_names, render
from dragpoint.report.setup import setup_sheet
from dragpoint.spec.job import JobSpec
from dragpoint.spec.load import load_job
from dragpoint.spec.sheetload import load_csv_job
from dragpoint.units import parse_length

__all__ = ["job"]

SCHEDULE = click.argument("schedule", type=click.Path(exists=True, dir_okay=False, path_type=Path))
"""The schedule file every job command takes."""


@click.group()
def job() -> None:
    """Work on a whole job."""


def read_schedule(path: Path) -> JobSpec:
    """Read a schedule, whichever of the two formats it is in.

    The suffix decides. A drawing office sends a spreadsheet and a shop
    keeps a TOML file, and both of them are the same job, so every command
    takes either rather than making somebody convert one.
    """
    if path.suffix.lower() == ".csv":
        return load_csv_job(path)
    return load_job(path)


@job.command("check")
@SCHEDULE
@click.option("--plate", "only", default=None, help="Check one plate rather than all of them.")
@click.option("--quiet", is_flag=True, help="Say nothing, just set the exit code.")
@click.option("--json", "as_json", is_flag=True, help="Print the whole thing as JSON.")
@click.pass_context
def check(
    context: click.Context, /, schedule: Path, only: str | None, quiet: bool, as_json: bool
) -> None:
    """Compile a schedule and print what the rules say."""
    with handled():
        spec = read_schedule(schedule)
        made = compile_job(spec)
        plates = (made.plate(only),) if only else made.plates
    unknown = rule_selection(spec).unknown_names()
    if unknown and not quiet:
        click.echo(f"the schedule names rules that do not exist: {', '.join(unknown)}", err=True)
    report = made.plate(only).report if only else made.report()
    if as_json:
        echo_json(
            {
                "job": made.name,
                "pieces": made.piece_count(),
                "ok": all(plate.ok for plate in plates),
                "plates": [plate_json(plate) for plate in plates],
            }
        )
        context.exit(exit_code_for(report))
    for plate in plates:
        if not quiet:
            click.echo(str(plate))
        echo_report(plate.report, quiet=quiet)
    if not quiet:
        click.echo(str(made))
    context.exit(exit_code_for(report))


@job.command("post")
@SCHEDULE
@click.option(
    "--out",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Directory to write the programs into.",
)
@click.option("--force", is_flag=True, help="Post plates that failed the rules.")
@click.pass_context
def post_job(context: click.Context, /, schedule: Path, out: Path, force: bool) -> None:
    """Post every plate in a schedule, one file each."""
    with handled():
        spec = read_schedule(schedule)
        made = compile_job(spec)
    if not made.ok and not force:
        echo_report(made.report())
        raise click.ClickException("the job has errors, pass --force to post it anyway")
    if spec.post not in post_names():
        raise click.ClickException(
            f"no post called {spec.post!r}, there is {', '.join(post_names())}"
        )
    for number, plate in enumerate(made, start=1):
        text = render(
            spec.post,
            plate.toolpath,
            PostOptions(
                program=f"{spec.name} {plate.name}",
                number=1000 + number,
                spindle=plate.stock.spindle,
                notes=(f"{plate.cutter.name} in {plate.stock.name} at {plate.depth:.3f}mm",),
            ),
        )
        write_out(text, out / f"{plate.name}.{_extension(spec.post)}")
    context.exit(exit_code_for(made.report()))


def _extension(post_name: str) -> str:
    """The file extension the named post writes."""
    from dragpoint.post.base import POSTS

    return POSTS[post_name].extension


@job.command("time")
@SCHEDULE
@click.option("--block-time", default=0.004, show_default=True, help="Seconds a move costs.")
def time_job(schedule: Path, block_time: float) -> None:
    """Estimate how long a whole job takes."""
    with handled():
        made = compile_job(read_schedule(schedule))
        estimate = estimate_job(made, block_time=block_time)
    for name, quantity, time in estimate.per_plate:
        click.echo(f"{name:<10} x{quantity:<4} {time}")
    click.echo(str(estimate))


@job.command("nest")
@SCHEDULE
@click.option("--no-rotate", is_flag=True, help="Keep every piece the way round it was drawn.")
@click.option("--first-fit", is_flag=True, help="Take the first row that fits, not the best.")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Draw the nest to this file instead of listing it.",
)
@click.option("--scale", default=1.0, show_default=True, help="Pixels per millimetre.")
def nest(schedule: Path, no_rotate: bool, first_fit: bool, out: Path | None, scale: float) -> None:
    """Lay the pieces out on the sheet the schedule names."""
    with handled():
        spec = read_schedule(schedule)
        result = nest_job(spec, allow_rotation=not no_rotate, best_fit=not first_fit)
        if out is not None:
            write_out(render_nest(result, scale=scale), out)
            return
    for item in result:
        click.echo(str(item))
    click.echo(str(result))


@job.command("summary")
@SCHEDULE
def summary(schedule: Path) -> None:
    """Say what a job comes to without printing every violation."""
    with handled():
        spec = read_schedule(schedule)
        made = compile_job(spec, setup=MachineSetup())
    click.echo(str(made))
    click.echo(f"  cutters {', '.join(spec.cutter_codes())}")
    for stock, count in made.stock_usage().items():
        click.echo(f"  {stock:<10} {count} pieces")
    failed = made.failed()
    if failed:
        click.echo(f"  not ok: {', '.join(plate.name for plate in failed)}")


@job.command("sheet")
@SCHEDULE
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--no-nest", is_flag=True, help="Leave the nest off the sheet.")
def sheet(schedule: Path, out: Path | None, no_nest: bool) -> None:
    """Write the setup sheet that goes to the machine with the job."""
    with handled():
        spec = read_schedule(schedule)
        made = compile_job(spec)
        nest = None if no_nest or spec.sheet is None else nest_job(spec)
        text = setup_sheet(made, nest=nest)
    write_out(text, out)


@job.command("drill")
@SCHEDULE
@click.option(
    "--out",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Directory to write the drilling programs into.",
)
@click.option("--peck", default=f"{DEFAULT_PECK}mm", show_default=True, help="Depth per peck.")
@click.option("--all-plates", is_flag=True, help="Write a file even for plates with no holes.")
def drill_job(schedule: Path, out: Path, peck: str, all_plates: bool) -> None:
    """Post the drilling for every plate that has holes in it."""
    with handled():
        spec = read_schedule(schedule)
        step = parse_length(peck)
        plans = [drill_plate(plate, peck=step) for plate in spec.plates]
    written = 0
    for plan in plans:
        if not len(plan) and not all_plates:
            continue
        text = render(
            spec.post,
            plan.toolpath,
            PostOptions(
                program=f"{spec.name} {plan.name} DRILL",
                spindle=plan.stock.spindle,
                notes=(f"{len(plan)} holes {plan.depth:.2f}mm deep in {plan.stock.name}",),
            ),
        )
        write_out(text, out / f"{plan.name}-drill.{_extension(spec.post)}")
        written += 1
    click.echo(f"{written} plates have holes in them")
