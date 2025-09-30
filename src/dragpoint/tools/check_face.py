"""The shipped faces have to obey the rules written at the top of them.

A stroke face is data, and data rots quietly. Somebody opens a .strk file to
nudge one letter, the letter looks right on screen, and six weeks later a
pair of plates come back from a customer with two letters run together at the
bottom of a legend nobody checked.

Every rule here is a number from the header of the face file. They are not
opinions about drawing; they are what makes the face safe with the cutters
this shop owns, and the header says so.

The separation rule is the one that matters. Two strokes in a glyph either
meet, on purpose, or they stay a clear distance apart. Anything in between
is a gap the cutter will bridge at some depth and not at others, which is
the worst kind of fault: it passes the first article and fails the batch.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dragpoint.font.face import StrokeFace
from dragpoint.font.library import load_face, shipped_names
from dragpoint.font.parse import parse_face
from dragpoint.geometry.nearness import closest_approach, self_approach
from dragpoint.tools.support import PACKAGE, Problem, report

__all__ = [
    "MAX_KERN",
    "MIN_BEARING",
    "MIN_SEPARATION",
    "MIN_STROKE",
    "REQUIRED",
    "main",
]

MIN_SEPARATION = 90.0
"""Font units two strokes must keep apart unless they deliberately meet."""

MIN_BEARING = 80.0
"""Font units of clear space each side of the marks inside the advance."""

MAX_KERN = 30
"""Font units a kern may pull a pair together, at most."""

MIN_STROKE = 20.0
"""Font units a stroke must be long, below which it is a dimple."""

TOUCH = 2.0
"""Font units within which two strokes count as meeting on purpose."""

REQUIRED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-/()"
"""Every face has to draw these. A legend plate cannot be set without them."""


def face_path(name: str) -> Path:
    """Where a shipped face lives in the checkout."""
    return PACKAGE / "font" / "faces" / f"{name}.strk"


def _glyph_problems(path: Path, face: StrokeFace, glyph_name: str) -> list[Problem]:
    """Everything wrong with one glyph."""
    glyph = face.glyph(glyph_name)
    box = glyph.ink_bounds()
    if box is None:
        return []
    problems: list[Problem] = []
    upem = face.metrics.units_per_em

    gap = closest_approach(glyph.strokes, touch=TOUCH)
    if gap < MIN_SEPARATION:
        problems.append(
            Problem(
                path,
                1,
                f"{glyph_name}: two strokes are {gap:.1f} units apart, wanted {MIN_SEPARATION:.0f}",
            )
        )

    for stroke in glyph.strokes:
        folded = self_approach(stroke, min_arc=upem / 2.0, touch=TOUCH)
        if folded < MIN_SEPARATION:
            problems.append(
                Problem(path, 1, f"{glyph_name}: a stroke closes to {folded:.1f} units on itself")
            )
        if stroke.length() < MIN_STROKE:
            problems.append(
                Problem(path, 1, f"{glyph_name}: a stroke is only {stroke.length():.1f} units")
            )

    if box.min_x < MIN_BEARING - 0.5:
        problems.append(Problem(path, 1, f"{glyph_name}: left bearing is {box.min_x:.1f} units"))
    right = glyph.advance - box.max_x
    if right < MIN_BEARING - 0.5:
        problems.append(Problem(path, 1, f"{glyph_name}: right bearing is {right:.1f} units"))
    return problems


def check_face(name: str, face: StrokeFace) -> list[Problem]:
    """Everything wrong with one face."""
    path = face_path(name)
    problems: list[Problem] = [
        Problem(path, 1, f"{name} cannot draw {missing!r}") for missing in face.missing(REQUIRED)
    ]
    for glyph_name in face.names():
        problems.extend(_glyph_problems(path, face, glyph_name))
    for (left, right), value in sorted(face.kerning.items()):
        if abs(value) > MAX_KERN:
            problems.append(
                Problem(path, 1, f"kern {left} {right} is {value}, more than {MAX_KERN}")
            )
    return problems


def main() -> int:
    """Check every shipped face against the rules in its own header."""
    problems: list[Problem] = []
    names = shipped_names()
    for name in names:
        face = load_face(name)
        problems.extend(check_face(name, face))
        again = parse_face(face_path(name).read_text(encoding="utf-8"))
        if again.names() != face.names():
            problems.append(Problem(face_path(name), 1, "the file does not parse back the same"))
    return report("faces", problems, len(names))


if __name__ == "__main__":
    sys.exit(main())
