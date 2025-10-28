"""The last gate before a release: is everything that should agree, agreeing.

Three numbers have to be the same and live in three places, the changelog
has to have something to say about the version being released, and every
generated document has to be the one the code would write today. None of
those is hard. All of them have been wrong at least once in some shop, and
every one of them is only found by the customer.

This runs after everything else in CI. It is the job that fails when the
build is green and the release is still wrong.
"""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Callable, Sequence

from dragpoint import __version__
from dragpoint.tools import (
    build_architecture,
    build_commands,
    build_crib,
    build_rules,
    check_docstrings,
    check_face,
    check_layers,
    check_naming,
    check_tests,
    check_wiring,
    smoke,
)
from dragpoint.tools.support import DOCS, ROOT

__all__ = ["main"]

CHECKS: tuple[Callable[[], int], ...] = (
    check_docstrings.main,
    check_layers.main,
    check_naming.main,
    check_tests.main,
    check_wiring.main,
    check_face.main,
)
"""Every check, run again here so a release cannot skip one."""

GENERATORS: tuple[Callable[[Sequence[str] | None], int], ...] = (
    build_architecture.main,
    build_commands.main,
    build_crib.main,
    build_rules.main,
)
"""Every generated document, checked rather than written."""

WANTED_DOCS = ("architecture.md", "commands.md", "crib.md", "rules.md")
"""The pages a release ships. A missing one is a broken link in the README."""


def _pyproject_version() -> str:
    """The version the packaging metadata claims."""
    text = (ROOT / "pyproject.toml").read_bytes()
    document = tomllib.loads(text.decode("utf-8"))
    return str(document["project"]["version"])


def _changelog_mentions(version: str) -> bool:
    """True when the changelog has a heading for this version."""
    path = ROOT / "CHANGELOG.md"
    if not path.is_file():
        return False
    return f"## {version}" in path.read_text(encoding="utf-8")


def main(arguments: Sequence[str] | None = None) -> int:
    """Run every check and every generated document check, and compare versions."""
    verbose = "--verbose" in list(sys.argv[1:] if arguments is None else arguments)
    problems: list[str] = []

    packaged = _pyproject_version()
    if packaged != __version__:
        problems.append(f"pyproject says {packaged} and the package says {__version__}")
    if not _changelog_mentions(__version__):
        problems.append(f"the changelog has nothing to say about {__version__}")
    for name in WANTED_DOCS:
        if not (DOCS / name).is_file():
            problems.append(f"docs/{name} is missing")

    for check in CHECKS:
        if check() != 0:
            problems.append(f"{check.__module__} failed")
    for generator in GENERATORS:
        if generator(["--check"]) != 0:
            problems.append(f"{generator.__module__} is out of date")
    if smoke.main(["--quiet"]) != 0:
        problems.append("the smoke run failed")

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"release: {len(problems)} problems", file=sys.stderr)
        return 1
    if verbose:
        print(f"release: {__version__} is ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
