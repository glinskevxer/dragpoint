"""The layer check."""

from __future__ import annotations

import ast

import pytest

from dragpoint.tools import check_layers
from dragpoint.tools.support import PACKAGE


def test_the_package_keeps_its_own_layering(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_layers.main() == 0
    assert "clean" in capsys.readouterr().out


def test_every_package_directory_has_a_rank() -> None:
    directories = {
        path.name
        for path in PACKAGE.iterdir()
        if path.is_dir() and path.name != "__pycache__" and (path / "__init__.py").is_file()
    }
    assert directories <= set(check_layers.RANKS)


def test_every_top_level_module_has_a_rank() -> None:
    modules = {path.stem for path in PACKAGE.glob("*.py") if path.name not in {"__init__.py"}}
    assert modules <= set(check_layers.RANKS)


def test_geometry_is_below_everything_that_uses_it() -> None:
    ranks = check_layers.RANKS
    assert ranks["errors"] < ranks["units"] < ranks["geometry"]
    assert ranks["geometry"] < ranks["font"] < ranks["text"]
    assert ranks["text"] < ranks["spec"] < ranks["rules"]
    assert ranks["compiler"] < ranks["draw"]
    assert ranks["cli"] > max(ranks[name] for name in ranks if name not in {"cli", "tools"})


def test_a_dotted_name_maps_to_its_layer() -> None:
    assert check_layers._package_of("dragpoint.geometry.point") == "geometry"
    assert check_layers._package_of("dragpoint.units") == "units"
    assert check_layers._package_of("dragpoint") is None
    assert check_layers._package_of("click") is None


def test_a_file_maps_to_its_own_layer() -> None:
    assert check_layers._own_layer(PACKAGE / "units.py") == "units"
    assert check_layers._own_layer(PACKAGE / "geometry" / "point.py") == "geometry"
    assert check_layers._own_layer(PACKAGE / "__init__.py") is None


def test_both_import_forms_are_seen() -> None:
    tree = ast.parse("import dragpoint.units\nfrom dragpoint.geometry import Point\n")
    found = {name for _, name in check_layers._imports(tree)}
    assert found == {"dragpoint.units", "dragpoint.geometry"}


def test_a_relative_import_is_not_counted() -> None:
    tree = ast.parse("from . import thing\n")
    assert check_layers._imports(tree) == []
