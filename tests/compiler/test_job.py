"""Compiling a whole job."""

from __future__ import annotations

import pytest

from dragpoint.compiler.job import compile_job
from dragpoint.compiler.settings import MachineSetup
from dragpoint.rules.report import Severity
from dragpoint.spec.job import JobSpec
from dragpoint.spec.load import load_job

from .conftest import EXAMPLE, plate_spec


def small_job(**overrides: object) -> JobSpec:
    values: dict[str, object] = {
        "name": "J1",
        "plates": (
            plate_spec(name="P-1", lines=("ONE",)),
            plate_spec(name="P-2", lines=("TWO",), quantity=4),
        ),
    }
    values.update(overrides)
    return JobSpec(**values)  # type: ignore[arg-type]


def test_every_plate_is_compiled() -> None:
    made = compile_job(small_job())
    assert len(made) == 2
    assert [plate.name for plate in made] == ["P-1", "P-2"]


def test_a_job_of_good_plates_is_ok() -> None:
    made = compile_job(small_job())
    assert made.ok
    assert made.failed() == ()
    assert made.worst() is None


def test_the_report_gathers_every_plate_in_order() -> None:
    job = JobSpec(
        name="J1",
        plates=(
            plate_spec(name="P-1", lines=("ONE",)),
            plate_spec(name="P-2", lines=("45°C",)),
        ),
    )
    report = compile_job(job).report()
    assert not report.clean
    assert all(item.subject is not None and "P-2" in item.subject for item in report)


def test_a_job_with_a_bad_plate_names_it() -> None:
    job = JobSpec(
        name="J1",
        plates=(
            plate_spec(name="P-1", lines=("ONE",)),
            plate_spec(name="P-2", lines=("45°C",)),
        ),
    )
    made = compile_job(job)
    assert not made.ok
    assert [plate.name for plate in made.failed()] == ["P-2"]
    assert made.worst() is Severity.ERROR


def test_plate_lookup() -> None:
    made = compile_job(small_job())
    assert made.plate("P-2").spec.quantity == 4


def test_an_unknown_plate_lists_the_ones_that_are_there() -> None:
    with pytest.raises(KeyError) as caught:
        compile_job(small_job()).plate("P-9")
    assert "P-1" in str(caught.value)


def test_an_empty_job_lists_none() -> None:
    with pytest.raises(KeyError, match="none"):
        compile_job(JobSpec(name="J1")).plate("P-1")


def test_a_plate_is_compiled_once_however_many_are_wanted() -> None:
    made = compile_job(small_job())
    one = made.plate("P-1")
    four = made.plate("P-2")
    assert one.spec.quantity == 1
    assert four.spec.quantity == 4
    assert len(four.cuts) < len(one.cuts) * 4 + len(one.cuts)


def test_the_cut_length_counts_the_quantities() -> None:
    made = compile_job(small_job())
    single = made.plate("P-1").cuts.cut_length()
    four = made.plate("P-2").cuts.cut_length()
    assert made.cut_length() == pytest.approx(single + four * 4)


def test_the_travel_counts_the_quantities_too() -> None:
    made = compile_job(small_job())
    assert made.travel_length() == pytest.approx(
        made.plate("P-1").order.after + made.plate("P-2").order.after * 4
    )


def test_the_piece_count_comes_off_the_job() -> None:
    assert compile_job(small_job()).piece_count() == 5


def test_stock_usage_is_counted_per_code() -> None:
    job = JobSpec(
        name="J1",
        plates=(
            plate_spec(name="P-1", lines=("ONE",), quantity=2),
            plate_spec(name="P-2", lines=("TWO",), stock="LAM32-RW", quantity=3, depth=0.4),
            plate_spec(name="P-3", lines=("THREE",), quantity=1),
        ),
    )
    assert compile_job(job).stock_usage() == {"LAM16-BW": 3, "LAM32-RW": 3}


def test_the_setup_reaches_every_plate() -> None:
    plain = compile_job(small_job(), setup=MachineSetup().without_optimising())
    tidy = compile_job(small_job())
    assert tidy.travel_length() <= plain.travel_length()


def test_the_shipped_example_compiles_clean() -> None:
    made = compile_job(load_job(EXAMPLE))
    assert made.ok, str(made.report())
    assert len(made) == 7
    assert made.piece_count() == 15
    assert made.cut_length() > 0.0


def test_the_shipped_example_uses_three_stocks() -> None:
    made = compile_job(load_job(EXAMPLE))
    assert sorted(made.stock_usage()) == ["ANOD-10", "LAM16-BW", "LAM32-RW"]


def test_an_empty_job_compiles_to_nothing() -> None:
    made = compile_job(JobSpec(name="empty"))
    assert len(made) == 0
    assert made.ok
    assert made.cut_length() == 0.0
    assert made.stock_usage() == {}


def test_str_says_what_the_job_comes_to() -> None:
    text = str(compile_job(small_job()))
    assert text.startswith("J1: 2 plates, 5 pieces, ")
    assert text.endswith("ok")


