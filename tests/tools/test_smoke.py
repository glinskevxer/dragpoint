"""The end to end smoke run."""

from __future__ import annotations

import pytest

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
