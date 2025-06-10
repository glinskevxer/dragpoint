"""The plotter post, which has no Z axis to write."""

from __future__ import annotations

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList
from dragpoint.path.plan import Toolpath, build_toolpath
from dragpoint.post.base import POSTS, PostOptions, post_names
from dragpoint.post.plotter import UNITS_PER_MM, first_pen_down, render_plotter


def path_of(cuts: CutList) -> Toolpath:
    return build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, start=Point(0.0, 0.0))


def two_cuts() -> CutList:
    return CutList.of(
        [
            Cut(
                stroke=Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)]),
                depth=0.25,
                pass_index=0,
            ),
            Cut(
                stroke=Stroke.from_pairs([(20.0, 0.0), (30.0, 0.0)]),
                depth=0.25,
                pass_index=0,
            ),
        ]
    )


def test_the_post_is_registered() -> None:
    assert "plotter" in post_names()
    assert POSTS["plotter"].extension == "plt"


def test_the_file_opens_with_the_initialise_and_pen_select() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    assert text.startswith("IN;\nSP1;")


def test_the_file_ends_with_the_end_command_and_a_newline() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    assert text.endswith("!END;\n")


def test_every_command_is_terminated() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    for line in text.splitlines():
        assert line.endswith(";")


def test_the_pen_number_follows_the_tool() -> None:
    assert "SP3;" in render_plotter(path_of(two_cuts()), PostOptions(tool=3))


def test_the_depth_comes_out_in_microns() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    assert "!DEP250;" in text


def test_the_depth_is_only_written_when_it_changes() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    assert text.count("!DEP") == 1


def test_a_second_depth_gets_its_own_setting() -> None:
    cuts = CutList.of(
        [
            Cut(stroke=Stroke.from_pairs([(0.0, 0.0), (5.0, 0.0)]), depth=0.2, pass_index=0),
            Cut(stroke=Stroke.from_pairs([(0.0, 0.0), (5.0, 0.0)]), depth=0.4, pass_index=1),
        ]
    )
    text = render_plotter(path_of(cuts), PostOptions())
    assert "!DEP200;" in text
    assert "!DEP400;" in text


def test_no_z_coordinate_ever_appears() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    assert "Z" not in text


def test_coordinates_are_in_plotter_units() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    assert f"PD{10 * UNITS_PER_MM},0;" in text
    assert "PU800,0;" in text


def test_coordinates_are_whole_numbers() -> None:
    cuts = CutList.of(
        [Cut(stroke=Stroke.from_pairs([(0.0, 0.0), (1.234567, 0.0)]), depth=0.25, pass_index=0)]
    )
    text = render_plotter(path_of(cuts), PostOptions())
    assert "PD49,0;" in text
    assert "." not in text.split("!DEP")[1]


def test_the_pen_goes_up_before_a_rapid_and_down_after() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions())
    commands = [line.rstrip(";") for line in text.splitlines()]
    rapid = commands.index("PU800,0")
    assert commands[rapid - 1] == "PU"
    assert commands[rapid + 1] == "PD"


def test_the_program_name_comes_out_as_a_comment() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions(program="MCC-7"))
    assert 'CO"MCC-7";' in text


def test_a_semicolon_in_a_comment_cannot_end_it() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions(notes=("stop; then go",)))
    assert 'CO"stop, then go";' in text


def test_comments_can_be_turned_off() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions(comments=False))
    assert "CO" not in text


def test_the_spindle_speed_is_a_setting_not_a_word() -> None:
    text = render_plotter(path_of(two_cuts()), PostOptions(spindle=9000))
    assert "!SPN9000;" in text
    assert "M03" not in text


def test_a_spindle_of_zero_writes_nothing() -> None:
    assert "!SPN" not in render_plotter(path_of(two_cuts()), PostOptions(spindle=0))


def test_an_empty_toolpath_still_makes_a_valid_file() -> None:
    text = render_plotter(Toolpath(), PostOptions())
    assert text.startswith("IN;")
    assert text.endswith("!END;\n")


def test_the_first_pen_down_is_findable() -> None:
    move = first_pen_down(path_of(two_cuts()))
    assert move is not None
    assert move.z == -0.25
    assert move.to == Point(0.0, 0.0)


def test_a_path_that_never_cuts_has_no_first_pen_down() -> None:
    assert first_pen_down(Toolpath()) is None
