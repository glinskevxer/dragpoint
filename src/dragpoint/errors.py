"""The exceptions dragpoint raises, and nothing else.

Every one of these carries the thing that went wrong as data, not as a
prebaked sentence, so a caller can decide whether to print it, count it or
turn it into a row in a violation report. The CLI is the only layer allowed
to turn one into English.
"""

from __future__ import annotations

__all__ = [
    "BadLength",
    "BadUnit",
    "DragpointError",
    "FontSyntax",
    "MissingGlyph",
    "OutOfRange",
]


class DragpointError(Exception):
    """Base class for everything this package raises deliberately."""


class BadUnit(DragpointError):
    """A unit suffix that is not one this shop uses."""

    def __init__(self, suffix: str, known: tuple[str, ...]) -> None:
        super().__init__(suffix, known)
        self.suffix = suffix
        self.known = known

    def __str__(self) -> str:
        return f"unknown unit {self.suffix!r}, expected one of {', '.join(self.known)}"


class BadLength(DragpointError):
    """A length that could not be read at all."""

    def __init__(self, text: str, why: str) -> None:
        super().__init__(text, why)
        self.text = text
        self.why = why

    def __str__(self) -> str:
        return f"cannot read {self.text!r} as a length: {self.why}"


class OutOfRange(DragpointError):
    """A value that parsed cleanly and is still not usable."""

    def __init__(self, what: str, value: float, low: float, high: float) -> None:
        super().__init__(what, value, low, high)
        self.what = what
        self.value = value
        self.low = low
        self.high = high

    def __str__(self) -> str:
        return f"{self.what} is {self.value:g}, outside {self.low:g} to {self.high:g}"


class MissingGlyph(DragpointError):
    """A character the face cannot draw and has no fallback for."""

    def __init__(self, name: str, face: str) -> None:
        super().__init__(name, face)
        self.name = name
        self.face = face

    def __str__(self) -> str:
        return f"face {self.face} has no glyph named {self.name!r}"


class FontSyntax(DragpointError):
    """A .strk file that does not parse, with the line it went wrong on.

    Line zero means the problem is with the file as a whole rather than with
    any one line, which is how a missing header field is reported.
    """

    def __init__(self, source: str, line: int, why: str) -> None:
        super().__init__(source, line, why)
        self.source = source
        self.line = line
        self.why = why

    def __str__(self) -> str:
        where = f"{self.source}:{self.line}" if self.line else self.source
        return f"{where}: {self.why}"
