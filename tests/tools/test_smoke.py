"""The end to end smoke run."""

from __future__ import annotations

import pytest

from dragpoint.compiler.drill import drill_plate
from dragpoint.compiler.job import compile_job
from dragpoint.estimate.setups import job_work
from dragpoint.geometry.box import Box
from dragpoint.spec.load import load_job
from dragpoint.tools import smoke


def test_the_shipped_job_goes_all_the_way_through(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main([]) == 0
    printed = capsys.readouterr().out
    assert "MCC-7" in printed
    assert "pieces in" in printed
    assert "min for" in printed


def test_quiet_says_nothing_when_it_is_happy(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_the_example_it_runs_is_the_one_that_ships() -> None:
    assert smoke.EXAMPLE.is_file()
    assert smoke.EXAMPLE.name == "mcc-panel-7.toml"


def test_a_problem_is_recorded_when_the_condition_fails() -> None:
    problems: list[str] = []
    smoke._complain(problems, True, "fine")
    assert problems == []
    smoke._complain(problems, False, "not fine")
    assert problems == ["not fine"]


def test_the_slowest_sensible_time_is_a_legend_job_and_not_a_milling_job() -> None:
    assert 1.0 < smoke.SLOWEST_SENSIBLE < 120.0


def test_the_drilling_is_checked_too(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main([]) == 0
    assert "plates drilled" in capsys.readouterr().out


def test_the_run_says_how_long_the_whole_shop_takes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert smoke.main([]) == 0
    assert "min in all" in capsys.readouterr().out


def test_a_drilling_program_off_the_plate_is_caught() -> None:
    problems: list[str] = []
    made = compile_job(load_job(smoke.EXAMPLE))
    outline = made.plates[0].spec.outline()
    assert smoke._inside(outline, made.plates[0].toolpath)
    assert not smoke._inside(Box(0.0, 0.0, 1.0, 1.0), made.plates[0].toolpath)
    assert problems == []


def test_the_setups_add_up_on_the_shipped_job() -> None:
    made = compile_job(load_job(smoke.EXAMPLE))
    drilled, milled = smoke._other_setups([], made)
    work, _ = job_work(made)
    assert sum(item.setups for item in work) == len(made) + drilled + milled


def test_every_plate_that_has_holes_is_counted_once() -> None:
    made = compile_job(load_job(smoke.EXAMPLE))
    drilled, _ = smoke._other_setups([], made)
    assert drilled == len([plate for plate in made if drill_plate(plate.spec).holes])
