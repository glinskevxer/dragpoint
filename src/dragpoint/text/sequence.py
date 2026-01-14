"""Legends that count, for a run of plates that differ only by a number.

Half the work through this shop is a run of tags: VLV-001 to VLV-024, twelve
door numbers, a rack of terminal strips. On paper the drawing office writes
one line and a quantity, and up to now the schedule had to carry twenty four
rows saying the same thing with the number changed, which is twenty four
chances to fat finger one of them.

A sequenced line carries a placeholder instead. There are four of them and
that is deliberately all there is going to be: the number, the total, the
plate name, and a literal brace for the rare legend with a brace in it. This
is not a template language and it must not grow into one, because the thing
being expanded is going to be cut into a piece of laminate.

The number is what the piece is called, not what index it has. A run that
starts at 101 is a run whose first plate says 101, so the offset is a
property of the plate and lives on the spec.
"""

from __future__ import annotations

import re

from dragpoint.errors import SpecError

__all__ = ["expand_sequence", "is_sequenced", "sequence_lines"]

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
"""One placeholder, brace to brace, with no nesting allowed inside it."""

NUMBER = "n"
"""The placeholder that becomes the number of this piece."""

TOTAL = "of"
"""The placeholder that becomes how many pieces there are in the run."""

PLATE = "plate"
"""The placeholder that becomes the name of the plate off the schedule."""

KNOWN = (NUMBER, TOTAL, PLATE)
"""Everything that may appear inside a brace, and nothing else may."""


def is_sequenced(lines: tuple[str, ...]) -> bool:
    """True when any line has a placeholder in it.

    A line with a doubled brace and nothing else is not sequenced. It has a
    brace in it, which is a different thing, and expanding a run of one plate
    to get the brace back would be a surprise.
    """
    return any(PLACEHOLDER.search(_hide_doubles(line)) for line in lines)


def expand_sequence(
    text: str,
    *,
    piece: int,
    quantity: int = 1,
    plate: str = "",
) -> str:
    """Fill the placeholders in one line for one piece of a run.

    ``piece`` is the number the plate will carry, which is what a placeholder
    with a format on it formats. ``{n:03}`` on piece 7 gives 007, and the
    format is handed straight to Python, so anything Python will do to an
    integer works and anything it will not do is a message naming the line.
    """
    if quantity < 1:
        raise SpecError("sequence", text, f"a run of {quantity} pieces has nothing to number")

    def fill(found: re.Match[str]) -> str:
        """One match, turned into what it stands for."""
        return _one(found.group(1), piece=piece, quantity=quantity, plate=plate, line=text)

    return _restore_doubles(PLACEHOLDER.sub(fill, _hide_doubles(text)))


def sequence_lines(
    lines: tuple[str, ...],
    *,
    piece: int,
    quantity: int = 1,
    plate: str = "",
) -> tuple[str, ...]:
    """Expand every line of a legend for one piece."""
    return tuple(
        expand_sequence(line, piece=piece, quantity=quantity, plate=plate) for line in lines
    )


def _one(body: str, *, piece: int, quantity: int, plate: str, line: str) -> str:
    """One placeholder, filled."""
    name, _, spec = body.partition(":")
    name = name.strip()
    if name not in KNOWN:
        wanted = ", ".join(f"{{{known}}}" for known in KNOWN)
        raise SpecError("sequence", line, f"{{{body}}} is not a placeholder, there are {wanted}")
    if name == PLATE:
        if spec:
            raise SpecError("sequence", line, f"{{{PLATE}}} takes no format, it is not a number")
        return plate
    value = piece if name == NUMBER else quantity
    try:
        return format(value, spec)
    except ValueError as bad:
        raise SpecError("sequence", line, f"{spec!r} is not a format a number takes") from bad


DOUBLE_OPEN = "\x00"
"""What a doubled opening brace is held as while placeholders are filled."""

DOUBLE_CLOSE = "\x01"
"""What a doubled closing brace is held as while placeholders are filled."""


def _hide_doubles(text: str) -> str:
    """Put doubled braces out of reach of the placeholder pattern."""
    return text.replace("{{", DOUBLE_OPEN).replace("}}", DOUBLE_CLOSE)


def _restore_doubles(text: str) -> str:
    """Put them back, singly, which is what a doubled brace is for."""
    return text.replace(DOUBLE_OPEN, "{").replace(DOUBLE_CLOSE, "}")
