"""Every module has a test module, and every test module has a module.

Not a coverage measure. Coverage says how many lines ran; this says whether
anybody sat down and thought about a file. A module with no test file beside
it has usually been tested through something else, which works until that
something else changes and takes the only evidence with it.

The mapping is a mirror. ``src/dragpoint/geometry/point.py`` is tested by
``tests/geometry/test_point.py`` and by nothing else, so the file to open
when a test fails is never in doubt.

It runs both ways. A test module with no source module beside it is a test
for something that has been deleted or renamed, and it is still passing.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from dragpoint.tools.support import (
    PACKAGE,
    TESTS,
    Problem,
    parsed,
    report,
    source_files,
    test_files,
)

__all__ = ["MIN_TESTS", "main"]

MIN_TESTS = 5
"""A test module with fewer than this has not really been thought about."""

SKIP_DIRECTORIES = {"tools"}
"""Package directories whose tests are optional rather than mirrored."""


def _expected_test(path: Path) -> Path:
    """Where the tests for one source file have to live."""
    relative = path.relative_to(PACKAGE)
    return TESTS / relative.parent / f"test_{relative.stem}.py"


def _expected_source(path: Path) -> Path:
    """Which source file a test module is the test for."""
    relative = path.relative_to(TESTS)
    return PACKAGE / relative.parent / f"{relative.stem.removeprefix('test_')}.py"


def _test_count(path: Path) -> int:
    """How many test functions a test module holds."""
    tree = parsed(path)
    return sum(
        1
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )


def main() -> int:
    """Check that source and tests mirror each other."""
    problems: list[Problem] = []
    sources = [
        path
        for path in source_files()
        if path.name != "__init__.py" and path.parent.name not in SKIP_DIRECTORIES
    ]
    for path in sources:
        wanted = _expected_test(path)
        if not wanted.is_file():
            problems.append(
                Problem(path, 1, f"no test module, expected {wanted.relative_to(TESTS.parent)}")
            )

    tests = [
        path
        for path in test_files()
        if path.name.startswith("test_") and path.name != "__init__.py"
    ]
    for path in tests:
        source = _expected_source(path)
        if not source.is_file() and source.parent.name not in SKIP_DIRECTORIES:
            problems.append(Problem(path, 1, "tests a module that is not there"))
        found = _test_count(path)
        if found < MIN_TESTS:
            problems.append(Problem(path, 1, f"only {found} tests, wanted {MIN_TESTS}"))

    return report("tests", problems, len(sources) + len(tests))


if __name__ == "__main__":
    sys.exit(main())
