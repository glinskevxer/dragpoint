"""How a run of text is to be set, in millimetres on the plate.

Everything here is a plate level decision that a drawing office would write
on the drawing: lettering height, how tight it is, whether it leans. None of
it is a machine decision, so nothing in this module knows about cutters,
depths or feed rates.

The limits are not arbitrary. A condense below a fifth is unreadable at any
size, a slant past forty five degrees puts the stems of adjacent letters into
each other, and negative tracking wider than the tightest kern in the face
would have letters overlapping before any glyph was even looked at.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dragpoint.errors import OutOfRange
from dragpoint.font.face import StrokeFace
from dragpoint.geometry.transform import Transform

__all__ = ["TextStyle"]

MIN_CONDENSE = 0.2
"""Below a fifth a letter is a stroke with no shape left in it."""

MAX_CONDENSE = 3.0
"""Above three times it is not lettering, it is a fence."""

MAX_SLANT = 45.0
"""Past forty five degrees the stems of neighbouring letters cross."""


@dataclass(frozen=True, slots=True)
class TextStyle:
    """The settable properties of a run of lettering.

    ``cap_height`` is the height of a capital in millimetres, which is what
    the drawing dimensions. ``tracking`` is extra space added after every
    glyph including the last, because a run that is going to be centred needs
    the trailing space counted or it sits half a track to the left.

    ``tabular`` sets every figure on the same pitch, which is what a scale
    or a column of readings wants and what a word does not. A one is
    narrower than a zero in every face worth having, so 110 under 100 comes
    out shifted unless somebody asks for this.
    """

    cap_height: float
    tracking: float = 0.0
    word_space: float | None = None
    slant: float = 0.0
    condense: float = 1.0
    kerning: bool = True
    mirror: bool = False
    line_pitch: float | None = None
    tabular: bool = False

    def __post_init__(self) -> None:
        if self.cap_height <= 0.0:
            raise OutOfRange("cap height", self.cap_height, 0.0, float("inf"))
        if not MIN_CONDENSE <= self.condense <= MAX_CONDENSE:
            raise OutOfRange("condense", self.condense, MIN_CONDENSE, MAX_CONDENSE)
        if abs(self.slant) > MAX_SLANT:
            raise OutOfRange("slant", self.slant, -MAX_SLANT, MAX_SLANT)
        if self.word_space is not None and self.word_space < 0.0:
            raise OutOfRange("word space", self.word_space, 0.0, float("inf"))
        if self.line_pitch is not None and self.line_pitch <= 0.0:
            raise OutOfRange("line pitch", self.line_pitch, 0.0, float("inf"))
        if self.tracking < -self.cap_height:
            raise OutOfRange("tracking", self.tracking, -self.cap_height, float("inf"))

    def scale(self, face: StrokeFace) -> float:
        """Font units to millimetres for this style on ``face``."""
        return face.scale_for_cap_height(self.cap_height)

    def resolved_line_pitch(self, face: StrokeFace) -> float:
        """Baseline to baseline in millimetres.

        The face has an opinion and the style can overrule it. Plates with
        four lines in a twelve millimetre window nearly always overrule it.
        """
        if self.line_pitch is not None:
            return self.line_pitch
        return face.metrics.default_line_pitch * self.scale(face)

    def glyph_transform(self) -> Transform:
        """The shape distortion applied to every glyph, in millimetre space.

        Condense first, then slant. The order is fixed and it matters:
        slanting a condensed glyph leans the condensed stem, while condensing
        a slanted one changes the lean angle as well, which is not what
        anybody means by a fifteen degree oblique.

        Mirroring is not here. Reverse engraving flips the whole run, not
        each letter in place, and a per glyph flip would give a line of
        backwards letters still reading left to right.
        """
        transform = Transform.scaling(self.condense, 1.0)
        if self.slant:
            transform = transform.then(Transform.slant(self.slant))
        return transform

    def run_transform(self, width: float) -> Transform:
        """What a whole run of ``width`` millimetres gets after shaping.

        Only mirroring lands here, and the translation puts the flipped run
        back on the same span it started on, so a mirrored legend still
        occupies the box the layout reserved for it.
        """
        if not self.mirror:
            return Transform.identity()
        return Transform.mirror_x().then(Transform.translation(width, 0.0))

    def condensed_to(self, factor: float) -> TextStyle:
        """A copy at a different condense, for the fitter to try."""
        return replace(self, condense=factor)

    def at_cap_height(self, cap_height: float) -> TextStyle:
        """A copy at a different lettering height."""
        return replace(self, cap_height=cap_height)

    def with_tracking(self, tracking: float) -> TextStyle:
        """A copy at a different tracking."""
        return replace(self, tracking=tracking)

    def __str__(self) -> str:
        parts = [f"{self.cap_height:g}mm cap"]
        if self.condense != 1.0:
            parts.append(f"condensed {self.condense:g}")
        if self.slant:
            parts.append(f"slant {self.slant:g}")
        if self.tracking:
            parts.append(f"tracking {self.tracking:g}mm")
        if self.mirror:
            parts.append("mirrored")
        if not self.kerning:
            parts.append("unkerned")
        return ", ".join(parts)
