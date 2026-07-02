"""A face: the glyph set, the metrics block and the kerning table.

Sizing is by cap height, not by point size. A legend plate drawing says the
lettering is 3 mm and it means the capitals are 3 mm tall, because that is
what an inspector can put a rule against. Point size would be a number about
an em square nobody can measure on the finished plate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from dragpoint.errors import MissingGlyph
from dragpoint.font.glyph import Glyph, glyph_name_for

__all__ = ["FaceMetrics", "StrokeFace"]


@dataclass(frozen=True, slots=True)
class FaceMetrics:
    """The vertical measurements, all in font units.

    ``descender`` is negative, the way every font format writes it. A face
    that stored it positive would read fine and place every accent below the
    baseline on the wrong side, so it is checked rather than assumed.
    """

    units_per_em: int
    cap_height: int
    x_height: int
    ascender: int
    descender: int
    line_gap: int = 0

    def __post_init__(self) -> None:
        if self.units_per_em <= 0:
            raise ValueError(f"units per em must be positive, got {self.units_per_em}")
        if self.cap_height <= 0:
            raise ValueError(f"cap height must be positive, got {self.cap_height}")
        if self.x_height <= 0 or self.x_height > self.cap_height:
            raise ValueError(f"x height {self.x_height} is not below the cap height")
        if self.ascender < self.cap_height:
            raise ValueError(f"ascender {self.ascender} is below the cap height")
        if self.descender > 0:
            raise ValueError(f"descender {self.descender} should be negative or zero")
        if self.line_gap < 0:
            raise ValueError(f"line gap {self.line_gap} is negative")

    @property
    def default_line_pitch(self) -> int:
        """Baseline to baseline in font units when nothing overrides it."""
        return self.ascender - self.descender + self.line_gap


@dataclass(frozen=True, slots=True)
class StrokeFace:
    """A named glyph set with its metrics and kerning.

    The mappings are wrapped so a face cannot be edited after it is built.
    Faces get shared between plates in one job and a face that changed under
    a later plate would be the kind of bug that only shows on the machine.
    """

    name: str
    metrics: FaceMetrics
    glyphs: Mapping[str, Glyph]
    kerning: Mapping[tuple[str, str], int] = field(default_factory=dict)
    fallback: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a face needs a name")
        object.__setattr__(self, "glyphs", MappingProxyType(dict(self.glyphs)))
        object.__setattr__(self, "kerning", MappingProxyType(dict(self.kerning)))
        for key, glyph in self.glyphs.items():
            if key != glyph.name:
                raise ValueError(f"glyph filed under {key!r} calls itself {glyph.name!r}")
        if self.fallback is not None and self.fallback not in self.glyphs:
            raise ValueError(f"fallback glyph {self.fallback!r} is not in the face")
        for left, right in self.kerning:
            if left not in self.glyphs or right not in self.glyphs:
                raise ValueError(f"kern pair {left!r},{right!r} names a glyph that is not here")

    def names(self) -> tuple[str, ...]:
        """Every glyph name, sorted, so output is stable across runs."""
        return tuple(sorted(self.glyphs))

    def glyph(self, name: str) -> Glyph:
        """Look a glyph up by name, falling back only if a fallback is set."""
        found = self.glyphs.get(name)
        if found is not None:
            return found
        if self.fallback is not None:
            return self.glyphs[self.fallback]
        raise MissingGlyph(name, self.name)

    def glyph_for(self, character: str) -> Glyph:
        """Look a glyph up by the character it draws."""
        return self.glyph(glyph_name_for(character))

    def figure_advance(self) -> int:
        """The widest advance among the figures, or zero if it draws none.

        A scale plate wants its figures on a pitch rather than set the way
        they were drawn, so that 110 sits under 100 rather than half a digit
        to the left of it. This is the pitch to use, and it comes off the
        face rather than being a number somebody types.
        """
        widths = [
            self.glyphs[glyph_name_for(digit)].advance
            for digit in "0123456789"
            if glyph_name_for(digit) in self.glyphs
        ]
        return max(widths) if widths else 0

    def has(self, character: str) -> bool:
        """True when the face draws ``character`` without falling back."""
        return glyph_name_for(character) in self.glyphs

    def missing(self, text: str) -> tuple[str, ...]:
        """The characters of ``text`` this face cannot draw, in order, once each.

        Order is the order they appear, not sorted. An operator fixing a
        legend reads the message left to right and wants the first offender
        named first.
        """
        seen: list[str] = []
        for character in text:
            if not self.has(character) and character not in seen:
                seen.append(character)
        return tuple(seen)

    def kern(self, left: str, right: str) -> int:
        """The kern between two glyph names, zero when the pair is not listed."""
        return self.kerning.get((left, right), 0)

    def scale_for_cap_height(self, cap_height_mm: float) -> float:
        """Font units to millimetres for lettering of the given cap height."""
        if cap_height_mm <= 0.0:
            raise ValueError(f"cap height must be positive, got {cap_height_mm}")
        return cap_height_mm / self.metrics.cap_height

    def scale_for_em(self, em_mm: float) -> float:
        """Font units to millimetres for a given em size.

        Here for the DXF import path, which quotes sizes in ems because the
        drawings it reads came from a system that thought in points.
        """
        if em_mm <= 0.0:
            raise ValueError(f"em size must be positive, got {em_mm}")
        return em_mm / self.metrics.units_per_em

    def with_glyphs(self, extra: Iterable[Glyph]) -> StrokeFace:
        """A copy of this face with more glyphs merged in.

        Later glyphs win. This is how a job adds a customer's logo mark or a
        one off symbol without editing the shipped face.
        """
        merged = dict(self.glyphs)
        for glyph in extra:
            merged[glyph.name] = glyph
        return StrokeFace(
            name=self.name,
            metrics=self.metrics,
            glyphs=merged,
            kerning=dict(self.kerning),
            fallback=self.fallback,
        )

    def __len__(self) -> int:
        return len(self.glyphs)

    def __contains__(self, name: object) -> bool:
        return name in self.glyphs

    def __str__(self) -> str:
        return f"{self.name} ({len(self.glyphs)} glyphs, {self.metrics.units_per_em} upem)"
