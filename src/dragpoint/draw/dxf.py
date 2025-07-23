"""DXF, for the drawing office and for the machines that read nothing else.

Release 12 on purpose. It is the last version of DXF that everything reads,
it has no object handles to keep consistent, and a plate is polylines and
circles, none of which gained anything after 1992. Anything that can open a
DXF at all can open this one.

The format is pairs of lines: a group code and a value. Nothing here is
clever about that, because the moment a DXF writer gets clever it starts
producing files that one particular program will not open and nobody can say
why.

Layers carry the meaning. The engraving is on ENGRAVE, the blank on OUTLINE,
the holes on FEATURES, and a shop that only wants to see one of those turns
the others off rather than asking for a different file.
"""

from __future__ import annotations

from dragpoint.compiler.plate import EngravedPlate
from dragpoint.geometry.box import Box
from dragpoint.geometry.stroke import Stroke
from dragpoint.spec.feature import Feature

__all__ = ["LAYERS", "render_dxf"]

LAYERS: dict[str, int] = {
    "OUTLINE": 7,
    "AREA": 8,
    "ENGRAVE": 1,
    "BORDER": 3,
    "FEATURES": 5,
}
"""Layer name to AutoCAD colour number."""


def render_dxf(plate: EngravedPlate, *, decimals: int = 4) -> str:
    """Draw one compiled plate as a release 12 DXF."""
    if not 0 <= decimals <= 8:
        raise ValueError(f"decimals of {decimals} is not a sane number of places")
    out: list[str] = []
    extents = _extents(plate)
    _header(out, extents, decimals)
    _tables(out)
    _entities(out, plate, decimals)
    out.extend(_pair(0, "EOF"))
    return "\n".join(out) + "\n"


def _pair(code: int, value: str | float) -> list[str]:
    """One group code and its value, as the two lines they occupy."""
    return [f"{code:>3}", str(value)]


def _number(value: float, decimals: int) -> str:
    """A coordinate, with negative zero flattened."""
    text = f"{value:.{decimals}f}"
    return f"{0.0:.{decimals}f}" if float(text) == 0.0 else text


def _extents(plate: EngravedPlate) -> Box:
    """The box the drawing covers, which is the blank plus anything outside it."""
    box = plate.spec.outline()
    for stroke in plate.runs:
        box = box.union(stroke.bounds())
    for feature in plate.spec.features:
        box = box.union(feature.keepout_bounds())
    return box


def _header(out: list[str], extents: Box, decimals: int) -> None:
    """The smallest header a reader will accept."""
    out.extend(_pair(0, "SECTION"))
    out.extend(_pair(2, "HEADER"))
    out.extend(_pair(9, "$ACADVER"))
    out.extend(_pair(1, "AC1009"))
    out.extend(_pair(9, "$INSUNITS"))
    out.extend(_pair(70, 4))
    out.extend(_pair(9, "$EXTMIN"))
    out.extend(_pair(10, _number(extents.min_x, decimals)))
    out.extend(_pair(20, _number(extents.min_y, decimals)))
    out.extend(_pair(9, "$EXTMAX"))
    out.extend(_pair(10, _number(extents.max_x, decimals)))
    out.extend(_pair(20, _number(extents.max_y, decimals)))
    out.extend(_pair(0, "ENDSEC"))


def _tables(out: list[str]) -> None:
    """The layer table."""
    out.extend(_pair(0, "SECTION"))
    out.extend(_pair(2, "TABLES"))
    out.extend(_pair(0, "TABLE"))
    out.extend(_pair(2, "LAYER"))
    out.extend(_pair(70, len(LAYERS)))
    for name, colour in LAYERS.items():
        out.extend(_pair(0, "LAYER"))
        out.extend(_pair(2, name))
        out.extend(_pair(70, 0))
        out.extend(_pair(62, colour))
        out.extend(_pair(6, "CONTINUOUS"))
    out.extend(_pair(0, "ENDTAB"))
    out.extend(_pair(0, "ENDSEC"))


def _entities(out: list[str], plate: EngravedPlate, decimals: int) -> None:
    """Everything that gets drawn."""
    out.extend(_pair(0, "SECTION"))
    out.extend(_pair(2, "ENTITIES"))
    _rectangle(out, plate.spec.outline(), "OUTLINE", decimals)
    _rectangle(out, plate.spec.area(), "AREA", decimals)
    border = plate.spec.border_box()
    if border is not None:
        _rectangle(out, border, "BORDER", decimals)
    for feature in plate.spec.features:
        _feature(out, feature, decimals)
    for stroke in plate.runs:
        _polyline(out, stroke, "ENGRAVE", decimals)
    out.extend(_pair(0, "ENDSEC"))


def _polyline(out: list[str], stroke: Stroke, layer: str, decimals: int) -> None:
    """One open polyline, as the header, its vertices and the terminator."""
    out.extend(_pair(0, "POLYLINE"))
    out.extend(_pair(8, layer))
    out.extend(_pair(66, 1))
    out.extend(_pair(70, 0))
    out.extend(_pair(10, _number(0.0, decimals)))
    out.extend(_pair(20, _number(0.0, decimals)))
    out.extend(_pair(30, _number(0.0, decimals)))
    for point in stroke.points:
        out.extend(_pair(0, "VERTEX"))
        out.extend(_pair(8, layer))
        out.extend(_pair(10, _number(point.x, decimals)))
        out.extend(_pair(20, _number(point.y, decimals)))
        out.extend(_pair(30, _number(0.0, decimals)))
    out.extend(_pair(0, "SEQEND"))
    out.extend(_pair(8, layer))


def _rectangle(out: list[str], box: Box, layer: str, decimals: int) -> None:
    """A closed rectangle, drawn as a polyline back to its first corner."""
    corners = box.corners
    _polyline(out, Stroke(tuple(corners) + (corners[0],)), layer, decimals)


def _feature(out: list[str], feature: Feature, decimals: int) -> None:
    """One hole or cutout on the features layer."""
    if feature.is_round:
        out.extend(_pair(0, "CIRCLE"))
        out.extend(_pair(8, "FEATURES"))
        out.extend(_pair(10, _number(feature.centre.x, decimals)))
        out.extend(_pair(20, _number(feature.centre.y, decimals)))
        out.extend(_pair(30, _number(0.0, decimals)))
        out.extend(_pair(40, _number(feature.radius, decimals)))
        return
    _rectangle(out, feature.bounds(), "FEATURES", decimals)
