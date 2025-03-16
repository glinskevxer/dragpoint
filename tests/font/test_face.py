"""Faces: metrics validation, lookup, kerning and cap height sizing."""

from __future__ import annotations

import pytest

from dragpoint.errors import MissingGlyph
from dragpoint.font.face import FaceMetrics, StrokeFace
from dragpoint.font.glyph import Glyph

from .conftest import stub_glyphs, stub_metrics


def test_metrics_accept_a_sane_block() -> None:
    metrics = stub_metrics()
    assert metrics.units_per_em == 1000
    assert metrics.default_line_pitch == 1000


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("units_per_em", 0, "units per em"),
        ("cap_height", 0, "cap height"),
        ("x_height", 0, "x height"),
        ("x_height", 800, "x height"),
        ("ascender", 600, "ascender"),
        ("descender", 10, "descender"),
        ("line_gap", -1, "line gap"),
    ],
)
def test_metrics_reject_the_impossible(field: str, value: int, message: str) -> None:
    values = {
        "units_per_em": 1000,
        "cap_height": 700,
        "x_height": 500,
        "ascender": 750,
        "descender": -200,
        "line_gap": 0,
    }
    values[field] = value
    with pytest.raises(ValueError, match=message):
        FaceMetrics(**values)


def test_a_face_needs_a_name() -> None:
    with pytest.raises(ValueError, match="needs a name"):
        StrokeFace(name="", metrics=stub_metrics(), glyphs={})


def test_a_glyph_filed_under_the_wrong_key_is_refused() -> None:
    with pytest.raises(ValueError, match="calls itself"):
        StrokeFace(
            name="bad",
            metrics=stub_metrics(),
            glyphs={"B": Glyph(name="A", advance=100)},
        )


def test_a_fallback_that_is_not_present_is_refused() -> None:
    with pytest.raises(ValueError, match="fallback glyph"):
        StrokeFace(name="bad", metrics=stub_metrics(), glyphs={}, fallback="notdef")


def test_a_kern_pair_naming_an_absent_glyph_is_refused() -> None:
    with pytest.raises(ValueError, match="kern pair"):
        StrokeFace(
            name="bad",
            metrics=stub_metrics(),
            glyphs={"A": Glyph(name="A", advance=100)},
            kerning={("A", "W"): -20},
        )


def test_the_glyph_table_cannot_be_edited_afterwards(face: StrokeFace) -> None:
    with pytest.raises(TypeError):
        face.glyphs["Z"] = Glyph(name="Z", advance=100)  # type: ignore[index]


def test_names_come_back_sorted(face: StrokeFace) -> None:
    assert face.names() == ("A", "L", "V", "period", "question", "space")


def test_lookup_by_name_and_by_character(face: StrokeFace) -> None:
    assert face.glyph("A").advance == 600
    assert face.glyph_for("A").name == "A"
    assert face.glyph_for(".").name == "period"
    assert face.glyph_for(" ").is_blank


def test_a_missing_glyph_raises_when_there_is_no_fallback(face: StrokeFace) -> None:
    with pytest.raises(MissingGlyph) as caught:
        face.glyph_for("Z")
    assert "stub" in str(caught.value)
    assert "'Z'" in str(caught.value)


def test_a_fallback_answers_for_anything_missing() -> None:
    glyphs = {glyph.name: glyph for glyph in stub_glyphs()}
    glyphs["question"] = glyphs["question"]
    face = StrokeFace(
        name="withfallback",
        metrics=stub_metrics(),
        glyphs=glyphs,
        fallback="question",
    )
    assert face.glyph_for("Z").name == "question"
    assert not face.has("Z")


def test_has_reports_the_real_coverage(face: StrokeFace) -> None:
    assert face.has("A")
    assert face.has(" ")
    assert not face.has("Z")


def test_missing_lists_each_offender_once_in_reading_order(face: StrokeFace) -> None:
    assert face.missing("VALVE AZ Z") == ("E", "Z")


def test_missing_of_a_covered_string_is_empty(face: StrokeFace) -> None:
    assert face.missing("ALL") == ()


def test_kerning(face: StrokeFace) -> None:
    assert face.kern("A", "V") == -60
    assert face.kern("V", "A") == -60
    assert face.kern("A", "L") == 0


def test_scale_for_cap_height(face: StrokeFace) -> None:
    assert face.scale_for_cap_height(3.5) == pytest.approx(0.005)
    assert face.scale_for_em(10.0) == pytest.approx(0.01)


@pytest.mark.parametrize("size", [0.0, -1.0])
def test_a_non_positive_size_is_refused(face: StrokeFace, size: float) -> None:
    with pytest.raises(ValueError):
        face.scale_for_cap_height(size)
    with pytest.raises(ValueError):
        face.scale_for_em(size)


def test_with_glyphs_merges_and_lets_the_new_one_win(face: StrokeFace) -> None:
    wider_a = Glyph(name="A", advance=999)
    extended = face.with_glyphs([wider_a, Glyph(name="Z", advance=500)])
    assert extended.glyph("A").advance == 999
    assert extended.has("Z")
    assert face.glyph("A").advance == 600
    assert not face.has("Z")


def test_with_glyphs_keeps_the_kerning(face: StrokeFace) -> None:
    extended = face.with_glyphs([Glyph(name="Z", advance=500)])
    assert extended.kern("A", "V") == -60


def test_container_protocol(face: StrokeFace) -> None:
    assert len(face) == 6
    assert "A" in face
    assert "Z" not in face


def test_str_says_what_it_is(face: StrokeFace) -> None:
    assert str(face) == "stub (6 glyphs, 1000 upem)"
