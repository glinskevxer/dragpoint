"""The bits every command needs: exit codes, reports and error handling.

Two rules run through all of it.

An error in a report is an exit code of one. Nothing else is: a warning is
printed and the command succeeds, because a warning is something for a person
to look at rather than something for a script to stop on. A shop that pipes
this into a build wants the build to fail on a plate that cannot be cut, and
not on a plate whose lettering is a bit heavy.

Every exception this package raises deliberately becomes a message and an
exit code of two, never a traceback. A traceback on a shop floor terminal
tells the operator nothing and loses the one line that would have.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import click

from dragpoint.errors import DragpointError
from dragpoint.rules.report import Report, Severity, Violation

__all__ = [
    "OK",
    "REPORTED",
    "USAGE",
    "echo_json",
    "echo_report",
    "exit_code_for",
    "handled",
    "plate_json",
    "report_json",
    "write_out",
]

OK = 0
"""Nothing to report, or nothing worse than a warning."""

REPORTED = 1
"""At least one error in the report."""

USAGE = 2
"""The command could not be carried out at all."""

Parameters = ParamSpec("Parameters")
Result = TypeVar("Result")


@contextmanager
def handled() -> Iterator[None]:
    """Turn anything dragpoint raises into a message and exit code two."""
    try:
        yield
    except DragpointError as exc:
        raise click.ClickException(str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise click.ClickException(str(exc).strip("'")) from exc


def exit_code_for(report: Report) -> int:
    """One when the report holds an error, zero otherwise."""
    return REPORTED if not report.ok else OK


def _line(violation: Violation) -> str:
    """One violation as a line of output, coloured by how bad it is."""
    colour = {
        Severity.ERROR: "red",
        Severity.WARNING: "yellow",
        Severity.NOTE: "cyan",
    }[violation.severity]
    # str() first. Severity is an IntEnum, so formatting it directly gives
    # the number, and the number is not what anybody wants to read.
    head = click.style(f"{str(violation.severity):>7}", fg=colour)
    where = f" [{violation.rule}]"
    return f"{head}{where} {violation.message}{_numbers(violation)}{_subject(violation)}"


def _numbers(violation: Violation) -> str:
    """The measurement and the limit, when the rule took both."""
    if violation.measured is None or violation.limit is None:
        return ""
    return (
        f" ({violation.measured:.4g}{violation.unit} against {violation.limit:.4g}{violation.unit})"
    )


def _subject(violation: Violation) -> str:
    """What the violation is about, when it is not obvious."""
    return f" on {violation.subject}" if violation.subject else ""


def echo_report(report: Report, *, quiet: bool = False, worst_first: bool = True) -> None:
    """Print a report, worst first, and say so when there is nothing to print."""
    if quiet:
        return
    ordered = report.sorted_worst_first() if worst_first else report
    if ordered.clean:
        click.echo(click.style("no violations", fg="green"))
        return
    for violation in ordered:
        click.echo(_line(violation))
    click.echo(str(ordered))


def write_out(text: str, target: Path | None) -> None:
    """Write to a file, or to standard output when no file was named."""
    if target is None:
        click.echo(text, nl=False)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    click.echo(f"wrote {target}", err=True)


def echo_json(payload: Mapping[str, Any]) -> None:
    """Print a payload as indented JSON with a trailing newline."""
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


def report_json(report: Report) -> list[dict[str, Any]]:
    """A report as plain data, for the ``--json`` forms."""
    return [
        {
            "rule": violation.rule,
            "severity": str(violation.severity),
            "message": violation.message,
            "subject": violation.subject,
            "measured": violation.measured,
            "limit": violation.limit,
            "unit": violation.unit,
        }
        for violation in report
    ]


def plate_json(plate: Any) -> dict[str, Any]:
    """One compiled plate as plain data.

    Everything a script would otherwise have to parse out of the printed
    form. A shop that wants to feed this into a spreadsheet should not be
    reading columns out of a report meant for a person.
    """
    return {
        "plate": plate.spec.name,
        "quantity": plate.spec.quantity,
        "stock": plate.stock.name,
        "cutter": plate.cutter.name,
        "depth": plate.depth,
        "groove": plate.cutter.width_at_depth(plate.depth),
        "passes": plate.passes.cutting_passes,
        "cap_height": plate.style.cap_height,
        "condense": plate.style.condense,
        "lines": list(plate.lines),
        "fits": plate.fit.fits,
        "cut_length": plate.cuts.cut_length(),
        "travel": plate.order.after,
        "ok": plate.ok,
        "violations": report_json(plate.report),
    }


def pass_through(function: Callable[Parameters, Result]) -> Callable[Parameters, Result]:
    """Decorator that runs a command body inside :func:`handled`.

    Here so a command body can be a plain function that raises whatever it
    likes, rather than every command opening with the same four lines.
    """

    def wrapper(*args: Parameters.args, **kwargs: Parameters.kwargs) -> Result:
        """Run the wrapped body with the error handling in place."""
        with handled():
            return function(*args, **kwargs)

    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper
