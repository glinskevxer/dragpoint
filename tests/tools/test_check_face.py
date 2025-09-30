"""The face check."""

from __future__ import annotations

import pytest

from dragpoint.font.face import StrokeFace
from dragpoint.font.glyph import Glyph
from dragpoint.font.library import load_face, shipped_names
from dragpoint.geometry.stroke import Stroke
from dragpoint.tools import check_face


def panelgothic() -> StrokeFace:
    return load_face("panelgothic")


def bent(name: str, glyph: Glyph) -> StrokeFace:
    """The house face with one glyph replaced by a bad one."""
    face = panelgothic()
    return StrokeFace(
        name=face.name,
        metrics=face.metrics,
        glyphs={**dict(face.glyphs), name: glyph},
        kerning=dict(face.kerning),
        fallback=face.fallback,
    )


def test_every_shipped_face_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_face.main() == 0
    assert "clean" in capsys.readouterr().out


def test_the_house_face_has_nothing_wrong_with_it() -> None:
    assert check_face.check_face("panelgothic", panelgothic()) == []


def test_the_face_file_is_where_it_says_it_is() -> None:
    for name in shipped_names():
        assert check_face.face_path(name).is_file()


def test_a_missing_required_character_is_reported() -> None:
    face = panelgothic()
    without = StrokeFace(
        name=face.name,
        metrics=face.metrics,
        glyphs={name: face.glyph(name) for name in face.names() if name != "A"},
        kerning={},
        fallback=None,
    )
    problems = check_face.check_face("panelgothic", without)
    assert any("cannot draw 'A'" in str(problem) for problem in problems)


def test_two_strokes_that_nearly_meet_are_reported() -> None:
    near = Glyph(
        name="A",
        advance=700,
        strokes=(
            Stroke.from_pairs([(100.0, 0.0), (100.0, 700.0)]),
            Stroke.from_pairs([(140.0, 0.0), (140.0, 700.0)]),
        ),
        codepoint=ord("A"),
    )
    problems = check_face.check_face("panelgothic", bent("A", near))
    assert any("units apart" in str(problem) for problem in problems)


def test_two_strokes_that_meet_on_purpose_are_not_reported() -> None:
    joined = Glyph(
        name="A",
        advance=700,
        strokes=(
            Stroke.from_pairs([(100.0, 0.0), (100.0, 700.0)]),
            Stroke.from_pairs([(100.0, 350.0), (500.0, 350.0)]),
        ),
        codepoint=ord("A"),
    )
    problems = check_face.check_face("panelgothic", bent("A", joined))
    assert not any("units apart" in str(problem) for problem in problems)


def test_a_stroke_that_folds_onto_itself_is_reported() -> None:
    folded = Glyph(
        name="A",
        advance=700,
        strokes=(Stroke.from_pairs([(100.0, 0.0), (600.0, 0.0), (600.0, 40.0), (100.0, 40.0)]),),
        codepoint=ord("A"),
    )
    problems = check_face.check_face("panelgothic", bent("A", folded))
    assert any("closes to" in str(problem) for problem in problems)


def test_a_stroke_too_short_to_be_a_stroke_is_reported() -> None:
    stubby = Glyph(
        name="A",
        advance=700,
        strokes=(Stroke.from_pairs([(300.0, 0.0), (305.0, 0.0)]),),
        codepoint=ord("A"),
    )
    problems = check_face.check_face("panelgothic", bent("A", stubby))
    assert any("only 5.0 units" in str(problem) for problem in problems)


def test_a_tight_left_bearing_is_reported() -> None:
    tight = Glyph(
        name="A",
        advance=700,
        strokes=(Stroke.from_pairs([(10.0, 0.0), (10.0, 700.0)]),),
        codepoint=ord("A"),
    )
    problems = check_face.check_face("panelgothic", bent("A", tight))
    assert any("left bearing is 10.0" in str(problem) for problem in problems)


def test_a_tight_right_bearing_is_reported() -> None:
    tight = Glyph(
        name="A",
        advance=140,
        strokes=(Stroke.from_pairs([(100.0, 0.0), (100.0, 700.0)]),),
        codepoint=ord("A"),
    )
    problems = check_face.check_face("panelgothic", bent("A", tight))
    assert any("right bearing is 40.0" in str(problem) for problem in problems)


def test_a_kern_that_is_too_tight_is_reported() -> None:
    face = panelgothic()
    hard = StrokeFace(
        name=face.name,
        metrics=face.metrics,
        glyphs=dict(face.glyphs),
        kerning={("A", "V"): -120},
        fallback=face.fallback,
    )
    problems = check_face.check_face("panelgothic", hard)
    assert any("more than 30" in str(problem) for problem in problems)


def test_a_blank_glyph_has_nothing_to_check() -> None:
    space = Glyph(name="space", advance=300, codepoint=ord(" "))
    assert check_face.check_face("panelgothic", bent("space", space)) == []


def test_the_numbers_are_the_ones_the_face_header_states() -> None:
    assert check_face.MIN_SEPARATION == 90.0
    assert check_face.MIN_BEARING == 80.0
    assert check_face.MAX_KERN == 30
