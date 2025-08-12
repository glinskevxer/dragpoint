"""A runner for the command line tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dragpoint.cli.main import main

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mcc-panel-7.toml"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def run(runner: CliRunner, *arguments: str) -> Result:
    """Run the command line and hand back what happened."""
    return runner.invoke(main, list(arguments), catch_exceptions=False)


def lines(result: Result) -> Sequence[str]:
    """The output as lines, blank ones dropped."""
    return [line for line in result.output.splitlines() if line.strip()]
