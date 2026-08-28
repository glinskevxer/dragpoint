"""The crib commands, and the top level group."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def test_the_rack_can_come_from_a_file(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "rack.toml"
    target.write_text(
        "[SHOP-10]\n"
        'description = "shop laminate"\n'
        "thickness = 1.0\n"
        "cap = 0.1\n"
        "nominal = 0.2\n"
        "per_pass = 0.3\n"
        "feed = 900.0\n"
        "plunge = 200.0\n"
        "spindle = 11000\n",
        encoding="utf-8",
    )
    result = run(runner, "crib", "stock", "--rack", str(target))
    assert result.exit_code == 0
    assert len(lines(result)) == 1
    assert "SHOP-10" in result.output
    assert "shop laminate" in result.output


def test_a_rack_file_that_is_wrong_is_a_message_and_not_a_traceback(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "rack.toml"
    target.write_text("", encoding="utf-8")
    result = run(runner, "crib", "stock", "--rack", str(target))
    assert result.exit_code != 0
    assert "no stock in this file" in result.output


def test_about_says_what_the_installation_is(runner: CliRunner) -> None:
    result = run(runner, "crib", "about")
    assert result.exit_code == 0
    assert __version__ in result.output
    assert "rack" in result.output
    assert "panelgothic" in result.output


def test_about_says_where_the_rack_came_from(runner: CliRunner) -> None:
    result = run(runner, "crib", "about")
    assert "rack.toml" in result.output
    assert f"{len(MATERIALS)} stocks" in result.output


def test_about_says_the_face_path_is_not_set_when_it_is_not(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DRAGPOINT_FACES", raising=False)
    assert "not set" in run(runner, "crib", "about").output


def test_about_names_the_shop_faces_when_there_are_some(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "housecut.strk").write_text(
        "face housecut\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DRAGPOINT_FACES", str(tmp_path))
    result = run(runner, "crib", "about")
    assert "housecut" in result.output
    assert str(tmp_path) in result.output


def test_about_can_come_out_as_json(runner: CliRunner) -> None:
    payload = json.loads(run(runner, "crib", "about", "--json").output)
    assert payload["version"] == __version__
    assert payload["stock"] == len(MATERIALS)
    assert "iso" in payload["posts"]
    assert payload["rules"] > 0
