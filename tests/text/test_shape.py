"""Shaping a line: advances, kerning, tracking and the word space."""

from __future__ import annotations

import pytest

from dragpoint.errors import MissingGlyph
from dragpoint.font.face import StrokeFace
from dragpoint.font.library import shipped_face
from dragpoint.geometry.point import Point
from dragpoint.geometry.transform import Transform
from dragpoint.text.shape import shape_run
from dragpoint.text.style import TextStyle


@pytest.fixture
def face() -> StrokeFace:
    return shipped_face("panelgothic")


def test_an_empty_string_shapes_to_nothing(face: StrokeFace) -> None:
    run = shape_run("", face, TextStyle(cap_height=3.0))
    assert len(run) == 0
    assert run.width == 0.0
    assert run.strokes() == ()
    assert run.ink_bounds() is None
    assert run.is_blank


def test_a_single_glyph_starts_at_the_origin(face: StrokeFace) -> None:
    run = shape_run("H", face, TextStyle(cap_height=7.0))
    assert run.placed[0].origin == Point(0.0, 0.0)
    assert run.width == pytest.approx(640 * 0.01)


def test_the_cap_height_is_what_it_says_on_the_drawing(face: StrokeFace) -> None:
    run = shape_run("H", face, TextStyle(cap_height=3.5))
    box = run.ink_bounds()
    assert box is not None
    assert box.height == pytest.approx(3.5)


def test_advances_accumulate(face: StrokeFace) -> None:
    run = shape_run("HH", face, TextStyle(cap_height=7.0))
    assert run.placed[1].origin.x == pytest.approx(6.4)
    assert run.width == pytest.approx(12.8)


def test_kerning_pulls_a_pair_together(face: StrokeFace) -> None:
    style = TextStyle(cap_height=7.0)
    kerned = shape_run("AV", face, style)
    unkerned = shape_run("AV", face, TextStyle(cap_height=7.0, kerning=False))
    assert kerned.width < unkerned.width
    assert kerned.width == pytest.approx(unkerned.width - 0.30)


def test_kerning_off_leaves_the_pair_at_its_advances(face: StrokeFace) -> None:
    run = shape_run("AV", face, TextStyle(cap_height=7.0, kerning=False))
    advances = face.glyph("A").advance + face.glyph("V").advance
    assert run.width == pytest.approx(advances * 0.01)


def test_an_unkerned_pair_is_unaffected_either_way(face: StrokeFace) -> None:
    style = TextStyle(cap_height=7.0)
    assert shape_run("HH", face, style).width == pytest.approx(12.8)


def test_tracking_is_added_after_every_glyph_including_the_last(face: StrokeFace) -> None:
    plain = shape_run("HH", face, TextStyle(cap_height=7.0))
    tracked = shape_run("HH", face, TextStyle(cap_height=7.0, tracking=0.5))
    assert tracked.width == pytest.approx(plain.width + 1.0)
    assert tracked.placed[1].origin.x == pytest.approx(plain.placed[1].origin.x + 0.5)


def test_the_word_space_overrides_the_space_glyph(face: StrokeFace) -> None:
    default = shape_run("H H", face, TextStyle(cap_height=7.0))
    wide = shape_run("H H", face, TextStyle(cap_height=7.0, word_space=5.0))
    assert default.width == pytest.approx(6.4 + 3.0 + 6.4)
    assert wide.width == pytest.approx(6.4 + 5.0 + 6.4)


def test_the_word_space_does_not_touch_other_glyphs(face: StrokeFace) -> None:
    run = shape_run("HH", face, TextStyle(cap_height=7.0, word_space=5.0))
    assert run.width == pytest.approx(12.8)


def test_condense_narrows_the_advances_as_well_as_the_glyphs(face: StrokeFace) -> None:
    run = shape_run("HH", face, TextStyle(cap_height=7.0, condense=0.5))
    assert run.width == pytest.approx(6.4)
    box = run.ink_bounds()
    assert box is not None
    assert box.height == pytest.approx(7.0)


def test_condense_scales_the_kern_too(face: StrokeFace) -> None:
    full = shape_run("AV", face, TextStyle(cap_height=7.0))
    half = shape_run("AV", face, TextStyle(cap_height=7.0, condense=0.5))
    assert half.width == pytest.approx(full.width / 2)


