"""One character, drawn as centreline strokes on the design grid.

Glyph coordinates are integers in font units, not millimetres. The design
grid is whatever the face says it is, usually a thousand units to the em, and
keeping glyphs in integers means two faces built at different sizes still
compare exactly and a round trip through the font file changes nothing.

Scaling to millimetres happens once, in the shaper, and never here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from dragpoint.geometry.box import Box
from dragpoint.geometry.stroke import Stroke
from dragpoint.geometry.transform import Transform

__all__ = ["Glyph", "glyph_name_for", "is_valid_glyph_name"]

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

_NAMED_CHARACTERS = {
    " ": "space",
    "!": "exclam",
    '"': "quotedbl",
    "#": "numbersign",
    "$": "dollar",
    "%": "percent",
    "&": "ampersand",
    "'": "quotesingle",
    "(": "parenleft",
    ")": "parenright",
    "*": "asterisk",
    "+": "plus",
    ",": "comma",
    "-": "hyphen",
    ".": "period",
    "/": "slash",
    ":": "colon",
    ";": "semicolon",
    "<": "less",
    "=": "equal",
    ">": "greater",
    "?": "question",
    "@": "at",
    "[": "bracketleft",
    "\\": "backslash",
    "]": "bracketright",
    "^": "asciicircum",
    "_": "underscore",
    "`": "grave",
    "{": "braceleft",
    "|": "bar",
    "}": "braceright",
    "~": "asciitilde",
}

_ACCENTED_CHARACTERS = {
    "À": "Agrave",
    "Á": "Aacute",
    "Â": "Acircumflex",
    "Ä": "Adieresis",
    "È": "Egrave",
    "É": "Eacute",
    "Ê": "Ecircumflex",
    "Ë": "Edieresis",
    "Ì": "Igrave",
    "Í": "Iacute",
    "Ï": "Idieresis",
    "Ñ": "Ntilde",
    "Ò": "Ograve",
    "Ó": "Oacute",
    "Ô": "Ocircumflex",
    "Ö": "Odieresis",
    "Ù": "Ugrave",
    "Ú": "Uacute",
    "Û": "Ucircumflex",
    "Ü": "Udieresis",
}
"""The accented capitals, under the names a type designer would use.

Held apart from the punctuation table because they are a different kind of
thing: every one of these is composed rather than drawn, and a face that
does not compose them will not have them under any name.
"""

_DIGIT_NAMES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


def glyph_name_for(character: str) -> str:
    """The name this package files ``character`` under.

    Letters are their own name. Digits and punctuation get the Adobe style
    names, because a font source file full of bare punctuation is unreadable
    and unparseable at the same time.
    """
    if len(character) != 1:
        raise ValueError(f"expected a single character, got {character!r}")
    if character.isalpha() and character.isascii():
        return character
    if character.isdigit() and character.isascii():
        return _DIGIT_NAMES[int(character)]
    named = _NAMED_CHARACTERS.get(character) or _ACCENTED_CHARACTERS.get(character)
    if named is not None:
        return named
    return f"uni{ord(character):04X}"


def is_valid_glyph_name(name: str) -> bool:
    """True when ``name`` is one the font file format can carry."""
    return bool(_NAME_RE.match(name))


@dataclass(frozen=True, slots=True)
class Glyph:
    """A named set of strokes plus the width it takes up on the line.

    ``advance`` is the pen movement, which is not the same as the width of
    the marks. A space has an advance and no strokes at all, and a swash
    would have marks wider than its advance. Keeping the two apart is what
    lets side bearings be negative without anything downstream noticing.

    ``composed_from`` is a note of where a composed glyph came from, and
    nothing reads it except the writer. The strokes are already in the
    glyph, so everything downstream sees an accented capital exactly as it
    would see a drawn one, which is the point of composing at load time.
    """

    name: str
    advance: int
    strokes: tuple[Stroke, ...] = ()
    codepoint: int | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    composed_from: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        if not is_valid_glyph_name(self.name):
            raise ValueError(f"{self.name!r} is not a usable glyph name")
        if self.advance < 0:
            raise ValueError(f"glyph {self.name} has a negative advance of {self.advance}")

    @property
    def is_blank(self) -> bool:
        """True when the glyph puts no cutter down at all."""
        return not self.strokes

    def ink_bounds(self) -> Box | None:
        """The box around the marks, or ``None`` for a blank glyph.

        Not the advance box. A rule that wants the space a glyph reserves on
        the line wants :attr:`advance`; a rule that wants where the cutter
        goes wants this.
        """
        points = [point for stroke in self.strokes for point in stroke.points]
        return Box.around(points)

    def left_bearing(self) -> float | None:
        """Gap from the origin to the leftmost mark, or ``None`` if blank."""
        box = self.ink_bounds()
        return None if box is None else box.min_x

    def right_bearing(self) -> float | None:
        """Gap from the rightmost mark to the advance, or ``None`` if blank."""
        box = self.ink_bounds()
        return None if box is None else self.advance - box.max_x

    def stroke_count(self) -> int:
        """How many separate pen downs the glyph needs."""
        return len(self.strokes)

    def path_length(self) -> float:
        """Total cut length in font units, before any scaling."""
        return sum(stroke.length() for stroke in self.strokes)

    def transformed(self, transform: Transform) -> Glyph:
        """The same glyph with every stroke mapped.

        The advance is not transformed, because a transform that moves the
        advance is a face level decision and belongs to the shaper. This is
        for mirroring and obliquing a single glyph in place.
        """
        return Glyph(
            name=self.name,
            advance=self.advance,
            strokes=tuple(stroke.transformed(transform) for stroke in self.strokes),
            codepoint=self.codepoint,
            tags=self.tags,
            composed_from=self.composed_from,
        )

    def with_advance(self, advance: int) -> Glyph:
        """A copy with a different advance, for a face level width override."""
        return Glyph(
            name=self.name,
            advance=advance,
            strokes=self.strokes,
            codepoint=self.codepoint,
            tags=self.tags,
            composed_from=self.composed_from,
        )

    def has_tag(self, tag: str) -> bool:
        """True when the glyph carries ``tag``.

        Tags mark the handful of glyphs that need different treatment on the
        machine. ``thin`` says the glyph has strokes too close together to
        survive a wide cutter, ``fixed`` says its advance is not to be
        adjusted by fitting, and the loader is free to add more.
        """
        return tag in self.tags

    def __str__(self) -> str:
        return f"{self.name}({self.advance}, {len(self.strokes)} strokes)"
