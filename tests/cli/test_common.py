"""Exit codes, report printing and error handling."""

from __future__ import annotations

from pathlib import Path

import click
import pytest

from dragpoint.cli.common import (
    OK,
    REPORTED,
    USAGE,
    echo_json,
    echo_report,
    exit_code_for,
    handled,
    report_json,
    write_out,
)
from dragpoint.errors import BadLength
from dragpoint.rules.report import Report, Severity, Violation


def note() -> Violation:
    return Violation(rule="a", severity=Severity.NOTE, message="just saying")


def warning() -> Violation:
    return Violation(rule="b", severity=Severity.WARNING, message="look at this")


def error() -> Violation:
    return Violation(
        rule="c",
        severity=Severity.ERROR,
        message="will not cut",
        measured=0.3,
        limit=0.5,
        subject="P-1",
    )


def test_the_codes_are_the_three_a_shop_script_reads() -> None:
    assert (OK, REPORTED, USAGE) == (0, 1, 2)


def test_a_clean_report_is_zero() -> None:
    assert exit_code_for(Report()) == OK


def test_a_report_of_warnings_is_still_zero() -> None:
    assert exit_code_for(Report.of([note(), warning()])) == OK


def test_one_error_is_one() -> None:
    assert exit_code_for(Report.of([error()])) == REPORTED


def test_a_clean_report_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    echo_report(Report())
    assert "no violations" in capsys.readouterr().out


def test_a_report_prints_worst_first(capsys: pytest.CaptureFixture[str]) -> None:
    echo_report(Report.of([note(), error(), warning()]))
    printed = capsys.readouterr().out.splitlines()
    assert "error" in printed[0]
    assert "warning" in printed[1]
    assert "note" in printed[2]


def test_the_order_can_be_left_alone(capsys: pytest.CaptureFixture[str]) -> None:
    echo_report(Report.of([note(), error()]), worst_first=False)
    assert "note" in capsys.readouterr().out.splitlines()[0]


def test_a_violation_line_carries_its_numbers(capsys: pytest.CaptureFixture[str]) -> None:
    echo_report(Report.of([error()]))
    printed = capsys.readouterr().out
    assert "0.3mm against 0.5mm" in printed
    assert "on P-1" in printed
    assert "[c]" in printed


def test_a_violation_with_no_numbers_prints_without_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    echo_report(Report.of([warning()]))
    assert "against" not in capsys.readouterr().out


def test_quiet_prints_nothing_at_all(capsys: pytest.CaptureFixture[str]) -> None:
    echo_report(Report.of([error()]), quiet=True)
    assert capsys.readouterr().out == ""


def test_a_dragpoint_error_becomes_a_click_exception() -> None:
    with pytest.raises(click.ClickException, match="cannot read"), handled():
        raise BadLength("wide", "expected a number")


def test_a_key_error_loses_its_quotes() -> None:
    with pytest.raises(click.ClickException) as caught, handled():
        raise KeyError("no cutter called 'V99'")
    assert not str(caught.value).startswith("'")


def test_a_value_error_becomes_a_click_exception() -> None:
    with pytest.raises(click.ClickException, match="not a size"), handled():
        raise ValueError("not a size")


def test_anything_else_is_left_alone() -> None:
    with pytest.raises(RuntimeError), handled():
        raise RuntimeError("something else")


def test_output_goes_to_the_terminal_when_no_file_is_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_out("hello\n", None)
    assert capsys.readouterr().out == "hello\n"


def test_output_goes_to_a_file_when_one_is_named(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "file.txt"
    write_out("hello\n", target)
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_a_written_file_says_where_it_went(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    write_out("hello\n", tmp_path / "file.txt")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "wrote" in captured.err


def test_a_written_file_is_always_lf(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    write_out("one\ntwo\n", target)
    assert b"\r\n" not in target.read_bytes()


def test_json_comes_out_sorted_and_indented(capsys: pytest.CaptureFixture[str]) -> None:
    echo_json({"b": 1, "a": 2})
    printed = capsys.readouterr().out
    assert printed.index('"a"') < printed.index('"b"')
    assert "  " in printed


def test_a_report_turns_into_plain_data() -> None:
    payload = report_json(Report.of([error()]))
    assert payload == [
        {
            "rule": "c",
            "severity": "error",
            "message": "will not cut",
            "subject": "P-1",
            "measured": 0.3,
            "limit": 0.5,
            "unit": "mm",
        }
    ]
