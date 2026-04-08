"""A picture of the plate, for looking at before anything is cut.

The point of the preview is the groove. A centreline drawing of a legend
tells nobody anything they did not already know; a drawing with every stroke
rendered at the width the cutter will actually leave shows the operator the
letters closing up, half a second after the rules said they would.

So the strokes are drawn at the groove width with round caps and joins,
which is what a conical cutter leaves, and everything else is drawn as a
hairline so it cannot be mistaken for something that gets cut.

Y is flipped once, here. Everywhere else in dragpoint y is up.
"""

from __future__ import annotations

from dragpoint.compiler.cutout import cutout_plate
from dragpoint.compiler.plate import EngravedPlate
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.spec.feature import Feature

__all__ = ["render_svg"]

OUTLINE_COLOUR = "#333333"
"""The blank."""

AREA_COLOUR = "#bbbbbb"
"""The engraving area and the border, both drawn as a guide."""

FEATURE_COLOUR = "#c05050"
"""Holes and cutouts, in the one colour nothing else uses."""

GROOVE_COLOUR = "#202020"
"""The engraving itself, near black so the width reads."""

TRAVEL_COLOUR = "#7090c0"
"""Rapid moves, pale enough to ignore when they are not the question."""

MILL_COLOUR = "#308030"
"""The path a window is milled on, which is not the window."""


def render_svg(
    plate: EngravedPlate,
    *,
    scale: float = 4.0,
    show_area: bool = True,
    show_features: bool = True,
    show_travel: bool = False,
) -> str:
    """Draw one compiled plate as an SVG document.

    ``scale`` is pixels per millimetre. Four is about right on a screen: a
    3 mm capital comes out twelve pixels tall, which is small enough to see
    a whole plate and big enough to see a groove closing.
    """
    if scale <= 0.0:
        raise ValueError(f"a scale of {scale} draws nothing")
    outline = plate.spec.outline()
    width = outline.width * scale
    height = outline.height * scale

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" height="{height:.2f}" '
        f'viewBox="0 0 {outline.width:.4f} {outline.height:.4f}">',
        f"  <title>{_escape(plate.name)}</title>",
        f'  <g transform="translate(0,{outline.height:.4f}) scale(1,-1)">',
        _rect(outline, OUTLINE_COLOUR, 0.1),
    ]
    if show_area:
        parts.append(_rect(plate.spec.area(), AREA_COLOUR, 0.05, dashed=True))
    border = plate.spec.border_box()
    if border is not None:
        parts.append(_rect(border, AREA_COLOUR, 0.05, dashed=True))
    if show_features:
        parts.extend(_feature(item) for item in plate.spec.features)
        parts.extend(_milling(plate))
    if show_travel:
        parts.append(_travel(plate))
    groove = _width(plate)
    parts.extend(_groove(stroke, groove) for stroke in plate.runs)
    parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(part for part in parts if part) + "\n"


def _width(plate: EngravedPlate) -> float:
    """The groove width this plate will actually carry."""
    return plate.cutter.width_at_depth(plate.depth)


def _rect(box: Box, colour: str, width: float, *, dashed: bool = False) -> str:
    """One rectangle as an SVG rect."""
    dash = ' stroke-dasharray="0.8 0.6"' if dashed else ""
    return (
        f'    <rect x="{box.min_x:.4f}" y="{box.min_y:.4f}" '
        f'width="{box.width:.4f}" height="{box.height:.4f}" fill="none" '
        f'stroke="{colour}" stroke-width="{width:.4f}"{dash} />'
    )


def _feature(item: Feature) -> str:
    """One hole or cutout, with its clearance ring."""
    if item.is_round:
        body = (
            f'    <circle cx="{item.centre.x:.4f}" cy="{item.centre.y:.4f}" '
            f'r="{item.radius:.4f}" fill="none" stroke="{FEATURE_COLOUR}" '
            f'stroke-width="0.1" />'
        )
        ring = (
            f'    <circle cx="{item.centre.x:.4f}" cy="{item.centre.y:.4f}" '
            f'r="{item.radius + item.clearance:.4f}" fill="none" '
            f'stroke="{FEATURE_COLOUR}" stroke-width="0.05" '
            f'stroke-dasharray="0.5 0.5" />'
        )
    else:
        body = _rect(item.bounds(), FEATURE_COLOUR, 0.1)
        ring = _rect(item.keepout_bounds(), FEATURE_COLOUR, 0.05, dashed=True)
    return body + "\n" + ring


def _milling(plate: EngravedPlate) -> list[str]:
    """The window paths, drawn at the width of the cutter that mills them.

    One pass of it. Ten passes down the same line draw the same line ten
    times and take ten times as long to open.
    """
    plan = cutout_plate(plate.spec)
    drawn: list[str] = []
    for cut in plan.cuts:
        if cut.pass_index != 0:
            continue
        points = " ".join(f"{point.x:.4f},{point.y:.4f}" for point in cut.stroke.points)
        drawn.append(
            f'    <polyline points="{points}" fill="none" stroke="{MILL_COLOUR}" '
            f'stroke-width="{plan.cutter.tip_width:.4f}" stroke-linecap="round" '
            f'stroke-linejoin="round" stroke-opacity="0.5" />'
        )
    return drawn


def _groove(stroke: Stroke, width: float) -> str:
    """One stroke drawn at the width the cutter leaves."""
    points = " ".join(f"{point.x:.4f},{point.y:.4f}" for point in stroke.points)
    return (
        f'    <polyline points="{points}" fill="none" stroke="{GROOVE_COLOUR}" '
        f'stroke-width="{width:.4f}" stroke-linecap="round" stroke-linejoin="round" />'
    )


def _travel(plate: EngravedPlate) -> str:
    """The rapid moves, as one thin dashed path."""
    moves: list[str] = []
    here: Point | None = None
    for cut in plate.cuts:
        if here is not None:
            moves.append(f"M {here.x:.4f} {here.y:.4f} L {cut.start.x:.4f} {cut.start.y:.4f}")
        here = cut.end
    if not moves:
        return ""
    return (
        f'    <path d="{" ".join(moves)}" fill="none" stroke="{TRAVEL_COLOUR}" '
        f'stroke-width="0.05" stroke-dasharray="0.4 0.4" />'
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
