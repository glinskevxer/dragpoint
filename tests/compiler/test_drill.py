"""Drilling the holes, as a program of its own."""

from __future__ import annotations

import pytest

from dragpoint.compiler.drill import BREAKTHROUGH, DrillPlan, drill_plate, drillable
from dragpoint.compiler.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.path.plan import MoveKind
from dragpoint.spec.feature import Feature, FeatureKind
from dragpoint.spec.plate import PlateSpec
from dragpoint.tool.material import material


def holes() -> tuple[Feature, ...]:
    return (
        Feature.round_hole("fix-left", Point(6.0, 12.5), 4.2),
        Feature.round_hole("fix-right", Point(114.0, 12.5), 4.2),
    )


def spec(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-120",
        "width": 120.0,
        "height": 25.0,
        "stock": "LAM16-BW",
        "features": holes(),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def test_holes_and_bores_are_drilled() -> None:
    bore = Feature.round_hole("bore", Point(60.0, 12.5), 12.0, kind=FeatureKind.BORE)
    assert len(drillable(spec(features=(*holes(), bore)))) == 3


def test_a_cutout_is_not_a_hole() -> None:
    window = Feature.rectangle("meter", Point(60.0, 12.5), 10.0, 6.0)
    assert len(drillable(spec(features=(*holes(), window)))) == 2


def test_a_keepout_is_not_a_hole() -> None:
    zone = Feature.rectangle("zone", Point(60.0, 12.5), 10.0, 6.0, kind=FeatureKind.KEEPOUT)
    assert drillable(spec(features=(zone,))) == ()


def test_the_depth_goes_through_the_sheet_and_out_the_back() -> None:
    plan = drill_plate(spec())
    assert plan.depth == pytest.approx(material("LAM16-BW").thickness + BREAKTHROUGH)


def test_a_thicker_sheet_is_drilled_deeper() -> None:
    thin = drill_plate(spec(stock="LAM16-BW"))
    thick = drill_plate(spec(stock="LAM32-RW", depth=0.4))
    assert thick.depth > thin.depth


def test_every_hole_gets_a_rapid_over_it() -> None:
    plan = drill_plate(spec())
    rapids = plan.toolpath.of_kind(MoveKind.RAPID)
    assert len(rapids) == 2
    assert {move.to for move in rapids} == {hole.centre for hole in holes()}


def test_the_drill_pecks_rather_than_going_straight_through() -> None:
    plan = drill_plate(spec(), peck=0.5)
    plunges = plan.toolpath.of_kind(MoveKind.PLUNGE)
    assert len(plunges) == plan.pecks_per_hole * len(plan)
    assert plan.pecks_per_hole > 1


def test_each_peck_goes_deeper_than_the_one_before() -> None:
    plan = drill_plate(spec(), peck=0.5)
    depths = [move.z for move in plan.toolpath.of_kind(MoveKind.PLUNGE)][: plan.pecks_per_hole]
    assert depths == sorted(depths, reverse=True)


def test_the_last_peck_reaches_the_full_depth() -> None:
    plan = drill_plate(spec(), peck=0.5)
    assert plan.toolpath.deepest() == pytest.approx(-plan.depth)


def test_a_peck_bigger_than_the_hole_is_one_plunge() -> None:
    plan = drill_plate(spec(), peck=10.0)
    assert plan.pecks_per_hole == 1
    assert len(plan.toolpath.of_kind(MoveKind.PLUNGE)) == len(plan)


def test_the_drill_comes_out_to_the_clearance_between_pecks() -> None:
    setup = MachineSetup(clearance=0.8)
    plan = drill_plate(spec(), setup=setup, peck=0.5)
    lifts = plan.toolpath.of_kind(MoveKind.LIFT)
    assert any(move.z == pytest.approx(0.8) for move in lifts)


def test_every_hole_finishes_at_the_safe_height() -> None:
    plan = drill_plate(spec(), setup=MachineSetup(safe=7.0))
    assert plan.toolpath.moves[-1].z == 7.0
    assert plan.toolpath.highest() == 7.0


def test_a_peck_of_nothing_is_refused() -> None:
    with pytest.raises(OutOfRange, match="peck"):
        drill_plate(spec(), peck=0.0)


def test_the_holes_are_visited_nearest_first() -> None:
    far = Feature.round_hole("far", Point(114.0, 12.5), 4.2)
    near = Feature.round_hole("near", Point(6.0, 12.5), 4.2)
    plan = drill_plate(spec(features=(far, near)))
    first = plan.toolpath.of_kind(MoveKind.RAPID)[0]
    assert first.to == near.centre


def test_a_plate_with_no_holes_makes_an_empty_program() -> None:
    plan = drill_plate(spec(features=()))
    assert len(plan) == 0
    assert len(plan.toolpath) == 0
    assert str(plan) == "P-120: nothing to drill"


def test_the_diameters_are_listed_smallest_first() -> None:
    big = Feature.round_hole("bore", Point(60.0, 12.5), 12.0, kind=FeatureKind.BORE)
    plan = drill_plate(spec(features=(*holes(), big)))
    assert plan.diameters() == (4.2, 12.0)


def test_str_reads_like_a_line_on_a_drilling_list() -> None:
    assert str(drill_plate(spec())) == "P-120: 2 holes at 4.2mm, 2.10mm deep"


def test_the_plan_keeps_the_plate_it_came_from() -> None:
    plan = drill_plate(spec())
    assert isinstance(plan, DrillPlan)
    assert plan.name == "P-120"
    assert plan.plate.name == "P-120"
    assert plan.stock.name == "LAM16-BW"
