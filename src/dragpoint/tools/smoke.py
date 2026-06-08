"""Run the shipped job all the way through and look at what came out.

Every layer of this package has its own tests and they all pass on files
that were written to make them pass. This runs the one job that ships with
the package from the schedule to the machine program, and then asks whether
the answers are the right shape: a program that starts and ends the way a
control expects, a drawing that is XML, a nest that fits, an estimate that
is a number of minutes rather than a number of hours.

None of it is a substitute for the tests. What it catches is the class of
fault the tests cannot: two layers that each behave correctly and do not
fit together, and a wiring change that leaves everything importable and
nothing connected.

It runs the other two setups as well, because the plate that carries a
window is the plate where the setups meet: the same spec is engraved,
drilled and milled by three different bits of this package, and the way
that goes wrong is one of them disagreeing with the others about where the
plate is.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from dragpoint.compiler.cutout import cutout_plate
from dragpoint.compiler.drill import drill_plate
from dragpoint.compiler.job import EngravedJob, compile_job
from dragpoint.draw.dxf import render_dxf
from dragpoint.draw.svg import render_svg
from dragpoint.estimate.cycle import estimate_job
from dragpoint.estimate.setups import job_work
from dragpoint.geometry.box import Box
from dragpoint.nest.shelf import nest_job
from dragpoint.path.plan import Toolpath
from dragpoint.post.base import PostOptions, post_names, render
from dragpoint.spec.load import load_job
from dragpoint.tools.support import ROOT

__all__ = ["main"]

EXAMPLE = ROOT / "examples" / "mcc-panel-7.toml"
"""The schedule that ships with the package and is cut for real."""

SLOWEST_SENSIBLE = 20.0
"""Minutes. A legend job that takes longer than this has something wrong."""


def _complain(problems: list[str], condition: bool, message: str) -> None:
    """Record ``message`` when ``condition`` is false."""
    if not condition:
        problems.append(message)


def _other_setups(problems: list[str], made: EngravedJob) -> tuple[int, int]:
    """Drill and mill every plate, and say how many of each there were.

    Every hole and every window is checked against the blank it is in, the
    same way the engraving is. A drilling program that walks off the plate
    is the same fault as a legend that does, and it is the one nobody sees
    coming because the holes came off a customer drawing.
    """
    drilled = 0
    milled = 0
    for plate in made:
        holes = drill_plate(plate.spec)
        if len(holes):
            drilled += 1
            _complain(
                problems,
                len(holes.toolpath) > 0,
                f"{plate.name} has holes and an empty drilling program",
            )
            _complain(
                problems,
                holes.depth > plate.stock.thickness,
                f"{plate.name} drills shallower than the sheet is thick",
            )
            _complain(
                problems,
                _inside(plate.spec.outline(), holes.toolpath),
                f"{plate.name} drills off the plate",
            )
        windows = cutout_plate(plate.spec)
        if len(windows):
            milled += 1
            _complain(
                problems,
                windows.passes > 1,
                f"{plate.name} mills right through in one pass",
            )
            _complain(
                problems,
                _inside(plate.spec.outline(), windows.toolpath),
                f"{plate.name} mills off the plate",
            )
    return drilled, milled


def _inside(outline: Box, path: Toolpath) -> bool:
    """True when everything a toolpath does happens on the blank."""
    box = path.bounds()
    return box is not None and outline.contains_box(box, tolerance=0.001)


def main(arguments: Sequence[str] | None = None) -> int:
    """Compile, post, draw, nest and estimate the shipped job."""
    quiet = "--quiet" in list(sys.argv[1:] if arguments is None else arguments)
    problems: list[str] = []

    spec = load_job(EXAMPLE)
    made = compile_job(spec)
    _complain(problems, made.ok, f"the shipped job has errors: {made.report()}")
    _complain(problems, len(made) == len(spec.plates), "a plate went missing on the way through")
    _complain(problems, made.cut_length() > 0.0, "the job cuts nothing at all")

    for plate in made:
        _complain(problems, len(plate.toolpath) > 0, f"{plate.name} has an empty toolpath")
        _complain(
            problems,
            plate.toolpath.deepest() < 0.0,
            f"{plate.name} never puts the cutter into the work",
        )
        box = plate.toolpath.bounds()
        _complain(
            problems,
            box is not None and plate.spec.outline().contains_box(box, tolerance=0.001),
            f"{plate.name} moves off the plate",
        )

    first = made.plates[0]
    for name in post_names():
        text = render(name, first.toolpath, PostOptions(program=first.name))
        _complain(problems, text.endswith("\n"), f"the {name} post wrote no trailing newline")
        _complain(problems, len(text.splitlines()) > 10, f"the {name} post wrote almost nothing")

    svg = render_svg(first)
    _complain(problems, svg.startswith("<svg"), "the preview is not an SVG")
    _complain(problems, "</svg>" in svg, "the preview does not close")
    dxf = render_dxf(first)
    _complain(problems, dxf.rstrip().endswith("EOF"), "the DXF does not end")

    nest = nest_job(spec)
    _complain(problems, nest.complete, f"{nest.missed} pieces do not fit the sheet")
    _complain(problems, 0.0 < nest.utilisation() < 1.0, "the nest uses an impossible area")

    drilled, milled = _other_setups(problems, made)
    _complain(problems, drilled > 0, "no plate in the shipped job has a hole in it")

    estimate = estimate_job(made)
    _complain(problems, 0.0 < estimate.minutes < SLOWEST_SENSIBLE, "the estimate is not sensible")
    work, shop = job_work(made)
    _complain(problems, shop >= estimate.total, "the whole shop takes less time than one setup")
    _complain(
        problems,
        sum(item.setups for item in work) == len(made) + drilled + milled,
        "the setups do not add up",
    )

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"smoke: {len(problems)} problems", file=sys.stderr)
        return 1
    if not quiet:
        print(f"smoke: {made}")
        print(f"smoke: {nest}")
        print(f"smoke: {estimate}")
        print(f"smoke: {drilled} plates drilled, {milled} milled, {shop / 60.0:.1f} min in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
