"""What the checks and the generators both need.

These tools run over the checkout rather than over the installed package.
They are development tools: they read the source, they are run by CI, and
they are shipped inside the package only because that is the least
surprising place to find them when something they check has failed.

Every check has the same shape. It walks the source, collects problems as
``(path, line, message)``, prints them one per line and exits one if there
were any. Nothing prints on success except a single line saying what was
checked, because a check that says nothing at all is a check nobody notices
has stopped running.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import dragpoint

__all__ = [
    "DOCS",
    "PACKAGE",
    "ROOT",
    "SOURCE",
    "TESTS",
    "Problem",
    "modules",
    "parsed",
    "report",
    "source_files",
    "test_files",
]

PACKAGE = Path(dragpoint.__file__).resolve().parent
"""The ``dragpoint`` package directory."""

SOURCE = PACKAGE.parent
"""The ``src`` directory."""

ROOT = SOURCE.parent
"""The checkout."""

TESTS = ROOT / "tests"
DOCS = ROOT / "docs"


@dataclass(frozen=True, slots=True)
class Problem:
    """One thing a check is unhappy about."""

    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        try:
            where = self.path.relative_to(ROOT)
        except ValueError:  # pragma: no cover - only when run from a wheel
            where = self.path
        return f"{where}:{self.line}: {self.message}"


def source_files(*, skip_tools: bool = False) -> list[Path]:
    """Every Python file in the package, sorted, in a stable order."""
    files = sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)
    if skip_tools:
        files = [path for path in files if path.parent.name != "tools"]
    return files


def test_files() -> list[Path]:
    """Every Python file under ``tests``, sorted."""
    if not TESTS.is_dir():
        return []
    return sorted(path for path in TESTS.rglob("*.py") if "__pycache__" not in path.parts)


def parsed(path: Path) -> ast.Module:
    """Read and parse one file."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def modules(paths: Iterable[Path]) -> Iterator[tuple[Path, ast.Module]]:
    """Each path with its parsed tree."""
    for path in paths:
        yield path, parsed(path)


def dotted_name(path: Path) -> str:
    """The import name of a file inside the package."""
    relative = path.relative_to(SOURCE).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def report(name: str, problems: Iterable[Problem], counted: int) -> int:
    """Print the problems and hand back the exit code."""
    found = list(problems)
    for problem in found:
        print(str(problem), file=sys.stderr)
    if found:
        print(f"{name}: {len(found)} problems in {counted} files", file=sys.stderr)
        return 1
    print(f"{name}: {counted} files clean")
    return 0
