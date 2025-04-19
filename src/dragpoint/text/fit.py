"""Making a legend fit the plate it has to go on.

Every shop does this by hand and every shop does it in the same order:
squeeze the letters first, and only drop the lettering height when squeezing
has run out. Dropping the height is visible from across the workshop when the
plate next to it is at the drawing size, so it is the last resort.

The squeeze does not need searching for. A run's width is linear in the
condense factor, because every advance and every kern is multiplied by it and
tracking is not, so the factor that lands exactly on the target comes out of
one division. Searching for it would be slower and would land somewhere near.

Heights do get searched, because the shop keeps a list of heights it will
cut. A plate at 2.7 mm next to a plate at 3 mm reads as a mistake even when
it is what fits, so the fitter picks from the list rather than solving.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from dragpoint.font.face import StrokeFace
from dragpoint.text.layout import layout_lines
from dragpoint.text.style import MIN_CONDENSE, TextStyle

__all__ = [
    "PREFERRED_CAP_HEIGHTS",
    "FitPolicy",
    "FitResult",
    "fit_lines",
    "measure_lines",
]

PREFERRED_CAP_HEIGHTS = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)
"""The lettering heights this shop will set up for, in millimetres."""

CONDENSE_STEP = 0.01
"""Condense is quoted to a percent. Nobody can see a tenth of one."""


class FitPolicy(StrEnum):
    """What the fitter is allowed to change."""

    NONE = "none"
    CONDENSE = "condense"
    SHRINK = "shrink"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class FitResult:
    """What the fitter settled on, and whether it was enough.

    ``fits`` false is not an error. The caller decides whether an overlong
    legend is a reason to stop the job or a reason to print a warning and
    let the operator look at it, and that decision is not the fitter's.
    """

    style: TextStyle
    fits: bool
    width: float
    limit: float
    stopped_at: str | None

    @property
    def overrun(self) -> float:
        """How much wider than the limit the result is, zero when it fits."""
        return max(0.0, self.width - self.limit)

    def __str__(self) -> str:
        verdict = "fits" if self.fits else f"over by {self.overrun:.3f}mm"
        return f"{self.style}: {self.width:.3f}mm of {self.limit:.3f}mm, {verdict}"


def measure_lines(lines: Sequence[str], face: StrokeFace, style: TextStyle) -> float:
    """The width of the widest line, measured the way alignment measures it."""
    return layout_lines(lines, face, style).widest


def _condense_to_fit(
    lines: Sequence[str],
    face: StrokeFace,
    style: TextStyle,
    limit: float,
    floor: float,
) -> TextStyle:
    """The condense factor that lands on ``limit``, floored and rounded down.

    Width is ``constant * condense + tracking * glyph count``, so measuring
    at the current factor is enough to recover the constant. A style with no
    glyphs at all measures zero and is left alone.
    """
    current = measure_lines(lines, face, style)
    if current <= limit:
        return style
    fixed = _tracking_component(lines, style)
    scalable = current - fixed
    if scalable <= 0.0:
        return style
    wanted = (limit - fixed) / scalable * style.condense
    stepped = max(floor, (wanted // CONDENSE_STEP) * CONDENSE_STEP)
    return style.condensed_to(min(style.condense, max(MIN_CONDENSE, stepped)))


def _tracking_component(lines: Sequence[str], style: TextStyle) -> float:
    """The part of the widest line's width that condensing will not touch."""
    if not style.tracking:
        return 0.0
    longest = max((len(line) for line in lines), default=0)
    return max(0, longest - 1) * style.tracking


def _shrink_to_fit(
    lines: Sequence[str],
    face: StrokeFace,
    style: TextStyle,
    limit: float,
    floor: float,
) -> TextStyle:
    """The largest cap height off the shop list that fits, or the floor."""
    candidates = [height for height in PREFERRED_CAP_HEIGHTS if floor <= height <= style.cap_height]
    for height in reversed(candidates):
        if measure_lines(lines, face, style.at_cap_height(height)) <= limit:
            return style.at_cap_height(height)
    if candidates:
        return style.at_cap_height(candidates[0])
    return style


def fit_lines(
    lines: Sequence[str],
    face: StrokeFace,
    style: TextStyle,
    limit: float,
    policy: FitPolicy = FitPolicy.CONDENSE,
    *,
    min_condense: float = 0.6,
    min_cap_height: float = 1.5,
) -> FitResult:
    """Adjust ``style`` until the widest line fits ``limit`` millimetres.

    Condensing is tried before shrinking under :attr:`FitPolicy.BOTH`, and
    the condense is redone after a shrink because a smaller height may need
    less squeezing than the first pass asked for. A plate that ends up at
    both limits reports the one that stopped it as the height, since that is
    the one the operator argues about.
    """
    if limit <= 0.0:
        raise ValueError(f"a width limit must be positive, got {limit}")
    working = style
    stopped_at: str | None = None

    if policy in (FitPolicy.CONDENSE, FitPolicy.BOTH):
        working = _condense_to_fit(lines, face, working, limit, min_condense)
        if measure_lines(lines, face, working) > limit:
            stopped_at = "condense"

    if policy in (FitPolicy.SHRINK, FitPolicy.BOTH) and measure_lines(lines, face, working) > limit:
        working = _shrink_to_fit(lines, face, working, limit, min_cap_height)
        if policy is FitPolicy.BOTH:
            # The squeeze is redone from the factor the caller asked for, not
            # from the one the first pass ground down to. A shorter letter is
            # a narrower letter, so the height that finally fits usually
            # needs less squeezing than the full size one did, and leaving
            # the old factor on would set a plate tighter than it has to be.
            relaxed = working.condensed_to(style.condense)
            working = _condense_to_fit(lines, face, relaxed, limit, min_condense)
        if measure_lines(lines, face, working) > limit:
            stopped_at = "cap height"

    width = measure_lines(lines, face, working)
    fits = width <= limit
    return FitResult(
        style=working,
        fits=fits,
        width=width,
        limit=limit,
        stopped_at=None if fits else stopped_at,
    )
