"""The packages are a stack and imports only ever go downwards.

Geometry knows nothing about fonts. Fonts know nothing about millimetres.
Text knows nothing about cutters. The cutter knows nothing about plates. Each
of those is what makes the layer below testable on its own, and every one of
them would be lost the first time somebody reached upwards for something
convenient.

The ranks below are the whole design of the package in fifteen lines. An
import that goes up the stack is either a mistake or a sign that the thing
being reached for is in the wrong place, and it is nearly always the second.

Within one package anything may import anything. The stack is about packages
and not about files.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from dragpoint.tools.support import PACKAGE, Problem, modules, report, source_files

__all__ = ["RANKS", "main"]

RANKS: dict[str, int] = {
    "errors": 0,
    "units": 1,
    "geometry": 2,
    "font": 3,
    "text": 4,
    "tool": 5,
    "spec": 6,
    "rules": 7,
    "path": 8,
    "nest": 8,
    "post": 9,
    "compiler": 10,
    "draw": 11,
    "estimate": 11,
    "report": 12,
    "cli": 13,
    "tools": 14,
}
"""Package to its place in the stack. Lower is further down."""


def _package_of(dotted: str) -> str | None:
    """The layer a dotted name belongs to, or ``None`` for anything else."""
    parts = dotted.split(".")
    if not parts or parts[0] != "dragpoint" or len(parts) < 2:
        return None
    return parts[1]


def _own_layer(path: Path) -> str | None:
    """The layer a file in the package belongs to.

    A file directly under ``dragpoint`` is its own layer, which is how
    ``units`` and ``errors`` sit at the bottom without a package each.
    """
    relative = path.relative_to(PACKAGE)
    name = relative.parts[0]
    if name.endswith(".py"):
        name = name[:-3]
    return name if name in RANKS else None


def _imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Every dragpoint name this module imports, with the line it is on."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
    return found


def main() -> int:
    """Check that no import goes up the stack."""
    problems: list[Problem] = []
    files = source_files()
    for path, tree in modules(files):
        own = _own_layer(path)
        if own is None:
            continue
        rank = RANKS[own]
        for line, imported in _imports(tree):
            other = _package_of(imported)
            if other is None or other == own:
                continue
            if other not in RANKS:
                problems.append(Problem(path, line, f"{imported} is in no layer"))
                continue
            if RANKS[other] >= rank:
                problems.append(
                    Problem(
                        path,
                        line,
                        f"{own} is above {other} and must not import it",
                    )
                )
    return report("layers", problems, len(files))


if __name__ == "__main__":
    sys.exit(main())
