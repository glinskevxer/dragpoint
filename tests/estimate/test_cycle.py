"""Cycle time, and why block time is in it."""

from __future__ import annotations

from typing import Any

import pytest

from dragpoint.compiler.job import compile_job
from dragpoint.compiler.plate import compile_plate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.estimate.cycle import estimate_job, estimate_plate
from dragpoint.spec.job import JobSpec
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


def test_a_plate_takes_a_sensible_number_of_seconds() -> None:
    time = estimate_plate(compile_plate(spec()))
    assert 20.0 < time.total < 200.0
    assert time.minutes == pytest.approx(time.total / 60.0)


def test_the_cutting_time_is_the_cut_length_over_the_feed() -> None:
    made = compile_plate(spec())
    time = estimate_plate(made)
    expected = made.toolpath.cut_length() / made.stock.feed * 60.0
    assert time.cutting == pytest.approx(expected)


def test_the_rapid_time_uses_the_rapid_rate_and_not_the_feed() -> None:
    made = compile_plate(spec())
    slow = estimate_plate(made, setup=MachineSetup(rapid_rate=1000.0))
    fast = estimate_plate(made, setup=MachineSetup(rapid_rate=12000.0))
    assert slow.rapid > fast.rapid
    assert slow.cutting == pytest.approx(fast.cutting)


def test_block_time_is_charged_once_per_move() -> None:
    made = compile_plate(spec())
    time = estimate_plate(made, block_time=0.01)
    assert time.blocks == pytest.approx(len(made.toolpath) * 0.01)


def test_block_time_is_a_large_part_of_a_lettering_job() -> None:
    made = compile_plate(spec())
    time = estimate_plate(made)
    assert time.blocks > 0.0
    assert time.blocks > time.rapid * 0.1


def test_turning_block_time_off_makes_the_estimate_shorter() -> None:
    made = compile_plate(spec())
    assert estimate_plate(made, block_time=0.0).total < estimate_plate(made).total


def test_the_load_time_is_charged_once_a_plate() -> None:
    made = compile_plate(spec())
    with_load = estimate_plate(made, load_time=30.0)
    without = estimate_plate(made, load_time=0.0)
    assert with_load.total - without.total == pytest.approx(30.0)


def test_the_plunge_time_counts_both_ways_at_the_plunge_feed() -> None:
    made = compile_plate(spec())
    time = estimate_plate(made)
    assert time.plunging > 0.0


def test_a_deeper_cut_takes_more_plunging() -> None:
    shallow = estimate_plate(compile_plate(spec(stock="LAM32-RW", depth=0.3)))
    deep = estimate_plate(compile_plate(spec(stock="LAM32-RW", depth=0.9)))
    assert deep.plunging > shallow.plunging


def test_the_air_time_is_everything_that_is_not_cutting() -> None:
    time = estimate_plate(compile_plate(spec()))
    assert time.in_the_air == pytest.approx(time.rapid + time.blocks + time.loading)
    assert time.cutting_fraction < 1.0


def test_a_blank_plate_is_all_loading() -> None:
    time = estimate_plate(compile_plate(spec(lines=())), load_time=20.0)
    assert time.cutting == 0.0
    assert time.total == pytest.approx(20.0)
    assert time.cutting_fraction == 0.0


def test_a_cycle_time_of_nothing_has_no_cutting_fraction() -> None:
    time = estimate_plate(compile_plate(spec(lines=())), load_time=0.0)
    assert time.total == 0.0
    assert time.cutting_fraction == 0.0


@pytest.mark.parametrize(
    ("kwargs", "what"), [({"block_time": -1.0}, "block"), ({"load_time": -1.0}, "load")]
)
def test_a_negative_time_is_refused(kwargs: dict[str, Any], what: str) -> None:
    with pytest.raises(OutOfRange) as caught:
        estimate_plate(compile_plate(spec()), **kwargs)
    assert what in str(caught.value)


def test_str_reads_like_a_line_of_a_quote() -> None:
    text = str(estimate_plate(compile_plate(spec())))
    assert "min" in text
    assert "cutting" in text


def small_job(**overrides: object) -> JobSpec:
    values: dict[str, object] = {
        "name": "J1",
        "plates": (
            spec(name="P-1", lines=("ONE",)),
            spec(name="P-2", lines=("TWO",), quantity=4),
        ),
    }
    values.update(overrides)
    return JobSpec(**values)  # type: ignore[arg-type]


def test_a_job_counts_every_piece() -> None:
    made = compile_job(small_job())
    time = estimate_job(made)
    one = time.for_plate("P-1")
    four = time.for_plate("P-2")
    assert time.machining == pytest.approx(one.total + four.total * 4)


def test_a_job_with_one_cutter_changes_none() -> None:
    time = estimate_job(compile_job(small_job()))
    assert time.tool_changes == 0
    assert time.total == pytest.approx(time.machining)


def test_a_second_cutter_costs_a_change() -> None:
    job = JobSpec(
        name="J1",
        plates=(
            spec(name="P-1", lines=("ONE",)),
            spec(name="P-2", lines=("TWO",), cutter="V60-020"),
        ),
    )
    time = estimate_job(compile_job(job), tool_change_time=60.0)
    assert time.tool_changes == 1
    assert time.total - time.machining == pytest.approx(60.0)


def test_an_unknown_plate_lists_the_ones_in_the_estimate() -> None:
    time = estimate_job(compile_job(small_job()))
    with pytest.raises(KeyError) as caught:
        time.for_plate("P-9")
    assert "P-1" in str(caught.value)


def test_the_slowest_plate_is_findable() -> None:
    job = JobSpec(
        name="J1",
        plates=(
            spec(name="P-short", lines=("I",)),
            spec(name="P-long", lines=("EMERGENCY STOP", "PUSHBUTTON")),
        ),
    )
    assert estimate_job(compile_job(job)).slowest() == "P-long"


def test_an_empty_job_has_nothing_to_be_slowest() -> None:
    time = estimate_job(compile_job(JobSpec(name="empty")))
    assert time.slowest() is None
    assert time.total == 0.0
    assert time.tool_changes == 0


def test_str_says_the_plates_and_the_changes() -> None:
    text = str(estimate_job(compile_job(small_job())))
    assert "2 plates" in text
    assert "tool changes" in text
