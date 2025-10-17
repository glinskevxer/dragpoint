"""Write the rule reference out of the register.

The rules are the part of this package a customer argues with. When a plate
comes back rejected, the conversation is about which rule fired and what its
number is, and a list that was typed by hand would by then be a list of the
rules as they were the day somebody typed it.

So the document is the register. Every rule in it is a rule that runs.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from dragpoint.rules.check import REGISTRY
from dragpoint.rules.legibility import FOLD_RATIO, JOINT_FRACTION, MAX_WEIGHT_RATIO
from dragpoint.rules.process import MAX_SENSIBLE_PASSES, PLUNGE_RATIO
from dragpoint.tools.generate import generated, run
from dragpoint.tools.support import DOCS

__all__ = ["main"]

TOOL = "dragpoint.tools.build_rules"
"""The module name that goes in the do not edit line."""

NUMBERS = (
    ("joint fraction", JOINT_FRACTION, "of the cap height, within which two strokes are joined"),
    ("fold ratio", FOLD_RATIO, "times further along a stroke than across it before it is a fold"),
    ("weight ratio", MAX_WEIGHT_RATIO, "of the cap height, past which the groove is too wide"),
    ("sensible passes", MAX_SENSIBLE_PASSES, "passes, past which the depth is worth a second look"),
    ("plunge ratio", PLUNGE_RATIO, "times its own width, past which a parallel cutter is buried"),
)
"""The numbers the rules turn on, with what each of them is a fraction of."""


def _body() -> list[str]:
    """The document, section by section."""
    lines = [
        "Every rule below runs on every plate unless a job turns it off.",
        "",
        "A rule reports what it measured and what the limit was. It never changes",
        "anything: a plate that fails a rule comes out of the compiler exactly as",
        "it was asked for, with the failure written down beside it.",
        "",
        "| rule | severity | what it checks |",
        "| --- | --- | --- |",
    ]
    for definition in REGISTRY.values():
        lines.append(f"| `{definition.name}` | {definition.severity} | {definition.description} |")
    lines.extend(
        [
            "",
            "## Severity",
            "",
            "`error` stops a job. `warning` is printed and the job goes on, because",
            "the operator is the one who decides whether heavy lettering matters on",
            "this plate. `note` is something worth knowing and nothing more.",
            "",
            "## The numbers",
            "",
            "| number | value | what it is |",
            "| --- | --- | --- |",
        ]
    )
    for name, value, meaning in NUMBERS:
        lines.append(f"| {name} | {value:g} | {meaning} |")
    return lines


def main(arguments: Sequence[str] | None = None) -> int:
    """Write or check the rule reference.

    ``arguments`` defaults to the command line, and is a parameter so a test
    can ask for a check without going near ``sys.argv``.
    """
    wanted = list(sys.argv[1:] if arguments is None else arguments)
    text = generated(TOOL, "Rules", _body())
    return run(DOCS / "rules.md", text, wanted)


if __name__ == "__main__":
    sys.exit(main())
