"""The job commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from .conftest import EXAMPLE, run


def test_the_shipped_schedule_checks_clean(runner: CliRunner) -> None:
    result = run(runner, "job", "check", str(EXAMPLE))
    assert result.exit_code == 0
    assert "MCC-7" in result.output
    assert "error" not in result.output


def test_every_plate_is_reported(runner: CliRunner) -> None:
    result = run(runner, "job", "check", str(EXAMPLE))
    for name in ("P-101", "P-110", "P-120", "P-130"):
        assert name in result.output


def test_one_plate_can_be_checked_on_its_own(runner: CliRunner) -> None:
    result = run(runner, "job", "check", str(EXAMPLE), "--plate", "P-110")
    assert result.exit_code == 0
    assert "P-110" in result.output
    assert "P-101:" not in result.output


def test_an_unknown_plate_is_a_message(runner: CliRunner) -> None:
    result = run(runner, "job", "check", str(EXAMPLE), "--plate", "P-999")
    assert result.exit_code == 1
    assert "has no plate" in result.output


def test_quiet_says_nothing(runner: CliRunner) -> None:
    result = run(runner, "job", "check", str(EXAMPLE), "--quiet")
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_a_schedule_that_is_not_there_is_a_usage_error(runner: CliRunner) -> None:
    result = run(runner, "job", "check", "no-such-job.toml")
    assert result.exit_code == 2


def test_a_schedule_that_will_not_parse_is_a_message(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not toml = = =", encoding="utf-8")
    result = run(runner, "job", "check", str(bad))
    assert result.exit_code == 1
    assert "not readable as TOML" in result.output


def test_a_job_posts_one_file_a_plate(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "programs"
    result = run(runner, "job", "post", str(EXAMPLE), "--out", str(out))
    assert result.exit_code == 0
    written = sorted(path.name for path in out.iterdir())
    assert written == [
        "P-101.nc",
        "P-102.nc",
        "P-103.nc",
        "P-110.nc",
        "P-111.nc",
        "P-120.nc",
        "P-130.nc",
    ]


def test_every_posted_program_is_a_program(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "programs"
    run(runner, "job", "post", str(EXAMPLE), "--out", str(out))
    for path in out.iterdir():
        text = path.read_text(encoding="utf-8")
        assert text.startswith("%")
        assert "M30" in text


def test_a_posted_program_is_numbered_from_the_job(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "programs"
    run(runner, "job", "post", str(EXAMPLE), "--out", str(out))
    text = (out / "P-101.nc").read_text(encoding="utf-8")
    assert "O1001 (MCC-7 P-101)" in text


def test_a_job_with_errors_is_not_posted(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    out = tmp_path / "programs"
    result = run(runner, "job", "post", str(bad), "--out", str(out))
    assert result.exit_code == 1
    assert "--force" in result.output
    assert not out.exists()


def test_force_posts_a_job_with_errors(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    out = tmp_path / "programs"
    result = run(runner, "job", "post", str(bad), "--out", str(out), "--force")
    assert result.exit_code == 1
    assert (out / "P.nc").is_file()


def test_a_job_is_timed_plate_by_plate(runner: CliRunner) -> None:
    result = run(runner, "job", "time", str(EXAMPLE))
    assert result.exit_code == 0
    assert "P-101" in result.output
    assert "tool changes" in result.output


def test_the_block_time_changes_the_estimate(runner: CliRunner) -> None:
    slow = run(runner, "job", "time", str(EXAMPLE), "--block-time", "0.05")
    fast = run(runner, "job", "time", str(EXAMPLE), "--block-time", "0.0")
    slow_total = float(slow.output.strip().splitlines()[-1].split()[0])
    fast_total = float(fast.output.strip().splitlines()[-1].split()[0])
    assert slow_total > fast_total


def test_a_job_nests_onto_its_sheet(runner: CliRunner) -> None:
    result = run(runner, "job", "nest", str(EXAMPLE))
    assert result.exit_code == 0
    assert "pieces in" in result.output
    assert "all on" in result.output


def test_nesting_can_be_told_not_to_rotate(runner: CliRunner) -> None:
    turned = run(runner, "job", "nest", str(EXAMPLE))
    straight = run(runner, "job", "nest", str(EXAMPLE), "--no-rotate")
    assert turned.exit_code == straight.exit_code == 0
    assert "turned" not in straight.output


def test_a_job_with_no_sheet_cannot_be_nested(runner: CliRunner, tmp_path: Path) -> None:
    plain = tmp_path / "plain.toml"
    plain.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['A']\n",
        encoding="utf-8",
    )
    result = run(runner, "job", "nest", str(plain))
    assert result.exit_code == 1
    assert "does not say what sheet" in result.output


def test_the_summary_says_what_the_job_comes_to(runner: CliRunner) -> None:
    result = run(runner, "job", "summary", str(EXAMPLE))
    assert result.exit_code == 0
    assert "7 plates" in result.output
    assert "cutters V20-010" in result.output
    assert "LAM16-BW" in result.output


def test_the_summary_names_the_plates_that_are_not_ok(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    result = run(runner, "job", "summary", str(bad))
    assert "not ok: P" in result.output


def test_a_job_writes_a_setup_sheet(runner: CliRunner) -> None:
    result = run(runner, "job", "sheet", str(EXAMPLE))
    assert result.exit_code == 0
    assert "SETUP SHEET   MCC-7" in result.output
    assert "nest      " in result.output


def test_the_nest_can_be_left_off_the_sheet(runner: CliRunner) -> None:
    result = run(runner, "job", "sheet", str(EXAMPLE), "--no-nest")
    assert "nest      " not in result.output


def test_a_setup_sheet_can_go_to_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "setup.txt"
    run(runner, "job", "sheet", str(EXAMPLE), "--out", str(target))
    assert "SETUP SHEET" in target.read_text(encoding="utf-8")


def test_a_job_with_no_sheet_still_writes_a_setup_sheet(runner: CliRunner, tmp_path: Path) -> None:
    plain = tmp_path / "plain.toml"
    plain.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['60mm','20mm']\nlines=['A']\n",
        encoding="utf-8",
    )
    result = run(runner, "job", "sheet", str(plain))
    assert result.exit_code == 0
    assert "SETUP SHEET   J" in result.output


def test_a_job_drills_the_plates_that_have_holes(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "drilling"
    result = run(runner, "job", "drill", str(EXAMPLE), "--out", str(out))
    assert result.exit_code == 0
    written = sorted(path.name for path in out.iterdir())
    assert written == ["P-111-drill.nc", "P-120-drill.nc"]
    assert "2 plates have holes" in result.output


def test_the_drilling_programs_are_programs(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "drilling"
    run(runner, "job", "drill", str(EXAMPLE), "--out", str(out))
    text = (out / "P-120-drill.nc").read_text(encoding="utf-8")
    assert text.startswith("%")
    assert "DRILL" in text
    assert "M30" in text


def test_every_plate_can_be_asked_for(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "drilling"
    run(runner, "job", "drill", str(EXAMPLE), "--out", str(out), "--all-plates")
    assert len(list(out.iterdir())) == 7


def test_the_peck_can_be_set_for_a_job(runner: CliRunner, tmp_path: Path) -> None:
    coarse = tmp_path / "coarse"
    fine = tmp_path / "fine"
    run(runner, "job", "drill", str(EXAMPLE), "--out", str(coarse), "--peck", "2mm")
    run(runner, "job", "drill", str(EXAMPLE), "--out", str(fine), "--peck", "0.2mm")
    coarse_lines = len((coarse / "P-120-drill.nc").read_text(encoding="utf-8").splitlines())
    fine_lines = len((fine / "P-120-drill.nc").read_text(encoding="utf-8").splitlines())
    assert fine_lines > coarse_lines


def test_a_job_comes_out_as_json(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "job", "check", "--json", str(EXAMPLE)).output)
    assert payload["job"] == "MCC-7"
    assert payload["pieces"] == 15
    assert payload["ok"] is True
    assert len(payload["plates"]) == 7


def test_one_plate_can_be_asked_for_as_json(runner: CliRunner) -> None:
    payload = json.loads(
        run(runner, "job", "check", "--json", str(EXAMPLE), "--plate", "P-110").output
    )
    assert len(payload["plates"]) == 1
    assert payload["plates"][0]["plate"] == "P-110"


def test_the_job_json_carries_every_plate_in_order(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "job", "check", "--json", str(EXAMPLE)).output)
    assert [plate["plate"] for plate in payload["plates"]][:3] == ["P-101", "P-102", "P-103"]


def test_a_job_with_errors_says_so_in_the_json(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    result = run(runner, "job", "check", "--json", str(bad))
    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["ok"] is False


def test_a_schedule_that_names_a_rule_nobody_has_says_so(runner: CliRunner, tmp_path: Path) -> None:
    schedule = tmp_path / "job.toml"
    schedule.write_text(
        "[job]\nname='J'\n\n[job.rules]\nskip = ['no-such-rule']\n"
        "[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['60mm','20mm']\nlines=['RUN']\n",
        encoding="utf-8",
    )
    result = run(runner, "job", "check", str(schedule))
    assert result.exit_code == 0
    assert "names rules that do not exist" in result.output


def test_a_schedule_can_turn_a_rule_off(runner: CliRunner, tmp_path: Path) -> None:
    body = (
        "[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['60mm','20mm']\nlines=['RUN']\ncap_height='2.7mm'\n"
    )
    loud = tmp_path / "loud.toml"
    loud.write_text("[job]\nname='J'\n" + body, encoding="utf-8")
    quiet = tmp_path / "quiet.toml"
    quiet.write_text(
        "[job]\nname='J'\n\n[job.rules]\nskip = ['odd-lettering-height']\n" + body,
        encoding="utf-8",
    )
    assert "note" in run(runner, "job", "check", str(loud)).output
    assert "note" not in run(runner, "job", "check", str(quiet)).output
