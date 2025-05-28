"""Legibility: what the groove width does to lettering that looked fine."""

from __future__ import annotations

import pytest

from dragpoint.rules.legibility import (
    MAX_WEIGHT_RATIO,
    letter_weight,
    stroke_merge,
    stroke_self_merge,
    stroke_stub,
)
from dragpoint.rules.report import Severity

from .conftest import build_check


def test_a_normal_plate_has_no_merging_strokes() -> None:
    check = build_check(("PUMP 2", "RUN"), cutter="V30-015", depth=0.25)
    assert list(stroke_merge(check)) == []


def test_a_wide_groove_merges_the_strokes_of_a_small_legend() -> None:
    check = build_check(("PUMP 2", "RUN"), cutter="V90-030", depth=0.9, stock="LAM32-RW")
    found = list(stroke_merge(check))
    assert len(found) == 1
    assert found[0].measured is not None
    assert found[0].limit is not None
    assert found[0].measured < found[0].limit


def test_the_merge_rule_reports_once_per_plate() -> None:
    check = build_check(
        ("EMERGENCY STOP PUSHBUTTON",), cutter="V90-030", depth=0.9, stock="LAM32-RW"
    )
    assert len(list(stroke_merge(check))) == 1


def test_the_merge_rule_names_the_plate_and_a_place() -> None:
    check = build_check(("PUMP 2", "RUN"), cutter="V90-030", depth=0.9, stock="LAM32-RW")
    found = list(stroke_merge(check))[0]
    assert found.subject == "P-101"
    assert found.where is not None


def test_the_merge_limit_is_the_groove_and_not_half_of_it() -> None:
    check = build_check(("PUMP 2", "RUN"), cutter="V90-030", depth=0.9, stock="LAM32-RW")
    found = list(stroke_merge(check))[0]
    assert found.limit == pytest.approx(check.groove_width)


def test_a_blank_plate_merges_nothing() -> None:
    check = build_check(lines=())
    assert list(stroke_merge(check)) == []
    assert list(stroke_self_merge(check)) == []
    assert list(stroke_stub(check)) == []


def test_one_stroke_on_its_own_cannot_merge_with_anything() -> None:
    check = build_check(("I",), cutter="V90-030", depth=0.9, stock="LAM32-RW")
    assert list(stroke_merge(check)) == []


def test_the_counter_of_a_letter_closes_at_a_wide_enough_groove() -> None:
    tight = build_check(("O",), cutter="V30-015", depth=0.25)
    wide = build_check(("O",), cutter="V90-030", depth=1.0, stock="LAM32-RW")
    assert list(stroke_self_merge(tight)) == []
    assert list(stroke_self_merge(wide)) != []


def test_a_letter_that_meets_itself_is_left_alone() -> None:
    # The eight is drawn as one run through its own waist. Everything near
    # that junction is close for the reason the junction is there.
    assert (
        list(stroke_self_merge(build_check(("8",), cutter="V90-030", depth=1.0, stock="LAM32-RW")))
        == []
    )


def test_the_self_merge_rule_reports_the_stroke_it_found() -> None:
    wide = build_check(("O",), cutter="V90-030", depth=1.0, stock="LAM32-RW")
    found = list(stroke_self_merge(wide))[0]
    assert found.where is not None
    assert found.measured is not None
    assert found.measured < wide.groove_width


def test_a_straight_letter_never_closes_on_itself() -> None:
    check = build_check(("I",), cutter="V90-030", depth=1.0, stock="LAM32-RW")
    assert list(stroke_self_merge(check)) == []


def test_a_full_stop_is_a_stub_and_says_so() -> None:
    check = build_check(("A.",), cutter="V60-020", depth=0.4, stock="LAM32-RW")
    found = list(stroke_stub(check))
    assert len(found) == 1
    assert found[0].severity is Severity.WARNING


def test_nothing_is_a_stub_with_a_fine_cutter() -> None:
    check = build_check(("A.",), cutter="V10-005", depth=0.25)
    assert list(stroke_stub(check)) == []


def test_the_stub_limit_is_the_groove_width() -> None:
    check = build_check(("A.",), cutter="V60-020", depth=0.4, stock="LAM32-RW")
    found = list(stroke_stub(check))[0]
    assert found.limit == pytest.approx(check.groove_width)


def test_normal_lettering_is_not_too_heavy() -> None:
    check = build_check(("RUN",), cutter="V30-015", depth=0.25)
    assert list(letter_weight(check)) == []


def test_a_wide_groove_on_small_lettering_is_too_heavy() -> None:
    check = build_check(("RUN",), cutter="V90-030", depth=0.9, stock="LAM32-RW", cap_height=2.0)
    found = list(letter_weight(check))
    assert len(found) == 1
    assert found[0].limit == pytest.approx(2.0 * MAX_WEIGHT_RATIO)


def test_the_same_groove_on_bigger_lettering_is_fine() -> None:
    check = build_check(("RUN",), cutter="V90-030", depth=0.9, stock="LAM32-RW", cap_height=12.0)
    assert list(letter_weight(check)) == []


def test_weight_is_measured_against_the_height_the_fitter_settled_on() -> None:
    check = build_check(
        ("EMERGENCY STOP PUSHBUTTON",),
        cutter="V60-020",
        depth=0.4,
        stock="LAM32-RW",
        cap_height=6.0,
        fit="shrink",
    )
    assert check.style.cap_height < 6.0
    found = list(letter_weight(check))
    if found:
        assert found[0].limit == pytest.approx(check.style.cap_height * MAX_WEIGHT_RATIO)
