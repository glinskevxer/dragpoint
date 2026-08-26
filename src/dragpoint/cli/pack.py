"""One command that writes everything a job needs to be cut.

The other commands each answer one question, which is right for a person
working something out and wrong for the thing that happens forty times a
week: a schedule arrives, and somebody has to produce the programs, the
drilling, the windows, the setup sheet, the travellers and a nest drawing,
put them in a folder and take the folder to the machine.

Doing that with six commands means six chances to forget one. Every job this
shop has ever had to recut for a missing drilling file was a job where
somebody ran five of them.

Nothing here is new work. It is the other commands in one order, writing
into one directory with names an operator can read, and it stops before
writing anything if the rules found an error, because a pack of programs for
a job that cannot be cut is worse than no pack at all.

The last file it writes is a list of the others. A folder of forty files is
a folder somebody has to work out the shape of, and the one thing that is
never in it is what it is supposed to contain, so a file that went missing
between here and the machine goes unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import click

from dragpoint.cli.common import echo_report, exit_code_for, handled, write_out
from dragpoint.cli.job import read_schedule
from dragpoint.compiler.cutout import cutout_plate
from dragpoint.compiler.drill import drill_plate
from dragpoint.compiler.job import EngravedJob, compile_job
from dragpoint.draw.sheet import render_nest
from dragpoint.draw.svg import render_svg
from dragpoint.estimate.price import quote_job
from dragpoint.nest.shelf import nest_job
from dragpoint.post.base import POSTS, PostOptions, render
from dragpoint.report.setup import setup_sheet
from dragpoint.report.traveller import travellers
from dragpoint.spec.job import JobSpec

__all__ = ["pack"]

PROGRAMS = "programs"
"""Subdirectory the engraving programs go in."""

DRILLING = "drilling"
"""Subdirectory the drilling programs go in."""

WINDOWS = "windows"
"""Subdirectory the window milling goes in."""

DRAWINGS = "drawings"
"""Subdirectory the plate previews go in."""

NEWLINE = "\n"
"""What the text files in a pack are joined with, on every machine."""


@click.command("pack")
@click.argument("schedule", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Directory to write the whole pack into.",
)
@click.option("--force", is_flag=True, help="Write the pack even if the rules found an error.")
@click.option("--no-drawings", is_flag=True, help="Leave the plate previews out.")
@click.pass_context
def pack(
    context: click.Context,
    /,
    schedule: Path,
    out: Path,
    force: bool,
    no_drawings: bool,
) -> None:
    """Write every file a job needs, in one folder, in one go."""
    with handled():
        spec = read_schedule(schedule)
        made = compile_job(spec)
    if not made.ok and not force:
        echo_report(made.report())
        raise click.ClickException("the job has errors, pass --force to write the pack anyway")
    if spec.post not in POSTS:
        raise click.ClickException(f"no post called {spec.post!r}")

    written = _programs(made, spec, out)
    written += _drilling(made, spec, out)
    written += _windows(made, spec, out)
    if not no_drawings:
        written += _drawings(made, out)
    written += _paperwork(made, spec, out)
    written += _contents(made, out)
    click.echo(f"{written} files in {out}")
    context.exit(exit_code_for(made.report()))


def _extension(post: str) -> str:
    """The suffix the named post's files carry."""
    return POSTS[post].extension


def _programs(made: EngravedJob, spec: JobSpec, out: Path) -> int:
    """The engraving, one file per plate, numbered from the job."""
    for number, plate in enumerate(made, start=1):
        text = render(
            spec.post,
            plate.toolpath,
            PostOptions(
                work_offset=spec.work_offset,
                program=f"{spec.name} {plate.name}",
                number=1000 + number,
                spindle=plate.stock.spindle,
                notes=(f"{plate.cutter.name} in {plate.stock.name} at {plate.depth:.3f}mm",),
            ),
        )
        write_out(text, out / PROGRAMS / f"{plate.name}.{_extension(spec.post)}")
    return len(made.plates)


