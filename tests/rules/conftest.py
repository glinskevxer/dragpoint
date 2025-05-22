"""A plate laid out and ready for the rules to pick over."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pytest

from dragpoint.font.library import shipped_face
from dragpoint.rules.check import REGISTRY, PlateCheck, RuleDef
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import fit_lines
from dragpoint.text.layout import layout_lines
from dragpoint.tool.cutter import catalogue_cutter
from dragpoint.tool.material import material
from dragpoint.tool.passes import plan_passes


def build_check(
    lines: Sequence[str] = ("PUMP 2", "RUN"),
    *,
    cutter: str = "V30-015",
    stock: str = "LAM16-BW",
    depth: float | None = None,
    **plate_kwargs: object,
) -> PlateCheck:
    """Lay a plate out the way the compiler will, for a rule to look at."""
    values: dict[str, object] = {
        "name": "P-101",
        "width": 60.0,
        "height": 20.0,
        "stock": stock,
        "lines": tuple(lines),
    }
    values.update(plate_kwargs)
    plate = PlateSpec(**values)  # type: ignore[arg-type]
    face = shipped_face(plate.face)
    sheet = material(stock)
    tool = catalogue_cutter(cutter)
    cut_depth = depth if depth is not None else sheet.nominal_depth
    fit = fit_lines(plate.lines, face, plate.style(), plate.area().width, plate.fit)
    text = layout_lines(
        plate.lines,
        face,
        fit.style,
        box=plate.area(),
        halign=plate.halign,
        valign=plate.valign,
    )
    return PlateCheck(
        plate=plate,
        face=face,
        style=fit.style,
        fit=fit,
        text=text,
        strokes=text.strokes(),
        cutter=tool,
        stock=sheet,
        depth=cut_depth,
        passes=plan_passes(cut_depth, sheet, tool),
    )


@pytest.fixture
def check() -> PlateCheck:
    return build_check()


@pytest.fixture
def clean_registry() -> Iterator[dict[str, RuleDef]]:
    """Hand the tests an empty register and put the real one back after."""
    saved = dict(REGISTRY)
    REGISTRY.clear()
    try:
        yield REGISTRY
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)
