"""Glyphs, and the difference between the advance and the marks."""

from __future__ import annotations

import pytest

from dragpoint.font.glyph import Glyph, glyph_name_for, is_valid_glyph_name
from dragpoint.geometry.stroke import Stroke
from dragpoint.geometry.transform import Transform


def letter_l() -> Glyph:
    return Glyph(
        name="L",
        advance=500,
        strokes=(Stroke.from_pairs([(80.0, 700.0), (80.0, 0.0), (420.0, 0.0)]),),
        codepoint=ord("L"),
    )


@pytest.mark.parametrize(
    ("character", "expected"),
    [
        ("A", "A"),
        ("z", "z"),
        ("0", "zero"),
        ("7", "seven"),
        (".", "period"),
        (" ", "space"),
        ("-", "hyphen"),
        ("/", "slash"),
        ("\\", "backslash"),
        ("°", "uni00B0"),
        ("Ω", "uni2126"),
    ],
)
def test_glyph_name_for(character: str, expected: str) -> None:
    assert glyph_name_for(character) == expected


def test_glyph_name_for_refuses_a_string() -> None:
    with pytest.raises(ValueError, match="single character"):
        glyph_name_for("AB")


def test_every_generated_name_is_a_valid_name() -> None:
    for code in range(32, 127):
        assert is_valid_glyph_name(glyph_name_for(chr(code)))


@pytest.mark.parametrize("name", ["A", "period", "A.alt", "_notdef", "uni00B0"])
def test_valid_names(name: str) -> None:
    assert is_valid_glyph_name(name)


@pytest.mark.parametrize("name", ["", "1", ".alt", "a b", "a-b", "a/b"])
def test_invalid_names(name: str) -> None:
    assert not is_valid_glyph_name(name)


def test_a_glyph_refuses_an_unusable_name() -> None:
    with pytest.raises(ValueError, match="not a usable glyph name"):
        Glyph(name="a b", advance=100)


def test_a_glyph_refuses_a_negative_advance() -> None:
    with pytest.raises(ValueError, match="negative advance"):
        Glyph(name="A", advance=-1)


def test_a_blank_glyph_is_allowed_and_knows_it() -> None:
    space = Glyph(name="space", advance=300)
    assert space.is_blank
    assert space.ink_bounds() is None
    assert space.left_bearing() is None
    assert space.right_bearing() is None
    assert space.stroke_count() == 0
    assert space.path_length() == 0.0


def test_ink_bounds_are_the_marks_and_not_the_advance() -> None:
    box = letter_l().ink_bounds()
    assert box is not None
    assert box.min_x == 80.0
    assert box.max_x == 420.0
    assert box.max_y == 700.0


def test_bearings_come_off_the_advance() -> None:
    glyph = letter_l()
    assert glyph.left_bearing() == 80.0
    assert glyph.right_bearing() == 80.0


def test_a_bearing_can_be_negative_when_the_marks_overhang() -> None:
    wide = Glyph(
        name="W",
        advance=200,
        strokes=(Stroke.from_pairs([(-20.0, 0.0), (260.0, 0.0)]),),
    )
    assert wide.left_bearing() == -20.0
    assert wide.right_bearing() == -60.0


def test_path_length_is_in_font_units() -> None:
    assert letter_l().path_length() == pytest.approx(1040.0)


def test_transformed_moves_the_marks_and_leaves_the_advance() -> None:
    mirrored = letter_l().transformed(Transform.mirror_x())
    box = mirrored.ink_bounds()
    assert box is not None
    assert box.min_x == -420.0
    assert mirrored.advance == 500
    assert mirrored.name == "L"
    assert mirrored.codepoint == ord("L")


def test_with_advance_keeps_everything_else() -> None:
    changed = letter_l().with_advance(600)
    assert changed.advance == 600
    assert changed.strokes == letter_l().strokes
    assert changed.codepoint == ord("L")


def test_tags_default_to_empty_and_are_queryable() -> None:
    plain = letter_l()
    assert not plain.has_tag("thin")
    tagged = Glyph(name="i", advance=200, tags=frozenset({"thin", "fixed"}))
    assert tagged.has_tag("thin")
    assert tagged.has_tag("fixed")
    assert not tagged.has_tag("swash")


def test_tags_survive_a_transform() -> None:
    tagged = Glyph(
        name="i",
        advance=200,
        strokes=(Stroke.from_pairs([(0.0, 0.0), (0.0, 500.0)]),),
        tags=frozenset({"thin"}),
    )
    assert tagged.transformed(Transform.scaling(2.0)).has_tag("thin")


def test_glyphs_are_hashable_so_a_shaper_can_cache_them() -> None:
    assert len({letter_l(), letter_l()}) == 1


def test_str_says_what_it_is() -> None:
    assert str(letter_l()) == "L(500, 1 strokes)"
