"""The one command that writes the whole job pack."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from .conftest import EXAMPLE, run


def packed(runner: CliRunner, out: Path, *extra: str) -> list[str]:
    result = run(runner, "pack", str(EXAMPLE), "--out", str(out), *extra)
    assert result.exit_code == 0, result.output
    return sorted(str(path.relative_to(out)).replace("\\", "/") for path in out.rglob("*.*"))


def test_the_pack_has_a_program_for_every_plate(runner: CliRunner, tmp_path: Path) -> None:
    files = packed(runner, tmp_path / "pack")
    assert "programs/P-101.nc" in files
    assert len([name for name in files if name.startswith("programs/")]) == 7


def test_the_pack_drills_the_plates_that_have_holes(runner: CliRunner, tmp_path: Path) -> None:
    files = packed(runner, tmp_path / "pack")
    drilling = [name for name in files if name.startswith("drilling/")]
    assert drilling == ["drilling/P-111.nc", "drilling/P-120.nc"]


def test_the_pack_draws_every_plate(runner: CliRunner, tmp_path: Path) -> None:
    files = packed(runner, tmp_path / "pack")
    assert len([name for name in files if name.startswith("drawings/")]) == 7


def test_the_drawings_can_be_left_out(runner: CliRunner, tmp_path: Path) -> None:
    files = packed(runner, tmp_path / "pack", "--no-drawings")
    assert not [name for name in files if name.startswith("drawings/")]


def test_the_pack_carries_the_paperwork(runner: CliRunner, tmp_path: Path) -> None:
    files = packed(runner, tmp_path / "pack")
    assert "setup.txt" in files
    assert "travellers.txt" in files


def test_the_pack_draws_the_nest_when_the_job_names_a_sheet(
    runner: CliRunner, tmp_path: Path
) -> None:
    assert "nest.svg" in packed(runner, tmp_path / "pack")


def test_the_setup_sheet_in_the_pack_is_the_setup_sheet(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "pack"
    packed(runner, out)
    assert "SETUP SHEET   MCC-7" in (out / "setup.txt").read_text(encoding="utf-8")


def test_the_travellers_in_the_pack_are_one_per_plate(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "pack"
    packed(runner, out)
    assert (out / "travellers.txt").read_text(encoding="utf-8").count("TRAVELLER") == 7


def test_the_programs_are_numbered_from_the_job(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "pack"
    packed(runner, out)
    assert "O1001 (MCC-7 P-101)" in (out / "programs" / "P-101.nc").read_text(encoding="utf-8")


def test_a_job_with_errors_writes_nothing(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    out = tmp_path / "pack"
    result = run(runner, "pack", str(bad), "--out", str(out))
    assert result.exit_code == 1
    assert "--force" in result.output
    assert not out.exists()


def test_force_writes_the_pack_anyway(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['20mm','10mm']\nlines=['EMERGENCY STOP']\nfit='none'\n",
        encoding="utf-8",
    )
    out = tmp_path / "pack"
    result = run(runner, "pack", str(bad), "--out", str(out), "--force")
    assert result.exit_code == 1
    assert (out / "programs" / "P.nc").is_file()


def test_a_job_with_no_sheet_packs_without_a_nest(runner: CliRunner, tmp_path: Path) -> None:
    plain = tmp_path / "plain.toml"
    plain.write_text(
        "[job]\nname='J'\n[defaults]\nstock='LAM16-BW'\n"
        "[[plate]]\nname='P'\nsize=['60mm','20mm']\nlines=['RUN']\n",
        encoding="utf-8",
    )
    out = tmp_path / "pack"
    result = run(runner, "pack", str(plain), "--out", str(out))
    assert result.exit_code == 0
    assert not (out / "nest.svg").exists()
    assert (out / "setup.txt").is_file()


def test_the_command_says_how_many_files_it_wrote(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "pack"
    result = run(runner, "pack", str(EXAMPLE), "--out", str(out))
    assert "19 files" in result.output


def test_a_schedule_that_is_not_there_is_a_usage_error(runner: CliRunner, tmp_path: Path) -> None:
    result = run(runner, "pack", "no-such-job.toml", "--out", str(tmp_path / "pack"))
    assert result.exit_code == 2
