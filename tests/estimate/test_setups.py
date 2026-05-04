"""Timing every setup a plate goes through, not just the lettering."""

from __future__ import annotations

import pytest

from dragpoint.compiler.job import compile_job
from dragpoint.compiler.plate import compile_plate
from dragpoint.estimate.setups import job_work, plate_work
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature
from dragpoint.spec.job import JobSpec
from dragpoint.spec.plate import PlateSpec

HOLES = (
    Feature.round_hole("fix-left", Point(8.0, 10.0), 4.2),
    Feature.round_hole("fix-right", Point(112.0, 10.0), 4.2),
)

WINDOW = (Feature.rectangle("meter", Point(60.0, 14.0), 40.0, 16.0),)


def spec(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-1",
        "width": 120.0,
        "height": 60.0,
        "stock": "LAM32-RW",
        "lines": ("METER",),
        "cap_height": 4.0,
        "margin": 3.0,
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def test_a_plain_plate_is_one_setup() -> None:
    made = plate_work(compile_plate(spec()))
    assert made.setups == 1
    assert made.drilling is None
    assert made.milling is None


def test_a_plate_with_holes_is_two_setups() -> None:
    made = plate_work(compile_plate(spec(features=HOLES)))
    assert made.setups == 2
    assert made.drilling is not None


def test_a_plate_with_a_window_is_two_setups() -> None:
    made = plate_work(compile_plate(spec(features=WINDOW)))
    assert made.setups == 2
    assert made.milling is not None


def test_a_plate_with_both_is_three_setups() -> None:
    made = plate_work(compile_plate(spec(features=(*HOLES, *WINDOW))))
    assert made.setups == 3


def test_the_drilling_takes_time() -> None:
    made = plate_work(compile_plate(spec(features=HOLES)))
    assert made.drilling is not None
    assert made.drilling.total > 0.0


def test_the_drilling_is_mostly_plunging() -> None:
    made = plate_work(compile_plate(spec(features=HOLES)))
    assert made.drilling is not None
    assert made.drilling.plunging > made.drilling.cutting


def test_the_milling_takes_longer_than_the_lettering_on_this_plate() -> None:
    made = plate_work(compile_plate(spec(features=WINDOW)))
    assert made.milling is not None
    assert made.milling.total > made.engraving.total


def test_the_time_for_one_piece_adds_the_setups_up() -> None:
    made = plate_work(compile_plate(spec(features=(*HOLES, *WINDOW))))
    assert made.drilling is not None
    assert made.milling is not None
    assert made.each == pytest.approx(
        made.engraving.total + made.drilling.total + made.milling.total
    )


def test_the_quantity_multiplies_the_whole_thing() -> None:
    one = plate_work(compile_plate(spec(features=HOLES)))
    ten = plate_work(compile_plate(spec(features=HOLES, quantity=10)))
    assert ten.total == pytest.approx(10.0 * one.total)


def test_the_minutes_are_the_seconds_over_sixty() -> None:
    made = plate_work(compile_plate(spec(features=HOLES)))
    assert made.minutes == pytest.approx(made.total / 60.0)


def test_a_plate_reads_like_a_line_on_a_quote() -> None:
    made = plate_work(compile_plate(spec(features=HOLES, quantity=4)))
    assert "P-1 x4" in str(made)
    assert "2 setups" in str(made)


def test_one_setup_is_written_in_the_singular() -> None:
    assert "1 setup" in str(plate_work(compile_plate(spec())))


def test_a_job_is_timed_plate_by_plate() -> None:
    job = JobSpec(
        name="J",
        plates=(spec(name="P-1"), spec(name="P-2", features=HOLES)),
    )
    work, shop = job_work(compile_job(job))
    assert [item.name for item in work] == ["P-1", "P-2"]
    assert shop > 0.0


def test_the_shop_total_counts_a_tool_change_for_every_extra_setup() -> None:
    job = JobSpec(name="J", plates=(spec(name="P-1", features=HOLES),))
    made = compile_job(job)
    work, shop = job_work(made, tool_change_time=100.0)
    _, without = job_work(made, tool_change_time=0.0)
    assert shop - without == pytest.approx(100.0 * sum(item.setups - 1 for item in work))


def test_a_job_of_plain_plates_needs_no_extra_tool_changes() -> None:
    job = JobSpec(name="J", plates=(spec(name="P-1"),))
    made = compile_job(job)
    _, with_change = job_work(made, tool_change_time=100.0)
    _, without = job_work(made, tool_change_time=0.0)
    assert with_change == pytest.approx(without)


def test_a_longer_block_time_makes_every_setup_longer() -> None:
    made = compile_plate(spec(features=HOLES))
    quick = plate_work(made, block_time=0.0)
    slow = plate_work(made, block_time=0.05)
    assert slow.each > quick.each
