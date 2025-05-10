"""Reading a job out of TOML, and naming the table when it will not read."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.errors import SpecError
from dragpoint.spec.feature import FeatureKind
from dragpoint.spec.load import load_job, parse_job
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign

MINIMAL = """
[job]
name = "J1"

[defaults]
stock = "LAM16-BW"

[[plate]]
name = "P-1"
size = ["60mm", "20mm"]
lines = ["RUN"]
"""

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mcc-panel-7.toml"


def test_a_minimal_job_reads() -> None:
    job = parse_job(MINIMAL)
    assert job.name == "J1"
    assert len(job) == 1
    assert job.plate("P-1").width == 60.0
    assert job.plate("P-1").stock == "LAM16-BW"


def test_the_shipped_example_reads() -> None:
    job = load_job(EXAMPLE)
    assert job.name == "MCC-7"
    assert len(job) == 6
    assert job.piece_count == 14
    assert job.sheet is not None
    assert job.sheet.width == 300.0
    assert job.stock_codes() == ("ANOD-10", "LAM16-BW", "LAM32-RW")


def test_units_are_converted_on_the_way_in() -> None:
    job = load_job(EXAMPLE)
    bore = job.plate("P-110").feature("bore")
    assert bore.diameter == pytest.approx(22.225)
    assert bore.kind is FeatureKind.BORE


def test_defaults_fill_in_underneath_every_plate() -> None:
    job = load_job(EXAMPLE)
    assert job.plate("P-101").cap_height == 3.0
    assert job.plate("P-110").cap_height == 5.0
    assert job.plate("P-101").face == "panelgothic"


def test_a_plate_can_overrule_the_default_stock() -> None:
    job = load_job(EXAMPLE)
    assert job.plate("P-101").stock == "LAM16-BW"
    assert job.plate("P-130").stock == "ANOD-10"


def test_alignment_and_fit_words_are_read() -> None:
    job = load_job(EXAMPLE)
    assert job.plate("P-120").halign is HAlign.LEFT
    assert job.plate("P-110").fit is FitPolicy.BOTH
    assert job.plate("P-101").halign is HAlign.CENTRE


def test_tags_come_through() -> None:
    assert load_job(EXAMPLE).plate("P-130").has_tag("spares")


def test_features_come_through_in_order() -> None:
    plate = load_job(EXAMPLE).plate("P-120")
    assert [item.name for item in plate.features] == ["fix-left", "fix-right"]


def test_a_bare_string_is_one_line() -> None:
    job = parse_job(MINIMAL.replace('lines = ["RUN"]', 'lines = "RUN"'))
    assert job.plate("P-1").lines == ("RUN",)


def test_width_and_height_may_be_given_separately() -> None:
    text = MINIMAL.replace('size = ["60mm", "20mm"]', 'width = "60mm"\nheight = "20mm"')
    assert parse_job(text).plate("P-1").height == 20.0


def test_a_job_with_no_plates_is_allowed() -> None:
    assert len(parse_job('[job]\nname = "empty"\n')) == 0


def test_junk_is_not_toml() -> None:
    with pytest.raises(SpecError, match="not readable as TOML"):
        parse_job("this is not toml = = =")


def test_a_file_that_is_not_there() -> None:
    with pytest.raises(SpecError, match="cannot read the file"):
        load_job(Path("no-such-job.toml"))


def test_bytes_and_text_read_the_same() -> None:
    assert parse_job(MINIMAL.encode("utf-8")).name == parse_job(MINIMAL).name


def test_a_job_with_no_name_says_so() -> None:
    with pytest.raises(SpecError, match=r"\[job\]: name is missing"):
        parse_job("[job]\ncutter = 'V30-015'\n")


def test_an_unknown_top_level_table_is_refused() -> None:
    with pytest.raises(SpecError, match="unknown key 'panel'"):
        parse_job(MINIMAL + "\n[panel]\nname = 'x'\n")


def test_an_unknown_job_key_is_refused() -> None:
    with pytest.raises(SpecError, match="unknown key 'speed'"):
        parse_job(MINIMAL.replace('name = "J1"', 'name = "J1"\nspeed = 3'))


def test_an_unknown_plate_key_is_refused_and_names_the_plate() -> None:
    with pytest.raises(SpecError, match=r'plate\[0\] "P-1".*unknown key'):
        parse_job(MINIMAL + "\ncolour = 'red'\n")


def test_an_unknown_feature_key_is_refused_and_names_the_feature() -> None:
    text = MINIMAL + "\n[[plate.feature]]\nname='f'\nat=['1mm','1mm']\ndiameter='2mm'\nnope=1\n"
    with pytest.raises(SpecError, match=r"feature\[0\].*unknown key 'nope'"):
        parse_job(text)


def test_a_plate_that_is_not_an_array_of_tables_is_refused() -> None:
    with pytest.raises(SpecError, match=r"use \[\[plate\]\]"):
        parse_job("[job]\nname='J'\n[plate]\nname='P'\n")


def test_a_size_with_the_wrong_number_of_entries_is_refused() -> None:
    with pytest.raises(SpecError, match="exactly two lengths"):
        parse_job(MINIMAL.replace('size = ["60mm", "20mm"]', 'size = ["60mm"]'))


def test_a_length_that_is_not_a_length_names_the_key() -> None:
    with pytest.raises(SpecError, match="cap_height"):
        parse_job(MINIMAL + "\ncap_height = 'wide'\n")


def test_an_unknown_unit_names_the_units_that_are_known() -> None:
    with pytest.raises(SpecError, match="thou"):
        parse_job(MINIMAL.replace('"60mm"', '"60furlong"'))


def test_lines_that_are_not_strings_are_refused() -> None:
    with pytest.raises(SpecError, match="not a string"):
        parse_job(MINIMAL.replace('lines = ["RUN"]', "lines = [1, 2]"))


def test_lines_that_are_not_a_list_are_refused() -> None:
    with pytest.raises(SpecError, match="a list of strings"):
        parse_job(MINIMAL.replace('lines = ["RUN"]', "lines = 3"))


def test_an_unknown_alignment_lists_the_ones_that_work() -> None:
    with pytest.raises(SpecError, match="centre"):
        parse_job(MINIMAL + "\nhalign = 'middle'\n")


def test_an_impossible_plate_is_reported_against_its_own_table() -> None:
    with pytest.raises(SpecError, match=r'plate\[0\] "P-1".*margin'):
        parse_job(MINIMAL + "\nmargin = '30mm'\n")


def test_a_feature_at_with_one_coordinate_is_refused() -> None:
    text = MINIMAL + "\n[[plate.feature]]\nname='f'\nat=['1mm']\ndiameter='2mm'\n"
    with pytest.raises(SpecError, match="exactly two lengths"):
        parse_job(text)


def test_a_feature_with_neither_diameter_nor_size_is_refused() -> None:
    text = MINIMAL + "\n[[plate.feature]]\nname='f'\nat=['1mm','1mm']\n"
    with pytest.raises(SpecError, match="width is missing"):
        parse_job(text)


def test_a_duplicate_plate_name_is_reported_against_the_job() -> None:
    with pytest.raises(SpecError, match="two plates called"):
        parse_job(MINIMAL + MINIMAL.split("[[plate]]")[1].join(["[[plate]]", ""]))


def test_a_sheet_missing_its_stock_is_refused() -> None:
    text = MINIMAL.replace('name = "J1"', 'name = "J1"\n\n[job.sheet]\nwidth="300mm"')
    with pytest.raises(SpecError, match=r"job.sheet.*stock is missing"):
        parse_job(text)


def test_the_source_name_comes_back_in_the_message() -> None:
    with pytest.raises(SpecError) as caught:
        parse_job("[job]\n", "schedule.toml")
    assert str(caught.value).startswith("schedule.toml [job]")
