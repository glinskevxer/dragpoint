"""Violations and reports."""

from __future__ import annotations

from dragpoint.geometry.point import Point
from dragpoint.rules.report import Report, Severity, Violation


def note(rule: str = "a", measured: float = 1.0, limit: float = 2.0) -> Violation:
    return Violation(
        rule=rule,
        severity=Severity.NOTE,
        message="just saying",
        measured=measured,
        limit=limit,
    )


def error(rule: str = "b", measured: float = 5.0, limit: float = 2.0) -> Violation:
    return Violation(
        rule=rule,
        severity=Severity.ERROR,
        message="will not cut",
        measured=measured,
        limit=limit,
    )


def warning(rule: str = "c") -> Violation:
    return Violation(rule=rule, severity=Severity.WARNING, message="look at this")


def test_severity_is_ordered() -> None:
    assert Severity.NOTE < Severity.WARNING < Severity.ERROR
    assert max([Severity.NOTE, Severity.ERROR, Severity.WARNING]) is Severity.ERROR


def test_severity_prints_lowercase() -> None:
    assert str(Severity.ERROR) == "error"
    assert str(Severity.NOTE) == "note"


def test_the_margin_is_how_far_past_the_limit_it_went() -> None:
    assert error(measured=5.0, limit=2.0).margin == 3.0
    assert note(measured=1.0, limit=2.0).margin == -1.0


def test_a_violation_with_no_numbers_has_no_margin() -> None:
    assert warning().margin is None


def test_a_violation_reads_as_a_line_of_a_report() -> None:
    item = Violation(
        rule="gap",
        severity=Severity.ERROR,
        message="strokes merge",
        where=Point(1.0, 2.0),
        measured=0.31,
        limit=0.4,
        subject="line 1",
    )
    text = str(item)
    assert text.startswith("line 1 error: strokes merge")
    assert "0.31mm against 0.4mm" in text
    assert "(1.0000, 2.0000)" in text


def test_a_bare_violation_prints_without_the_extras() -> None:
    assert str(warning()) == "warning: look at this"


def test_an_empty_report_is_clean_and_ok() -> None:
    report = Report()
    assert report.clean
    assert report.ok
    assert report.worst is None
    assert len(report) == 0
    assert not report
    assert str(report) == "no violations"


def test_a_report_of_warnings_is_not_clean_but_is_still_ok() -> None:
    report = Report.of([warning()])
    assert not report.clean
    assert report.ok
    assert report
    assert report.worst is Severity.WARNING


def test_one_error_makes_a_report_not_ok() -> None:
    report = Report.of([note(), warning(), error()])
    assert not report.ok
    assert report.worst is Severity.ERROR


def test_filtering_by_severity() -> None:
    report = Report.of([note(), warning(), error()])
    assert len(report.at_least(Severity.WARNING)) == 2
    assert len(report.at_least(Severity.ERROR)) == 1
    assert len(report.at_least(Severity.NOTE)) == 3


def test_filtering_by_rule() -> None:
    report = Report.of([note("gap"), error("gap"), warning("edge")])
    assert len(report.by_rule("gap")) == 2
    assert len(report.by_rule("edge")) == 1
    assert len(report.by_rule("nothing")) == 0


def test_sorting_puts_the_worst_first() -> None:
    report = Report.of([note(), error(), warning()]).sorted_worst_first()
    assert [item.severity for item in report] == [
        Severity.ERROR,
        Severity.WARNING,
        Severity.NOTE,
    ]


def test_sorting_within_a_severity_puts_the_widest_margin_first() -> None:
    small = error("b", measured=3.0, limit=2.0)
    big = error("b", measured=9.0, limit=2.0)
    report = Report.of([small, big]).sorted_worst_first()
    assert report.violations[0] is big


def test_sorting_is_stable_when_the_margins_match() -> None:
    first = error("first")
    second = error("second")
    report = Report.of([first, second]).sorted_worst_first()
    assert [item.rule for item in report] == ["first", "second"]


def test_merging_keeps_both_sides_in_order() -> None:
    left = Report.of([note("a")])
    right = Report.of([error("b")])
    merged = left.merged(right)
    assert [item.rule for item in merged] == ["a", "b"]
    assert len(left) == 1


def test_counts_include_the_zeros() -> None:
    tally = Report.of([error(), error(), note()]).counts()
    assert tally[Severity.ERROR] == 2
    assert tally[Severity.NOTE] == 1
    assert tally[Severity.WARNING] == 0


def test_str_summarises_worst_first() -> None:
    assert str(Report.of([note(), error(), error()])) == "2 error, 1 note"


def test_a_report_is_iterable_in_order() -> None:
    items = [note("a"), warning("b"), error("c")]
    assert [item.rule for item in Report.of(items)] == ["a", "b", "c"]
