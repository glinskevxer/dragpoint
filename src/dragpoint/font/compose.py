"""Building an accented capital out of a letter and a mark.

Export work needs accents. A panel going to Lyon has ARRET D'URGENCE on it
and the E has an acute over it, and drawing E acute, E grave and E
circumflex by hand as three more glyphs is three more places for the E to
drift when somebody nudges the E.

So a composed glyph names a base and a mark, and this works out where the
mark goes. Two rules do all of it.

The mark sits above the ink of the base, not above the cap line. That is
what makes O acute and A acute look like they belong to the same face: the
A comes to a point at the cap line and the O bulges past it, so a mark set
at a fixed height sits visibly closer to one than the other.

The mark is centred on the ink of the base and then pushed back inside the
side bearings if it stuck out. An accent that overhangs the advance is an
accent that collides with the next letter, which on a plate cut at half a
millimetre wide means two letters joined together, and the face rules this
shop works to forbid that outright.

A mark wider than the room inside the bearings is narrowed until it fits,
and only in x. That is what a type founder does for the accents over a
narrow letter, and I acute is the reason: the I is 260 units wide, an acute
is 150, and there are 160 units of bearing to keep clear.
"""

from __future__ import annotations

from dragpoint.errors import FontSyntax
from dragpoint.font.glyph import Glyph
from dragpoint.geometry.transform import Transform

__all__ = ["ACCENT_GAP", "SIDE_BEARING", "compose_glyph"]

ACCENT_GAP = 110
"""Font units between the top of the base ink and the bottom of the mark.

The separation rule this shop's faces are held to is ninety units. This is
above it rather than on it, because a mark that only just clears the letter
reads as part of the letter at three millimetres tall.
"""

SIDE_BEARING = 80
"""Font units of clear space a mark must leave each side of the advance.

The same number the faces are drawn to. A mark is not a special case: it is
ink, it is inside somebody's advance, and it obeys the same rule as ink.
"""


def compose_glyph(
    name: str,
    base: Glyph,
    mark: Glyph,
    *,
    codepoint: int | None = None,
    gap: int = ACCENT_GAP,
    source: str = "<compose>",
    line: int = 0,
) -> Glyph:
    """Put ``mark`` over ``base`` and call the result ``name``.

    The advance is the base's. An accent does not make a letter wider, and a
    face where it did would set ETE wider than ETE with no accents on it,
    which nobody wants on a plate where the legend has to fit a box.
    """
    base_box = base.ink_bounds()
    if base_box is None:
        raise FontSyntax(source, line, f"{name}: {base.name} has no ink to put a mark over")
    mark_box = mark.ink_bounds()
    if mark_box is None:
        raise FontSyntax(source, line, f"{name}: {mark.name} has no ink in it to use as a mark")
    if gap < 0:
        raise FontSyntax(source, line, f"{name}: a gap of {gap} would put the mark in the letter")

    fitted = _narrowed(mark, base.advance)
    fitted_box = fitted.ink_bounds() or mark_box
    shift_x = _centred(base_box.centre.x, fitted_box.centre.x)
    shift_x = _inside_bearings(shift_x, fitted_box.min_x, fitted_box.max_x, base.advance)
    shift_y = base_box.max_y + gap - fitted_box.min_y
    moved = fitted.transformed(Transform.translation(shift_x, shift_y))
    return Glyph(
        name=name,
        advance=base.advance,
        strokes=base.strokes + moved.strokes,
        codepoint=codepoint,
        tags=frozenset(base.tags | {"composed"}),
        composed_from=(base.name, mark.name),
    )


def _narrowed(mark: Glyph, advance: int) -> Glyph:
    """The mark, squeezed in x if the letter is too narrow to hold it.

    Squeezing in x only is deliberate. An accent that keeps its height keeps
    its weight on the plate, and a mark scaled in both directions over a
    narrow letter comes out as a scratch nobody can see.
    """
    box = mark.ink_bounds()
    if box is None:
        return mark
    room = advance - 2 * SIDE_BEARING
    if box.width <= room or box.width <= 0.0 or room <= 0.0:
        return mark
    factor = room / box.width
    about = Transform.translation(-box.centre.x, 0.0)
    back = Transform.translation(box.centre.x, 0.0)
    return mark.transformed(about.then(Transform.scaling(factor, 1.0)).then(back))


def _centred(base_middle: float, mark_middle: float) -> float:
    """How far to move the mark to sit over the middle of the base ink."""
    return base_middle - mark_middle


def _inside_bearings(shift: float, min_x: float, max_x: float, advance: int) -> float:
    """The shift again, pulled back if the mark would break the bearings.

    A narrow letter under a wide mark is the case this exists for: a tilde
    centred on an I is wider than the I's whole advance, and centring it is
    less important than keeping it off the letter next door.
    """
    left = SIDE_BEARING - (min_x + shift)
    if left > 0.0:
        shift += left
    right = (min_x + shift) + (max_x - min_x) - (advance - SIDE_BEARING)
    if right > 0.0:
        shift -= right
    return shift
