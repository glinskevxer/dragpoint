"""The top level group."""

from __future__ import annotations

import click
from click.testing import CliRunner

from dragpoint import __version__
from dragpoint.cli.main import main

from .conftest import run

GROUPS = ("crib", "font", "job", "pack", "plate")


def test_the_root_is_a_group() -> None:
    assert isinstance(main, click.Group)


def test_every_group_is_attached() -> None:
    assert sorted(main.commands) == sorted(GROUPS)


def test_the_pack_command_hangs_off_the_root_rather_than_a_group() -> None:
    assert not isinstance(main.commands["pack"], click.Group)


def test_the_version_option_answers(runner: CliRunner) -> None:
    result = run(runner, "--version")
    assert result.exit_code == 0
    assert __version__ in result.output


def test_the_short_version_flag_answers(runner: CliRunner) -> None:
    assert __version__ in run(runner, "-V").output


def test_the_help_names_every_group(runner: CliRunner) -> None:
    output = run(runner, "--help").output
    for group in GROUPS:
        assert group in output


def test_every_group_has_help_of_its_own(runner: CliRunner) -> None:
    for group in GROUPS:
        result = run(runner, group, "--help")
        assert result.exit_code == 0
        assert "Usage:" in result.output


def every_command() -> list[tuple[str, click.Command]]:
    """Every command the root offers, groups walked into."""
    found: list[tuple[str, click.Command]] = []
    for name in GROUPS:
        entry = main.commands[name]
        if isinstance(entry, click.Group):
            found.extend((name, command) for command in entry.commands.values())
        else:
            found.append(("", entry))
    return found


def test_every_command_has_a_summary_line() -> None:
    for name, command in every_command():
        assert command.help, f"{name} {command.name} has no help"


def test_no_command_help_ends_without_a_full_stop() -> None:
    for name, command in every_command():
        summary = (command.help or "").strip().splitlines()[0]
        assert summary.endswith("."), f"{name} {command.name}: {summary}"


def test_an_unknown_command_is_a_usage_error(runner: CliRunner) -> None:
    result = run(runner, "wibble")
    assert result.exit_code == 2


def test_an_unknown_subcommand_is_a_usage_error(runner: CliRunner) -> None:
    assert run(runner, "plate", "wibble").exit_code == 2


def test_no_arguments_prints_the_help(runner: CliRunner) -> None:
    result = run(runner)
    assert "Usage:" in result.output


def test_the_version_the_command_line_reports_is_the_package_version(runner: CliRunner) -> None:
    from dragpoint import __version__

    result = run(runner, "--version")
    assert __version__ in result.output


def test_the_version_is_the_one_the_packaging_says(runner: CliRunner) -> None:
    import tomllib
    from pathlib import Path

    from dragpoint import __version__

    root = Path(__file__).resolve().parents[2]
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert document["project"]["version"] == __version__
