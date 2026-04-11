"""The rules the milling setup asks about the windows."""

from __future__ import annotations

from dragpoint.compiler.plate import compile_plate
from dragpoint.geometry.point import Point
from dragpoint.rules.milling import MIN_RAIL, MIN_WEB
from dragpoint.rules.report import Severity
from dragpoint.spec.feature import Feature, FeatureKind
from dragpoint.spec.plate import PlateSpec


def spec(*features: Feature, **overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-1",
        "width": 120.0,
        "height": 60.0,
        "stock": "LAM32-RW",
        "lines": ("METER",),
        "cap_height": 4.0,
        "margin": 3.0,
        "features": features,
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def rules_on(*features: Feature, **overrides: object) -> list[str]:
    made = compile_plate(spec(*features, **overrides))
    return [violation.rule for violation in made.report.violations]


def window(x: float = 60.0, y: float = 14.0, width: float = 40.0, height: float = 16.0) -> Feature:
    return Feature.rectangle("meter", Point(x, y), width, height)


def test_a_plain_window_passes_every_milling_rule() -> None:
    assert rules_on(window()) == []


def test_a_window_narrower_than_the_cutter_is_an_error() -> None:
    slot = Feature.rectangle("slot", Point(60.0, 14.0), 0.4, 16.0)
    assert "window-narrower-than-the-cutter" in rules_on(slot)


def test_the_narrow_window_message_names_the_cutter_width() -> None:
    slot = Feature.rectangle("slot", Point(60.0, 14.0), 0.4, 16.0)
    made = compile_plate(spec(slot))
    said = " ".join(violation.message for violation in made.report.violations)
    assert "0.508mm" in said


def test_a_window_the_cutter_fits_in_is_not_flagged() -> None:
    assert "window-narrower-than-the-cutter" not in rules_on(window(width=2.0, height=16.0))


def test_a_window_close_to_the_edge_leaves_a_thin_rail() -> None:
    assert "window-rail-too-thin" in rules_on(window(x=25.0, y=14.0, width=48.0))


def test_a_window_well_inside_the_blank_leaves_no_complaint() -> None:
    assert "window-rail-too-thin" not in rules_on(window())


def test_the_rail_is_measured_to_the_nearest_edge() -> None:
    made = compile_plate(spec(window(x=25.0, y=14.0, width=48.0)))
    thin = [item for item in made.report.violations if item.rule == "window-rail-too-thin"]
    assert thin[0].measured is not None
    assert thin[0].measured < MIN_RAIL


def test_two_windows_almost_touching_are_a_warning() -> None:
    left = Feature.rectangle("left", Point(40.0, 14.0), 20.0, 16.0)
    right = Feature.rectangle("right", Point(61.0, 14.0), 20.0, 16.0)
    assert "windows-too-close-together" in rules_on(left, right)


def test_two_windows_with_a_web_between_them_are_fine() -> None:
    left = Feature.rectangle("left", Point(35.0, 14.0), 20.0, 16.0)
    right = Feature.rectangle("right", Point(75.0, 14.0), 20.0, 16.0)
    assert "windows-too-close-together" not in rules_on(left, right)


def test_the_web_is_measured_between_the_windows() -> None:
    left = Feature.rectangle("left", Point(40.0, 14.0), 20.0, 16.0)
    right = Feature.rectangle("right", Point(61.0, 14.0), 20.0, 16.0)
    made = compile_plate(spec(left, right))
    close = [item for item in made.report.violations if item.rule == "windows-too-close-together"]
    assert close[0].measured is not None
    assert close[0].measured < MIN_WEB


def test_three_windows_in_a_row_are_reported_pair_by_pair() -> None:
    made = compile_plate(
        spec(
            Feature.rectangle("a", Point(30.0, 14.0), 20.0, 16.0),
            Feature.rectangle("b", Point(51.0, 14.0), 20.0, 16.0),
            Feature.rectangle("c", Point(72.0, 14.0), 20.0, 16.0),
        )
    )
    close = [item for item in made.report.violations if item.rule == "windows-too-close-together"]
    assert len(close) == 2


def test_lettering_inside_a_window_is_an_error() -> None:
    over = Feature.rectangle("meter", Point(60.0, 40.0), 80.0, 20.0)
    assert "window-over-the-lettering" in rules_on(over)


def test_the_message_says_how_much_of_the_legend_is_in_the_window() -> None:
    over = Feature.rectangle("meter", Point(60.0, 40.0), 80.0, 20.0)
    made = compile_plate(spec(over))
    lost = [item for item in made.report.violations if item.rule == "window-over-the-lettering"]
    assert lost[0].measured is not None
    assert lost[0].measured > 0.0


def test_a_window_away_from_the_lettering_is_not_flagged() -> None:
    assert "window-over-the-lettering" not in rules_on(window())


def test_a_hole_is_none_of_these_rules_business() -> None:
    hole = Feature.round_hole("fix", Point(10.0, 10.0), 4.0)
    found = rules_on(hole)
    assert "window-narrower-than-the-cutter" not in found
    assert "window-rail-too-thin" not in found


def test_a_keepout_is_none_of_them_either() -> None:
    keepout = Feature.rectangle("clamp", Point(6.0, 6.0), 8.0, 8.0, kind=FeatureKind.KEEPOUT)
    assert "window-rail-too-thin" not in rules_on(keepout)


def test_a_window_that_cannot_be_cut_stops_the_plate() -> None:
    slot = Feature.rectangle("slot", Point(60.0, 14.0), 0.4, 16.0)
    made = compile_plate(spec(slot))
    assert made.report.worst is Severity.ERROR
    assert not made.ok
