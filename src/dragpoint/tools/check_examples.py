"""Every shipped example has to compile clean and cut something.

An example is documentation that runs. That is the whole reason to ship one,
and it is also why an example nobody checks is worse than no example: it is
the first thing anybody copies, and a copy of a schedule with an error in it
is an error in forty schedules six months later.

So each of them is compiled here and held to what a job in the shop is held
to. No errors from the rules. Every plate cuts something. Every piece nests
onto the sheet the schedule names, if it names one. Warnings are allowed,
because two of the examples exist to show what a warning looks like.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dragpoint.compiler.job import compile_job
from dragpoint.nest.shelf import nest_job
from dragpoint.rules.report import Severity
from dragpoint.spec.job import JobSpec
from dragpoint.spec.load import load_job
from dragpoint.spec.sheetload import load_csv_job
from dragpoint.tools.support import ROOT, Problem, report

__all__ = ["EXAMPLES", "check_example", "main"]

EXAMPLES = ROOT / "examples"
"""Where the shipped schedules live."""

SUFFIXES = (".toml", ".csv")
"""The two ways a schedule arrives, and both of them are checked."""


def _read(path: Path) -> JobSpec:
    """One schedule, whichever of the two formats it is in."""
    if path.suffix.lower() == ".csv":
        return load_csv_job(path)
    return load_job(path)


def check_example(path: Path) -> list[Problem]:
    """Everything wrong with one example."""
    problems: list[Problem] = []
    try:
        spec = _read(path)
    except Exception as bad:  # noqa: BLE001 - the message is the point
        return [Problem(path, 1, f"will not load: {bad}")]

    made = compile_job(spec)
    for violation in made.report().at_least(Severity.ERROR).violations:
        problems.append(Problem(path, 1, f"{violation.subject or spec.name}: {violation.message}"))
    if not made.plates:
        problems.append(Problem(path, 1, "has no plates in it"))
    for plate in made:
        if not plate.cuts:
            problems.append(Problem(path, 1, f"{plate.name} cuts nothing"))
    if spec.sheet is not None:
        nest = nest_job(spec)
        if not nest.complete:
            problems.append(Problem(path, 1, f"{nest.missed} pieces do not fit the sheet"))
    return problems


def examples() -> list[Path]:
    """Every shipped schedule, sorted, whatever format it is in."""
    return sorted(path for path in EXAMPLES.iterdir() if path.suffix.lower() in SUFFIXES)


def main() -> int:
    """Compile every shipped example and say what is wrong with it."""
    found = examples()
    problems: list[Problem] = []
    for path in found:
        problems.extend(check_example(path))
    if not found:
        problems.append(Problem(EXAMPLES, 1, "there are no examples to check"))
    return report("examples", problems, len(found))


if __name__ == "__main__":
    sys.exit(main())
