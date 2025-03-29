"""Writing .strk source back out, canonically."""

from __future__ import annotations

import pytest

from dragpoint.font.face import FaceMetrics, StrokeFace
from dragpoint.font.glyph import Glyph
from dragpoint.font.parse import parse_face
from dragpoint.font.write import format_number, write_face
from dragpoint.geometry.stroke import Stroke

from .test_parse import GOOD


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (40.0, "40"),
        (-200.0, "-200"),
        (0.0, "0"),
        (12.5, "12.5"),
        (0.12345, "0.1235"),
        (1e-9, "0"),
    ],
)
def test_format_number(value: float, expected: str) -> None:
    assert format_number(value) == expected


def test_the_output_ends_with_a_newline() -> None:
    assert write_face(parse_face(GOOD)).endswith("\n")


def test_a_face_survives_a_round_trip() -> None:
    original = parse_face(GOOD)
    again = parse_face(write_face(original))
    assert again.name == original.name
    assert again.metrics == original.metrics
    assert again.names() == original.names()
    assert again.fallback == original.fallback
    assert dict(again.kerning) == dict(original.kerning)
    for name in original.names():
        assert again.glyph(name) == original.glyph(name)


def test_writing_is_stable_across_two_passes() -> None:
    once = write_face(parse_face(GOOD))
    twice = write_face(parse_face(once))
    assert once == twice


def test_glyph_order_follows_the_code_point_not_the_input_order() -> None:
    metrics = FaceMetrics(
        units_per_em=1000, cap_height=700, x_height=500, ascender=700, descender=0
    )
    face = StrokeFace(
        name="ordered",
        metrics=metrics,
        glyphs={
            "B": Glyph(name="B", advance=100, codepoint=ord("B")),
            "A": Glyph(name="A", advance=100, codepoint=ord("A")),
            "later": Glyph(name="later", advance=100),
            "early": Glyph(name="early", advance=100),
        },
    )
    text = write_face(face)
    assert text.index("glyph A ") < text.index("glyph B ")
    assert text.index("glyph B ") < text.index("glyph early ")
    assert text.index("glyph early ") < text.index("glyph later ")


def test_a_glyph_without_a_code_point_writes_no_u_plus() -> None:
    metrics = FaceMetrics(
        units_per_em=1000, cap_height=700, x_height=500, ascender=700, descender=0
    )
    face = StrokeFace(
        name="bare",
        metrics=metrics,
        glyphs={"logo": Glyph(name="logo", advance=100)},
    )
    assert "glyph logo 100\n" in write_face(face)


def test_tags_come_out_sorted() -> None:
    metrics = FaceMetrics(
        units_per_em=1000, cap_height=700, x_height=500, ascender=700, descender=0
    )
    face = StrokeFace(
        name="tagged",
        metrics=metrics,
        glyphs={
            "i": Glyph(
                name="i",
                advance=100,
                strokes=(Stroke.from_pairs([(0.0, 0.0), (0.0, 500.0)]),),
                tags=frozenset({"thin", "fixed", "alt"}),
            )
        },
    )
    text = write_face(face)
    assert text.index("tag alt") < text.index("tag fixed") < text.index("tag thin")


def test_kerns_come_out_sorted_and_after_the_glyphs() -> None:
    text = write_face(parse_face(GOOD + "\nkern V A -40\n"))
    assert text.index("glyph ") < text.index("kern ")
    assert text.index("kern A V -60") < text.index("kern V A -40")


def test_a_face_with_no_kerning_writes_no_kern_lines() -> None:
    text = write_face(parse_face(GOOD.replace("kern A V -60", "")))
    assert "kern " not in text


def test_fractional_coordinates_survive_the_round_trip() -> None:
    metrics = FaceMetrics(
        units_per_em=1000, cap_height=700, x_height=500, ascender=700, descender=0
    )
    face = StrokeFace(
        name="curvy",
        metrics=metrics,
        glyphs={
            "O": Glyph(
                name="O",
                advance=600,
                strokes=(Stroke.from_pairs([(12.5, 0.25), (587.5, 699.75)]),),
                codepoint=ord("O"),
            )
        },
    )
    again = parse_face(write_face(face))
    assert again.glyph("O").strokes[0].points[0].x == pytest.approx(12.5)
    assert again.glyph("O").strokes[0].points[1].y == pytest.approx(699.75)


def test_the_header_comes_out_in_a_fixed_order() -> None:
    text = write_face(parse_face(GOOD))
    lines = [line.split()[0] for line in text.splitlines()[:8] if line]
    assert lines[:8] == [
        "face",
        "upem",
        "cap",
        "xheight",
        "ascender",
        "descender",
        "linegap",
        "fallback",
    ]
