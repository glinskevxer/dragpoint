"""Rules about a whole schedule rather than about one plate."""

from __future__ import annotations

import pytest

from dragpoint.compiler.job import compile_job
from dragpoint.rules.batch import (
    JOB_REGISTRY,
    JobCheck,
    job_rule,
    job_rule_names,
    run_job_rules,
)
from dragpoint.rules.check import RuleSelection
from dragpoint.rules.report import Severity
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.plate import PlateSpec


def spec(name: str, **overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": name,
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("RUN",),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def checked(*plates: PlateSpec, sheet: Sheet | None = None) -> JobCheck:
    job = JobSpec(name="J", plates=plates, sheet=sheet)
    made = compile_job(job)
    return JobCheck(job=job, plates=tuple(plate.check() for plate in made))


def rules_on(*plates: PlateSpec, sheet: Sheet | None = None) -> tuple[str, ...]:
    report = run_job_rules(checked(*plates, sheet=sheet))
    return tuple(violation.rule for violation in report.violations)


def test_every_job_rule_is_registered_under_its_own_name() -> None:
    assert set(job_rule_names()) == set(JOB_REGISTRY)


def test_a_job_rule_cannot_be_registered_twice() -> None:
    with pytest.raises(ValueError, match="already registered"):
        job_rule("stock-changes", "again")(lambda check: ())


def test_a_plain_schedule_says_nothing() -> None:
    assert rules_on(spec("P-1"), spec("P-2", lines=("STOP",))) == ()


def collision() -> JobCheck:
    """A numbered run whose second piece is called what another plate is.

    The schedule itself cannot hold two plates of one name, so the only way
    to get one is a run that numbers into a name somebody else already used.
    """
    return checked(
        spec("TAG", lines=("VLV-{n}",), quantity=3),
        spec("TAG-2", lines=("SPARE",)),
    )


def test_a_numbered_run_that_collides_with_another_plate_is_an_error() -> None:
    report = run_job_rules(collision())
    assert report.worst is Severity.ERROR
    assert "plate-name-repeated" in [violation.rule for violation in report.violations]


def test_the_repeated_name_is_named() -> None:
    report = run_job_rules(collision())
    assert "TAG-2" in report.violations[0].message


def test_a_run_that_does_not_collide_is_fine() -> None:
    found = rules_on(
        spec("TAG", lines=("VLV-{n}",), quantity=3),
        spec("SPARE", lines=("SPARE",)),
    )
    assert "plate-name-repeated" not in found


def test_two_plates_saying_the_same_thing_is_a_warning() -> None:
    assert "legend-repeated" in rules_on(spec("P-1"), spec("P-2"))


def test_the_repeat_names_the_plate_it_matches() -> None:
    report = run_job_rules(checked(spec("P-1"), spec("P-2")))
    assert "P-1" in report.violations[0].message


def test_three_the_same_is_reported_twice_because_two_are_wrong() -> None:
    found = rules_on(spec("P-1"), spec("P-2"), spec("P-3"))
    assert list(found).count("legend-repeated") == 2


def test_blank_plates_are_not_repeats_of_each_other() -> None:
    assert "legend-repeated" not in rules_on(spec("P-1", lines=()), spec("P-2", lines=()))


def test_one_stock_is_not_a_stock_change() -> None:
    assert "stock-changes" not in rules_on(spec("P-1"), spec("P-2", lines=("STOP",)))


def test_two_stocks_in_one_setup_is_a_warning() -> None:
    found = rules_on(spec("P-1"), spec("P-2", lines=("STOP",), stock="LAM32-RW"))
    assert "stock-changes" in found


def test_the_stock_change_names_both_stocks() -> None:
    report = run_job_rules(checked(spec("P-1"), spec("P-2", lines=("STOP",), stock="LAM32-RW")))
    message = " ".join(violation.message for violation in report.violations)
    assert "LAM16-BW" in message
    assert "LAM32-RW" in message


def test_two_cutters_in_one_setup_is_a_warning() -> None:
    found = rules_on(spec("P-1"), spec("P-2", lines=("STOP",), cutter="V20-010"))
    assert "cutter-changes" in found


def test_one_stock_at_two_depths_is_a_warning() -> None:
    found = rules_on(spec("P-1"), spec("P-2", lines=("STOP",), depth=0.35))
    assert "depth-varies-on-one-stock" in found


def test_the_depth_warning_names_the_stock_and_both_depths() -> None:
    report = run_job_rules(checked(spec("P-1"), spec("P-2", lines=("STOP",), depth=0.35)))
    message = " ".join(violation.message for violation in report.violations)
    assert "LAM16-BW" in message
    assert "0.35mm" in message


def test_two_stocks_at_their_own_depths_is_not_a_depth_warning() -> None:
    found = rules_on(spec("P-1"), spec("P-2", lines=("STOP",), stock="LAM32-RW"))
    assert "depth-varies-on-one-stock" not in found


def test_a_job_with_no_sheet_is_not_measured_against_one() -> None:
    assert "sheet-too-small" not in rules_on(spec("P-1", quantity=500))


def test_more_blank_than_the_sheet_holds_is_a_warning() -> None:
    sheet = Sheet(stock="LAM16-BW", width=300.0, height=200.0)
    assert "sheet-too-small" in rules_on(spec("P-1", quantity=100), sheet=sheet)


def test_a_sheet_that_holds_the_job_says_nothing() -> None:
    sheet = Sheet(stock="LAM16-BW", width=300.0, height=200.0)
    assert "sheet-too-small" not in rules_on(spec("P-1", quantity=2), sheet=sheet)


def test_a_job_rule_can_be_skipped() -> None:
    check = checked(spec("P-1"), spec("P-2"))
    selection = RuleSelection(skip=frozenset({"legend-repeated"}))
    assert run_job_rules(check, selection).violations == ()


def test_a_job_rule_can_be_raised_to_an_error() -> None:
    check = checked(spec("P-1"), spec("P-2"))
    selection = RuleSelection(severity={"legend-repeated": Severity.ERROR})
    assert run_job_rules(check, selection).worst is Severity.ERROR


def test_the_check_counts_the_blank_the_job_needs() -> None:
    check = checked(spec("P-1", quantity=3))
    assert check.piece_area() == pytest.approx(60.0 * 20.0 * 3)


def test_the_check_reads_like_a_line_about_the_job() -> None:
    assert "2 plates" in str(checked(spec("P-1"), spec("P-2", lines=("STOP",))))