def test_str_says_how_many_plates_are_not_ok() -> None:
    job = JobSpec(name="J1", plates=(plate_spec(name="P-1", lines=("45°C",)),))
    assert "1 plates not ok" in str(compile_job(job))


def test_a_job_that_skips_a_rule_does_not_run_it() -> None:
    from dragpoint.compiler.plate import rule_selection

    plate = plate_spec(name="P-1", lines=("RUN",), cap_height=2.7)
    loud = compile_job(JobSpec(name="J1", plates=(plate,)))
    quiet = compile_job(JobSpec(name="J1", plates=(plate,), rules_skip=("odd-lettering-height",)))
    assert not loud.report().by_rule("odd-lettering-height").clean
    assert quiet.report().by_rule("odd-lettering-height").clean
    assert rule_selection(quiet.spec).unknown_names() == ()


def test_a_job_can_narrow_the_rules_to_the_ones_it_cares_about() -> None:
    plate = plate_spec(name="P-1", lines=("45\u00b0C",))
    narrowed = compile_job(JobSpec(name="J1", plates=(plate,), rules_only=("stroke-merge",)))
    assert narrowed.report().by_rule("legend-missing-glyph").clean
    assert {item.rule for item in narrowed.report()} <= {"stroke-merge"}


def test_a_job_can_make_a_warning_into_an_error() -> None:
    from dragpoint.rules.report import Severity

    plate = plate_spec(name="P-1", lines=("RUN",), cap_height=2.7)
    strict = compile_job(
        JobSpec(name="J1", plates=(plate,), rules_severity={"odd-lettering-height": "error"})
    )
    assert not strict.ok
    assert strict.worst() is Severity.ERROR


def test_a_severity_word_nobody_recognises_is_left_alone() -> None:
    plate = plate_spec(name="P-1", lines=("RUN",), cap_height=2.7)
    made = compile_job(
        JobSpec(name="J1", plates=(plate,), rules_severity={"odd-lettering-height": "shouty"})
    )
    assert made.ok


def test_a_rule_name_nobody_recognises_is_reported_rather_than_raised() -> None:
    from dragpoint.compiler.plate import rule_selection

    job = JobSpec(
        name="J1", plates=(plate_spec(name="P-1", lines=("RUN",)),), rules_skip=("no-such-rule",)
    )
    assert compile_job(job).ok
    assert rule_selection(job).unknown_names() == ("no-such-rule",)


def test_a_numbered_run_compiles_one_plate_per_piece() -> None:
    made = compile_job(
        JobSpec(
            name="tags",
            plates=(plate_spec(name="VLV", lines=("VLV-{n:03}",), quantity=4),),
        )
    )
    assert len(made) == 4
    assert [plate.name for plate in made] == ["VLV-1", "VLV-2", "VLV-3", "VLV-4"]


def test_each_piece_of_a_run_gets_its_own_number_cut_into_it() -> None:
    made = compile_job(
        JobSpec(
            name="tags",
            plates=(plate_spec(name="VLV", lines=("VLV-{n:03}",), quantity=3),),
        )
    )
    assert [plate.lines[0] for plate in made] == ["VLV-001", "VLV-002", "VLV-003"]


def test_a_numbered_run_still_counts_as_the_pieces_it_asked_for() -> None:
    job = JobSpec(
        name="tags",
        plates=(plate_spec(name="VLV", lines=("VLV-{n}",), quantity=5),),
    )
    made = compile_job(job)
    assert made.stock_usage() == {"LAM16-BW": 5}
    assert made.piece_count() == 5


def test_a_run_of_identical_plates_is_still_compiled_once() -> None:
    made = compile_job(
        JobSpec(
            name="plain",
            plates=(plate_spec(name="P-1", lines=("RUN",), quantity=5),),
        )
    )
    assert len(made) == 1
    assert made.piece_count() == 5


def test_a_job_says_what_it_asks_of_each_cutter() -> None:
    made = compile_job(small_job())
    lives = made.tip_lives()
    assert [life.cutter for life in lives] == ["V30-015"]
    assert lives[0].cutting > 0.0


def test_the_tip_reckoning_counts_the_quantities() -> None:
    one = compile_job(JobSpec(name="J", plates=(plate_spec(name="P-1", lines=("ONE",)),)))
    many = compile_job(
        JobSpec(name="J", plates=(plate_spec(name="P-1", lines=("ONE",), quantity=10),))
    )
    assert many.tip_lives()[0].cutting == pytest.approx(10.0 * one.tip_lives()[0].cutting)


def test_two_cutters_get_a_line_each() -> None:
    made = compile_job(
        JobSpec(
            name="J",
            plates=(
                plate_spec(name="P-1", lines=("ONE",)),
                plate_spec(name="P-2", lines=("TWO",), cutter="V20-010"),
            ),
        )
    )
    assert [life.cutter for life in made.tip_lives()] == ["V20-010", "V30-015"]


def test_a_job_of_nothing_asks_nothing_of_any_cutter() -> None:
    assert compile_job(JobSpec(name="empty")).tip_lives() == ()
