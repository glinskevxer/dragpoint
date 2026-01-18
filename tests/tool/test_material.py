"""Stock, and the depth window a two ply sheet allows."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.errors import OutOfRange, StockError
from dragpoint.tool.material import (
    BACKING_LEFT,
    BREAK_THROUGH,
    MATERIALS,
    RACK_FILE,
    Material,
    load_rack,
    material,
    parse_rack,
)


def two_ply() -> Material:
    return material("LAM16-BW")


def solid() -> Material:
    return material("ACRYL-30")


def test_a_two_ply_sheet_knows_it_is_one() -> None:
    assert two_ply().is_two_ply
    assert not solid().is_two_ply


def test_the_floor_is_the_cap_plus_the_break_through() -> None:
    low, _ = two_ply().depth_window()
    assert low == pytest.approx(0.13 + BREAK_THROUGH)


def test_solid_stock_has_no_floor() -> None:
    low, _ = solid().depth_window()
    assert low == 0.0


def test_the_ceiling_leaves_backing_under_the_groove() -> None:
    _, high = two_ply().depth_window()
    assert high == pytest.approx(1.6 - BACKING_LEFT)


def test_a_depth_inside_the_window_is_accepted() -> None:
    assert two_ply().accepts_depth(0.25)
    assert two_ply().require_depth(0.25) == 0.25


def test_a_depth_that_would_not_break_the_cap_is_refused() -> None:
    with pytest.raises(OutOfRange) as caught:
        two_ply().require_depth(0.10)
    assert "LAM16-BW" in str(caught.value)


def test_a_depth_that_would_cut_the_sheet_in_half_is_refused() -> None:
    with pytest.raises(OutOfRange):
        two_ply().require_depth(1.5)


def test_the_edges_of_the_window_are_inside_it() -> None:
    low, high = two_ply().depth_window()
    assert two_ply().accepts_depth(low)
    assert two_ply().accepts_depth(high)


def test_a_hair_outside_the_window_is_still_inside_it() -> None:
    low, high = two_ply().depth_window()
    assert two_ply().accepts_depth(low - 1e-5)
    assert two_ply().accepts_depth(high + 1e-5)


def test_the_nominal_depth_of_every_stocked_sheet_is_in_its_own_window() -> None:
    for sheet in MATERIALS.values():
        assert sheet.accepts_depth(sheet.nominal_depth), sheet.name


def test_pass_counting_rounds_up() -> None:
    sheet = two_ply()
    assert sheet.max_depth_per_pass == 0.35
    assert sheet.passes_for(0.25) == 1
    assert sheet.passes_for(0.35) == 1
    assert sheet.passes_for(0.36) == 2
    assert sheet.passes_for(0.70) == 2
    assert sheet.passes_for(0.71) == 3


def test_a_depth_that_lands_exactly_on_a_pass_boundary_does_not_add_one() -> None:
    sheet = material("BRASS-15")
    assert sheet.max_depth_per_pass == 0.08
    assert sheet.passes_for(0.16) == 2


def test_no_depth_means_no_passes() -> None:
    assert two_ply().passes_for(0.0) == 0
    assert two_ply().passes_for(-1.0) == 0


def test_brass_and_stainless_take_more_passes_than_plastic() -> None:
    assert material("STAIN-10").passes_for(0.08) >= material("ACRYL-30").passes_for(0.08)


@pytest.mark.parametrize(
    ("kwargs", "what"),
    [
        ({"thickness": 0.0}, "thickness"),
        ({"cap": 0.0}, "cap"),
        ({"cap": 5.0}, "cap"),
        ({"max_depth_per_pass": 0.0}, "max depth per pass"),
        ({"feed": 0.0}, "feed"),
        ({"plunge_feed": 0.0}, "plunge feed"),
        ({"spindle": -1}, "spindle"),
        ({"nominal_depth": 0.01}, "nominal depth"),
        ({"nominal_depth": 3.0}, "nominal depth"),
    ],
)
def test_an_impossible_sheet_is_refused(kwargs: dict[str, object], what: str) -> None:
    values: dict[str, object] = {
        "name": "bad",
        "description": "test",
        "thickness": 1.6,
        "cap": 0.13,
        "nominal_depth": 0.25,
        "max_depth_per_pass": 0.35,
        "feed": 1000.0,
        "plunge_feed": 200.0,
        "spindle": 12000,
    }
    values.update(kwargs)
    with pytest.raises(OutOfRange) as caught:
        Material(**values)  # type: ignore[arg-type]
    assert what in str(caught.value)


def test_a_sheet_too_thin_to_have_a_window_is_refused() -> None:
    with pytest.raises(OutOfRange):
        Material(
            name="tissue",
            description="far too thin",
            thickness=0.3,
            cap=0.13,
            nominal_depth=0.2,
            max_depth_per_pass=0.1,
            feed=100.0,
            plunge_feed=50.0,
            spindle=10000,
        )


def test_the_rack_is_keyed_by_the_stock_code() -> None:
    for name, sheet in MATERIALS.items():
        assert sheet.name == name


def test_the_rack_holds_both_laminate_and_solid() -> None:
    assert any(sheet.is_two_ply for sheet in MATERIALS.values())
    assert any(not sheet.is_two_ply for sheet in MATERIALS.values())


def test_an_unknown_stock_code_lists_what_the_rack_holds() -> None:
    with pytest.raises(KeyError) as caught:
        material("LAM99-ZZ")
    assert "LAM16-BW" in str(caught.value)


def test_str_reads_like_a_stock_label() -> None:
    assert str(two_ply()) == "LAM16-BW (black on white laminate, 1.6mm, 0.13mm cap)"
    assert str(solid()) == "ACRYL-30 (clear acrylic, 3mm, solid)"


ONE_SHEET = """
[LAM16-BW]
description = "black on white laminate"
thickness = 1.6
cap = 0.13
nominal = 0.25
per_pass = 0.35
feed = 1200.0
plunge = 300.0
spindle = 12000
"""


def test_the_shipped_rack_is_what_the_package_hands_out() -> None:
    assert load_rack(RACK_FILE) == MATERIALS


def test_the_shipped_rack_holds_the_stock_the_shop_cuts() -> None:
    assert "LAM16-BW" in MATERIALS
    assert "BRASS-15" in MATERIALS


def test_a_rack_of_one_sheet_reads() -> None:
    rack = parse_rack(ONE_SHEET)
    assert list(rack) == ["LAM16-BW"]
    assert rack["LAM16-BW"].thickness == 1.6


def test_the_code_comes_from_the_table_name() -> None:
    assert parse_rack(ONE_SHEET)["LAM16-BW"].name == "LAM16-BW"


def test_a_sheet_with_no_cap_is_solid() -> None:
    text = ONE_SHEET.replace("cap = 0.13\n", "")
    assert parse_rack(text)["LAM16-BW"].cap is None
    assert not parse_rack(text)["LAM16-BW"].is_two_ply


def test_a_file_that_is_not_a_rack_file_is_a_message() -> None:
    with pytest.raises(StockError, match="not a rack file"):
        parse_rack("this is not toml at all [[[")


def test_an_empty_file_is_refused() -> None:
    with pytest.raises(StockError, match="no stock in this file"):
        parse_rack("")


def test_a_stock_code_that_is_not_a_table_is_refused() -> None:
    with pytest.raises(StockError, match="table of numbers"):
        parse_rack('LAM16-BW = "black on white"')


def test_a_missing_number_names_the_stock_and_the_number() -> None:
    text = ONE_SHEET.replace("feed = 1200.0\n", "")
    with pytest.raises(StockError, match=r"LAM16-BW.*nothing says feed"):
        parse_rack(text)


def test_a_key_nobody_uses_is_refused_rather_than_ignored() -> None:
    text = ONE_SHEET + 'colour = "black"\n'
    with pytest.raises(StockError, match="nothing here uses colour"):
        parse_rack(text)


def test_a_number_that_is_not_a_number_names_the_stock() -> None:
    text = ONE_SHEET.replace("thickness = 1.6", 'thickness = "thin"')
    with pytest.raises(StockError, match="LAM16-BW"):
        parse_rack(text)


def test_a_sheet_whose_numbers_do_not_work_names_the_stock() -> None:
    text = ONE_SHEET.replace("cap = 0.13", "cap = 1.5")
    with pytest.raises(StockError, match="LAM16-BW"):
        parse_rack(text)


def test_a_rack_reads_off_disk(tmp_path: Path) -> None:
    target = tmp_path / "rack.toml"
    target.write_text(ONE_SHEET, encoding="utf-8")
    assert list(load_rack(target)) == ["LAM16-BW"]


def test_a_rack_that_is_not_there_says_so(tmp_path: Path) -> None:
    with pytest.raises(StockError, match="cannot read the file"):
        load_rack(tmp_path / "gone.toml")


def test_the_source_of_a_message_is_the_file_it_came_from(tmp_path: Path) -> None:
    target = tmp_path / "rack.toml"
    target.write_text("", encoding="utf-8")
    with pytest.raises(StockError, match="rack.toml"):
        load_rack(target)
