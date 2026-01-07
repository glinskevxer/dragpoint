"""A picture of the nest, for the person who has to cut the sheet up.

The nest result is a list of coordinates and nobody parts a sheet off a list
of coordinates. What they want is the sheet drawn the way it will be lying on
the bed, with every piece labelled and the ones that have been turned marked
as turned, because a piece put down the wrong way round is a plate with the
legend across the short axis and a blank to cut again.

Three things are drawn and they are drawn in this order. The sheet and the
clamp margin first, because that is the thing on the bed. Then the pieces,
filled so they read as solid. Then the labels, on top, because a label under
a piece is a label nobody can read.

Pieces that did not fit are not drawn. They are listed under the sheet, which
is where somebody will look for them, and the caption says how many there
were so a nest that lost half the job cannot look like a nest that fitted.

The y flip is the same one the plate drawing does: y is up everywhere in
dragpoint and down in SVG, so it is turned over once at the top of the
document and never thought about again.
"""

from __future__ import annotations

from dragpoint.nest.shelf import NestResult, Placement

__all__ = ["render_nest"]

SHEET_COLOUR = "#333333"
"""The blank itself."""

MARGIN_COLOUR = "#bbbbbb"
"""The strip the clamps sit on, which nothing may be nested in."""

PIECE_FILL = "#dce6f0"
"""The pieces, pale enough that a label reads over the top of one."""

PIECE_EDGE = "#40608a"
"""The edge of a piece, which is where the parting cut goes."""

TURNED_FILL = "#f0e4d0"
"""A piece that had to be turned to fit, in a colour that stands out."""

TURNED_EDGE = "#a07830"
"""The edge of a turned piece."""

LABEL_COLOUR = "#202020"
"""Piece labels and the caption."""

LABEL_HEIGHT = 3.0
"""Millimetres tall a piece label is drawn, on the sheet's own scale."""

MIN_LABEL_ROOM = 6.0
"""Millimetres a piece has to be before a label will fit inside it."""

CAPTION_GAP = 6.0
"""Millimetres between the bottom of the sheet and the caption under it."""


def render_nest(
    result: NestResult,
    *,
    scale: float = 1.0,
    show_labels: bool = True,
    show_margin: bool = True,
) -> str:
    """Draw a nest as an SVG document.

    ``scale`` is pixels per millimetre and one is the useful default here: a
    sheet is measured in hundreds of millimetres, and a nest drawn at four
    pixels to the millimetre is a drawing nobody can see the whole of.
    """
    if scale <= 0.0:
        raise ValueError(f"a scale of {scale} draws nothing")
    sheet = result.sheet
    caption = _caption_lines(result)
    below = CAPTION_GAP + LABEL_HEIGHT * 1.4 * len(caption)
    height = sheet.height + below

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{sheet.width * scale:.2f}" height="{height * scale:.2f}" '
        f'viewBox="0 0 {sheet.width:.4f} {height:.4f}">',
        f"  <title>{_escape(str(sheet))}</title>",
        f'  <g transform="translate(0,{sheet.height:.4f}) scale(1,-1)">',
        _rect(0.0, 0.0, sheet.width, sheet.height, SHEET_COLOUR, 0.4),
    ]
    if show_margin and sheet.margin > 0.0:
        parts.append(
            _rect(
                sheet.margin,
                sheet.margin,
                sheet.usable_width,
                sheet.usable_height,
                MARGIN_COLOUR,
                0.3,
                dashed=True,
            )
        )
    parts.extend(_piece(item) for item in result.placements)
    parts.append("  </g>")
    if show_labels:
        for item in result.placements:
            label = _label(item, sheet.height)
            if label:
                parts.append(label)
    for index, line in enumerate(caption):
        parts.append(_caption(line, sheet.height + CAPTION_GAP + index * LABEL_HEIGHT * 1.4))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _caption_lines(result: NestResult) -> list[str]:
    """What is written under the sheet, one entry per line."""
    lines = [f"{result.sheet} - {result}"]
    lines.extend(f"not on the sheet: {name} x{count}" for name, count in result.left_over)
    return lines


def _piece(item: Placement) -> str:
    """One nested piece, filled so it reads as material rather than air."""
    fill = TURNED_FILL if item.rotated else PIECE_FILL
    edge = TURNED_EDGE if item.rotated else PIECE_EDGE
    return (
        f'    <rect x="{item.origin.x:.4f}" y="{item.origin.y:.4f}" '
        f'width="{item.width:.4f}" height="{item.height:.4f}" fill="{fill}" '
        f'stroke="{edge}" stroke-width="0.3" />'
    )


def _label(item: Placement, flip: float) -> str:
    """A piece label, drawn the right way up over the middle of the piece.

    The label is written outside the flipped group, so its y is measured from
    the top of the sheet. A piece too small to hold the text gets nothing: a
    label spilling over three neighbours is worse than no label.
    """
    if min(item.width, item.height) < MIN_LABEL_ROOM:
        return ""
    text = f"{item.plate} #{item.piece}" + (" T" if item.rotated else "")
    room = item.width - 1.0
    size = min(LABEL_HEIGHT, room / (0.62 * max(len(text), 1)))
    if size < 1.2:
        return ""
    middle_x = item.origin.x + item.width / 2.0
    middle_y = flip - (item.origin.y + item.height / 2.0) + size / 3.0
    return (
        f'  <text x="{middle_x:.4f}" y="{middle_y:.4f}" fill="{LABEL_COLOUR}" '
        f'font-size="{size:.4f}" font-family="sans-serif" '
        f'text-anchor="middle">{_escape(text)}</text>'
    )


def _caption(text: str, y: float) -> str:
    """One line under the sheet."""
    return (
        f'  <text x="0" y="{y:.4f}" fill="{LABEL_COLOUR}" '
        f'font-size="{LABEL_HEIGHT:.4f}" font-family="sans-serif">{_escape(text)}</text>'
    )


def _rect(
    x: float,
    y: float,
    width: float,
    height: float,
    colour: str,
    stroke: float,
    *,
    dashed: bool = False,
) -> str:
    """One unfilled rectangle."""
    dash = ' stroke-dasharray="3 2"' if dashed else ""
    return (
        f'    <rect x="{x:.4f}" y="{y:.4f}" width="{width:.4f}" height="{height:.4f}" '
        f'fill="none" stroke="{colour}" stroke-width="{stroke:.4f}"{dash} />'
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
