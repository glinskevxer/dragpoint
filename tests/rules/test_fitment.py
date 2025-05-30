"""Fitment: does everything land where it is allowed to."""

from __future__ import annotations

import pytest

from dragpoint.geometry.point import Point
from dragpoint.rules.fitment import (
    border_clearance,
    engraving_inside_area,
    feature_clearance,
    feature_on_plate,
    legend_missing_glyph,
    legend_overrun,
)
from dragpoint.rules.report import Severity
from dragpoint.spec.feature import Feature
from dragpoint.text.fit import FitPolicy

from .conftest import build_check


def test_a_legend_the_face_can_draw_reports_nothing() -> None:
    assert list(legend_missing_glyph(build_check(("PUMP 2", "RUN")))) == []


def test_a_character_the_face_cannot_draw_is_named() -> None:
    found = list(legend_missing_glyph(build_check(("run",))))
    assert len(found) == 1
    assert "'r'" in found[0].message
    assert found[0].subject == "P-101 line 1"


def test_every_offender_on_a_line_is_named_once_in_order() -> None:
    found = list(legend_missing_glyph(build_check(("aXbXa",))))
    assert found[0].message.endswith("'a' 'b'")


def test_each_line_is_reported_separately() -> None:
    found = list(legend_missing_glyph(build_check(("ok", "OK", "no"))))
    assert [item.subject for item in found] == ["P-101 line 1", "P-101 line 3"]


def test_a_legend_that_fits_reports_no_overrun() -> None:
    assert list(legend_overrun(build_check(("RUN",)))) == []


def test_a_legend_that_will_not_fit_says_what_stopped_it() -> None:
    check = build_check(("EMERGENCY STOP PUSHBUTTON ISOLATOR",), width=30.0, fit=FitPolicy.CONDENSE)
    found = list(legend_overrun(check))
    assert len(found) == 1
    assert "condense" in found[0].message
    assert found[0].measured is not None
    assert found[0].limit is not None
    assert found[0].measured > found[0].limit


def test_an_unfitted_overrun_blames_the_policy() -> None:
    check = build_check(("EMERGENCY STOP PUSHBUTTON",), width=30.0, fit=FitPolicy.NONE)
    assert "fit policy" in list(legend_overrun(check))[0].message


def test_a_normal_plate_keeps_its_marks_inside_the_area() -> None:
    assert list(engraving_inside_area(build_check(("RUN",)))) == []


def test_a_legend_that_overhangs_the_area_is_reported() -> None:
    check = build_check(("EMERGENCY STOP PUSHBUTTON",), width=30.0, fit=FitPolicy.NONE)
    found = list(engraving_inside_area(check))
    assert found
    assert found[0].measured is not None
    assert found[0].measured > 0.0


def test_the_area_test_allows_for_half_the_groove() -> None:
    fine = build_check(("RUN",), cutter="V10-005", depth=0.25, margin=0.05, height=4.0)
    wide = build_check(
        ("RUN",), cutter="V90-030", depth=0.9, stock="LAM32-RW", margin=0.05, height=4.0
    )
    assert list(engraving_inside_area(fine)) == []
    assert list(engraving_inside_area(wide)) != []


def test_a_feature_well_away_from_the_legend_is_clear() -> None:
    hole = Feature.round_hole("fix1", Point(3.0, 3.0), 2.0, clearance=0.5)
    assert list(feature_clearance(build_check(("RUN",), features=(hole,)))) == []


def test_a_feature_under_the_legend_is_reported_once() -> None:
    bore = Feature.round_hole("bore", Point(30.0, 10.0), 8.0, clearance=1.0)
    found = list(feature_clearance(build_check(("PUMP 2", "RUN"), features=(bore,))))
    assert len(found) == 1
    assert found[0].where == Point(30.0, 10.0)
    assert found[0].limit == 1.0


def test_every_offending_feature_gets_its_own_violation() -> None:
    left = Feature.round_hole("a", Point(26.0, 10.0), 6.0, clearance=1.0)
    right = Feature.round_hole("b", Point(34.0, 10.0), 6.0, clearance=1.0)
    found = list(feature_clearance(build_check(("PUMP 2",), features=(left, right))))
    assert {item.message for item in found} == {
        "engraving comes inside the clearance on a",
        "engraving comes inside the clearance on b",
    }


def test_clearance_is_measured_from_the_edge_of_the_groove() -> None:
    bore = Feature.round_hole("bore", Point(30.0, 16.0), 3.0, clearance=1.0)
    fine = build_check(("RUN",), cutter="V10-005", depth=0.25, features=(bore,))
    wide = build_check(("RUN",), cutter="V90-030", depth=0.9, stock="LAM32-RW", features=(bore,))
    for found in feature_clearance(wide):
        assert found.measured is not None
    fine_worst = [item.measured for item in feature_clearance(fine)]
    wide_worst = [item.measured for item in feature_clearance(wide)]
    assert fine_worst == [] or wide_worst != []


def test_a_plate_with_no_features_is_clear() -> None:
    assert list(feature_clearance(build_check(("RUN",)))) == []


def test_a_feature_on_the_plate_is_not_reported() -> None:
    hole = Feature.round_hole("fix1", Point(5.0, 10.0), 4.0)
    assert list(feature_on_plate(build_check(("RUN",), features=(hole,)))) == []


def test_a_feature_off_the_plate_is_named() -> None:
    stray = Feature.round_hole("stray", Point(500.0, 10.0), 4.0)
    found = list(feature_on_plate(build_check(("RUN",), features=(stray,))))
    assert len(found) == 1
    assert "stray" in found[0].message


def test_a_plate_with_no_border_reports_nothing() -> None:
    assert list(border_clearance(build_check(("RUN",)))) == []


def test_a_legend_inside_the_border_is_clear() -> None:
    check = build_check(("RUN",), border=1.0, margin=4.0)
    assert list(border_clearance(check)) == []


def test_a_legend_that_runs_into_the_border_is_a_warning() -> None:
    check = build_check(("EMERGENCY STOP",), border=8.0, margin=1.0, fit=FitPolicy.NONE)
    found = list(border_clearance(check))
    assert found
    assert found[0].severity is Severity.WARNING


def test_a_blank_plate_passes_everything() -> None:
    check = build_check(lines=())
    for check_rule in (
        legend_missing_glyph,
        legend_overrun,
        engraving_inside_area,
        feature_clearance,
        feature_on_plate,
        border_clearance,
    ):
        assert list(check_rule(check)) == []


def test_the_area_overhang_is_the_worst_side() -> None:
    check = build_check(("EMERGENCY STOP PUSHBUTTON",), width=30.0, fit=FitPolicy.NONE)
    worst = max(item.measured or 0.0 for item in engraving_inside_area(check))
    assert worst == pytest.approx(
        max(
            check.area.min_x - (check.ink_bounds().min_x - check.groove_width / 2.0),  # type: ignore[union-attr]
            (check.ink_bounds().max_x + check.groove_width / 2.0) - check.area.max_x,  # type: ignore[union-attr]
        ),
        abs=0.01,
    )
