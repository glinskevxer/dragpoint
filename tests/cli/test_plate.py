"""The single plate commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from .conftest import run


def test_a_good_plate_checks_clean_and_exits_zero(runner: CliRunner) -> None:
    result = run(runner, "plate", "check", "PUMP 2", "RUN")
    assert result.exit_code == 0
    assert "no violations" in result.output


def test_a_plate_with_an_error_exits_one(runner: CliRunner) -> None:
    result = run(
        runner, "plate", "check", "--fit", "none", "--size", "20x10mm", "EMERGENCY STOP PUSHBUTTON"
    )
    assert result.exit_code == 1
    assert "error" in result.output


def test_quiet_says_nothing_and_still_sets_the_code(runner: CliRunner) -> None:
    result = run(
        runner,
        "plate",
        "check",
        "--quiet",
        "--fit",
        "none",
        "--size",
        "20x10mm",
        "EMERGENCY STOP PUSHBUTTON",
    )
    assert result.exit_code == 1
    assert result.output.strip() == ""


def test_a_warning_does_not_fail_the_command(runner: CliRunner) -> None:
    result = run(runner, "plate", "check", "--cap-height", "2.7mm", "RUN")
    assert result.exit_code == 0
    assert "note" in result.output


def test_the_size_option_takes_a_unit_on_the_pair(runner: CliRunner) -> None:
    result = run(runner, "plate", "check", "--size", "2x1in", "RUN")
    assert result.exit_code == 0


def test_a_size_that_is_not_a_size_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "plate", "check", "--size", "wide", "RUN")
    assert result.exit_code == 1
    assert "not a size" in result.output


def test_an_unknown_stock_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "plate", "check", "--stock", "NOPE", "RUN")
    assert result.exit_code == 1
    assert "no stock called" in result.output


def test_an_unknown_cutter_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "plate", "check", "--cutter", "V99-999", "RUN")
    assert result.exit_code == 1
    assert "no cutter called" in result.output


def test_a_plate_posts_to_g_code_on_standard_output(runner: CliRunner) -> None:
    result = run(runner, "plate", "post", "RUN")
    assert result.exit_code == 0
    assert result.output.startswith("%")
    assert "M30" in result.output


def test_the_post_can_be_chosen(runner: CliRunner) -> None:
    result = run(runner, "plate", "post", "--post", "plotter", "RUN")
    assert result.output.startswith("IN;")


def test_a_posted_program_carries_the_cutter_and_the_stock(runner: CliRunner) -> None:
    result = run(runner, "plate", "post", "--name", "P-9", "RUN")
    assert "(P-9)" in result.output
    assert "V30-015 in LAM16-BW" in result.output


def test_line_numbers_can_be_asked_for(runner: CliRunner) -> None:
    assert "N10 " in run(runner, "plate", "post", "--line-numbers", "RUN").output


def test_a_plate_with_errors_is_not_posted(runner: CliRunner) -> None:
    result = run(
        runner, "plate", "post", "--fit", "none", "--size", "20x10mm", "EMERGENCY STOP PUSHBUTTON"
    )
    assert result.exit_code == 1
    assert "--force" in result.output
    assert "M30" not in result.output


def test_force_posts_it_anyway(runner: CliRunner) -> None:
    result = run(
        runner,
        "plate",
        "post",
        "--force",
        "--fit",
        "none",
        "--size",
        "20x10mm",
        "EMERGENCY STOP PUSHBUTTON",
    )
    assert "M30" in result.output
    assert result.exit_code == 1


def test_a_program_can_go_to_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "P-9.nc"
    result = run(runner, "plate", "post", "--out", str(target), "RUN")
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").startswith("%")


def test_a_plate_draws_an_svg(runner: CliRunner) -> None:
    result = run(runner, "plate", "draw", "RUN")
    assert result.output.startswith("<svg")
    assert "</svg>" in result.output


def test_a_plate_draws_a_dxf(runner: CliRunner) -> None:
    result = run(runner, "plate", "draw", "--format", "dxf", "RUN")
    assert "SECTION" in result.output
    assert result.output.rstrip().endswith("EOF")


def test_the_travel_can_be_drawn(runner: CliRunner) -> None:
    plain = run(runner, "plate", "draw", "PUMP 2", "RUN")
    with_travel = run(runner, "plate", "draw", "--travel", "PUMP 2", "RUN")
    assert "<path" not in plain.output
    assert "<path" in with_travel.output


def test_a_drawing_can_go_to_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "P-9.svg"
    run(runner, "plate", "draw", "--out", str(target), "RUN")
    assert target.read_text(encoding="utf-8").startswith("<svg")


def test_a_plate_is_timed(runner: CliRunner) -> None:
    result = run(runner, "plate", "time", "PUMP 2", "RUN")
    assert result.exit_code == 0
    assert "min" in result.output
    assert "passes" in result.output


def test_turning_the_optimiser_off_lengthens_the_travel(runner: CliRunner) -> None:
    tidy = run(runner, "plate", "time", "PUMP 2", "RUN")
    plain = run(runner, "plate", "time", "--no-optimise", "PUMP 2", "RUN")
    tidy_travel = float(tidy.output.split("travel ")[1].split("mm")[0])
    plain_travel = float(plain.output.split("travel ")[1].split("mm")[0])
    assert tidy_travel <= plain_travel


def test_a_blank_plate_still_works(runner: CliRunner) -> None:
    result = run(runner, "plate", "check")
    assert result.exit_code == 0
    assert "0 strokes" in result.output


def test_a_plate_with_no_holes_drills_an_empty_program(runner: CliRunner) -> None:
    result = run(runner, "plate", "drill", "--size", "60x20mm")
    assert result.exit_code == 0
    assert "\n%\n" in result.output
    assert "M30" in result.output
    assert "G01" not in result.output


def test_the_drilling_says_what_it_is_doing(runner: CliRunner) -> None:
    result = run(runner, "plate", "drill", "--size", "60x20mm")
    assert "nothing to drill" in result.output


def test_the_drill_program_can_go_to_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "P-9-drill.nc"
    result = run(runner, "plate", "drill", "--out", str(target), "--size", "60x20mm")
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").startswith("%")


def test_the_peck_can_be_set(runner: CliRunner) -> None:
    fine = run(runner, "plate", "drill", "--peck", "0.2mm", "--size", "60x20mm")
    assert fine.exit_code == 0


def test_a_plate_comes_out_as_json(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "plate", "check", "--json", "PUMP 2", "RUN").output)
    assert payload["plate"] == "PLATE"
    assert payload["stock"] == "LAM16-BW"
    assert payload["cutter"] == "V30-015"
    assert payload["lines"] == ["PUMP 2", "RUN"]
    assert payload["ok"] is True
    assert payload["violations"] == []


def test_the_json_carries_the_numbers_a_script_would_want(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "plate", "check", "--json", "RUN").output)
    assert payload["groove"] > payload["depth"] * 0.0
    assert payload["cut_length"] > 0.0
    assert payload["passes"] >= 1


def test_the_json_carries_the_violations(runner: CliRunner) -> None:
    result = run(
        runner,
        "plate",
        "check",
        "--json",
        "--fit",
        "none",
        "--size",
        "20x10mm",
        "EMERGENCY STOP PUSHBUTTON",
    )
    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["ok"] is False
    assert any(item["severity"] == "error" for item in payload["violations"])


def test_the_json_reports_the_lines_that_were_actually_set(runner: CliRunner) -> None:
    result = run(
        runner,
        "plate",
        "check",
        "--json",
        "--wrap",
        "--size",
        "40x40mm",
        "ISOLATE BEFORE WORKING ON THIS PANEL",
    )
    payload = json.loads(result.output)
    assert len(payload["lines"]) > 1


def test_a_fixture_of_blanks_posts_as_one_subprogram(runner: CliRunner) -> None:
    result = run(
        runner, "plate", "post", "--size", "60x20mm", "--repeats", "4", "--pitch", "65mm", "RUN"
    )
    assert result.exit_code == 0
    assert result.output.count("M98") == 4
    assert result.output.count("O1001") == 1


def test_a_fixture_with_no_pitch_is_a_message_and_not_a_traceback(runner: CliRunner) -> None:
    result = run(runner, "plate", "post", "--size", "60x20mm", "--repeats", "4", "RUN")
    assert result.exit_code != 0
    assert "same blank" in result.output


def test_the_fixture_can_step_in_y(runner: CliRunner) -> None:
    result = run(
        runner, "plate", "post", "--size", "60x20mm", "--repeats", "2", "--pitch-y", "25mm", "RUN"
    )
    assert result.exit_code == 0
    assert "G52 X0.0000 Y25.0000" in result.output


def test_cutout_posts_a_window_program(runner: CliRunner) -> None:
    result = run(
        runner,
        "plate",
        "cutout",
        "--size",
        "120x60mm",
        "--stock",
        "LAM32-RW",
        "--window",
        "40x20mm@60,30mm",
        "METER",
    )
    assert result.exit_code == 0
    assert "G01" in result.output


def test_cutout_on_a_plate_with_no_windows_posts_an_empty_program(runner: CliRunner) -> None:
    result = run(runner, "plate", "cutout", "--size", "60x20mm", "RUN")
    assert result.exit_code == 0
    assert "nothing to mill" in result.output


def test_figures_can_be_set_on_one_pitch(runner: CliRunner) -> None:
    plain = run(runner, "plate", "draw", "--size", "60x20mm", "--face", "dialface", "111")
    tabular = run(
        runner, "plate", "draw", "--size", "60x20mm", "--face", "dialface", "--tabular", "100"
    )
    assert plain.exit_code == tabular.exit_code == 0
    assert plain.output != tabular.output


def test_the_datum_can_be_chosen_on_the_command_line(runner: CliRunner) -> None:
    result = run(runner, "plate", "post", "--size", "60x20mm", "--work-offset", "56", "RUN")
    assert result.exit_code == 0
    assert "G56" in result.output


def test_a_datum_the_control_does_not_have_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "plate", "post", "--size", "60x20mm", "--work-offset", "99", "RUN")
    assert result.exit_code != 0
    assert "not a work offset" in result.output
