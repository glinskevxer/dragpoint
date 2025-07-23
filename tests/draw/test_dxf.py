"""The DXF export."""

from __future__ import annotations

import pytest

from dragpoint.compiler.plate import compile_plate
from dragpoint.draw.dxf import LAYERS, render_dxf
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


def pairs(text: str) -> list[tuple[str, str]]:
    """The file read back as the group code and value pairs it is."""
    lines = text.splitlines()
    assert len(lines) % 2 == 0, "a DXF is pairs of lines"
    return [(lines[index].strip(), lines[index + 1]) for index in range(0, len(lines), 2)]


def values_for(text: str, code: str) -> list[str]:
    return [value for group, value in pairs(text) if group == code]


def test_the_file_is_pairs_of_lines() -> None:
    assert pairs(render_dxf(compile_plate(spec())))


def test_the_file_ends_with_eof() -> None:
    text = render_dxf(compile_plate(spec()))
    assert pairs(text)[-1] == ("0", "EOF")
    assert text.endswith("\n")


def test_the_sections_open_and_close_in_pairs() -> None:
    text = render_dxf(compile_plate(spec()))
    opens = sum(1 for group, value in pairs(text) if group == "0" and value == "SECTION")
    closes = sum(1 for group, value in pairs(text) if group == "0" and value == "ENDSEC")
    assert opens == closes == 3


def test_it_says_it_is_release_twelve() -> None:
    text = render_dxf(compile_plate(spec()))
    assert ("1", "AC1009") in pairs(text)


def test_it_says_the_drawing_is_in_millimetres() -> None:
    text = render_dxf(compile_plate(spec()))
    assert ("9", "$INSUNITS") in pairs(text)
    index = pairs(text).index(("9", "$INSUNITS"))
    assert pairs(text)[index + 1] == ("70", "4")


def test_the_extents_cover_the_plate() -> None:
    text = render_dxf(compile_plate(spec()))
    listing = pairs(text)
    low = listing.index(("9", "$EXTMIN"))
    high = listing.index(("9", "$EXTMAX"))
    assert listing[low + 1][1] == "0.0000"
    assert listing[high + 1][1] == "60.0000"
    assert listing[high + 2][1] == "20.0000"


def test_the_extents_grow_to_cover_a_feature_that_hangs_off() -> None:
    stray = Feature.round_hole("stray", Point(70.0, 10.0), 4.0)
    text = render_dxf(compile_plate(spec(features=(stray,))))
    listing = pairs(text)
    high = listing.index(("9", "$EXTMAX"))
    assert float(listing[high + 1][1]) > 60.0


def test_every_layer_is_declared() -> None:
    text = render_dxf(compile_plate(spec()))
    declared = {value for group, value in pairs(text) if group == "2"}
    for layer in LAYERS:
        assert layer in declared


def test_the_layer_table_says_how_many_layers_there_are() -> None:
    listing = pairs(render_dxf(compile_plate(spec())))
    table = listing.index(("2", "LAYER"))
    assert listing[table + 1] == ("70", str(len(LAYERS)))


def test_the_engraving_is_on_its_own_layer() -> None:
    made = compile_plate(spec())
    text = render_dxf(made)
    polylines = sum(1 for group, value in pairs(text) if group == "0" and value == "POLYLINE")
    on_engrave = sum(1 for group, value in pairs(text) if group == "8" and value == "ENGRAVE")
    assert polylines == len(made.runs) + 2
    assert on_engrave > 0


def test_every_polyline_is_closed_off_with_a_seqend() -> None:
    text = render_dxf(compile_plate(spec()))
    opens = sum(1 for group, value in pairs(text) if group == "0" and value == "POLYLINE")
    closes = sum(1 for group, value in pairs(text) if group == "0" and value == "SEQEND")
    assert opens == closes


def test_the_vertices_add_up_to_the_points_that_were_drawn() -> None:
    made = compile_plate(spec())
    text = render_dxf(made)
    vertices = sum(1 for group, value in pairs(text) if group == "0" and value == "VERTEX")
    drawn = sum(len(stroke) for stroke in made.runs)
    assert vertices == drawn + 10


def test_a_round_feature_comes_out_as_a_circle() -> None:
    hole = Feature.round_hole("fix1", Point(6.0, 10.0), 4.0)
    text = render_dxf(compile_plate(spec(features=(hole,))))
    assert ("0", "CIRCLE") in pairs(text)
    assert ("40", "2.0000") in pairs(text)


def test_a_rectangular_feature_comes_out_as_a_polyline() -> None:
    window = Feature.rectangle("meter", Point(10.0, 10.0), 6.0, 4.0)
    with_it = render_dxf(compile_plate(spec(features=(window,))))
    without = render_dxf(compile_plate(spec()))
    assert ("0", "CIRCLE") not in pairs(with_it)
    opens = sum(1 for group, value in pairs(with_it) if group == "0" and value == "POLYLINE")
    before = sum(1 for group, value in pairs(without) if group == "0" and value == "POLYLINE")
    assert opens == before + 1


def test_a_border_gets_its_own_layer() -> None:
    text = render_dxf(compile_plate(spec(border=1.5, margin=3.0)))
    assert any(group == "8" and value == "BORDER" for group, value in pairs(text))


def test_a_plate_with_no_border_draws_none() -> None:
    text = render_dxf(compile_plate(spec()))
    assert not any(group == "8" and value == "BORDER" for group, value in pairs(text))


def test_a_negative_zero_never_reaches_the_file() -> None:
    text = render_dxf(compile_plate(spec()), decimals=3)
    assert "-0.000" not in text


def test_the_places_can_be_set() -> None:
    text = render_dxf(compile_plate(spec()), decimals=2)
    assert "60.00" in values_for(text, "10")


def test_a_silly_precision_is_refused() -> None:
    with pytest.raises(ValueError, match="places"):
        render_dxf(compile_plate(spec()), decimals=20)


def test_a_blank_plate_still_draws_the_blank() -> None:
    text = render_dxf(compile_plate(spec(lines=())))
    polylines = sum(1 for group, value in pairs(text) if group == "0" and value == "POLYLINE")
    assert polylines == 2
