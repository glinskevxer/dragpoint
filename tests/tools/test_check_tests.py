"""The source and test mirror check."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.tools import check_tests
from dragpoint.tools.support import PACKAGE, TESTS


def test_the_checkout_mirrors_itself(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_tests.main() == 0
    assert "clean" in capsys.readouterr().out


def test_a_source_file_maps_to_its_test_file() -> None:
    wanted = check_tests._expected_test(PACKAGE / "geometry" / "point.py")
    assert wanted == TESTS / "geometry" / "test_point.py"


def test_a_top_level_module_maps_to_the_top_of_the_tests() -> None:
    assert check_tests._expected_test(PACKAGE / "units.py") == TESTS / "test_units.py"


def test_a_test_file_maps_back_to_its_source() -> None:
    source = check_tests._expected_source(TESTS / "geometry" / "test_point.py")
    assert source == PACKAGE / "geometry" / "point.py"


def test_the_mapping_is_a_round_trip() -> None:
    for path in (PACKAGE / "units.py", PACKAGE / "path" / "order.py"):
        assert check_tests._expected_source(check_tests._expected_test(path)) == path


def test_test_functions_are_counted() -> None:
    assert check_tests._test_count(Path(__file__)) >= check_tests.MIN_TESTS


def test_a_module_with_no_tests_counts_zero(tmp_path: Path) -> None:
    target = tmp_path / "test_nothing.py"
    target.write_text('"""Nothing."""\n\n\ndef helper() -> None:\n    pass\n', encoding="utf-8")
    assert check_tests._test_count(target) == 0


def test_nested_functions_do_not_count(tmp_path: Path) -> None:
    target = tmp_path / "test_nested.py"
    body = [
        '"""Nothing."""',
        "",
        "",
        "def test_one() -> None:",
        "    def test_inner() -> None:",
        "        pass",
        "",
    ]
    target.write_text("\n".join(body), encoding="utf-8")
    assert check_tests._test_count(target) == 1


def test_the_tools_are_the_one_directory_that_is_not_mirrored() -> None:
    assert "tools" in check_tests.SKIP_DIRECTORIES
