"""The naming check."""

from __future__ import annotations

import ast

import pytest

from dragpoint.tools import check_naming


def test_the_package_keeps_its_own_naming(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_naming.main() == 0
    assert "clean" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("name", "word"),
    [
        ("utils", "utils"),
        ("string_utils", "utils"),
        ("PlateManager", "manager"),
        ("temp_file", "temp"),
        ("do_stuff", "stuff"),
        ("MiscThings", "misc"),
    ],
)
def test_a_vague_name_is_named(name: str, word: str) -> None:
    assert check_naming._vague(name) == word


@pytest.mark.parametrize(
    "name",
    ["compile_plate", "PlateSpec", "order_cuts", "utilisation", "handled", "themes"],
)
def test_a_name_that_only_contains_a_banned_word_as_letters_is_fine(name: str) -> None:
    assert check_naming._vague(name) is None


def test_a_constant_name_is_public_and_shouting() -> None:
    assert check_naming._is_constant_name("MIN_TESTS")
    assert not check_naming._is_constant_name("_PRIVATE")
    assert not check_naming._is_constant_name("lowercase")
    assert not check_naming._is_constant_name("X")


def test_a_documented_constant_is_seen_as_documented() -> None:
    tree = ast.parse('LIMIT = 3\n"""How many."""\n')
    assert check_naming._documented(tree.body, 0)


def test_an_undocumented_constant_is_seen_as_undocumented() -> None:
    tree = ast.parse("LIMIT = 3\nOTHER = 4\n")
    assert not check_naming._documented(tree.body, 0)


def test_a_constant_at_the_end_of_a_file_is_undocumented() -> None:
    tree = ast.parse("LIMIT = 3\n")
    assert not check_naming._documented(tree.body, 0)


def test_type_machinery_is_not_a_constant_that_needs_a_reason() -> None:
    tree = ast.parse('Thing = TypeVar("Thing")\n')
    assert check_naming._machinery(tree.body[0])


def test_a_real_constant_is_not_machinery() -> None:
    tree = ast.parse("LIMIT = 3\n")
    assert not check_naming._machinery(tree.body[0])


def test_the_banned_list_holds_the_words_that_say_nothing() -> None:
    assert {"utils", "helper", "manager", "misc"} <= check_naming.BANNED
