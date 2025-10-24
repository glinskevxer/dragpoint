"""Write the architecture page out of the layer ranks and the docstrings.

The stack is the design. Everything else in this package is a consequence of
it, and somebody arriving at the code for the first time needs the stack
before they need anything else.

Both halves of this page come from the code: the order from the ranks the
layer check enforces, and the description of each layer from the docstring at
the top of its package. A page that agreed with neither would be worse than
none, and one written by hand eventually agrees with neither.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence

from dragpoint.tools.check_layers import RANKS
from dragpoint.tools.generate import generated, run
from dragpoint.tools.support import DOCS, PACKAGE, parsed

__all__ = ["main"]

TOOL = "dragpoint.tools.build_architecture"
"""The module name that goes in the do not edit line."""


def _docstring_for(layer: str) -> str:
    """The first paragraph of a layer's own docstring."""
    package = PACKAGE / layer / "__init__.py"
    module = PACKAGE / f"{layer}.py"
    path = package if package.is_file() else module
    if not path.is_file():
        return ""
    text = ast.get_docstring(parsed(path)) or ""
    paragraphs = text.strip().split("\n\n")
    return " ".join(paragraphs[0].split()) if paragraphs else ""


def _modules_in(layer: str) -> list[str]:
    """Every module in one layer, sorted, without its init."""
    directory = PACKAGE / layer
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.py") if path.name != "__init__.py")


def _body() -> list[str]:
    """The document: the stack, then a section for each layer."""
    ordered = sorted(RANKS.items(), key=lambda entry: (entry[1], entry[0]))
    lines = [
        "dragpoint is a stack. Every import goes downwards and nothing reaches up,",
        "which is what makes each layer testable without the ones above it.",
        "",
        "`dragpoint.tools.check_layers` enforces exactly the order below, so an",
        "import that would break it fails the build rather than the review.",
        "",
        "| layer | rank | what it is |",
        "| --- | --- | --- |",
    ]
    for layer, rank in ordered:
        lines.append(f"| `dragpoint.{layer}` | {rank} | {_docstring_for(layer)} |")

    lines.extend(["", "## What is in each layer", ""])
    for layer, _ in ordered:
        modules = _modules_in(layer)
        if not modules:
            continue
        listed = ", ".join(f"`{name}`" for name in modules)
        lines.append(f"- **`dragpoint.{layer}`** {listed}")
    return lines


def main(arguments: Sequence[str] | None = None) -> int:
    """Write or check the architecture page.

    ``arguments`` defaults to the command line, and is a parameter so a test
    can ask for a check without going near ``sys.argv``.
    """
    wanted = list(sys.argv[1:] if arguments is None else arguments)
    text = generated(TOOL, "Architecture", _body())
    return run(DOCS / "architecture.md", text, wanted)


if __name__ == "__main__":
    sys.exit(main())
