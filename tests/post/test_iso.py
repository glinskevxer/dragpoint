"""ISO G code output."""

from __future__ import annotations

import pytest

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList
from dragpoint.path.plan import Toolpath, build_toolpath
from dragpoint.post.base import POSTS, PostOptions, post_names, render
from dragpoint.post.iso import render_iso


def simple_path() -> Toolpath:
    cuts = CutList.of(
        [
            Cut(
                stroke=Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)]),
                depth=0.3,
                pass_index=0,
            ),
            Cut(
                stroke=Stroke.from_pairs([(20.0, 0.0), (30.0, 0.0)]),
                depth=0.3,
                pass_index=0,
            ),
        ]
    )
    return build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, start=Point(0.0, 0.0))


def test_the_post_is_registered() -> None:
    assert "iso" in post_names()
    assert POSTS["iso"].extension == "nc"


def test_the_program_opens_and_closes_the_way_a_control_expects() -> None:
    text = render_iso(simple_path(), PostOptions())
    lines = text.splitlines()
    assert lines[0] == "%"
    assert lines[-1] == "%"
    assert "M30" in lines


def test_the_program_number_and_name_are_on_the_second_line() -> None:
    text = render_iso(simple_path(), PostOptions(program="MCC-7 P-101", number=1234))
    assert text.splitlines()[1] == "O1234 (MCC-7 P-101)"


def test_the_setup_words_are_there() -> None:
    text = render_iso(simple_path(), PostOptions())
    assert "G21 G90 G17 G40 G49" in text
    assert "T1 M06" in text


def test_the_spindle_starts_and_stops() -> None:
    text = render_iso(simple_path(), PostOptions(spindle=15000))
    assert "S15000 M03" in text
    assert "M05" in text


def test_a_spindle_of_zero_starts_nothing() -> None:
    text = render_iso(simple_path(), PostOptions(spindle=0))
    assert "M03" not in text
    assert "M05" not in text


def test_notes_come_out_as_comments() -> None:
    text = render_iso(simple_path(), PostOptions(notes=("cut after drilling",)))
    assert "(cut after drilling)" in text


def test_a_bracket_in_a_note_cannot_close_the_comment_early() -> None:
    text = render_iso(simple_path(), PostOptions(notes=("see drawing (rev B)",)))
    assert "(see drawing [rev B])" in text
    assert "(rev B)" not in text


def test_comments_can_be_turned_off() -> None:
    text = render_iso(simple_path(), PostOptions(notes=("hello",), comments=False))
    assert "hello" not in text


def test_rapids_are_g00_and_feeds_are_g01() -> None:
    text = render_iso(simple_path(), PostOptions())
    assert "G00" in text
    assert "G01" in text


def test_a_word_that_has_not_changed_is_not_repeated() -> None:
    text = render_iso(simple_path(), PostOptions())
    moves = [line for line in text.splitlines() if line.startswith(("G00", "G01", "X", "Y", "Z"))]
    along_x = [line for line in moves if "X10.0000" in line and "Y" not in line]
    assert along_x


def test_the_feed_rate_is_only_written_when_it_changes() -> None:
    lines = render_iso(simple_path(), PostOptions()).splitlines()
    # The second move of the first cut carries no feed word at all.
    assert "Y5.0000" in lines
    # It comes back once at the top of each cut, where the plunge feed
    # dropped it, and not on any of the moves in between.
    assert sum(1 for line in lines if "F1200" in line) == 2


def test_coordinates_carry_the_places_asked_for() -> None:
    text = render_iso(simple_path(), PostOptions(decimals=2))
    assert "X10.00" in text
    assert "X10.000" not in text


def test_a_negative_zero_never_reaches_the_control() -> None:
    cuts = CutList.of(
        [
            Cut(
                stroke=Stroke.from_pairs([(-0.00001, 0.0), (10.0, 0.0)]),
                depth=0.3,
                pass_index=0,
            )
        ]
    )
    path = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0)
    text = render_iso(path, PostOptions(decimals=3))
    assert "-0.000" not in text


def test_line_numbers_can_be_asked_for() -> None:
    text = render_iso(simple_path(), PostOptions(line_numbers=True))
    lines = text.splitlines()
    assert lines[0] == "%"
    assert lines[1].startswith("N10 ")
    assert lines[2].startswith("N20 ")


def test_without_line_numbers_nothing_is_numbered() -> None:
    assert "N10" not in render_iso(simple_path(), PostOptions())


def test_the_file_ends_with_a_newline() -> None:
    assert render_iso(simple_path(), PostOptions()).endswith("\n")


def test_rendering_through_the_register_gives_the_same_text() -> None:
    options = PostOptions(program="X")
    assert render("iso", simple_path(), options) == render_iso(simple_path(), options)


def test_an_unknown_post_lists_the_ones_there_are() -> None:
    with pytest.raises(KeyError) as caught:
        render("nosuchpost", simple_path())
    assert "iso" in str(caught.value)


def test_an_empty_toolpath_still_makes_a_valid_program() -> None:
    text = render_iso(Toolpath(), PostOptions())
    assert text.splitlines()[0] == "%"
    assert "M30" in text


def test_every_z_the_toolpath_reaches_appears_in_the_program() -> None:
    path = simple_path()
    text = render_iso(path, PostOptions(decimals=3))
    assert f"Z{path.deepest():.3f}" in text
    assert f"Z{path.highest():.3f}" in text


def repeated(**overrides: object) -> str:
    values: dict[str, object] = {"repeats": 3, "pitch_x": 45.0}
    values.update(overrides)
    return render_iso(simple_path(), PostOptions(**values))  # type: ignore[arg-type]


def test_one_blank_writes_the_moves_where_they_are() -> None:
    text = render_iso(simple_path(), PostOptions())
    assert "M98" not in text
    assert "G52" not in text


def test_a_fixture_calls_a_subprogram_once_per_blank() -> None:
    assert repeated().count("M98 P1001") == 3


def test_the_moves_are_written_once_however_many_blanks_there_are() -> None:
    assert repeated().count("O1001") == 1


def test_each_call_is_shifted_onto_its_own_blank() -> None:
    text = repeated()
    assert "G52 X45.0000 Y0.0000" in text
    assert "G52 X90.0000 Y0.0000" in text


def test_the_first_blank_needs_no_shift() -> None:
    lines = repeated().splitlines()
    assert lines[lines.index("M98 P1001") - 1] == "G52 X0 Y0"


def test_the_shift_is_cancelled_before_the_program_ends() -> None:
    lines = repeated().splitlines()
    assert lines.index("G52 X0 Y0", lines.index("G52 X90.0000 Y0.0000")) < lines.index("M30")


def test_the_subprogram_returns_rather_than_ending_the_program() -> None:
    assert repeated().rstrip().splitlines()[-2] == "M99"


def test_the_file_ends_after_the_subprogram() -> None:
    assert repeated().rstrip().endswith("%")


def test_the_subprogram_number_follows_the_program_number() -> None:
    assert "O2001" in repeated(number=2000)


def test_a_repeated_program_still_stops_the_spindle() -> None:
    assert "M05" in repeated()


def test_line_numbers_run_through_the_subprogram_as_well() -> None:
    text = repeated(line_numbers=True)
    assert "N10 " in text
    assert text.count("N") > 20
