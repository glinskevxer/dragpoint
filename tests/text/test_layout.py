"""Stacking and aligning lines inside a box."""

from __future__ import annotations

import pytest

from dragpoint.font.face import StrokeFace
from dragpoint.font.library import shipped_face
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.text.layout import HAlign, VAlign, layout_lines, visual_width
from dragpoint.text.shape import shape_run
from dragpoint.text.style import TextStyle


@pytest.fixture
def face() -> StrokeFace:
    return shipped_face("panelgothic")


@pytest.fixture
def style() -> TextStyle:
    return TextStyle(cap_height=3.5)


def plate() -> Box:
    return Box(0.0, 0.0, 50.0, 20.0)


def test_visual_width_takes_the_trailing_track_off(face: StrokeFace) -> None:
    tracked = shape_run("HH", face, TextStyle(cap_height=7.0, tracking=0.5))
    assert tracked.width == pytest.approx(13.8)
    assert visual_width(tracked) == pytest.approx(13.3)


def test_visual_width_of_an_empty_run_is_zero(face: StrokeFace) -> None:
    assert visual_width(shape_run("", face, TextStyle(cap_height=7.0, tracking=0.5))) == 0.0


def test_visual_width_never_goes_negative(face: StrokeFace) -> None:
    tight = shape_run("H", face, TextStyle(cap_height=1.0, tracking=-0.9))
    assert visual_width(tight) >= 0.0


def test_with_no_box_the_first_baseline_is_the_origin(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["TOP", "BOTTOM"], face, style)
    assert block.box is None
    assert block.lines[0].placed[0].origin == Point(0.0, 0.0)
    assert block.lines[1].placed[0].origin.y == pytest.approx(-block.line_pitch)


def test_left_alignment_starts_every_line_at_the_left_edge(
    face: StrokeFace, style: TextStyle
) -> None:
    block = layout_lines(["A", "LONGER"], face, style, box=plate(), halign=HAlign.LEFT)
    assert block.lines[0].placed[0].origin.x == 0.0
    assert block.lines[1].placed[0].origin.x == 0.0


def test_right_alignment_ends_every_line_at_the_right_edge(
    face: StrokeFace, style: TextStyle
) -> None:
    block = layout_lines(["A", "LONGER"], face, style, box=plate(), halign=HAlign.RIGHT)
    for line in block.lines:
        assert line.placed[0].origin.x + visual_width(line) == pytest.approx(50.0)


def test_centre_alignment_leaves_equal_slack(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["VALVE"], face, style, box=plate(), halign=HAlign.CENTRE)
    line = block.lines[0]
    left = line.placed[0].origin.x
    right = 50.0 - (left + visual_width(line))
    assert left == pytest.approx(right)


def test_centring_ignores_the_trailing_track(face: StrokeFace) -> None:
    tracked = TextStyle(cap_height=3.5, tracking=0.4)
    block = layout_lines(["RUN"], face, tracked, box=plate(), halign=HAlign.CENTRE)
    line = block.lines[0]
    left = line.placed[0].origin.x
    right = 50.0 - (left + visual_width(line))
    assert left == pytest.approx(right)


def test_top_alignment_puts_the_ascender_on_the_top_edge(
    face: StrokeFace, style: TextStyle
) -> None:
    block = layout_lines(["HI"], face, style, box=plate(), valign=VAlign.TOP)
    scale = face.scale_for_cap_height(3.5)
    assert block.lines[0].placed[0].origin.y == pytest.approx(20.0 - 750 * scale)


def test_baseline_alignment_puts_the_first_baseline_on_the_top_edge(
    face: StrokeFace, style: TextStyle
) -> None:
    block = layout_lines(["HI"], face, style, box=plate(), valign=VAlign.BASELINE)
    assert block.lines[0].placed[0].origin.y == pytest.approx(20.0)


def test_bottom_alignment_puts_the_descender_on_the_bottom_edge(
    face: StrokeFace, style: TextStyle
) -> None:
    block = layout_lines(["HI", "LO"], face, style, box=plate(), valign=VAlign.BOTTOM)
    scale = face.scale_for_cap_height(3.5)
    last = block.lines[-1].placed[0].origin.y
    assert last == pytest.approx(0.0 - (-200) * scale)


def test_middle_alignment_leaves_equal_slack_above_and_below(
    face: StrokeFace, style: TextStyle
) -> None:
    block = layout_lines(["HI", "LO"], face, style, box=plate(), valign=VAlign.MIDDLE)
    scale = face.scale_for_cap_height(3.5)
    top = block.lines[0].placed[0].origin.y + 750 * scale
    bottom = block.lines[-1].placed[0].origin.y + (-200) * scale
    assert 20.0 - top == pytest.approx(bottom - 0.0)


def test_lines_are_stacked_downwards_at_the_pitch(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["ONE", "TWO", "THREE"], face, style, box=plate())
    baselines = [line.placed[0].origin.y for line in block.lines]
    assert baselines[0] - baselines[1] == pytest.approx(block.line_pitch)
    assert baselines[1] - baselines[2] == pytest.approx(block.line_pitch)


def test_the_style_can_overrule_the_line_pitch(face: StrokeFace) -> None:
    block = layout_lines(["A", "B"], face, TextStyle(cap_height=3.5, line_pitch=6.0), box=plate())
    assert block.line_pitch == 6.0


def test_a_blank_line_still_takes_a_line(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["TOP", "", "BOTTOM"], face, style, box=plate())
    assert len(block) == 3
    first = block.lines[0].placed[0].origin.y
    last = block.lines[2].placed[0].origin.y
    assert first - last == pytest.approx(2 * block.line_pitch)


def test_a_blank_line_contributes_no_strokes(face: StrokeFace, style: TextStyle) -> None:
    with_blank = layout_lines(["TOP", "", "BOT"], face, style, box=plate())
    without = layout_lines(["TOP", "BOT"], face, style, box=plate())
    assert len(with_blank.strokes()) == len(without.strokes())


def test_the_widest_line_is_the_one_alignment_uses(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["I", "MMM"], face, style, box=plate())
    assert block.widest == pytest.approx(visual_width(block.lines[1]))


def test_ink_bounds_covers_every_line(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["TOP", "BOTTOM"], face, style, box=plate())
    box = block.ink_bounds()
    assert box is not None
    assert box.height > 3.5


def test_a_block_of_only_blank_lines_has_no_ink(face: StrokeFace, style: TextStyle) -> None:
    assert layout_lines(["", "  "], face, style, box=plate()).ink_bounds() is None


def test_moved_shifts_the_lines_and_the_box(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["HI"], face, style, box=plate()).moved(Point(5.0, 5.0))
    assert block.box == Box(5.0, 5.0, 55.0, 25.0)
    assert block.lines[0].placed[0].origin.x == pytest.approx(5.0)


def test_moving_a_boxless_block_leaves_it_boxless(face: StrokeFace, style: TextStyle) -> None:
    assert layout_lines(["HI"], face, style).moved(Point(5.0, 5.0)).box is None


def test_empty_input_lays_out_to_nothing(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines([], face, style, box=plate())
    assert len(block) == 0
    assert block.widest == 0.0
    assert block.ink_bounds() is None
    assert block.strokes() == ()


def test_str_says_how_many_lines(face: StrokeFace, style: TextStyle) -> None:
    block = layout_lines(["A", "B"], face, style, box=plate())
    assert str(block).startswith("2 lines, widest ")
