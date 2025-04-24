"""Depth passes: an even split, and who gets to veto a depth."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.tool.cutter import Cutter, catalogue_cutter
from dragpoint.tool.material import material
from dragpoint.tool.passes import PassPlan, plan_passes


def vee() -> Cutter:
    return catalogue_cutter("V30-015")


def test_a_shallow_cut_is_one_pass() -> None:
    plan = plan_passes(0.25, material("LAM16-BW"), vee())
    assert len(plan) == 1
    assert plan.final_depth == pytest.approx(0.25)
    assert plan.cutting_passes == 1


def test_a_deep_cut_is_split_evenly() -> None:
    plan = plan_passes(0.9, material("LAM32-RW"), vee())
    assert len(plan) == 3
    assert plan.step_of(0) == pytest.approx(0.3)
    assert plan.step_of(1) == pytest.approx(0.3)
    assert plan.step_of(2) == pytest.approx(0.3)


def test_the_split_never_leaves_a_rubbing_last_pass() -> None:
    plan = plan_passes(0.72, material("LAM32-RW"), vee())
    steps = [plan.step_of(index) for index in range(len(plan))]
    assert min(steps) == pytest.approx(max(steps))


def test_no_pass_goes_deeper_than_the_stock_allows() -> None:
    stock = material("LAM32-RW")
    plan = plan_passes(1.2, stock, vee())
    for index in range(len(plan)):
        assert plan.step_of(index) <= stock.max_depth_per_pass + 1e-9


def test_the_depths_are_cumulative_from_the_surface() -> None:
    plan = plan_passes(0.9, material("LAM32-RW"), vee())
    assert list(plan) == pytest.approx([0.3, 0.6, 0.9])


def test_the_groove_width_is_the_one_at_the_finished_depth() -> None:
    cutter = vee()
    plan = plan_passes(0.4, material("LAM32-RW"), cutter)
    assert plan.groove_width == pytest.approx(cutter.width_at_depth(0.4))


def test_a_spring_pass_repeats_the_final_depth() -> None:
    plan = plan_passes(0.25, material("LAM16-BW"), vee(), spring_pass=True)
    assert len(plan) == 2
    assert plan.cutting_passes == 1
    assert plan.depths[0] == pytest.approx(plan.depths[1])
    assert plan.has_spring_pass


def test_a_spring_pass_removes_nothing_extra() -> None:
    plain = plan_passes(0.4, material("LAM32-RW"), vee())
    sprung = plan_passes(0.4, material("LAM32-RW"), vee(), spring_pass=True)
    assert sprung.final_depth == pytest.approx(plain.final_depth)
    assert len(sprung) == len(plain) + 1


def test_a_depth_the_sheet_will_not_take_is_refused() -> None:
    with pytest.raises(OutOfRange, match="LAM16-BW"):
        plan_passes(0.10, material("LAM16-BW"), vee())


def test_a_depth_deeper_than_the_cutter_reaches_names_the_cutter() -> None:
    stubby = Cutter(name="stub", tip_width=0.3, included_angle=30.0, max_depth=0.2)
    with pytest.raises(OutOfRange, match="stub"):
        plan_passes(0.5, material("LAM32-RW"), stubby)


def test_a_plan_needs_at_least_one_pass() -> None:
    with pytest.raises(ValueError, match="at least one pass"):
        PassPlan(depths=(), groove_width=0.4)


def test_a_pass_that_cuts_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="cuts nothing"):
        PassPlan(depths=(0.0,), groove_width=0.4)


def test_passes_may_not_back_up() -> None:
    with pytest.raises(ValueError, match="never back up"):
        PassPlan(depths=(0.4, 0.2), groove_width=0.4)


def test_a_repeated_depth_is_allowed_because_that_is_a_spring_pass() -> None:
    plan = PassPlan(depths=(0.4, 0.4), groove_width=0.4, has_spring_pass=True)
    assert plan.cutting_passes == 1


def test_stainless_takes_far_more_passes_than_laminate() -> None:
    steel = plan_passes(0.08, material("STAIN-10"), vee())
    plastic = plan_passes(0.25, material("LAM16-BW"), vee())
    assert len(steel) > len(plastic)


def test_str_reads_like_a_line_on_a_setup_sheet() -> None:
    plan = plan_passes(0.9, material("LAM32-RW"), vee())
    assert str(plan).startswith("3 passes to 0.900mm, groove ")
    sprung = plan_passes(0.9, material("LAM32-RW"), vee(), spring_pass=True)
    assert "plus a spring pass" in str(sprung)
