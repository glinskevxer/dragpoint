"""The architecture page."""

from __future__ import annotations

import pytest

from dragpoint.tools import build_architecture
from dragpoint.tools.check_layers import RANKS
from dragpoint.tools.support import DOCS


def page() -> str:
    return (DOCS / "architecture.md").read_text(encoding="utf-8")


def test_the_page_is_up_to_date(capsys: pytest.CaptureFixture[str]) -> None:
    assert build_architecture.main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_every_layer_is_on_the_page() -> None:
    text = page()
    for layer in RANKS:
        assert f"`dragpoint.{layer}`" in text


def test_the_layers_are_listed_bottom_up() -> None:
    text = page()
    positions = [(text.index(f"| `dragpoint.{layer}` |"), rank) for layer, rank in RANKS.items()]
    ordered = [rank for _, rank in sorted(positions)]
    assert ordered == sorted(ordered)


def test_a_layer_brings_its_own_docstring_with_it() -> None:
    assert "Plane geometry, in millimetres" in page()


def test_a_top_level_module_is_described_too() -> None:
    assert "The exceptions dragpoint raises" in page()


def test_the_docstring_is_the_first_paragraph_and_no_more() -> None:
    summary = build_architecture._docstring_for("geometry")
    assert summary.endswith("above it.")
    assert "\n" not in summary


def test_a_layer_that_is_not_there_has_no_docstring() -> None:
    assert build_architecture._docstring_for("nosuchlayer") == ""


def test_the_modules_in_a_layer_are_listed() -> None:
    modules = build_architecture._modules_in("geometry")
    assert "point" in modules
    assert "__init__" not in modules
    assert modules == sorted(modules)


def test_a_layer_with_no_directory_lists_nothing() -> None:
    assert build_architecture._modules_in("units") == []


def test_the_page_names_the_check_that_enforces_it() -> None:
    assert "check_layers" in page()
