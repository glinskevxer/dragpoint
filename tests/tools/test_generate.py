"""Writing a generated document, and checking one."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.tools.generate import HEADER, generated, run


def test_a_document_opens_with_the_do_not_edit_line() -> None:
    text = generated("some.tool", "A title", ["body"])
    assert text.splitlines()[0] == HEADER.format(tool="some.tool")


def test_a_document_carries_its_title_as_a_heading() -> None:
    assert "# A title" in generated("some.tool", "A title", ["body"])


def test_a_document_ends_with_exactly_one_newline() -> None:
    text = generated("some.tool", "A title", ["body", "", "", ""])
    assert text.endswith("body\n")


def test_a_document_with_no_body_is_still_a_document() -> None:
    text = generated("some.tool", "A title", [])
    assert text.strip().endswith("# A title")


def test_writing_creates_the_file_and_its_directory(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "page.md"
    assert run(target, "hello\n", []) == 0
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_writing_is_always_lf(tmp_path: Path) -> None:
    target = tmp_path / "page.md"
    run(target, "one\ntwo\n", [])
    assert b"\r\n" not in target.read_bytes()


def test_checking_a_file_that_matches_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "page.md"
    run(target, "hello\n", [])
    assert run(target, "hello\n", ["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_checking_a_file_that_differs_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "page.md"
    run(target, "hello\n", [])
    assert run(target, "goodbye\n", ["--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_checking_a_file_that_is_missing_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path / "gone.md", "hello\n", ["--check"]) == 1
    assert "missing" in capsys.readouterr().err


def test_checking_never_writes_anything(tmp_path: Path) -> None:
    target = tmp_path / "page.md"
    run(target, "hello\n", [])
    run(target, "goodbye\n", ["--check"])
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_other_arguments_do_not_turn_checking_on(tmp_path: Path) -> None:
    target = tmp_path / "page.md"
    assert run(target, "hello\n", ["--verbose"]) == 0
    assert target.is_file()
