"""The laser marker post, which has no cutter and therefore no depth."""

from __future__ import annotations

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList
from dragpoint.path.plan import Toolpath, build_toolpath
from dragpoint.post.base import POSTS, PostOptions, post_names, render
from dragpoint.post.marker import DEFAULT_POWER, DEFAULT_SPEED, render_marker


def path_of(cuts: CutList) -> Toolpath:
    return build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, start=Point(0.0, 0.0))


def two_runs(passes: int = 1) -> CutList:
    return CutList.of(
        [
            Cut(
                stroke=Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)]),
                depth=0.05,
                pass_index=index,
            )
            for index in range(passes)
        ]
        + [
            Cut(
                stroke=Stroke.from_pairs([(20.0, 0.0), (30.0, 0.0)]),
                depth=0.05,
                pass_index=index,
            )
            for index in range(passes)
        ]
    )


def marked(cuts: CutList | None = None, **options: object) -> str:
    return render_marker(path_of(cuts or two_runs()), PostOptions(**options))  # type: ignore[arg-type]


def test_the_post_is_registered_with_its_own_extension() -> None:
    assert "marker" in post_names()
    assert POSTS["marker"].extension == "lmk"


def test_the_file_opens_with_the_job_name_and_the_settings() -> None:
    lines = marked(program="TAG-1").splitlines()
    assert lines[1] == "NAME TAG-1"
    assert f"POWER {DEFAULT_POWER}" in lines
    assert f"SPEED {DEFAULT_SPEED}" in lines


def test_the_file_ends_with_the_end_block() -> None:
    assert marked().rstrip().endswith("END")


def test_one_line_block_per_run() -> None:
    assert marked().count("LINE ") == 2


def test_a_line_carries_the_points_it_marks() -> None:
    text = marked()
    assert "LINE 0.0000,0.0000 10.0000,0.0000 10.0000,5.0000" in text


def test_there_is_no_z_anywhere_in_the_file() -> None:
    assert "Z" not in marked()


def test_positioning_moves_do_not_appear_at_all() -> None:
    text = marked()
    assert "20.0000,0.0000 30.0000,0.0000" in text
    assert text.count("LINE ") == 2


def test_a_plate_cut_in_three_passes_is_marked_three_times() -> None:
    assert marked(two_runs(passes=3)).count("LINE ") == 6


def test_notes_come_out_as_comments() -> None:
    assert "; 304 stainless" in marked(notes=("304 stainless",))


def test_notes_can_be_turned_off() -> None:
    assert "; 304" not in marked(notes=("304 stainless",), comments=False)


def test_a_semicolon_in_the_name_cannot_start_a_comment() -> None:
    assert "NAME TAG,1" in marked(program="TAG;1")


def test_a_fixture_writes_the_geometry_once_per_blank() -> None:
    one = marked()
    three = marked(repeats=3, pitch_x=40.0)
    assert three.count("LINE ") == 3 * one.count("LINE ")


def test_a_repeated_blank_is_written_at_its_offset() -> None:
    assert "40.0000,0.0000" in marked(repeats=2, pitch_x=40.0)


def test_the_marker_can_be_asked_for_by_name() -> None:
    assert render("marker", path_of(two_runs())).startswith("; dragpoint marker job")


def test_an_empty_toolpath_still_makes_a_job_file() -> None:
    text = render_marker(path_of(CutList()), PostOptions())
    assert "LINE" not in text
    assert text.rstrip().endswith("END")