def test_a_blank_run_reports_itself_blank(face: StrokeFace) -> None:
    run = shape_run("   ", face, TextStyle(cap_height=3.0))
    assert run.is_blank
    assert run.width > 0.0
    assert run.ink_bounds() is None


def test_the_ink_box_is_narrower_than_the_advance_width(face: StrokeFace) -> None:
    run = shape_run("HH ", face, TextStyle(cap_height=7.0))
    box = run.ink_bounds()
    assert box is not None
    assert box.width < run.width


def test_a_missing_glyph_comes_out_as_the_fallback(face: StrokeFace) -> None:
    run = shape_run("a", face, TextStyle(cap_height=3.0))
    assert run.placed[0].glyph.name == "question"


def test_a_face_without_a_fallback_raises(face: StrokeFace) -> None:
    bare = StrokeFace(name="bare", metrics=face.metrics, glyphs=dict(face.glyphs))
    with pytest.raises(MissingGlyph):
        shape_run("a", bare, TextStyle(cap_height=3.0))


def test_a_newline_is_not_this_layer_s_problem(face: StrokeFace) -> None:
    with pytest.raises(ValueError, match="one line"):
        shape_run("TOP\nBOTTOM", face, TextStyle(cap_height=3.0))


def test_moved_shifts_everything_and_keeps_the_width(face: StrokeFace) -> None:
    run = shape_run("HI", face, TextStyle(cap_height=7.0))
    moved = run.moved(Point(10.0, 20.0))
    assert moved.placed[0].origin == Point(10.0, 20.0)
    assert moved.width == run.width
    box = moved.ink_bounds()
    assert box is not None
    assert box.min_y == pytest.approx(20.0)


def test_slant_leans_the_marks_without_moving_the_origins(face: StrokeFace) -> None:
    upright = shape_run("HH", face, TextStyle(cap_height=7.0))
    leaning = shape_run("HH", face, TextStyle(cap_height=7.0, slant=15.0))
    assert leaning.width == pytest.approx(upright.width)
    assert leaning.placed[1].origin.x == pytest.approx(upright.placed[1].origin.x)
    upright_box = upright.ink_bounds()
    leaning_box = leaning.ink_bounds()
    assert upright_box is not None
    assert leaning_box is not None
    assert leaning_box.max_x > upright_box.max_x


def test_mirroring_flips_the_run_and_not_the_letters(face: StrokeFace) -> None:
    plain = shape_run("HI", face, TextStyle(cap_height=7.0))
    flipped = shape_run("HI", face, TextStyle(cap_height=7.0, mirror=True))
    assert flipped.width == pytest.approx(plain.width)
    assert flipped.placed[0].origin.x == pytest.approx(plain.width)
    assert flipped.placed[1].origin.x < flipped.placed[0].origin.x
    box = flipped.ink_bounds()
    plain_box = plain.ink_bounds()
    assert box is not None
    assert plain_box is not None
    assert box.width == pytest.approx(plain_box.width)


def test_a_mirrored_run_still_sits_on_the_span_it_was_given(face: StrokeFace) -> None:
    flipped = shape_run("HI", face, TextStyle(cap_height=7.0, mirror=True))
    box = flipped.ink_bounds()
    assert box is not None
    assert box.min_x >= -0.001
    assert box.max_x <= flipped.width + 0.001


def test_through_applies_a_transform_to_the_whole_run(face: StrokeFace) -> None:
    run = shape_run("HI", face, TextStyle(cap_height=7.0))
    turned = run.through(Transform.rotation(90.0))
    before = run.ink_bounds()
    after = turned.ink_bounds()
    assert before is not None
    assert after is not None
    assert after.width == pytest.approx(before.height)
    assert after.height == pytest.approx(before.width)
    assert turned.width == run.width


def test_str_says_the_text_the_face_and_the_width(face: StrokeFace) -> None:
    run = shape_run("HI", face, TextStyle(cap_height=7.0))
    assert str(run).startswith("'HI' in panelgothic, ")
    assert str(run).endswith("mm wide")
