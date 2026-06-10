"""The check that holds every shipped example to what a real job is held to."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.tools import check_examples


def test_every_shipped_example_is_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_examples.main() == 0
    assert "clean" in capsys.readouterr().out


def test_both_formats_are_picked_up() -> None:
    suffixes = {path.suffix for path in check_examples.examples()}
    assert suffixes == {".toml", ".csv"}


def test_the_gauge_panel_ships() -> None:
    names = {path.name for path in check_examples.examples()}
    assert "gauge-panel-4.toml" in names
    assert "mcc-panel-7.toml" in names


def test_a_schedule_that_will_not_load_is_a_problem(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not toml = = =", encoding="utf-8")
    problems = check_examples.check_example(bad)
    assert len(problems) == 1
    assert "will not load" in problems[0].message


def test_a_schedule_with_an_error_in_it_is_a_problem(tmp_path: Path) -> None:
    bad = tmp_path / "over.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    assert check_examples.check_example(bad)


def test_a_schedule_with_no_plates_is_a_problem(tmp_path: Path) -> None:
    empty = tmp_path / "empty.toml"
    empty.write_text("[job]\nname='J'\n", encoding="utf-8")
    problems = check_examples.check_example(empty)
    assert any("no plates" in problem.message for problem in problems)


def test_a_plate_that_cuts_nothing_is_a_problem(tmp_path: Path) -> None:
    blank = tmp_path / "blank.toml"
    blank.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['60mm','20mm']\nlines=[]\n",
        encoding="utf-8",
    )
    problems = check_examples.check_example(blank)
    assert any("cuts nothing" in problem.message for problem in problems)


def test_a_job_whose_pieces_do_not_fit_its_sheet_is_a_problem(tmp_path: Path) -> None:
    tight = tmp_path / "tight.toml"
    tight.write_text(
        "[job]\nname='J'\n"
        "[job.sheet]\nstock='LAM16-BW'\nwidth='80mm'\nheight='40mm'\n"
        "[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['60mm','20mm']\nlines=['RUN']\nquantity=20\n",
        encoding="utf-8",
    )
    problems = check_examples.check_example(tight)
    assert any("do not fit" in problem.message for problem in problems)


def test_a_warning_is_not_a_problem(tmp_path: Path) -> None:
    warned = tmp_path / "warned.toml"
    warned.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P-1'\nsize=['60mm','20mm']\nlines=['RUN']\n"
        "[[plate]]\nname='P-2'\nsize=['60mm','20mm']\nlines=['RUN']\n",
        encoding="utf-8",
    )
    assert check_examples.check_example(warned) == []


def test_the_check_is_wired_into_the_release_gate() -> None:
    from dragpoint.tools import release_check

    assert "check_examples" in release_check.check_names()


def test_the_check_is_wired_into_ci() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "dragpoint.tools.check_examples" in workflow
