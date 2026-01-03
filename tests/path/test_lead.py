"""Descending into the work along the line instead of straight down it."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.lead import ramp_entry, ramped_remainder

LINE = Stroke((Point(0.0, 0.0), Point(10.0, 0.0)))
BENT = Stroke((Point(0.0, 0.0), Point(4.0, 0.0), Point(4.0, 6.0)))


def test_no_ramp_is_a_single_plunge_at_full_depth() -> None:
    assert ramp_entry(LINE, 0.4, 0.0) == [(Point(0.0, 0.0), 0.4)]


def test_a_ramp_starts_at_the_start_of_the_stroke_and_at_nothing() -> None:
    entry = ramp_entry(LINE, 0.4, 2.0)
    assert entry[0] == (Point(0.0, 0.0), 0.0)


def test_a_ramp_reaches_full_depth_at_the_end_of_the_ramp() -> None:
    entry = ramp_entry(LINE, 0.4, 2.5)
    assert entry[-1][0] == Point(2.5, 0.0)
    assert entry[-1][1] == pytest.approx(0.4)


def test_the_ramp_never_goes_deeper_than_it_was_asked_for() -> None:
    for _, depth in ramp_entry(BENT, 0.5, 8.0):
        assert depth <= 0.5 + 1e-9


def test_the_ramp_gets_deeper_the_further_along_it_goes() -> None:
    depths = [depth for _, depth in ramp_entry(BENT, 0.5, 8.0)]
    assert depths == sorted(depths)


def test_a_ramp_over_a_corner_puts_a_step_on_the_corner() -> None:
    entry = ramp_entry(BENT, 0.6, 6.0)
    assert Point(4.0, 0.0) in [point for point, _ in entry]


def test_a_ramp_longer_than_the_stroke_uses_the_whole_stroke() -> None:
    entry = ramp_entry(LINE, 0.4, 50.0)
    assert entry[-1] == (Point(10.0, 0.0), 0.4)


def test_a_ramp_that_is_all_but_nothing_is_a_plunge() -> None:
    assert len(ramp_entry(LINE, 0.4, 1e-9)) == 1


def test_no_depth_is_refused_because_there_is_nothing_to_ramp_into() -> None:
    with pytest.raises(OutOfRange, match="depth"):
        ramp_entry(LINE, 0.0, 2.0)


def test_a_ramp_backwards_is_refused() -> None:
    with pytest.raises(OutOfRange, match="ramp"):
        ramp_entry(LINE, 0.4, -1.0)


def test_the_remainder_of_no_ramp_is_the_whole_stroke() -> None:
    assert ramped_remainder(LINE, 0.0) == LINE


def test_the_remainder_starts_where_the_ramp_finished() -> None:
    left = ramped_remainder(LINE, 2.5)
    assert left is not None
    assert left.start == Point(2.5, 0.0)
    assert left.end == Point(10.0, 0.0)


def test_the_remainder_keeps_the_corners_past_the_ramp() -> None:
    left = ramped_remainder(BENT, 2.0)
    assert left is not None
    assert left.points == (Point(2.0, 0.0), Point(4.0, 0.0), Point(4.0, 6.0))


def test_a_ramp_as_long_as_the_stroke_leaves_nothing() -> None:
    assert ramped_remainder(LINE, 10.0) is None


def test_the_ramp_and_the_remainder_add_back_up_to_the_stroke() -> None:
    entry = ramp_entry(BENT, 0.5, 3.0)
    left = ramped_remainder(BENT, 3.0)
    assert left is not None
    assert entry[-1][0] == left.start
    walked = sum(
        first.distance_to(second)
        for first, second in zip(
            [point for point, _ in entry], [point for point, _ in entry][1:], strict=False
        )
    )
    assert walked + left.length() == pytest.approx(BENT.length())
