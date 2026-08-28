"""Running the package as a module."""

from __future__ import annotations

import subprocess
import sys

from dragpoint import __version__
from dragpoint.__main__ import main


def run_module(*arguments: str) -> subprocess.CompletedProcess[str]:
    """The package run the way a shop terminal runs it."""
    return subprocess.run(
        [sys.executable, "-m", "dragpoint", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_module_is_the_command_line() -> None:
    from dragpoint.cli.main import main as command_line

    assert main is command_line


def test_the_module_runs_and_says_what_it_is() -> None:
    finished = run_module("--version")
    assert finished.returncode == 0
    assert __version__ in finished.stdout


def test_the_module_prints_help() -> None:
    finished = run_module("--help")
    assert finished.returncode == 0
    assert "Compile legend plate artwork" in finished.stdout


def test_a_command_works_through_the_module() -> None:
    finished = run_module("crib", "posts")
    assert finished.returncode == 0
    assert "iso" in finished.stdout


def test_an_unknown_command_is_a_usage_error_through_the_module() -> None:
    assert run_module("wibble").returncode == 2
