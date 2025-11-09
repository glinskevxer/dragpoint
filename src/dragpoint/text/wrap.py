"""Breaking a legend into lines that fit.

A schedule usually says where the line breaks go, because whoever wrote it
knows that ISOLATE BEFORE / WORKING reads better than ISOLATE / BEFORE
WORKING. Sometimes it does not, and the legend arrives as one long string
off a spreadsheet with no idea in it about where it should break.

The breaking is greedy and measured. It puts as many words on a line as the
width will take and starts another, using the real shaped width rather than
a character count, because a legend in this face is nowhere near monospaced
and counting characters puts the break in the wrong place about a third of
the time.

A word that will not fit on a line of its own is left where it is rather
than broken. Hyphenating PUSHBUTTON in the middle would be worse than the
overrun, and the overrun is something the fitter or a rule will speak up
about anyway.
"""

from __future__ import annotations

from dragpoint.errors import OutOfRange
from dragpoint.font.face import StrokeFace
from dragpoint.text.fit import measure_lines
from dragpoint.text.style import TextStyle
from dragpoint.units import QUANTUM

__all__ = ["longest_word", "wrap_lines", "wrap_to_box"]


def wrap_lines(
    text: str,
    face: StrokeFace,
    style: TextStyle,
    limit: float,
    *,
    max_lines: int | None = None,
) -> list[str]:
    """Break ``text`` into lines no wider than ``limit`` millimetres.

    ``max_lines`` stops the breaking and puts everything that is left on the
    last line, which is what a plate with room for two lines and nothing
    else has to do. The last line comes out too wide and says so, rather
    than a third line appearing off the bottom of the plate where nobody
    would see it until the plate did not fit the panel.
    """
    if limit <= 0.0:
        raise OutOfRange("width limit", limit, QUANTUM, float("inf"))
    if max_lines is not None and max_lines < 1:
        raise OutOfRange("max lines", max_lines, 1, float("inf"))

    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if max_lines is not None and len(lines) == max_lines - 1:
            current = f"{current} {word}"
            continue
        candidate = f"{current} {word}"
        if measure_lines([candidate], face, style) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def wrap_to_box(
    text: str,
    face: StrokeFace,
    style: TextStyle,
    width: float,
    height: float,
) -> list[str]:
    """Break ``text`` to ``width``, using no more lines than ``height`` allows.

    The line count comes out of the height and the pitch, so a tall plate
    breaks a legend into more lines than a short one does and both of them
    keep the lettering at the size the drawing asked for.
    """
    if height <= 0.0:
        raise OutOfRange("height", height, QUANTUM, float("inf"))
    pitch = style.resolved_line_pitch(face)
    room = max(1, int((height + pitch * 0.05) // pitch))
    return wrap_lines(text, face, style, width, max_lines=room)


def longest_word(text: str, face: StrokeFace, style: TextStyle) -> float:
    """The width of the widest single word, which is the narrowest a wrap gets.

    Nothing can break a legend narrower than its longest word, so this is
    the number to compare a plate against before deciding that wrapping will
    save it.
    """
    words = text.split()
    if not words:
        return 0.0
    return max(measure_lines([word], face, style) for word in words)
