"""Breaking a legend into lines."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.font.face import StrokeFace
from dragpoint.font.library import shipped_face
from dragpoint.text.fit import measure_lines
from dragpoint.text.style import TextStyle
from dragpoint.text.wrap import longest_word, wrap_lines, wrap_to_box


@pytest.fixture
def face() -> StrokeFace:
    return shipped_face("panelgothic")


@pytest.fixture
def style() -> TextStyle:
    return TextStyle(cap_height=3.0)


def test_a_short_legend_stays_on_one_line(face: StrokeFace, style: TextStyle) -> None:
    assert wrap_lines("PUMP 2 RUN", face, style, 100.0) == ["PUMP 2 RUN"]


def test_a_long_legend_is_broken(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("ISOLATE BEFORE WORKING ON THIS PANEL", face, style, 30.0)
    assert len(lines) > 1
    assert " ".join(lines).split() == "ISOLATE BEFORE WORKING ON THIS PANEL".split()


def test_no_line_is_wider_than_the_limit(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("ISOLATE BEFORE WORKING ON THIS PANEL", face, style, 30.0)
    for line in lines:
        assert measure_lines([line], face, style) <= 30.0


def test_the_break_is_greedy_and_fills_each_line(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("ISOLATE BEFORE WORKING ON THIS PANEL", face, style, 30.0)
    for index, line in enumerate(lines[:-1]):
        next_word = lines[index + 1].split()[0]
        assert measure_lines([f"{line} {next_word}"], face, style) > 30.0


def test_no_word_is_ever_split(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("EMERGENCY STOP PUSHBUTTON", face, style, 5.0)
    assert lines == ["EMERGENCY", "STOP", "PUSHBUTTON"]


def test_a_word_too_long_for_a_line_is_left_alone(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("PUSHBUTTON", face, style, 2.0)
    assert lines == ["PUSHBUTTON"]
    assert measure_lines(lines, face, style) > 2.0


def test_runs_of_spaces_come_out_as_single_ones(face: StrokeFace, style: TextStyle) -> None:
    assert wrap_lines("PUMP    2", face, style, 100.0) == ["PUMP 2"]


def test_an_empty_legend_is_one_empty_line(face: StrokeFace, style: TextStyle) -> None:
    assert wrap_lines("", face, style, 50.0) == [""]
    assert wrap_lines("   ", face, style, 50.0) == [""]


def test_a_line_limit_stops_the_breaking(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("ISOLATE BEFORE WORKING ON THIS PANEL", face, style, 30.0, max_lines=2)
    assert len(lines) == 2
    assert lines[1].endswith("PANEL")


def test_a_line_limit_of_one_keeps_everything_on_it(face: StrokeFace, style: TextStyle) -> None:
    assert wrap_lines("ONE TWO THREE", face, style, 5.0, max_lines=1) == ["ONE TWO THREE"]


def test_the_last_line_is_allowed_to_be_too_wide(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_lines("ISOLATE BEFORE WORKING ON THIS PANEL", face, style, 20.0, max_lines=2)
    assert measure_lines([lines[-1]], face, style) > 20.0


@pytest.mark.parametrize("limit", [0.0, -1.0])
def test_a_limit_that_is_not_a_width_is_refused(
    face: StrokeFace, style: TextStyle, limit: float
) -> None:
    with pytest.raises(OutOfRange, match="width limit"):
        wrap_lines("A B", face, style, limit)


def test_a_line_count_below_one_is_refused(face: StrokeFace, style: TextStyle) -> None:
    with pytest.raises(OutOfRange, match="max lines"):
        wrap_lines("A B", face, style, 50.0, max_lines=0)


def test_a_taller_box_takes_more_lines(face: StrokeFace, style: TextStyle) -> None:
    words = "ISOLATE BEFORE WORKING ON THIS PANEL"
    short = wrap_to_box(words, face, style, 25.0, 6.0)
    tall = wrap_to_box(words, face, style, 25.0, 30.0)
    assert len(tall) > len(short)


def test_a_box_with_room_for_one_line_gets_one(face: StrokeFace, style: TextStyle) -> None:
    lines = wrap_to_box("ISOLATE BEFORE WORKING", face, style, 25.0, 3.0)
    assert len(lines) == 1


def test_the_room_comes_from_the_line_pitch(face: StrokeFace, style: TextStyle) -> None:
    pitch = style.resolved_line_pitch(face)
    lines = wrap_to_box("ONE TWO THREE FOUR FIVE SIX", face, style, 8.0, pitch * 3.0)
    assert len(lines) <= 3


def test_a_box_with_no_height_is_refused(face: StrokeFace, style: TextStyle) -> None:
    with pytest.raises(OutOfRange, match="height"):
        wrap_to_box("A B", face, style, 25.0, 0.0)


def test_the_longest_word_is_the_narrowest_a_wrap_can_get(
    face: StrokeFace, style: TextStyle
) -> None:
    words = "EMERGENCY STOP PUSHBUTTON"
    narrowest = longest_word(words, face, style)
    assert narrowest == pytest.approx(measure_lines(["PUSHBUTTON"], face, style))
    lines = wrap_lines(words, face, style, narrowest)
    assert max(measure_lines([line], face, style) for line in lines) <= narrowest + 1e-9


def test_an_empty_legend_has_no_longest_word(face: StrokeFace, style: TextStyle) -> None:
    assert longest_word("", face, style) == 0.0
