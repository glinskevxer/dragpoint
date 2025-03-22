"""Parsing .strk source, and naming the line when it will not parse."""

from __future__ import annotations

import pytest

from dragpoint.errors import FontSyntax
from dragpoint.font.parse import parse_face

GOOD = """
# a face for testing
face testface
upem 1000
cap 700
xheight 500
ascender 750
descender -200
linegap 40
fallback question

glyph A 600 U+0041
  tag wide
  s 40,0 300,700 560,0
  s 140,250 460,250

glyph V 600 U+0056
  s 40,700 300,0 560,700

glyph space 300 U+0020

glyph question 550 U+003F
  s 80,500 275,700 470,500

kern A V -60
"""


def test_a_good_file_round_trips_into_a_face() -> None:
    face = parse_face(GOOD, "good.strk")
    assert face.name == "testface"
    assert face.metrics.units_per_em == 1000
    assert face.metrics.line_gap == 40
    assert face.names() == ("A", "V", "question", "space")
    assert face.glyph("A").stroke_count() == 2
    assert face.glyph("A").has_tag("wide")
    assert face.glyph("A").codepoint == ord("A")
    assert face.kern("A", "V") == -60
    assert face.fallback == "question"


def test_line_gap_defaults_to_zero_when_absent() -> None:
    text = GOOD.replace("linegap 40\n", "")
    assert parse_face(text).metrics.line_gap == 0


def test_comments_and_blank_lines_are_ignored() -> None:
    text = GOOD.replace("glyph V 600 U+0056", "glyph V 600 U+0056  # the vee")
    assert parse_face(text).glyph("V").advance == 600


def test_indentation_is_decoration_and_not_structure() -> None:
    text = GOOD.replace("  s 40,0 300,700 560,0", "s 40,0 300,700 560,0")
    assert parse_face(text).glyph("A").stroke_count() == 2


def test_a_glyph_may_have_no_strokes_at_all() -> None:
    assert parse_face(GOOD).glyph("space").is_blank


def test_a_code_point_is_optional() -> None:
    text = GOOD.replace("glyph V 600 U+0056", "glyph V 600")
    assert parse_face(text).glyph("V").codepoint is None


def test_a_file_with_no_face_name_is_refused() -> None:
    text = GOOD.replace("face testface\n", "")
    with pytest.raises(FontSyntax, match="never says what the face is called"):
        parse_face(text)


def test_a_second_face_line_is_refused() -> None:
    with pytest.raises(FontSyntax, match="set twice"):
        parse_face(GOOD + "\nface again\n")


def test_a_face_line_with_no_name_is_refused() -> None:
    with pytest.raises(FontSyntax, match="face needs a name"):
        parse_face("face\nupem 1000\n")


def test_a_missing_header_field_names_all_of_them() -> None:
    text = GOOD.replace("cap 700\n", "").replace("xheight 500\n", "")
    with pytest.raises(FontSyntax) as caught:
        parse_face(text)
    assert "cap" in str(caught.value)
    assert "xheight" in str(caught.value)


def test_a_header_key_after_the_first_glyph_is_refused() -> None:
    with pytest.raises(FontSyntax, match="before the first glyph"):
        parse_face(GOOD + "\nupem 2000\n")


def test_an_unknown_keyword_names_itself() -> None:
    with pytest.raises(FontSyntax, match="unknown keyword 'wibble'"):
        parse_face(GOOD + "\nwibble 3\n")


def test_the_reported_line_number_is_the_real_one() -> None:
    text = GOOD + "\n\nwibble 3\n"
    with pytest.raises(FontSyntax) as caught:
        parse_face(text, "face.strk")
    assert caught.value.line == len(text.splitlines())
    assert str(caught.value).startswith("face.strk:")


def test_a_stroke_outside_a_glyph_is_refused() -> None:
    with pytest.raises(FontSyntax, match="no glyph open"):
        parse_face("face f\nupem 1\ns 0,0 1,1\n")


