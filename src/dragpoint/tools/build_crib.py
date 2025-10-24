"""Write the crib page out of the cutter and stock tables.

This is the page that gets printed and stuck on the wall by the machine. It
is the tool crib and the stock rack, with the numbers that decide a setup:
what a cutter leaves at depth, and what depth a sheet will take.

The groove widths are worked out rather than listed, so a change to a cutter
in the table moves every number on the page that depends on it.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from dragpoint.tool.cutter import CATALOGUE, Cutter
from dragpoint.tool.material import MATERIALS
from dragpoint.tools.generate import generated, run
from dragpoint.tools.support import DOCS

__all__ = ["main"]

TOOL = "dragpoint.tools.build_crib"
"""The module name that goes in the do not edit line."""

DEPTHS = (0.1, 0.2, 0.3, 0.5, 0.8)
"""Depths in millimetres the groove width table is worked out at."""


def _groove_at(cutter: Cutter, depth: float) -> str:
    """The groove a cutter leaves at one depth, or a dash if it cannot reach."""
    if depth > cutter.max_depth:
        return "-"
    return f"{cutter.width_at_depth(depth):.3f}"


def _body() -> list[str]:
    """The document: the cutters, then the stock."""
    lines = [
        "What the shop holds, and the numbers a setup turns on.",
        "",
        "## Cutters",
        "",
        "A conical cutter leaves a groove as wide as the depth makes it. The",
        "columns are the groove width in millimetres at each depth, which is the",
        "number every legibility rule is measured against.",
        "",
        "| cutter | tip | angle | max depth | " + " | ".join(f"{depth:g}mm" for depth in DEPTHS),
        "| --- | --- | --- | --- | " + " | ".join("---" for _ in DEPTHS),
    ]
    for name in sorted(CATALOGUE):
        cutter = CATALOGUE[name]
        angle = "parallel" if cutter.is_parallel else f"{cutter.included_angle:g}"
        widths = " | ".join(_groove_at(cutter, depth) for depth in DEPTHS)
        lines.append(
            f"| `{name}` | {cutter.tip_width:.3f} | {angle} | {cutter.max_depth:g} | {widths}"
        )

    lines.extend(
        [
            "",
            "## Stock",
            "",
            "Two ply laminate has a floor as well as a ceiling: too shallow and the",
            "cap never breaks through, too deep and there is nothing holding the",
            "sheet together. Solid stock has no floor.",
            "",
            "| stock | what it is | thickness | cap | depth window | nominal | feed | spindle |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for name in sorted(MATERIALS):
        sheet = MATERIALS[name]
        low, high = sheet.depth_window()
        cap = f"{sheet.cap:g}" if sheet.cap is not None else "solid"
        lines.append(
            f"| `{name}` | {sheet.description} | {sheet.thickness:g} | {cap} | "
            f"{low:.2f} to {high:.2f} | {sheet.nominal_depth:g} | "
            f"{sheet.feed:g} | {sheet.spindle} |"
        )
    return lines


def main(arguments: Sequence[str] | None = None) -> int:
    """Write or check the crib page.

    ``arguments`` defaults to the command line, and is a parameter so a test
    can ask for a check without going near ``sys.argv``.
    """
    wanted = list(sys.argv[1:] if arguments is None else arguments)
    text = generated(TOOL, "The crib", _body())
    return run(DOCS / "crib.md", text, wanted)


if __name__ == "__main__":
    sys.exit(main())
