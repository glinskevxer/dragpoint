"""Every module, class and public function has to say what it is for.

Not a style rule. The whole of this package is domain knowledge that is
obvious to the four people who cut plates for a living and to nobody else,
and the docstrings are where that knowledge lives. A public function without
one is a piece of the trade that has been lost.

A private function may go without. A private function that needs explaining
is usually a public one in the wrong place.

The first line has to end in a full stop and start with a capital, which is
the only part of this that is style, and it is here because a summary line
that runs into the next paragraph reads as a sentence fragment in every tool
that shows one.
"""

from __future__ import annotations

import ast
import sys

from dragpoint.tools.support import Problem, modules, report, source_files

__all__ = ["main"]

Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _is_public(name: str) -> bool:
    """True for a name that something outside the module could reach."""
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _wanted(node: ast.AST) -> bool:
    """True when this node has to carry a docstring.

    Dunder methods are exempt. ``__str__`` says what it is by being called
    ``__str__``, and a docstring on every one of them would be noise in the
    files that need reading most.
    """
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return False
    if node.name.startswith("__") and node.name.endswith("__"):
        return False
    return _is_public(node.name)


def _summary_problems(node: Definition, docstring: str) -> str | None:
    """What is wrong with the first line, if anything."""
    summary = docstring.strip().splitlines()[0] if docstring.strip() else ""
    if not summary:
        return f"{node.name} has an empty docstring"
    if not summary[0].isupper() and not summary.startswith(("``", '"')):
        return f"{node.name} summary does not start with a capital"
    if not summary.endswith((".", ":", "?")):
        return f"{node.name} summary does not end with a full stop"
    return None


def main() -> int:
    """Check every module, class and public function for a docstring."""
    problems: list[Problem] = []
    files = source_files()
    for path, tree in modules(files):
        if ast.get_docstring(tree) is None:
            problems.append(Problem(path, 1, "the module has no docstring"))
        for node in ast.walk(tree):
            if not _wanted(node):
                continue
            assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            docstring = ast.get_docstring(node)
            if docstring is None:
                problems.append(Problem(path, node.lineno, f"{node.name} has no docstring"))
                continue
            complaint = _summary_problems(node, docstring)
            if complaint is not None:
                problems.append(Problem(path, node.lineno, complaint))
    return report("docstrings", problems, len(files))


if __name__ == "__main__":
    sys.exit(main())
