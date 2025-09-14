"""The wiring check."""

from __future__ import annotations

import ast

import pytest

from dragpoint.post.base import POSTS
from dragpoint.rules.check import REGISTRY
from dragpoint.tools import check_wiring


def test_nothing_in_the_package_is_unreachable(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_wiring.main() == 0
    assert "clean" in capsys.readouterr().out


def test_the_rule_register_is_not_empty() -> None:
    assert len(REGISTRY) >= 10


def test_the_post_register_is_not_empty() -> None:
    assert len(POSTS) >= 2


def test_every_rule_module_beside_the_register_has_rules_in_it() -> None:
    modules = check_wiring._neighbours("dragpoint.rules")
    assert "dragpoint.rules.legibility" in modules
    assert "dragpoint.rules.fitment" in modules
    assert "dragpoint.rules.process" in modules


def test_imports_are_collected_by_module_and_by_name() -> None:
    tree = ast.parse("from dragpoint.rules import legibility\nimport dragpoint.units\n")
    found = check_wiring._imported_names(tree)
    assert "dragpoint.rules" in found
    assert "dragpoint.rules.legibility" in found
    assert "dragpoint.units" in found


def test_imports_of_other_packages_are_ignored() -> None:
    tree = ast.parse("import click\nfrom pathlib import Path\n")
    assert check_wiring._imported_names(tree) == set()


def test_the_entry_points_are_the_ones_something_outside_runs() -> None:
    assert "dragpoint.cli.main" in check_wiring.ENTRY_POINTS


def test_the_neighbours_of_a_package_leave_out_its_init() -> None:
    modules = check_wiring._neighbours("dragpoint.post")
    assert "dragpoint.post" not in modules
    assert "dragpoint.post.iso" in modules
