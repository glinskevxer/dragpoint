"""The plate check bag, and the rule register that runs over it."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from dragpoint.rules.check import (
    REGISTRY,
    PlateCheck,
    RuleDef,
    RuleSelection,
    rule,
    rule_names,
    run_rules,
)
from dragpoint.rules.report import Severity, Violation

pytestmark = pytest.mark.usefixtures("clean_registry")


def always(message: str = "always") -> Iterator[Violation]:
    yield Violation(rule="ignored", severity=Severity.NOTE, message=message)


def test_the_check_knows_the_groove_it_will_leave(check: PlateCheck) -> None:
    assert check.groove_width == pytest.approx(check.cutter.width_at_depth(check.depth))
    assert check.groove_width > check.cutter.tip_width


def test_the_check_carries_the_engraving_area(check: PlateCheck) -> None:
    assert check.area == check.plate.area()


def test_the_ink_bounds_sit_inside_the_plate(check: PlateCheck) -> None:
    box = check.ink_bounds()
    assert box is not None
    assert check.plate.outline().contains_box(box)


def test_a_blank_plate_has_no_ink() -> None:
    from .conftest import build_check

    assert build_check(lines=()).ink_bounds() is None


def test_str_names_the_plate_the_stock_and_the_cutter(check: PlateCheck) -> None:
    assert str(check) == "P-101 on LAM16-BW with V30-015"


def test_a_rule_registers_itself_and_comes_back_unchanged() -> None:
    @rule("demo", "a demonstration")
    def demo(check: PlateCheck) -> Iterator[Violation]:
        yield from always()

    assert rule_names() == ("demo",)
    assert list(demo(None)) != []  # type: ignore[arg-type]
    assert REGISTRY["demo"].description == "a demonstration"


def test_registering_the_same_name_twice_is_refused() -> None:
    @rule("demo", "first")
    def first(check: PlateCheck) -> Iterator[Violation]:
        yield from always()

    with pytest.raises(ValueError, match="already registered"):

        @rule("demo", "second")
        def second(check: PlateCheck) -> Iterator[Violation]:
            yield from always()


def test_the_register_keeps_the_order_rules_were_written_in() -> None:
    for name in ("third", "first", "second"):

        @rule(name, name)
        def anything(check: PlateCheck) -> Iterator[Violation]:
            return iter(())

    assert rule_names() == ("third", "first", "second")


def test_running_the_rules_stamps_the_name_and_the_severity(check: PlateCheck) -> None:
    @rule("loud", "shouts", severity=Severity.ERROR)
    def loud(check: PlateCheck) -> Iterator[Violation]:
        yield from always("something is wrong")

    report = run_rules(check)
    assert len(report) == 1
    assert report.violations[0].rule == "loud"
    assert report.violations[0].severity is Severity.ERROR
    assert report.violations[0].message == "something is wrong"


def test_a_rule_cannot_promote_itself(check: PlateCheck) -> None:
    @rule("quiet", "murmurs", severity=Severity.NOTE)
    def quiet(check: PlateCheck) -> Iterator[Violation]:
        yield Violation(rule="me", severity=Severity.ERROR, message="listen to me")

    assert run_rules(check).violations[0].severity is Severity.NOTE


def test_a_rule_that_finds_nothing_says_nothing(check: PlateCheck) -> None:
    @rule("silent", "never complains")
    def silent(check: PlateCheck) -> Iterator[Violation]:
        return iter(())

    assert run_rules(check).clean


def test_the_measurements_survive_the_stamping(check: PlateCheck) -> None:
    @rule("measured", "measures")
    def measured(check: PlateCheck) -> Iterator[Violation]:
        yield Violation(
            rule="me",
            severity=Severity.NOTE,
            message="too close",
            measured=0.3,
            limit=0.5,
            unit="mm",
            subject="line 1",
        )

    found = run_rules(check).violations[0]
    assert found.measured == 0.3
    assert found.limit == 0.5
    assert found.subject == "line 1"


def register_three() -> None:
    for name in ("a", "b", "c"):

        @rule(name, name)
        def anything(check: PlateCheck, tag: str = name) -> Iterator[Violation]:
            yield from always(tag)


def test_only_runs_the_rules_it_names(check: PlateCheck) -> None:
    register_three()
    report = run_rules(check, RuleSelection(only=frozenset({"a", "c"})))
    assert [item.rule for item in report] == ["a", "c"]


def test_skip_drops_the_rules_it_names(check: PlateCheck) -> None:
    register_three()
    report = run_rules(check, RuleSelection(skip=frozenset({"b"})))
    assert [item.rule for item in report] == ["a", "c"]


def test_skip_wins_over_only(check: PlateCheck) -> None:
    register_three()
    selection = RuleSelection(only=frozenset({"a", "b"}), skip=frozenset({"b"}))
    assert [item.rule for item in run_rules(check, selection)] == ["a"]


def test_an_empty_selection_runs_everything(check: PlateCheck) -> None:
    register_three()
    assert len(run_rules(check, RuleSelection())) == 3


def test_the_severity_override_changes_what_a_rule_reports_at(check: PlateCheck) -> None:
    register_three()
    selection = RuleSelection(severity={"b": Severity.WARNING})
    levels = {item.rule: item.severity for item in run_rules(check, selection)}
    assert levels["b"] is Severity.WARNING
    assert levels["a"] is Severity.ERROR


def test_unknown_names_are_reported_rather_than_raised() -> None:
    register_three()
    selection = RuleSelection(
        only=frozenset({"a", "nope"}),
        skip=frozenset({"gone"}),
        severity={"vanished": Severity.ERROR},
    )
    assert selection.unknown_names() == ("gone", "nope", "vanished")


def test_a_selection_of_real_names_reports_nothing_unknown() -> None:
    register_three()
    assert RuleSelection(only=frozenset({"a"})).unknown_names() == ()


def test_a_rule_definition_reads_as_a_line_of_help() -> None:
    definition = RuleDef(
        name="gap",
        description="strokes must not merge",
        severity=Severity.ERROR,
        check=lambda check: (),
    )
    assert str(definition) == "gap (error): strokes must not merge"
