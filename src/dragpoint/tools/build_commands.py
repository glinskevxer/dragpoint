"""Write the command reference out of the command line itself.

Nobody reads the help for a command they have not thought of running. A
single page with every command on it is how somebody finds out that
``job nest`` exists, and the only version of that page worth having is the
one generated from the commands that are actually wired up.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

import click

from dragpoint.cli.main import main as root
from dragpoint.tools.generate import generated, run
from dragpoint.tools.support import DOCS

__all__ = ["main"]

TOOL = "dragpoint.tools.build_commands"
"""The module name that goes in the do not edit line."""

SKIP_OPTIONS = {"--help", "-h"}
"""Options every command has, which are not worth a row each."""


def _summary(command: click.Command) -> str:
    """The first line of a command's help."""
    return (command.help or "").strip().splitlines()[0]


def _options(command: click.Command) -> list[str]:
    """One row per option, leaving out the ones every command has."""
    rows: list[str] = []
    for parameter in command.params:
        if not isinstance(parameter, click.Option):
            continue
        names = [name for name in parameter.opts if name not in SKIP_OPTIONS]
        if not names:
            continue
        default = parameter.default
        shown = "" if default in (None, False) else f"`{default}`"
        rows.append(f"| `{' `, `'.join(names)}` | {parameter.help or ''} | {shown} |")
    return rows


def _arguments(command: click.Command) -> str:
    """The positional arguments, as they appear in a usage line."""
    parts = []
    for parameter in command.params:
        if not isinstance(parameter, click.Argument):
            continue
        name = parameter.name or "arg"
        parts.append(f"[{name.upper()}...]" if parameter.nargs == -1 else name.upper())
    return " ".join(parts)


def _body() -> list[str]:
    """The document, one section per group."""
    lines = [
        "Everything the command line does. Run any of them with `--help` for the",
        "full option list; this page is for finding out what exists.",
        "",
        "Every command that checks a plate exits zero when nothing worse than a",
        "warning was found, one when a rule reported an error, and two when the",
        "command could not be carried out at all.",
    ]
    assert isinstance(root, click.Group)
    for name in sorted(root.commands):
        entry = root.commands[name]
        if isinstance(entry, click.Group):
            lines.extend(["", f"## `dragpoint {name}`", "", _summary(entry)])
            for command_name in sorted(entry.commands):
                lines.extend(_command(entry.commands[command_name], f"{name} {command_name}"))
            continue
        lines.extend(["", f"## `dragpoint {name}`", "", _summary(entry)])
        lines.extend(_command(entry, name, heading="###"))
    return lines


def _command(command: click.Command, path: str, heading: str = "###") -> list[str]:
    """One command: its usage line, what it is for, and its options.

    A command hung straight off the root gets the same treatment as one
    inside a group. There is only one of those and it is the one most
    people run, so it is not a special case worth a second code path.
    """
    usage = f"dragpoint {path} {_arguments(command)}".strip()
    lines = ["", f"{heading} `{usage}`", "", _summary(command)]
    rows = _options(command)
    if rows:
        lines.extend(["", "| option | what it does | default |", "| --- | --- | --- |"])
        lines.extend(rows)
    return lines


def main(arguments: Sequence[str] | None = None) -> int:
    """Write or check the command reference.

    ``arguments`` defaults to the command line, and is a parameter so a test
    can ask for a check without going near ``sys.argv``.
    """
    wanted = list(sys.argv[1:] if arguments is None else arguments)
    text = generated(TOOL, "Commands", _body())
    return run(DOCS / "commands.md", text, wanted)


if __name__ == "__main__":
    sys.exit(main())
