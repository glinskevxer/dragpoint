"""The font commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dragpoint.font.library import shipped_names
from dragpoint.font.parse import parse_face

from .conftest import lines, run


def test_the_shipped_faces_are_listed(runner: CliRunner) -> None:
    result = run(runner, "font", "list")
    assert result.exit_code == 0
    assert len(lines(result)) == len(shipped_names())
    assert "panelgothic" in result.output


def test_a_face_shows_its_metrics_and_its_coverage(runner: CliRunner) -> None:
    result = run(runner, "font", "show", "panelgothic")
    assert result.exit_code == 0
    assert "upem 1000" in result.output
    assert "cap 700" in result.output
    assert "fallback question" in result.output
    assert " A " in result.output


def test_a_face_shows_as_json(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "font", "show", "panelgothic", "--json").output)
    assert payload["name"] == "panelgothic"
    assert payload["cap_height"] == 700
    assert "A" in payload["names"]
    assert payload["kern_pairs"] > 0


def test_an_unknown_face_is_a_message_and_not_a_traceback(runner: CliRunner) -> None:
    result = run(runner, "font", "show", "nosuchface")
    assert result.exit_code == 1
    assert "no face called" in result.output
    assert "Traceback" not in result.output


def test_a_legend_is_measured(runner: CliRunner) -> None:
    result = run(runner, "font", "measure", "PUMP 2")
    assert result.exit_code == 0
    assert "mm wide at 3mm cap" in result.output


def test_the_cap_height_changes_the_measurement(runner: CliRunner) -> None:
    small = run(runner, "font", "measure", "--cap-height", "2mm", "PUMP")
    large = run(runner, "font", "measure", "--cap-height", "6mm", "PUMP")
    assert float(small.output.split("mm")[0]) < float(large.output.split("mm")[0])


def test_the_measurement_takes_units(runner: CliRunner) -> None:
    result = run(runner, "font", "measure", "--cap-height", "0.125in", "PUMP")
    assert "3.175mm cap" in result.output


def test_characters_the_face_cannot_draw_are_named(runner: CliRunner) -> None:
    result = run(runner, "font", "measure", "45°C")
    assert "cannot draw" in result.output
    assert "'°'" in result.output


def test_a_width_asks_the_fitter_what_it_would_do(runner: CliRunner) -> None:
    result = run(
        runner,
        "font",
        "measure",
        "--cap-height",
        "5mm",
        "--width",
        "40mm",
        "--fit",
        "condense",
        "EMERGENCY STOP",
    )
    assert "fits" in result.output
    assert "condensed" in result.output


def test_a_legend_that_cannot_be_made_to_fit_says_how_far_over(runner: CliRunner) -> None:
    result = run(
        runner,
        "font",
        "measure",
        "--width",
        "5mm",
        "--fit",
        "none",
        "EMERGENCY STOP PUSHBUTTON",
    )
    assert "over by" in result.output


def test_several_lines_measure_the_widest(runner: CliRunner) -> None:
    one = run(runner, "font", "measure", "MMMMMM")
    two = run(runner, "font", "measure", "I", "MMMMMM")
    assert one.output.split()[0] == two.output.split()[0]


def test_a_bad_length_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "font", "measure", "--cap-height", "big", "PUMP")
    assert result.exit_code == 1
    assert "cannot read" in result.output


def test_a_face_dumps_back_out_and_parses_again(runner: CliRunner) -> None:
    result = run(runner, "font", "dump", "panelgothic")
    assert result.exit_code == 0
    again = parse_face(result.output)
    assert again.name == "panelgothic"
    assert "A" in again


def test_a_dump_can_go_to_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "out" / "panelgothic.strk"
    result = run(runner, "font", "dump", "panelgothic", "--out", str(target))
    assert result.exit_code == 0
    assert target.is_file()
    assert parse_face(target.read_text(encoding="utf-8")).name == "panelgothic"


def test_specimen_draws_the_face(runner: CliRunner) -> None:
    result = run(runner, "font", "specimen", "dialface")
    assert result.exit_code == 0
    assert result.output.startswith("<svg")
    assert "dialface" in result.output


def test_specimen_writes_to_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "sheet.svg"
    result = run(runner, "font", "specimen", "panelgothic", "--out", str(target))
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").startswith("<svg")


def test_specimen_takes_the_lettering_height_and_the_groove(runner: CliRunner) -> None:
    result = run(
        runner, "font", "specimen", "dialface", "--cap-height", "12mm", "--groove", "0.8mm"
    )
    assert result.exit_code == 0
    assert 'stroke-width="0.8000"' in result.output


def test_specimen_for_a_face_nobody_has_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "font", "specimen", "nosuchface")
    assert result.exit_code != 0
    assert "no face called" in result.output


def test_specimen_can_leave_the_boxes_off(runner: CliRunner) -> None:
    result = run(runner, "font", "specimen", "dialface", "--no-grid")
    assert result.exit_code == 0
    assert "<rect" not in result.output


def test_the_list_says_which_faces_ship(runner: CliRunner) -> None:
    result = run(runner, "font", "list")
    assert result.exit_code == 0
    assert all(line.endswith("shipped") for line in lines(result))


def test_a_shop_face_is_listed_as_local(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "housecut.strk").write_text(
        "face housecut\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DRAGPOINT_FACES", str(tmp_path))
    result = run(runner, "font", "list")
    assert result.exit_code == 0
    assert any("housecut" in line and line.endswith("local") for line in lines(result))


def test_a_shop_face_can_be_shown_by_name(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "housecut.strk").write_text(
        "face housecut\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DRAGPOINT_FACES", str(tmp_path))
    result = run(runner, "font", "show", "housecut")
    assert result.exit_code == 0
    assert "housecut" in result.output
