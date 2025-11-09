"""Process rules: can the machine do what the plate asks for."""

from __future__ import annotations

import pytest

from dragpoint.rules.check import PlateCheck
from dragpoint.rules.process import (
    MAX_SENSIBLE_PASSES,
    cutter_reach,
    depth_window,
    odd_lettering_height,
    parallel_cutter_buried,
    pass_count,
)
from dragpoint.rules.report import Severity
from dragpoint.tool.cutter import Cutter
from dragpoint.tool.passes import plan_passes

from .conftest import build_check


def at_depth(check: PlateCheck, depth: float) -> PlateCheck:
    """The same plate cut at a depth its constructors would have refused.

    The rules have to report what a constructor would have raised on,
    because a report carries every other fault alongside it and an
    exception carries one.
    """
    return PlateCheck(
        plate=check.plate,
        lines=check.lines,
        face=check.face,
        style=check.style,
        fit=check.fit,
        text=check.text,
        strokes=check.strokes,
        text_strokes=check.text_strokes,
        cutter=check.cutter,
        stock=check.stock,
        depth=depth,
        passes=check.passes,
    )


def test_the_nominal_depth_is_inside_the_window() -> None:
    assert list(depth_window(build_check(("RUN",)))) == []


def test_a_cut_that_will_not_break_the_cap_is_reported() -> None:
    found = list(depth_window(at_depth(build_check(("RUN",)), 0.05)))
    assert len(found) == 1
    assert "will not break through" in found[0].message
    assert found[0].measured == 0.05


def test_a_cut_through_the_backing_is_reported() -> None:
    found = list(depth_window(at_depth(build_check(("RUN",)), 1.5)))
    assert len(found) == 1
    assert "cut through the backing" in found[0].message


def test_solid_stock_has_no_shallow_limit() -> None:
    check = build_check(("RUN",), stock="ACRYL-30", depth=0.5)
    assert list(depth_window(at_depth(check, 0.01))) == []


def test_a_cutter_that_reaches_is_not_reported() -> None:
    assert list(cutter_reach(build_check(("RUN",)))) == []


def test_a_cutter_that_does_not_reach_names_itself() -> None:
    check = build_check(("RUN",), stock="LAM32-RW", depth=1.0)
    stubby = Cutter(name="stub", tip_width=0.3, included_angle=30.0, max_depth=0.4)
    check = PlateCheck(
        plate=check.plate,
        lines=check.lines,
        face=check.face,
        style=check.style,
        fit=check.fit,
        text=check.text,
        strokes=check.strokes,
        text_strokes=check.text_strokes,
        cutter=stubby,
        stock=check.stock,
        depth=1.0,
        passes=check.passes,
    )
    found = list(cutter_reach(check))
    assert len(found) == 1
    assert "stub" in found[0].message
    assert found[0].limit == 0.4


def test_a_normal_cut_does_not_warn_about_passes() -> None:
    assert list(pass_count(build_check(("RUN",)))) == []


def test_a_cut_needing_many_passes_warns() -> None:
    check = build_check(("RUN",), stock="STAIN-10", depth=0.08)
    deep = PlateCheck(
        plate=check.plate,
        lines=check.lines,
        face=check.face,
        style=check.style,
        fit=check.fit,
        text=check.text,
        strokes=check.strokes,
        text_strokes=check.text_strokes,
        cutter=check.cutter,
        stock=check.stock,
        depth=0.4,
        passes=plan_passes(0.4, check.stock, check.cutter),
    )
    found = list(pass_count(deep))
    assert len(found) == 1
    assert found[0].severity is Severity.WARNING
    assert found[0].measured is not None
    assert found[0].measured > MAX_SENSIBLE_PASSES


def test_a_spring_pass_is_not_counted_against_the_limit() -> None:
    check = build_check(("RUN",), stock="LAM32-RW", depth=0.4)
    sprung = PlateCheck(
        plate=check.plate,
        lines=check.lines,
        face=check.face,
        style=check.style,
        fit=check.fit,
        text=check.text,
        strokes=check.strokes,
        text_strokes=check.text_strokes,
        cutter=check.cutter,
        stock=check.stock,
        depth=0.4,
        passes=plan_passes(0.4, check.stock, check.cutter, spring_pass=True),
    )
    assert list(pass_count(sprung)) == []


def test_a_vee_cutter_is_never_reported_as_buried() -> None:
    check = build_check(("RUN",), stock="LAM32-RW", depth=1.0, cutter="V30-015")
    assert list(parallel_cutter_buried(check)) == []


def test_a_parallel_cutter_inside_its_own_width_is_fine() -> None:
    check = build_check(("RUN",), stock="LAM32-RW", depth=0.4, cutter="P-020")
    assert list(parallel_cutter_buried(check)) == []


def test_a_parallel_cutter_deeper_than_it_is_wide_warns() -> None:
    check = build_check(("RUN",), stock="LAM32-RW", depth=0.6, cutter="P-020")
    found = list(parallel_cutter_buried(check))
    assert len(found) == 1
    assert found[0].limit == pytest.approx(0.508)


def test_a_listed_lettering_height_is_not_remarked_on() -> None:
    assert list(odd_lettering_height(build_check(("RUN",), cap_height=3.0))) == []


def test_an_odd_lettering_height_names_the_nearest_listed_one() -> None:
    found = list(odd_lettering_height(build_check(("RUN",), cap_height=2.7)))
    assert len(found) == 1
    assert found[0].severity is Severity.NOTE
    assert found[0].limit == 2.5


def test_the_height_looked_at_is_the_one_after_fitting() -> None:
    check = build_check(("EMERGENCY STOP PUSHBUTTON",), cap_height=6.0, fit="shrink")
    assert check.style.cap_height != 6.0
    assert list(odd_lettering_height(check)) == []
