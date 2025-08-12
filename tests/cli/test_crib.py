"""The crib commands, and the top level group."""

from __future__ import annotations

import json

from click.testing import CliRunner

from dragpoint import __version__
from dragpoint.post.base import POSTS
from dragpoint.rules.check import REGISTRY
from dragpoint.tool.cutter import CATALOGUE
from dragpoint.tool.material import MATERIALS

from .conftest import lines, run


def test_the_version_is_the_package_version(runner: CliRunner) -> None:
    result = run(runner, "--version")
    assert result.exit_code == 0
    assert __version__ in result.output


def test_the_help_lists_every_group(runner: CliRunner) -> None:
    result = run(runner, "--help")
    for group in ("crib", "font", "job", "plate"):
        assert group in result.output


def test_short_help_works_too(runner: CliRunner) -> None:
    assert run(runner, "-h").exit_code == 0


def test_the_cutters_are_listed(runner: CliRunner) -> None:
    result = run(runner, "crib", "cutters")
    assert result.exit_code == 0
    assert len(lines(result)) == len(CATALOGUE)
    assert "V30-015" in result.output


def test_the_cutters_come_out_as_json_too(runner: CliRunner) -> None:
    result = run(runner, "crib", "cutters", "--json")
    payload = json.loads(result.output)
    assert set(payload) == set(CATALOGUE)
    assert payload["V30-015"]["tip_width"] == 0.381
    assert payload["P-020"]["parallel"] is True


def test_the_stock_is_listed_with_its_window(runner: CliRunner) -> None:
    result = run(runner, "crib", "stock")
    assert result.exit_code == 0
    assert len(lines(result)) == len(MATERIALS)
    assert "LAM16-BW" in result.output
    assert "black on white laminate" in result.output


def test_the_stock_json_carries_the_window(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "crib", "stock", "--json").output)
    assert payload["LAM16-BW"]["window"] == list(MATERIALS["LAM16-BW"].depth_window())
    assert payload["ACRYL-30"]["cap"] is None


def test_the_posts_are_listed(runner: CliRunner) -> None:
    result = run(runner, "crib", "posts")
    assert len(lines(result)) == len(POSTS)
    assert "iso (.nc)" in result.output
    assert "plotter (.plt)" in result.output


def test_the_rules_are_listed_in_registration_order(runner: CliRunner) -> None:
    result = run(runner, "crib", "rules")
    printed = [line.split()[0] for line in lines(result)]
    assert printed == list(REGISTRY)


def test_the_rules_json_carries_the_severity(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "crib", "rules", "--json").output)
    assert payload["stroke-merge"]["severity"] == "error"
    assert payload["odd-lettering-height"]["severity"] == "note"
