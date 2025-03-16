"""A small face the font tests can lean on without loading a file."""

from __future__ import annotations

import pytest

from dragpoint.font.face import FaceMetrics, StrokeFace
from dragpoint.font.glyph import Glyph
from dragpoint.geometry.stroke import Stroke


def stub_metrics() -> FaceMetrics:
    return FaceMetrics(
        units_per_em=1000,
        cap_height=700,
        x_height=500,
        ascender=750,
        descender=-200,
        line_gap=50,
    )


def stub_glyphs() -> list[Glyph]:
    return [
        Glyph(
            name="A",
            advance=600,
            strokes=(
                Stroke.from_pairs([(40.0, 0.0), (300.0, 700.0), (560.0, 0.0)]),
                Stroke.from_pairs([(140.0, 250.0), (460.0, 250.0)]),
            ),
            codepoint=ord("A"),
        ),
        Glyph(
            name="V",
            advance=600,
            strokes=(Stroke.from_pairs([(40.0, 700.0), (300.0, 0.0), (560.0, 700.0)]),),
            codepoint=ord("V"),
        ),
        Glyph(
            name="L",
            advance=500,
            strokes=(Stroke.from_pairs([(80.0, 700.0), (80.0, 0.0), (420.0, 0.0)]),),
            codepoint=ord("L"),
        ),
        Glyph(name="space", advance=300, codepoint=ord(" ")),
        Glyph(
            name="period",
            advance=250,
            strokes=(Stroke.from_pairs([(105.0, 0.0), (105.0, 40.0)]),),
            codepoint=ord("."),
        ),
        Glyph(
            name="question",
            advance=550,
            strokes=(Stroke.from_pairs([(80.0, 500.0), (275.0, 700.0), (470.0, 500.0)]),),
            codepoint=ord("?"),
        ),
    ]


@pytest.fixture
def face() -> StrokeFace:
    return StrokeFace(
        name="stub",
        metrics=stub_metrics(),
        glyphs={glyph.name: glyph for glyph in stub_glyphs()},
        kerning={("A", "V"): -60, ("V", "A"): -60},
        fallback=None,
    )
