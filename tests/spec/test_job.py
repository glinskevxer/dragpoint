"""The job spec: one setup, one cutter, many plates."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.plate import PlateSpec


def plate(name: str = "P-101", **overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": name,
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("RUN",),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def sheet() -> Sheet:
    return Sheet(stock="LAM16-BW", width=300.0, height=600.0)


def test_a_sheet_reports_the_area_inside_the_clamps() -> None:
    assert sheet().usable_width == 290.0
    assert sheet().usable_height == 590.0
    assert sheet().usable_area == pytest.approx(290.0 * 590.0)


@pytest.mark.parametrize(
    ("overrides", "what"),
    [
        ({"width": 0.0}, "sheet width"),
        ({"height": 0.0}, "sheet height"),
        ({"margin": -1.0}, "sheet margin"),
        ({"kerf": -1.0}, "kerf"),
        ({"margin": 200.0}, "sheet margin"),
    ],
)
def test_an_impossible_sheet_is_refused(overrides: dict[str, object], what: str) -> None:
    values: dict[str, object] = {
        "stock": "LAM16-BW",
        "width": 300.0,
        "height": 600.0,
        "margin": 5.0,
        "kerf": 1.5,
    }
    values.update(overrides)
    with pytest.raises(OutOfRange) as caught:
        Sheet(**values)  # type: ignore[arg-type]
    assert what in str(caught.value)


def test_a_job_needs_a_name() -> None:
    with pytest.raises(ValueError, match="needs a name"):
        JobSpec(name="")


def test_two_plates_with_the_same_name_are_refused() -> None:
    with pytest.raises(ValueError, match="two plates called"):
        JobSpec(name="J1", plates=(plate("P-101"), plate("P-101")))


def test_a_negative_job_depth_is_refused() -> None:
    with pytest.raises(OutOfRange, match="depth"):
        JobSpec(name="J1", depth=0.0)


def test_plate_lookup() -> None:
    job = JobSpec(name="J1", plates=(plate("P-101"), plate("P-102")))
    assert job.plate("P-102").name == "P-102"


def test_an_unknown_plate_lists_the_ones_that_are_there() -> None:
    job = JobSpec(name="J1", plates=(plate("P-101"),))
    with pytest.raises(KeyError) as caught:
        job.plate("P-999")
    assert "P-101" in str(caught.value)


def test_an_empty_job_says_none() -> None:
    with pytest.raises(KeyError, match="none"):
        JobSpec(name="J1").plate("P-101")


def test_the_job_cutter_applies_unless_a_plate_names_its_own() -> None:
    job = JobSpec(name="J1", plates=(plate("P-101"), plate("P-102", cutter="V60-020")))
    assert job.cutter_for(job.plate("P-101")) == "V30-015"
    assert job.cutter_for(job.plate("P-102")) == "V60-020"


def test_the_depth_falls_through_plate_then_job_then_nothing() -> None:
    job = JobSpec(name="J1", plates=(plate("P-101"), plate("P-102", depth=0.4)), depth=0.3)
    assert job.depth_for(job.plate("P-101")) == 0.3
    assert job.depth_for(job.plate("P-102")) == 0.4
    bare = JobSpec(name="J2", plates=(plate("P-101"),))
    assert bare.depth_for(bare.plate("P-101")) is None


def test_stock_codes_are_sorted_and_deduped() -> None:
    job = JobSpec(
        name="J1",
        plates=(plate("P-101"), plate("P-102", stock="LAM32-RW"), plate("P-103")),
        sheet=sheet(),
    )
    assert job.stock_codes() == ("LAM16-BW", "LAM32-RW")


def test_stock_codes_include_the_sheet_even_with_no_plates() -> None:
    assert JobSpec(name="J1", sheet=sheet()).stock_codes() == ("LAM16-BW",)


def test_cutter_codes_cover_every_override() -> None:
    job = JobSpec(name="J1", plates=(plate("P-101"), plate("P-102", cutter="V60-020")))
    assert job.cutter_codes() == ("V30-015", "V60-020")


def test_a_job_with_no_plates_still_needs_its_cutter() -> None:
    assert JobSpec(name="J1").cutter_codes() == ("V30-015",)


def test_the_piece_count_counts_quantities() -> None:
    job = JobSpec(name="J1", plates=(plate("P-101", quantity=4), plate("P-102", quantity=6)))
    assert len(job) == 2
    assert job.piece_count == 10


def test_str_says_plates_and_pieces() -> None:
    job = JobSpec(name="PANEL-7", plates=(plate("P-101", quantity=3),))
    assert str(job) == "PANEL-7: 1 plates, 3 pieces"
    assert str(sheet()) == "LAM16-BW 300x600mm"


def test_a_job_names_no_rules_unless_it_says_so() -> None:
    job = JobSpec(name="J1")
    assert job.rules_only == ()
    assert job.rules_skip == ()
    assert job.rules_severity == {}
    assert job.mentions_rules() == ()


def test_every_rule_a_job_names_is_listed_once_and_sorted() -> None:
    job = JobSpec(
        name="J1",
        rules_only=("stroke-merge",),
        rules_skip=("letter-weight", "stroke-merge"),
        rules_severity={"stroke-stub": "error"},
    )
    assert job.mentions_rules() == ("letter-weight", "stroke-merge", "stroke-stub")


def test_the_names_are_not_checked_against_the_register() -> None:
    job = JobSpec(name="J1", rules_skip=("no-such-rule",))
    assert job.mentions_rules() == ("no-such-rule",)
