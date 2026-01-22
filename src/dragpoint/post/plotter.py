"""The pen up and pen down language the older engraving machines speak.

There is no Z axis in this file. The machine has a spring loaded head with a
depth nose that rides on the work, and how deep it cuts is a setting made
once at the top of the program in microns. Depth therefore comes out as a
tool setting rather than as a coordinate, and a change of depth is a change
of setting rather than a move.

Coordinates are plotter units, forty to the millimetre, and integer. That is
a twenty five micron step, which is coarser than the machine positions to
and much coarser than the rest of this package works in, so the rounding
happens here and once. Rounding earlier would have the same file come out
differently depending on which post ran.

There is nothing like a subprogram in this language, so a fixture full of
blanks comes out longhand: the moves are written once per blank with the
offset already in the coordinates. The files get long and the machines that
read them do not care.
"""

from __future__ import annotations

from dragpoint.geometry.point import Point
from dragpoint.path.plan import Move, MoveKind, Toolpath
from dragpoint.post.base import PostOptions, post

__all__ = ["UNITS_PER_MM", "render_plotter"]

UNITS_PER_MM = 40
"""Plotter units to the millimetre. Twenty five microns a step."""


@post("plotter", "pen up and pen down for a nose riding engraver", "plt")
def render_plotter(path: Toolpath, options: PostOptions) -> str:
    """Render a toolpath as plotter commands."""
    commands: list[str] = ["IN", f"SP{options.tool}"]
    if options.comments:
        commands.append(f"CO{_quoted(options.program)}")
        commands.extend(f"CO{_quoted(note)}" for note in options.notes)
    if options.spindle:
        commands.append(f"!SPN{options.spindle}")

    depth: int | None = None
    for shift_x, shift_y in options.offsets():
        depth = _blank(commands, path, depth, shift_x, shift_y)
    commands.append("!END")
    return ";\n".join(commands) + ";\n"


def _blank(
    commands: list[str], path: Toolpath, depth: int | None, shift_x: float, shift_y: float
) -> int | None:
    """One copy of the moves, shifted onto one blank in the fixture.

    The depth setting carries across blanks, because the head has not been
    touched between them and repeating the setting would only be noise.
    """
    pen_down = False
    for move in path:
        if move.kind is MoveKind.PLUNGE:
            wanted = _microns(-move.z)
            if wanted != depth:
                commands.append(f"!DEP{wanted}")
                depth = wanted
            continue
        if move.kind is MoveKind.LIFT:
            if pen_down:
                commands.append("PU")
                pen_down = False
            continue
        if move.kind is MoveKind.RAPID:
            if pen_down:
                commands.append("PU")
                pen_down = False
            commands.append(f"PU{_pair(move.to, shift_x, shift_y)}")
            continue
        if not pen_down:
            commands.append("PD")
            pen_down = True
        commands.append(f"PD{_pair(move.to, shift_x, shift_y)}")
    if pen_down:
        commands.append("PU")
    return depth


def _pair(point: Point, shift_x: float = 0.0, shift_y: float = 0.0) -> str:
    """One coordinate pair in plotter units, the fixture offset included."""
    return (
        f"{round((point.x + shift_x) * UNITS_PER_MM)},{round((point.y + shift_y) * UNITS_PER_MM)}"
    )


def _microns(millimetres: float) -> int:
    """A depth in whole microns, which is what the depth setting takes."""
    return max(0, round(millimetres * 1000.0))


def _quoted(text: str) -> str:
    """Text with the characters that would end a command taken out.

    A semicolon in a comment ends the comment and starts the rest of it as
    commands, and the machine will happily try to run them.
    """
    return '"' + text.replace(";", ",").replace('"', "'") + '"'


def first_pen_down(path: Toolpath) -> Move | None:
    """The first move that puts the cutter into the work.

    Here because the plotter file has no Z in it and the setter needs to
    know where the head will first come down, which on a machine with no
    soft limits is worth checking before pressing start.
    """
    for move in path:
        if move.kind is MoveKind.PLUNGE:
            return move
    return None
