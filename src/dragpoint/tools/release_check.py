"""The last gate before a release: is everything that should agree, agreeing.

Three numbers have to be the same and live in three places, the changelog
has to lead with the version being released rather than merely mention it
somewhere, and every generated document has to be the one the code would
write today. None of
those is hard. All of them have been wrong at least once in some shop, and
every one of them is only found by the customer.

This runs after everything else in CI. It is the job that fails when the
build is green and the release is still wrong.

The checks it runs are found rather than listed. A list is a thing somebody
adds a tool without touching, and a check nobody runs is not a check: it is
a file that passes. So every ``check_`` module in the tools package is
imported and run, and the one thing this file does hold a list of is the
tools that are not checks, which is short and changes for reasons somebody
would notice.
"""

from __future__ import annotations

import pkgutil
import sys
import tomllib
from collections.abc import Callable, Sequence
from importlib import import_module

from dragpoint import __version__
from dragpoint.tools import (
    build_architecture,
    build_commands,
    build_crib,
    build_rules,
    smoke,
)
from dragpoint.tools.support import DOCS, ROOT

__all__ = ["check_names", "checks", "main"]

CHECK_PREFIX = "check_"
"""What a check module is called. The name is the register."""


def check_names() -> tuple[str, ...]:
    """Every check module in the tools package, sorted.

    Sorted so a failing release reports them in the same order every time,
    which matters when the thing being compared is two CI logs.
    """
    package = import_module("dragpoint.tools")
    return tuple(
        sorted(
            module.name
            for module in pkgutil.iter_modules(list(package.__path__))
            if module.name.startswith(CHECK_PREFIX)
        )
    )


def checks() -> tuple[tuple[str, Callable[[], int]], ...]:
    """Every check, named, ready to run.

    A module without a ``main`` is a programming error rather than a failed
    release, so it raises here instead of being skipped quietly.
    """
    found: list[tuple[str, Callable[[], int]]] = []
    for name in check_names():
        module = import_module(f"dragpoint.tools.{name}")
        entry = getattr(module, "main", None)
        if entry is None:
            raise AttributeError(f"{name} is a check with no main to run")
        found.append((name, entry))
    return tuple(found)


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
    return version in _changelog_versions()


def _changelog_versions() -> tuple[str, ...]:
    """Every version the changelog has a heading for, newest first."""
    path = ROOT / "CHANGELOG.md"
    if not path.is_file():
        return ()
    return tuple(
        line.removeprefix("## ").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    )


def _changelog_leads_with(version: str) -> bool:
    """True when the newest thing in the changelog is this version.

    Mentioning the version somewhere is not enough. A release built from a
    branch that added its notes under an older heading passes the mention
    check and ships a changelog whose top entry is the version before it,
    which is exactly the file everybody reads first.
    """
    found = _changelog_versions()
    return bool(found) and found[0] == version


def main(arguments: Sequence[str] | None = None) -> int:
    """Run every check and every generated document check, and compare versions."""
    verbose = "--verbose" in list(sys.argv[1:] if arguments is None else arguments)
    problems: list[str] = []

    packaged = _pyproject_version()
    if packaged != __version__:
        problems.append(f"pyproject says {packaged} and the package says {__version__}")
    if not _changelog_mentions(__version__):
        problems.append(f"the changelog has nothing to say about {__version__}")
    elif not _changelog_leads_with(__version__):
        problems.append(f"the changelog leads with {_changelog_versions()[0]}, not {__version__}")
    for name in WANTED_DOCS:
        if not (DOCS / name).is_file():
            problems.append(f"docs/{name} is missing")

    for name, check in checks():
        if check() != 0:
            problems.append(f"{name} failed")
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
