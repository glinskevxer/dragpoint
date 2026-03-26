"""Milling the windows out, tabs and all."""

from __future__ import annotations

import pytest

from dragpoint.compiler.cutout import (
    BREAKTHROUGH,
    DEFAULT_TAB_WIDTH,
    cutout_plate,
    cuttable,
    offcut_area,
    window_boxes,
    window_path,
)
from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature, FeatureKind
from dragpoint.spec.plate import PlateSpec
from dragpoint.tool.cutter import catalogue_cutter
from dragpoint.tool.material import material

WINDOW = Feature.rectangle("meter", Point(60.0, 30.0), 40.0, 20.0)


def spec(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-1",
        "width": 120.0,
        "height": 60.0,
        "stock": "LAM32-RW",
        "lines": ("METER",),
        "features": (WINDOW,),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def test_a_rectangular_cutout_gets_milled() -> None:
    assert len(cuttable(spec())) == 1


def test_a_hole_is_not_milled_because_it_is_drilled() -> None:
    hole = Feature.round_hole("fix", Point(10.0, 10.0), 4.2)
    assert cuttable(spec(features=(WINDOW, hole))) == (WINDOW,)


def test_a_keepout_is_not_milled_because_it_is_not_a_thing() -> None:
    keepout = Feature.rectangle("clamp", Point(10.0, 10.0), 8.0, 8.0, kind=FeatureKind.KEEPOUT)
    assert cuttable(spec(features=(WINDOW, keepout))) == (WINDOW,)


def test_the_path_is_inset_by_the_cutter_radius() -> None:
    path = window_path(WINDOW, 0.25)
    box = path.bounds()
    assert box.width == pytest.approx(40.0 - 0.5)
    assert box.height == pytest.approx(20.0 - 0.5)


def test_the_path_starts_and_ends_at_the_middle_of_the_bottom_edge() -> None:
    path = window_path(WINDOW, 0.25)
    assert path.start == path.end
    assert path.start.x == pytest.approx(60.0)
    assert path.start.y == pytest.approx(20.25)


def test_a_window_narrower_than_the_cutter_is_refused() -> None:
    tiny = Feature.rectangle("slot", Point(60.0, 30.0), 0.4, 20.0)
    with pytest.raises(OutOfRange, match="window"):
        window_path(tiny, 0.5)


def test_the_cut_goes_through_the_sheet_and_a_bit_past() -> None:
    plan = cutout_plate(spec())
    assert plan.depth == pytest.approx(material("LAM32-RW").thickness + BREAKTHROUGH)


def test_the_depth_is_reached_in_passes_the_stock_allows() -> None:
    plan = cutout_plate(spec())
    sheet = material("LAM32-RW")
    assert plan.passes * sheet.max_depth_per_pass >= plan.depth - 1e-9
    assert (plan.passes - 1) * sheet.max_depth_per_pass < plan.depth


def test_no_pass_cuts_deeper_than_the_stock_allows() -> None:
    plan = cutout_plate(spec())
    sheet = material("LAM32-RW")
    depths = sorted({cut.depth for cut in plan.cuts})
    steps = [second - first for first, second in zip(depths, depths[1:], strict=False)]
    assert all(step <= sheet.max_depth_per_pass + 1e-9 for step in steps)


def test_every_pass_but_the_last_goes_right_round_in_one() -> None:
    plan = cutout_plate(spec())
    for index in range(plan.passes - 1):
        assert len([cut for cut in plan.cuts if cut.pass_index == index]) == 1


def test_the_last_pass_is_broken_into_four_runs_by_four_tabs() -> None:
    plan = cutout_plate(spec())
    last = [cut for cut in plan.cuts if cut.pass_index == plan.passes - 1]
    assert len(last) == 4
    assert plan.tabs_per_window == 4


def test_a_tab_is_as_wide_as_it_was_asked_to_be() -> None:
    plan = cutout_plate(spec(), tab_width=3.0)
    last = [cut for cut in plan.cuts if cut.pass_index == plan.passes - 1]
    gap = last[0].start.distance_to(last[-1].end)
    assert gap == pytest.approx(3.0)


def test_turning_the_tabs_off_leaves_one_run_all_the_way_round() -> None:
    plan = cutout_plate(spec(), tab_width=0.0)
    last = [cut for cut in plan.cuts if cut.pass_index == plan.passes - 1]
    assert len(last) == 1
    assert plan.tabs_per_window == 0


def test_a_negative_tab_is_refused() -> None:
    with pytest.raises(OutOfRange, match="tab width"):
        cutout_plate(spec(), tab_width=-1.0)


def test_a_negative_tab_height_is_refused() -> None:
    with pytest.raises(OutOfRange, match="tab height"):
        cutout_plate(spec(), tab_height=-1.0)


def test_the_cutter_can_be_named() -> None:
    plan = cutout_plate(spec(), cutter=catalogue_cutter("P-010"))
    assert plan.cutter.name == "P-010"
    assert plan.cuts[0].stroke.bounds().width == pytest.approx(40.0 - 0.254)


def test_two_windows_are_both_milled() -> None:
    second = Feature.rectangle("switch", Point(20.0, 30.0), 10.0, 10.0)
    plan = cutout_plate(spec(features=(WINDOW, second)))
    assert len(plan) == 2
    assert len(plan.cuts) == 2 * len([cut for cut in plan.cuts if cut.stroke.start.x > 40.0])


def test_a_plate_with_no_windows_mills_nothing() -> None:
    plan = cutout_plate(spec(features=()))
    assert len(plan) == 0
    assert len(plan.cuts) == 0
    assert "nothing to mill" in str(plan)


def test_the_offcut_is_the_area_of_the_windows() -> None:
    assert offcut_area(spec()) == pytest.approx(800.0)
    assert cutout_plate(spec()).area() == pytest.approx(800.0)


def test_the_windows_come_back_as_boxes_for_drawing() -> None:
    boxes = window_boxes(spec())
    assert len(boxes) == 1
    assert boxes[0].width == pytest.approx(40.0)


def test_the_plan_reads_like_a_line_on_a_setup_sheet() -> None:
    assert "1 windows" in str(cutout_plate(spec()))
    assert "P-020" in str(cutout_plate(spec()))


def test_the_toolpath_carries_every_run() -> None:
    plan = cutout_plate(spec())
    plunges = [move for move in plan.toolpath if move.kind.name == "PLUNGE"]
    assert len(plunges) == len(plan.cuts)


def test_the_default_tab_is_the_one_the_module_names() -> None:
    assert cutout_plate(spec()).tab_width == DEFAULT_TAB_WIDTH
