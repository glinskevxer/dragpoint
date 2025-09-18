"""Names have to say something, and constants have to say what they are.

Two rules, both learned the hard way.

A public name with a vague word in it is a name that will be reached for by
whoever cannot find the right one. There is no ``utils`` in this package and
there is not going to be, because the first thing anybody puts in a ``utils``
is the thing that belonged in the module they were too busy to open.

A module level constant is a number somebody chose. Six months later nobody
remembers why it is 0.15 rather than 0.2, and the only place that reason can
live is under the constant. So every public one carries a docstring, the same
way a function does, and this check is what keeps that true.
"""

from __future__ import annotations

import ast
import re
import sys

from dragpoint.tools.support import Problem, modules, report, source_files

__all__ = ["BANNED", "main"]

BANNED = {
    "util",
    "utils",
    "helper",
    "helpers",
    "manager",
    "handler",
    "misc",
    "stuff",
    "thing",
    "temp",
    "tmp",
    "data2",
    "impl",
}
"""Words a public name may not contain. Every one of them means nothing."""

EXEMPT_ASSIGNMENTS = {"TypeVar", "ParamSpec", "TypeAlias", "NewType"}
"""Right hand sides that are type machinery rather than a decided number."""


def _is_constant_name(name: str) -> bool:
    """True for a public module level constant."""
    return name.isupper() and not name.startswith("_") and len(name) > 1


def _documented(body: list[ast.stmt], index: int) -> bool:
    """True when the statement after ``index`` is a bare string."""
    if index + 1 >= len(body):
        return False
    following = body[index + 1]
    return (
        isinstance(following, ast.Expr)
        and isinstance(following.value, ast.Constant)
        and isinstance(following.value.value, str)
    )


def _machinery(node: ast.stmt) -> bool:
    """True when an assignment is type machinery rather than a real constant."""
    value = getattr(node, "value", None)
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return value.func.id in EXEMPT_ASSIGNMENTS
    return False


def _words(name: str) -> set[str]:
    """The words in a name, whether it is snake case or capitals.

    ``PlateManager`` and ``plate_manager`` are the same name written two
    ways, and a check that only understood one of them would let the class
    through and stop the function.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {part.lower() for part in spaced.split("_") if part}


def _vague(name: str) -> str | None:
    """The banned word in a name, if there is one."""
    parts = _words(name)
    for word in sorted(BANNED):
        if word in parts:
            return word
    return None


def main() -> int:
    """Check public names for vague words and constants for docstrings."""
    problems: list[Problem] = []
    files = source_files()
    for path, tree in modules(files):
        word = _vague(path.stem)
        if word is not None:
            problems.append(Problem(path, 1, f"the module name says {word!r}, which says nothing"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                found = _vague(node.name)
                if found is not None and not node.name.startswith("_"):
                    problems.append(
                        Problem(
                            path, node.lineno, f"{node.name} says {found!r}, which says nothing"
                        )
                    )
        for index, node in enumerate(tree.body):
            names: list[str] = []
            if isinstance(node, ast.Assign):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            for name in names:
                if not _is_constant_name(name) or _machinery(node):
                    continue
                if not _documented(tree.body, index):
                    problems.append(Problem(path, node.lineno, f"{name} has no docstring under it"))
    return report("naming", problems, len(files))


if __name__ == "__main__":
    sys.exit(main())