def test_a_tag_outside_a_glyph_is_refused() -> None:
    with pytest.raises(FontSyntax, match="no glyph open"):
        parse_face("face f\ntag wide\n")


def test_an_empty_tag_is_refused() -> None:
    with pytest.raises(FontSyntax, match="tag needs a name"):
        parse_face(GOOD.replace("  tag wide", "  tag"))


def test_a_glyph_line_needs_a_name_and_an_advance() -> None:
    with pytest.raises(FontSyntax, match="a name and an advance"):
        parse_face(GOOD + "\nglyph Z\n")


def test_a_glyph_line_with_extra_words_is_refused() -> None:
    with pytest.raises(FontSyntax, match="a name, an advance and a code point"):
        parse_face(GOOD + "\nglyph Z 100 U+005A extra\n")


def test_an_unusable_glyph_name_is_refused() -> None:
    with pytest.raises(FontSyntax, match="not a usable glyph name"):
        parse_face(GOOD + "\nglyph 9bad 100\n")


def test_a_negative_advance_is_refused() -> None:
    with pytest.raises(FontSyntax, match="negative advance"):
        parse_face(GOOD + "\nglyph Z -5\n")


def test_a_fractional_advance_is_refused() -> None:
    with pytest.raises(FontSyntax, match="whole number"):
        parse_face(GOOD + "\nglyph Z 100.5\n")


def test_a_duplicate_glyph_is_refused_at_its_second_line() -> None:
    with pytest.raises(FontSyntax, match="appears twice"):
        parse_face(GOOD + "\nglyph A 600\n")


@pytest.mark.parametrize("token", ["0041", "X+0041", "U+zzzz"])
def test_a_bad_code_point_is_refused(token: str) -> None:
    with pytest.raises(FontSyntax, match="code point"):
        parse_face(GOOD + f"\nglyph Z 100 {token}\n")


def test_a_lowercase_u_plus_is_accepted() -> None:
    face = parse_face(GOOD + "\nglyph Z 100 u+005A\n")
    assert face.glyph("Z").codepoint == ord("Z")


def test_a_point_without_a_comma_is_refused() -> None:
    with pytest.raises(FontSyntax, match="not an x,y pair"):
        parse_face(GOOD.replace("s 40,700 300,0 560,700", "s 40,700 300 560,700"))


def test_a_point_with_a_junk_coordinate_is_refused() -> None:
    with pytest.raises(FontSyntax, match="should be a number"):
        parse_face(GOOD.replace("s 40,700 300,0 560,700", "s 40,700 abc,0 560,700"))


def test_a_one_point_stroke_is_refused() -> None:
    with pytest.raises(FontSyntax, match="at least two points"):
        parse_face(GOOD.replace("s 40,700 300,0 560,700", "s 40,700"))


def test_a_kern_line_needs_three_fields() -> None:
    with pytest.raises(FontSyntax, match="a left glyph, a right glyph and a value"):
        parse_face(GOOD + "\nkern A V\n")


def test_a_kern_naming_an_absent_glyph_names_it() -> None:
    with pytest.raises(FontSyntax, match="'Z', which is not a glyph here"):
        parse_face(GOOD + "\nkern A Z -20\n")
    with pytest.raises(FontSyntax, match="'Z', which is not a glyph here"):
        parse_face(GOOD + "\nkern Z A -20\n")


def test_a_bad_metrics_block_is_reported_against_the_file() -> None:
    with pytest.raises(FontSyntax) as caught:
        parse_face(GOOD.replace("xheight 500", "xheight 900"))
    assert caught.value.line == 0
    assert "x height" in str(caught.value)


def test_a_fallback_that_is_not_a_glyph_is_reported() -> None:
    with pytest.raises(FontSyntax, match="fallback glyph"):
        parse_face(GOOD.replace("fallback question", "fallback nothere"))
