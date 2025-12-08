"""Reading a plate schedule out of a spreadsheet export."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.errors import SpecError
from dragpoint.spec.sheetload import load_csv_job, parse_csv_plates

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mcc-panel-8.csv"

MINIMAL = "Plate,Size,Material\nP-1,60x20,LAM16-BW\n"


def test_the_shipped_example_reads() -> None:
    job = load_csv_job(EXAMPLE)
    assert job.name == "mcc-panel-8"
    assert len(job) == 5
    assert job.piece_count == 10


def test_the_job_takes_the_name_of_the_file() -> None:
    assert load_csv_job(EXAMPLE).name == "mcc-panel-8"


def test_the_job_name_can_be_given() -> None:
    assert load_csv_job(EXAMPLE, name="MCC-8").name == "MCC-8"


def test_job_settings_come_through() -> None:
    assert load_csv_job(EXAMPLE, cutter="V20-010").cutter == "V20-010"


def test_a_file_that_is_not_there_is_a_message() -> None:
    with pytest.raises(SpecError, match="cannot read the file"):
        load_csv_job(Path("no-such-schedule.csv"))


def test_a_minimal_row_makes_a_plate() -> None:
    plates = parse_csv_plates(MINIMAL)
    assert len(plates) == 1
    assert plates[0].name == "P-1"
    assert plates[0].width == 60.0
    assert plates[0].stock == "LAM16-BW"


@pytest.mark.parametrize(
    "heading",
    ["Plate", "PLATE", "plate name", "Drawing", "name"],
)
def test_the_name_column_is_matched_loosely(heading: str) -> None:
    text = f"{heading},Size,Material\nP-1,60x20,LAM16-BW\n"
    assert parse_csv_plates(text)[0].name == "P-1"


@pytest.mark.parametrize("heading", ["Qty", "QUANTITY", "No", "Off"])
def test_the_quantity_column_is_matched_loosely(heading: str) -> None:
    text = f"Plate,Size,Material,{heading}\nP-1,60x20,LAM16-BW,4\n"
    assert parse_csv_plates(text)[0].quantity == 4


def test_a_column_nobody_recognises_is_left_alone() -> None:
    text = "Plate,Size,Material,Drawing no,Due\nP-1,60x20,LAM16-BW,SK-1234,friday\n"
    assert parse_csv_plates(text)[0].name == "P-1"


def test_a_width_and_a_height_work_as_well_as_a_size() -> None:
    text = "Plate,Width,Height,Material\nP-1,60,20,LAM16-BW\n"
    plate = parse_csv_plates(text)[0]
    assert (plate.width, plate.height) == (60.0, 20.0)


def test_a_cell_may_carry_a_unit() -> None:
    text = "Plate,Size,Material,Cap\nP-1,2x1in,LAM16-BW,0.125in\n"
    plate = parse_csv_plates(text)[0]
    assert plate.width == pytest.approx(50.8)
    assert plate.cap_height == pytest.approx(3.175)


def test_the_lines_come_out_in_column_order() -> None:
    text = "Plate,Size,Material,Line2,Line1\nP-1,60x20,LAM16-BW,RUN,PUMP 2\n"
    assert parse_csv_plates(text)[0].lines == ("PUMP 2", "RUN")


def test_a_trailing_empty_line_column_is_not_a_blank_line() -> None:
    text = "Plate,Size,Material,Line1,Line2,Line3\nP-1,60x20,LAM16-BW,RUN,,\n"
    assert parse_csv_plates(text)[0].lines == ("RUN",)


def test_a_blank_line_in_the_middle_is_kept() -> None:
    text = "Plate,Size,Material,Line1,Line2,Line3\nP-1,60x30,LAM16-BW,TOP,,BOTTOM\n"
    assert parse_csv_plates(text)[0].lines == ("TOP", "", "BOTTOM")


def test_a_legend_column_counts_as_the_first_line() -> None:
    text = "Plate,Size,Material,Legend\nP-1,60x20,LAM16-BW,RUN\n"
    assert parse_csv_plates(text)[0].lines == ("RUN",)


def test_defaults_fill_in_what_the_spreadsheet_leaves_out() -> None:
    text = "Plate,Size\nP-1,60x20\n"
    plates = parse_csv_plates(text, defaults={"stock": "LAM16-BW", "cap_height": 4.0})
    assert plates[0].stock == "LAM16-BW"
    assert plates[0].cap_height == 4.0


def test_a_row_beats_the_default() -> None:
    text = "Plate,Size,Material\nP-1,60x20,LAM32-RW\n"
    plates = parse_csv_plates(text, defaults={"stock": "LAM16-BW", "depth": 0.4})
    assert plates[0].stock == "LAM32-RW"


def test_a_row_with_no_stock_and_no_default_is_a_message() -> None:
    with pytest.raises(SpecError, match="stock is missing"):
        parse_csv_plates("Plate,Size\nP-1,60x20\n")


def test_a_row_with_no_size_is_a_message() -> None:
    with pytest.raises(SpecError, match="width is missing"):
        parse_csv_plates("Plate,Material\nP-1,LAM16-BW\n")


def test_a_size_that_is_not_a_size_names_the_row() -> None:
    with pytest.raises(SpecError, match=r"row 2 \(P-1\).*not a size"):
        parse_csv_plates("Plate,Size,Material\nP-1,wide,LAM16-BW\n")


def test_a_quantity_that_is_not_a_number_names_the_row() -> None:
    with pytest.raises(SpecError, match="quantity"):
        parse_csv_plates("Plate,Size,Material,Qty\nP-1,60x20,LAM16-BW,lots\n")


def test_an_impossible_plate_names_the_row() -> None:
    with pytest.raises(SpecError, match=r"row 2 \(P-1\)"):
        parse_csv_plates("Plate,Size,Material,Margin\nP-1,60x20,LAM16-BW,30\n")


def test_a_row_with_no_name_gets_one_from_its_row_number() -> None:
    text = "Plate,Size,Material\n,60x20,LAM16-BW\n"
    assert parse_csv_plates(text)[0].name == "row2"


def test_blank_rows_are_skipped() -> None:
    text = "Plate,Size,Material\nP-1,60x20,LAM16-BW\n,,\nP-2,60x20,LAM16-BW\n"
    assert len(parse_csv_plates(text)) == 2


def test_a_short_row_is_padded_rather_than_refused() -> None:
    text = "Plate,Size,Material,Line1\nP-1,60x20,LAM16-BW\n"
    assert parse_csv_plates(text)[0].lines == ()


def test_an_empty_file_has_no_plates() -> None:
    assert parse_csv_plates("") == ()


def test_a_heading_row_that_says_nothing_useful_is_refused() -> None:
    with pytest.raises(SpecError, match="no column says"):
        parse_csv_plates("Colour,Finish\nred,matt\n")
