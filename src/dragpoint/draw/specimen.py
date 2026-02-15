"""A sheet of every glyph in a face, at the size it will be cut.

Choosing a face off a list of names is choosing blind. What the drawing
office actually asks is whether the figures are legible at two millimetres
and whether the O and the zero can be told apart, and the only way to answer
that is to look at them.

So this draws the face on a grid, one glyph to a cell, at a real lettering
height and at the groove width a real cutter leaves. That last part is the
whole point: a centreline specimen of a stroke face tells you nothing that
the glyph names did not, and a specimen drawn at the groove width shows the
counters filling in on the B and the eight before anybody cuts one.

Under each glyph is its name and its advance, because the person reading a
specimen sheet closely is usually the person about to edit the face.
"""

from __future__ import annotations

from dragpoint.font.face import StrokeFace
from dragpoint.font.glyph import Glyph
from dragpoint.geometry.transform import Transform

__all__ = ["render_specimen"]

COLUMNS = 8
"""Glyphs across the sheet. Eight fits an A4 page at a readable cell size."""

CELL_PAD = 4.0
"""Millimetres of white space round each cell, so the cells read separately."""

LABEL_HEIGHT = 2.2
"""Millimetres tall the glyph name under each cell is drawn."""

GRID_COLOUR = "#cccccc"
"""The cell boxes and the cap line, which are a guide and not a mark."""

GROOVE_COLOUR = "#202020"
"""The glyphs, drawn at the width the cutter leaves."""

LABEL_COLOUR = "#606060"
"""The names and advances under the cells."""


def render_specimen(
    face: StrokeFace,
    *,
    cap_height: float = 8.0,
    groove: float = 0.5,
    columns: int = COLUMNS,
    scale: float = 4.0,
    show_grid: bool = True,
) -> str:
    """Draw every glyph in ``face`` as an SVG specimen sheet.

    ``cap_height`` is the lettering height in millimetres and ``groove`` is
    the width of the mark. Eight and a half are a plate legend blown up four
    times, which is what a specimen is for: the shapes at a size a person
    can judge, with the groove kept in proportion to them.
    """
    if cap_height <= 0.0:
        raise ValueError(f"a cap height of {cap_height} draws nothing")
    if groove <= 0.0:
        raise ValueError(f"a groove width of {groove} draws nothing")
    if columns < 1:
        raise ValueError(f"{columns} columns is not a sheet")

    unit = cap_height / face.metrics.cap_height
    names = face.names()
    cell_w = _widest(face) * unit + 2.0 * CELL_PAD
    cell_h = (face.metrics.ascender - face.metrics.descender) * unit + 2.0 * CELL_PAD
    rows = (len(names) + columns - 1) // columns
    width = cell_w * columns
    height = cell_h * rows + LABEL_HEIGHT * 2.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width * scale:.2f}" height="{height * scale:.2f}" '
        f'viewBox="0 0 {width:.4f} {height:.4f}">',
        f"  <title>{_escape(face.name)}</title>",
    ]
    for index, name in enumerate(names):
        left = (index % columns) * cell_w
        top = (index // columns) * cell_h
        parts.extend(_cell(face.glyph(name), left, top, cell_w, cell_h, unit, groove, show_grid))
    parts.append(_caption(face, cap_height, height - LABEL_HEIGHT * 0.5))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _widest(face: StrokeFace) -> int:
    """The widest advance in the face, which sets the cell width."""
    return max((glyph.advance for glyph in face.glyphs.values()), default=1)


def _cell(
    glyph: Glyph,
    left: float,
    top: float,
    cell_w: float,
    cell_h: float,
    unit: float,
    groove: float,
    show_grid: bool,
) -> list[str]:
    """One glyph in its box, drawn the right way up.

    The glyph is flipped here rather than in a group round the whole sheet,
    because the labels are the right way up and a document with two flips in
    it is a document where somebody eventually puts a label in the wrong one.
    """
    baseline = top + cell_h - CELL_PAD + unit * _descender_of(glyph)
    parts: list[str] = []
    if show_grid:
        parts.append(
            f'  <rect x="{left:.4f}" y="{top:.4f}" width="{cell_w:.4f}" '
            f'height="{cell_h:.4f}" fill="none" stroke="{GRID_COLOUR}" stroke-width="0.1" />'
        )
    flip = Transform.scaling(unit, -unit).then(Transform.translation(left + CELL_PAD, baseline))
    for stroke in glyph.transformed(flip).strokes:
        points = " ".join(f"{point.x:.4f},{point.y:.4f}" for point in stroke.points)
        parts.append(
            f'  <polyline points="{points}" fill="none" stroke="{GROOVE_COLOUR}" '
            f'stroke-width="{groove:.4f}" stroke-linecap="round" stroke-linejoin="round" />'
        )
    parts.append(
        f'  <text x="{left + CELL_PAD:.4f}" y="{top + cell_h - 0.4:.4f}" '
        f'fill="{LABEL_COLOUR}" font-size="{LABEL_HEIGHT:.4f}" font-family="sans-serif">'
        f"{_escape(glyph.name)} {glyph.advance}</text>"
    )
    return parts


def _descender_of(glyph: Glyph) -> float:
    """How far below the baseline this cell has to leave room for.

    Zero for anything that sits on the line, which is nearly everything in a
    face of capitals, so the cells do not all carry a descender's worth of
    empty space for the sake of the comma.
    """
    box = glyph.ink_bounds()
    return 0.0 if box is None else min(0.0, box.min_y)


def _caption(face: StrokeFace, cap_height: float, y: float) -> str:
    """The line at the foot of the sheet that says what was drawn."""
    metrics = face.metrics
    text = (
        f"{face.name}: {len(face)} glyphs, {metrics.units_per_em} upem, "
        f"cap {metrics.cap_height}, drawn at {cap_height:g}mm"
    )
    return (
        f'  <text x="0.5" y="{y:.4f}" fill="{LABEL_COLOUR}" '
        f'font-size="{LABEL_HEIGHT:.4f}" font-family="sans-serif">{_escape(text)}</text>'
    )


def _escape(text: str) -> str:
    """The five characters XML will not take raw."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
