"""The SVG preview."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

import pytest

from dragpoint.compiler.plate import compile_plate
from dragpoint.draw.svg import render_svg
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature
from dragpoint.spec.plate import PlateSpec


def spec(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-101",
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("PUMP 2", "RUN"),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def parsed(text: str) -> ElementTree.Element:
    return ElementTree.fromstring(text)


def test_the_output_is_well_formed_xml() -> None:
    root = parsed(render_svg(compile_plate(spec())))
    assert root.tag.endswith("svg")


def test_the_document_is_the_size_of_the_plate() -> None:
    root = parsed(render_svg(compile_plate(spec()), scale=4.0))
    assert root.get("width") == "240.00"
    assert root.get("height") == "80.00"
    assert root.get("viewBox") == "0 0 60.0000 20.0000"


def test_the_scale_changes_the_pixels_and_not_the_millimetres() -> None:
    root = parsed(render_svg(compile_plate(spec()), scale=10.0))
    assert root.get("width") == "600.00"
    assert root.get("viewBox") == "0 0 60.0000 20.0000"


def test_a_scale_of_zero_draws_nothing_and_says_so() -> None:
    with pytest.raises(ValueError, match="draws nothing"):
        render_svg(compile_plate(spec()), scale=0.0)


def test_the_plate_is_named_in_the_title() -> None:
    text = render_svg(compile_plate(spec(name="P&Q")))
    assert "<title>P&amp;Q</title>" in text


def test_the_y_axis_is_flipped_once() -> None:
    text = render_svg(compile_plate(spec()))
    assert 'transform="translate(0,20.0000) scale(1,-1)"' in text


def test_every_run_is_drawn_at_the_groove_width() -> None:
    made = compile_plate(spec())
    text = render_svg(made)
    groove = made.cutter.width_at_depth(made.depth)
    assert text.count("<polyline") == len(made.runs)
    assert f'stroke-width="{groove:.4f}"' in text


def test_the_grooves_have_round_ends_because_the_cutter_does() -> None:
    text = render_svg(compile_plate(spec()))
    assert 'stroke-linecap="round"' in text
    assert 'stroke-linejoin="round"' in text


def test_a_wider_cutter_draws_wider_grooves() -> None:
    fine = compile_plate(spec(cutter="V10-005"))
    coarse = compile_plate(spec(cutter="V90-030", stock="LAM32-RW", depth=0.9))
    fine_width = fine.cutter.width_at_depth(fine.depth)
    coarse_width = coarse.cutter.width_at_depth(coarse.depth)
    assert f'stroke-width="{fine_width:.4f}"' in render_svg(fine)
    assert f'stroke-width="{coarse_width:.4f}"' in render_svg(coarse)
    assert coarse_width > fine_width


def test_the_engraving_area_is_drawn_dashed_and_can_be_turned_off() -> None:
    with_area = render_svg(compile_plate(spec()), show_area=True)
    without = render_svg(compile_plate(spec()), show_area=False)
    assert with_area.count("<rect") == without.count("<rect") + 1
    assert "stroke-dasharray" in with_area


def test_a_border_is_drawn_as_well_as_the_area() -> None:
    plain = render_svg(compile_plate(spec()))
    bordered = render_svg(compile_plate(spec(border=1.5, margin=3.0)))
    assert bordered.count("<rect") == plain.count("<rect") + 1


def test_a_round_feature_draws_its_hole_and_its_clearance() -> None:
    hole = Feature.round_hole("fix1", Point(6.0, 10.0), 4.0, clearance=1.0)
    text = render_svg(compile_plate(spec(features=(hole,))))
    assert text.count("<circle") == 2
    assert 'r="2.0000"' in text
    assert 'r="3.0000"' in text


def test_a_rectangular_feature_draws_two_rectangles() -> None:
    window = Feature.rectangle("meter", Point(10.0, 10.0), 6.0, 4.0, clearance=1.0)
    with_it = render_svg(compile_plate(spec(features=(window,))))
    without = render_svg(compile_plate(spec()))
    assert with_it.count("<rect") == without.count("<rect") + 2


def test_features_can_be_turned_off() -> None:
    hole = Feature.round_hole("fix1", Point(6.0, 10.0), 4.0)
    text = render_svg(compile_plate(spec(features=(hole,))), show_features=False)
    assert "<circle" not in text


def test_the_travel_can_be_drawn_and_is_off_by_default() -> None:
    made = compile_plate(spec())
    assert "<path" not in render_svg(made)
    assert "<path" in render_svg(made, show_travel=True)


def test_a_blank_plate_draws_the_plate_and_nothing_else() -> None:
    text = render_svg(compile_plate(spec(lines=())))
    assert "<polyline" not in text
    assert "<rect" in text


def test_a_blank_plate_has_no_travel_to_draw() -> None:
    assert "<path" not in render_svg(compile_plate(spec(lines=())), show_travel=True)


def test_the_file_ends_with_a_newline() -> None:
    assert render_svg(compile_plate(spec())).endswith("\n")
