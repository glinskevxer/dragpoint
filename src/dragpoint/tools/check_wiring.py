"""Nothing in the package is written and then never reached.

A module with a green test suite and no caller is not tested where it
matters. It is tested where it was written, which is the one place it was
certainly going to work. The failure is quiet and it survives a review,
because every individual file looks fine.

So every module has to be imported by something. The exceptions are the ones
that are entry points rather than libraries: the package inits, the tools,
which CI runs by name, and the command line root, which the console script
names in the packaging metadata.

The other half of the same question is the register decorators. A rule or a
post that is defined and never imported is registered nowhere and silently
does nothing, so the register modules are checked to import every module
beside them.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from dragpoint.tools.support import PACKAGE, Problem, dotted_name, modules, report, source_files

__all__ = ["ENTRY_POINTS", "main"]

ENTRY_POINTS = {
    "dragpoint.__main__",
    "dragpoint.cli.main",
    "dragpoint.tools.support",
}
"""Modules nothing imports because something outside the package runs them.

``__main__`` is the clearest case there is: the thing that imports it is the
interpreter, when somebody types ``python -m dragpoint``, and a package that
imported its own ``__main__`` would run the command line on import.
"""

REGISTERS = {
    "dragpoint.rules": "dragpoint.rules",
    "dragpoint.post": "dragpoint.post",
}
"""Package inits that have to import every module beside them."""


def _imported_names(tree: ast.Module) -> set[str]:
    """Every dragpoint module this file names in an import."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return {name for name in names if name.startswith("dragpoint")}


def _neighbours(package: str) -> set[str]:
    """Every module beside a package init, by dotted name."""
    directory = PACKAGE.parent / Path(package.replace(".", "/"))
    return {
        dotted_name(path) for path in sorted(directory.glob("*.py")) if path.name != "__init__.py"
    }


def main() -> int:
    """Check that every module is imported and every register is complete."""
    problems: list[Problem] = []
    files = source_files()
    trees = dict(modules(files))
    reached: set[str] = set()
    for tree in trees.values():
        reached.update(_imported_names(tree))

    for path in files:
        name = dotted_name(path)
        if path.name == "__init__.py" or name in ENTRY_POINTS:
            continue
        if path.parent.name == "tools":
            continue
        if name not in reached:
            problems.append(Problem(path, 1, f"{name} is imported by nothing"))

    for package, holder in REGISTERS.items():
        init = PACKAGE.parent / Path(holder.replace(".", "/")) / "__init__.py"
        names = _imported_names(trees[init])
        for neighbour in sorted(_neighbours(package)):
            if neighbour not in names:
                problems.append(
                    Problem(init, 1, f"{neighbour} is not imported, so it registers nothing")
                )
    return report("wiring", problems, len(files))


if __name__ == "__main__":
    sys.exit(main())
