"""Affine transforms, held as the six numbers a DXF or an SVG would carry.

Glyphs live on a nominal em square and land on a plate somewhere else, so
every glyph gets a transform on the way. Composition order matters and is
stated once here so no caller has to guess: ``a.then(b)`` applies ``a`` first.
That is the opposite of matrix multiplication written the usual way and it
reads correctly at the call site, which is where the mistakes happen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.geometry.point import Point

__all__ = ["Transform"]


@dataclass(frozen=True, slots=True)
class Transform:
    """The map ``(x, y) -> (a x + c y + e, b x + d y + f)``.

    The letters are the ones SVG and PostScript use, in that order, so a
    transform can be handed to the preview writer without renaming anything.
    """

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @classmethod
    def identity(cls) -> Transform:
        """The transform that changes nothing."""
        return cls()

    @classmethod
    def translation(cls, dx: float, dy: float) -> Transform:
        """Move by ``dx`` and ``dy``."""
        return cls(1.0, 0.0, 0.0, 1.0, dx, dy)

    @classmethod
    def scaling(cls, sx: float, sy: float | None = None) -> Transform:
        """Scale about the origin. One argument scales both axes."""
        return cls(sx, 0.0, 0.0, sx if sy is None else sy, 0.0, 0.0)

    @classmethod
    def rotation(cls, degrees: float) -> Transform:
        """Anticlockwise about the origin, in degrees because plates are.

        Nothing on a legend plate is ever specified in radians. The plate
        spec says ninety and means a vertical legend on a narrow strip.
        """
        radians = math.radians(degrees)
        cos = math.cos(radians)
        sin = math.sin(radians)
        return cls(cos, sin, -sin, cos, 0.0, 0.0)

    @classmethod
    def slant(cls, degrees: float) -> Transform:
        """Shear along x, which is how an oblique legend is made.

        There is no italic face here. Obliquing the upright is what the
        pantograph did mechanically and what the shop still expects.
        """
        if abs(degrees) >= 90.0:
            raise ValueError(f"slant of {degrees} degrees has no shear")
        return cls(1.0, 0.0, math.tan(math.radians(degrees)), 1.0, 0.0, 0.0)

    @classmethod
    def mirror_x(cls) -> Transform:
        """Flip about the y axis, for engraving the back of clear acrylic."""
        return cls(-1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    @classmethod
    def mirror_y(cls) -> Transform:
        """Flip about the x axis."""
        return cls(1.0, 0.0, 0.0, -1.0, 0.0, 0.0)

    def apply(self, point: Point) -> Point:
        """Map one point."""
        return Point(
            self.a * point.x + self.c * point.y + self.e,
            self.b * point.x + self.d * point.y + self.f,
        )

    def apply_vector(self, vector: Point) -> Point:
        """Map a direction, which means dropping the translation."""
        return Point(
            self.a * vector.x + self.c * vector.y,
            self.b * vector.x + self.d * vector.y,
        )

    def then(self, other: Transform) -> Transform:
        """This transform followed by ``other``."""
        return Transform(
            other.a * self.a + other.c * self.b,
            other.b * self.a + other.d * self.b,
            other.a * self.c + other.c * self.d,
            other.b * self.c + other.d * self.d,
            other.a * self.e + other.c * self.f + other.e,
            other.b * self.e + other.d * self.f + other.f,
        )

    @property
    def determinant(self) -> float:
        """Area scale factor, negative when the transform mirrors."""
        return self.a * self.d - self.b * self.c

    def inverse(self) -> Transform:
        """The transform that undoes this one."""
        det = self.determinant
        if abs(det) < 1e-12:
            raise ValueError("a degenerate transform has no inverse")
        return Transform(
            self.d / det,
            -self.b / det,
            -self.c / det,
            self.a / det,
            (self.c * self.f - self.d * self.e) / det,
            (self.b * self.e - self.a * self.f) / det,
        )

    @property
    def is_mirrored(self) -> bool:
        """True when the transform reverses handedness.

        The path planner cares because a mirrored run engraves back to front
        and the operator reads it through the plate, so the travel order that
        looked sensible on screen is the wrong one to optimise.
        """
        return self.determinant < 0.0

    def length_scale(self) -> float:
        """The factor a length is multiplied by, averaged over direction.

        Only exact for a similarity. Rules that need a real worst case use
        the singular values instead, and this is here for reporting.
        """
        return math.sqrt(abs(self.determinant))

    def __str__(self) -> str:
        parts = (self.a, self.b, self.c, self.d, self.e, self.f)
        return "matrix(" + " ".join(f"{value:g}" for value in parts) + ")"
