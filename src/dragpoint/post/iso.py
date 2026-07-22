"""ISO G code, for the controls that take it.

Written in the dialect the shop's own machines want, which is the common
subset and nothing else: G0 and G1, absolute, metric, no canned cycles, no
cutter compensation and no arcs. A legend plate is thousands of very short
straight moves and there is nothing in it an arc would help with.

Modal words are dropped when they have not changed. That is not a saving in
file size worth having on its own; it is a saving in what an operator has to
read when they scroll through the program looking for the one line where the
depth is wrong.

The work offset is written into the preamble rather than left to whatever
the control was last set to. A program that does not say which datum it
means is a program that will one day be run against the wrong one, and on a
machine with two fixtures on the bed that is a cutter into a clamp.

A fixture full of blanks comes out as a subprogram called once per blank
with a work shift in front of it. That is the whole reason a control has
subprograms, and it means twelve plates are one copy of the moves rather
than twelve, so the one place to fix a wrong depth stays one place.
"""

from __future__ import annotations

from dragpoint.path.plan import MoveKind, Toolpath
from dragpoint.post.base import PostOptions, post

__all__ = ["render_iso"]


SHIFT_OFF = "G52 X0 Y0"
"""Cancelling the work shift, which is left set otherwise."""


@post("iso", "ISO G code, absolute and metric", "nc")
def render_iso(path: Toolpath, options: PostOptions) -> str:
    """Render a toolpath as G code."""
    lines: list[str] = []
    _preamble(lines, options)
    if options.repeats > 1:
        _calls(lines, options)
    else:
        _body(lines, path, options)
    _postamble(lines, options)
    if options.repeats > 1:
        lines.append(f"O{_sub_number(options)}")
        _body(lines, path, options)
        lines.append("M99")
        lines.append("%")
    return _numbered(lines, options)


def _sub_number(options: PostOptions) -> int:
    """The number the repeated moves are filed under.

    One past the main program, which is what everybody does and what an
    operator looking for it will try first.
    """
    return options.number + 1


def _calls(lines: list[str], options: PostOptions) -> None:
    """One shift and one call per blank in the fixture."""
    sub = _sub_number(options)
    for x, y in options.offsets():
        shift = f"G52 X{options.coordinate(x)} Y{options.coordinate(y)}"
        lines.append(SHIFT_OFF if (x, y) == (0.0, 0.0) else shift)
        lines.append(f"M98 P{sub}")
    lines.append(SHIFT_OFF)


def _preamble(lines: list[str], options: PostOptions) -> None:
    """The header the control needs before anything moves."""
    lines.append("%")
    lines.append(f"O{options.number} ({options.program})")
    if options.comments:
        for note in options.notes:
            lines.append(f"({_comment_safe(note)})")
    lines.append(f"G21 G90 G17 G40 G49 G{options.work_offset}")
    lines.append(f"T{options.tool} M06")
    if options.spindle:
        lines.append(f"S{options.spindle} M03")


def _postamble(lines: list[str], options: PostOptions) -> None:
    """Stop the spindle and end the program.

    The trailing percent goes after the subprograms rather than here when
    there are any, because a control stops reading the file at it.
    """
    if options.spindle:
        lines.append("M05")
    lines.append("M30")
    if options.repeats == 1:
        lines.append("%")


def _body(lines: list[str], path: Toolpath, options: PostOptions) -> None:
    """Every move, with the modal words dropped where they repeat."""
    last_x: str | None = None
    last_y: str | None = None
    last_z: str | None = None
    last_feed: float | None = None
    last_code: str | None = None

    for move in path:
        code = "G00" if move.kind is MoveKind.RAPID else "G01"
        x = options.coordinate(move.to.x)
        y = options.coordinate(move.to.y)
        z = options.coordinate(move.z)
        words: list[str] = []
        if code != last_code:
            words.append(code)
            last_code = code
        if x != last_x:
            words.append(f"X{x}")
            last_x = x
        if y != last_y:
            words.append(f"Y{y}")
            last_y = y
        if z != last_z:
            words.append(f"Z{z}")
            last_z = z
        if move.feed is not None and move.feed != last_feed:
            words.append(f"F{move.feed:g}")
            last_feed = move.feed
        if words:
            lines.append(" ".join(words))


def _numbered(lines: list[str], options: PostOptions) -> str:
    """Add sequence numbers if they were asked for, and end with a newline."""
    if not options.line_numbers:
        return "\n".join(lines) + "\n"
    numbered: list[str] = []
    sequence = 10
    for line in lines:
        if line.startswith("%"):
            numbered.append(line)
            continue
        numbered.append(f"N{sequence} {line}")
        sequence += 10
    return "\n".join(numbered) + "\n"


def _comment_safe(text: str) -> str:
    """Strip the characters a comment cannot carry.

    Brackets close the comment early on every control that reads this
    dialect, and a program that ends its comment early starts reading the
    rest of the sentence as words.
    """
    return text.replace("(", "[").replace(")", "]")
