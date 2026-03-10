"""The job file the bench laser marker imports.

The shop has a small fibre marker for stainless tags, because a 304 tag cut
with a rotary cutter costs four cutters and an afternoon and a marked one
costs ninety seconds. It is a different machine with a different idea of
what a job is, and this is the only place in the package that has to know
about it.

Three things are different from a milling post and all three fall out of one
fact: there is no cutter, so there is no depth.

The beam has no Z, so a plunge is not a move. Where the milling posts write a
plunge and a lift, this writes the start and the end of a marked line, and
the rapid moves between them do not appear at all: the beam is off, the
galvos get there in under a millisecond, and a file full of positioning moves
would be a file describing something that does not happen.

Depth becomes passes, and it does so without anything here arranging it. A
plate planned for three cutting passes has three cuts along every line in
its toolpath, so the same line comes out of here three times and the beam
goes over it three times. That is exactly what makes a mark you can read on
stainless rather than a smudge, and it means a plate sent to the mill and to
the marker carries the same weight of line on both.

Power and speed are not in the toolpath because they are not machining. They
are settings for this machine and this material, they live in the options,
and the operator changes them on the machine anyway.
"""

from __future__ import annotations

from dragpoint.geometry.point import Point
from dragpoint.path.plan import MoveKind, Toolpath
from dragpoint.post.base import PostOptions, post

__all__ = ["DEFAULT_POWER", "DEFAULT_SPEED", "render_marker"]

DEFAULT_POWER = 60
"""Per cent of full power, which is what marks 304 without cutting into it."""

DEFAULT_SPEED = 400
"""Millimetres a second the beam is swept at."""

DEFAULT_FREQUENCY = 20
"""Kilohertz. Low enough that the pulses overlap into a line."""


@post("marker", "job file for the bench laser marker", "lmk")
def render_marker(path: Toolpath, options: PostOptions) -> str:
    """Render a toolpath as a marker job file.

    One ``LINE`` block per marked run, with the points that get marked and
    nothing else. The repeats in the options are honoured the way the
    plotter honours them, by writing the geometry once per blank with the
    offset in the coordinates, because the marker has no work offsets.
    """
    lines: list[str] = [
        "; dragpoint marker job",
        f"NAME {_clean(options.program)}",
        f"POWER {DEFAULT_POWER}",
        f"SPEED {DEFAULT_SPEED}",
        f"FREQ {DEFAULT_FREQUENCY}",
    ]
    if options.comments:
        lines.extend(f"; {_clean(note)}" for note in options.notes)
    for shift_x, shift_y in options.offsets():
        lines.extend(_blank(path, options, shift_x, shift_y))
    lines.append("END")
    return "\n".join(lines) + "\n"


def _blank(path: Toolpath, options: PostOptions, shift_x: float, shift_y: float) -> list[str]:
    """Every marked line on one blank, at one offset."""
    lines: list[str] = []
    run: list[Point] = []
    for move in path:
        if move.kind is MoveKind.FEED:
            run.append(move.to)
            continue
        if move.kind is MoveKind.PLUNGE:
            run = [move.to]
            continue
        if run:
            lines.append(_line(run, options, shift_x, shift_y))
            run = []
    if run:
        lines.append(_line(run, options, shift_x, shift_y))
    return lines


def _line(points: list[Point], options: PostOptions, shift_x: float, shift_y: float) -> str:
    """One marked run as a single block.

    A run of one point is a dot and is written as one anyway. The marker
    takes it, burns a spot, and that is what an i dot on a two millimetre
    legend is: a spot.
    """
    written = " ".join(
        f"{options.coordinate(point.x + shift_x)},{options.coordinate(point.y + shift_y)}"
        for point in points
    )
    return f"LINE {written}"


def _clean(text: str) -> str:
    """Text with the two characters the importer treats as structure taken out.

    A semicolon starts a comment and a newline ends a block. A plate called
    something with either in it is unlikely and would go wrong quietly,
    which is the sort of thing that only happens on a Friday.
    """
    return text.replace(";", ",").replace("\n", " ").strip()