def _drilling(made: EngravedJob, spec: JobSpec, out: Path) -> int:
    """The drilling, one file per drill, and nothing for a plate with no holes."""
    count = 0
    for plate in made:
        plan = drill_plate(plate.spec)
        if not len(plan):
            continue
        for run in plan.runs if len(plan.runs) > 1 else (None,):
            suffix = "" if run is None else f"-{run.diameter:g}mm".replace(".", "p")
            text = render(
                spec.post,
                plan.toolpath if run is None else run.toolpath,
                PostOptions(
                    work_offset=spec.work_offset,
                    program=f"{spec.name} {plan.name} DRILL",
                    spindle=plan.stock.spindle,
                    notes=(f"{len(plan)} holes {plan.depth:.2f}mm deep in {plan.stock.name}",),
                ),
            )
            write_out(text, out / DRILLING / f"{plan.name}{suffix}.{_extension(spec.post)}")
            count += 1
    return count


def _windows(made: EngravedJob, spec: JobSpec, out: Path) -> int:
    """The window milling, and nothing for a plate with no windows."""
    count = 0
    for plate in made:
        plan = cutout_plate(plate.spec)
        if not len(plan):
            continue
        text = render(
            spec.post,
            plan.toolpath,
            PostOptions(
                work_offset=spec.work_offset,
                program=f"{spec.name} {plan.name} CUTOUT",
                spindle=plan.stock.spindle,
                notes=(f"{len(plan)} windows with {plan.cutter.name}",),
            ),
        )
        write_out(text, out / WINDOWS / f"{plan.name}.{_extension(spec.post)}")
        count += 1
    return count


def _drawings(made: EngravedJob, out: Path) -> int:
    """A preview of every plate, at the width the cutter will leave."""
    for plate in made:
        write_out(render_svg(plate), out / DRAWINGS / f"{plate.name}.svg")
    return len(made.plates)


def _paperwork(made: EngravedJob, spec: JobSpec, out: Path) -> int:
    """The setup sheet, the travellers, the quote, and the nest if there is one."""
    nest = nest_job(spec) if spec.sheet is not None else None
    write_out(setup_sheet(made, nest=nest), out / "setup.txt")
    write_out(travellers(tuple(made)), out / "travellers.txt")
    write_out(_quote_page(made), out / "quote.txt")
    if nest is None:
        return 3
    write_out(render_nest(nest), out / "nest.svg")
    return 4


def _quote_page(made: EngravedJob) -> str:
    """What the job comes to, as a page for the folder.

    In the pack rather than only on the command line because the folder is
    what gets found six months later when somebody asks why the reorder
    costs more than the first one did.
    """
    priced = quote_job(made)
    lines = [
        f"QUOTE   {priced.job}",
        "",
        f"pieces     {priced.pieces}",
        f"stock      {priced.area / 1_000_000.0:.3f}m2",
        "",
        f"material   {priced.material:>10.2f}",
        f"machining  {priced.machining:>10.2f}",
        f"setting    {priced.setting:>10.2f}",
        f"total      {priced.total:>10.2f}",
        f"each       {priced.each:>10.2f}",
    ]
    if not priced.complete:
        lines.extend(["", f"no price on the rack for {', '.join(priced.unpriced_stock)}"])
    return NEWLINE.join(lines) + NEWLINE


def _contents(made: EngravedJob, out: Path) -> int:
    """A list of everything in the pack, written last so it lists itself.

    Sorted by path, because that is the order a folder shows them in and a
    list in a different order from the folder is a list nobody checks
    against the folder.
    """
    found = sorted(
        path for path in out.rglob("*") if path.is_file() and path.name != "contents.txt"
    )
    lines = [f"CONTENTS   {made.name}", "", f"{len(found)} files", ""]
    lines.extend(
        f"{str(path.relative_to(out)).replace(chr(92), '/'):<40}{path.stat().st_size:>9} bytes"
        for path in found
    )
    write_out(NEWLINE.join(lines) + NEWLINE, out / "contents.txt")
    return 1
