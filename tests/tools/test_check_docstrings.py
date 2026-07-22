"""The docstring check, and the support the checks share."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dragpoint.tools import check_docstrings
from dragpoint.tools.support import (
    DOCS,
    PACKAGE,
    ROOT,
    TESTS,
    Problem,
    dotted_name,
    parsed,
    report,
    source_files,
)
from dragpoint.tools.support import test_files as walk_tests


def test_the_paths_point_at_this_checkout() -> None:
    assert PACKAGE.name == "dragpoint"
    assert PACKAGE.parent.name == "src"
    assert (ROOT / "pyproject.toml").is_file()
    assert TESTS.is_dir()


def test_the_source_files_are_the_package() -> None:
    files = source_files()
    assert files
    assert all(path.suffix == ".py" for path in files)
    assert all("__pycache__" not in path.parts for path in files)
    assert files == sorted(files)


def test_the_tools_can_be_left_out() -> None:
    assert any(path.parent.name == "tools" for path in source_files())
    assert not any(path.parent.name == "tools" for path in source_files(skip_tools=True))


def test_the_test_files_are_found() -> None:
    files = walk_tests()
    assert files
    assert all(path.suffix == ".py" for path in files)


def test_a_file_maps_back_to_its_import_name() -> None:
    assert dotted_name(PACKAGE / "units.py") == "dragpoint.units"
    assert dotted_name(PACKAGE / "geometry" / "__init__.py") == "dragpoint.geometry"


def test_a_problem_prints_relative_to_the_checkout() -> None:
    problem = Problem(PACKAGE / "units.py", 12, "something")
    assert str(problem).replace("\\", "/") == "src/dragpoint/units.py:12: something"


def test_a_clean_report_says_how_many_files_it_looked_at(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert report("demo", [], 7) == 0
    assert "demo: 7 files clean" in capsys.readouterr().out


def test_a_report_with_problems_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    code = report("demo", [Problem(Path("a.py"), 1, "bad")], 7)
    assert code == 1
    assert "bad" in capsys.readouterr().err


def test_the_package_passes_its_own_docstring_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_docstrings.main() == 0
    assert "clean" in capsys.readouterr().out


def test_a_public_name_is_wanted_and_a_private_one_is_not() -> None:
    tree = ast.parse("def public(): pass\ndef _private(): pass\nclass Thing: pass\n")
    wanted = [node for node in ast.walk(tree) if check_docstrings._wanted(node)]
    names = {node.name for node in wanted}  # type: ignore[attr-defined]
    assert names == {"public", "Thing"}


def test_a_dunder_is_exempt() -> None:
    tree = ast.parse("class Thing:\n    def __str__(self): return ''\n")
    method = tree.body[0].body[0]  # type: ignore[attr-defined]
    assert not check_docstrings._wanted(method)


def test_nothing_that_is_not_a_definition_is_wanted() -> None:
    tree = ast.parse("x = 1\n")
    assert not check_docstrings._wanted(tree.body[0])


def _summary(text: str) -> str | None:
    tree = ast.parse(f'def thing():\n    """{text}"""\n')
    return check_docstrings._summary_problems(tree.body[0], text)  # type: ignore[arg-type]


def test_a_good_summary_has_nothing_wrong_with_it() -> None:
    assert _summary("Does the thing.") is None
    assert _summary("Does the thing:") is None
    assert _summary("Does the thing?") is None


def test_a_summary_that_does_not_start_with_a_capital_is_reported() -> None:
    assert "capital" in str(_summary("does the thing."))


def test_a_summary_that_starts_with_markup_is_allowed() -> None:
    assert _summary("``thing`` does it.") is None


def test_a_summary_with_no_full_stop_is_reported() -> None:
    assert "full stop" in str(_summary("Does the thing"))


def test_an_empty_docstring_is_reported() -> None:
    assert "empty" in str(_summary("   "))


def test_a_file_parses_to_a_module(tmp_path: Path) -> None:
    target = tmp_path / "thing.py"
    target.write_text('"""A thing."""\n', encoding="utf-8")
    assert isinstance(parsed(target), ast.Module)


def test_the_docs_directory_is_where_the_generators_write() -> None:
    assert DOCS.parent == ROOT


def problems_in(text: str) -> list[str]:
    """Run the docstring check over one made up module."""
    tree = ast.parse(text)
    found: list[str] = []
    if ast.get_docstring(tree) is None:
        found.append("the module has no docstring")
    for node in ast.walk(tree):
        if not check_docstrings._wanted(node):
            continue
        assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        docstring = ast.get_docstring(node)
        if docstring is None:
            found.append(f"{node.name} has no docstring")
            continue
        complaint = check_docstrings._summary_problems(node, docstring)
        if complaint is not None:
            found.append(complaint)
    return found


def test_a_module_with_no_docstring_is_caught() -> None:
    assert "the module has no docstring" in problems_in("def cut() -> None:\n    'Cut.'\n")


def test_a_function_with_no_docstring_is_caught() -> None:
    found = problems_in('"""A module."""\n\n\ndef cut() -> None:\n    pass\n')
    assert "cut has no docstring" in found


def test_a_class_with_no_docstring_is_caught() -> None:
    found = problems_in('"""A module."""\n\n\nclass Plate:\n    x = 1\n')
    assert "Plate has no docstring" in found


def test_a_private_function_is_not_asked_for_one() -> None:
    found = problems_in('"""A module."""\n\n\ndef _cut() -> None:\n    pass\n')
    assert found == []


def test_a_clean_module_says_nothing() -> None:
    text = '"""A module."""\n\n\ndef cut() -> None:\n    """Cut the plate."""\n'
    assert problems_in(text) == []
