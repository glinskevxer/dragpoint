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

A break is also allowed after a hyphen or a slash that is already in the
legend. That is not hyphenation: nothing is added and nothing is invented,
the break goes where the writer already put a mark, and the mark stays on
the upper line where a reader expects it. It matters more than it sounds
like it should, because half the legends through this shop are things like
PUMP-HOUSE ISOLATOR and ON/OFF, and a plate that breaks those anywhere else
has to be set smaller to fit.
"""

from __future__ import annotations

from dragpoint.errors import OutOfRange
from dragpoint.font.face import StrokeFace
from dragpoint.text.fit import measure_lines
from dragpoint.text.style import TextStyle
from dragpoint.units import QUANTUM

__all__ = ["BREAK_AFTER", "longest_word", "wrap_lines", "wrap_to_box"]

BREAK_AFTER = "-/"
"""Characters a line may break after, the character staying on the line.

Two of them and no more. A full stop looks like a break point and is not:
GND. 400V is one legend and breaking it after the stop reads as two.
"""


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

    pieces = break_points(text)
    if not pieces:
        return [""]

    lines: list[str] = []
    current = pieces[0][0]
    for piece, spaced in pieces[1:]:
        joined = f"{current} {piece}" if spaced else f"{current}{piece}"
        if max_lines is not None and len(lines) == max_lines - 1:
            current = joined
            continue
        if measure_lines([joined], face, style) <= limit:
            current = joined
        else:
            lines.append(current)
            current = piece
    lines.append(current)
    return lines


def break_points(text: str) -> list[tuple[str, bool]]:
    """``text`` cut into the pieces a line may start with.

    Each piece comes with whether a space goes in front of it when it is
    kept on the same line. A piece after a space needs one back; a piece
    after a hyphen does not, because the hyphen is already there.
    """
    pieces: list[tuple[str, bool]] = []
    for word in text.split():
        for position, part in enumerate(_split_on_marks(word)):
            pieces.append((part, position == 0 and bool(pieces)))
    return pieces


def _split_on_marks(word: str) -> list[str]:
    """One word cut after every hyphen and slash inside it.

    A mark at the end of a word is not a break point, because the break
    after it is the space that follows and that is already a break.
    """
    parts: list[str] = []
    held = ""
    for character in word:
        held += character
        if character in BREAK_AFTER:
            parts.append(held)
            held = ""
    if held:
        parts.append(held)
    return parts or [word]


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
    """The width of the widest piece, which is the narrowest a wrap gets.

    Nothing can break a legend narrower than its longest unbreakable piece,
    so this is the number to compare a plate against before deciding that
    wrapping will save it. A word with a hyphen in it is not one piece: it
    breaks there, and a plate that would have been called too narrow on the
    whole word is not.
    """
    pieces = break_points(text)
    if not pieces:
        return 0.0
    return max(measure_lines([piece], face, style) for piece, _ in pieces)
