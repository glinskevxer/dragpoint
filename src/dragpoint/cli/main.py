"""The command line, which is how the shop actually uses this.

One group per thing a person asks about: the faces, one plate, a whole job,
and the crib. Nothing in here does any work of its own; every command reads
something, calls into the package and prints what came back. A command with
logic in it is a command whose behaviour cannot be tested without a
subprocess, and there is enough of that in a shop already.
"""

from __future__ import annotations

import click

from dragpoint import __version__
from dragpoint.cli.crib import crib
from dragpoint.cli.font import font
from dragpoint.cli.job import job
from dragpoint.cli.plate import plate

__all__ = ["main"]

CONTEXT = {"help_option_names": ["-h", "--help"], "max_content_width": 100}
"""Click settings. The width is the one a shop floor terminal is."""


@click.group(context_settings=CONTEXT)
@click.version_option(__version__, "-V", "--version", prog_name="dragpoint")
def main() -> None:
    """Compile legend plate artwork into engraving toolpaths."""


main.add_command(font)
main.add_command(plate)
main.add_command(job)
main.add_command(crib)


if __name__ == "__main__":  # pragma: no cover
    main()
