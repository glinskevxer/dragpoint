"""The setup sheet."""

from __future__ import annotations

from pathlib import Path

from dragpoint.compiler.job import compile_job
from dragpoint.nest.shelf import nest_job, nest_pieces
from dragpoint.report.setup import WIDTH, setup_sheet, worst_severity
from dragpoint.rules.report import Severity
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.load import load_job
from dragpoint.spec.plate import PlateSpec

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mcc-panel-7.toml"


def small_job(**overrides: object) -> JobSpec:
    values: dict[str, object] = {
        "name": "J1",
        "plates": (
            PlateSpec(name="P-1", width=60.0, height=20.0, stock="LAM16-BW", lines=("ONE",)),
            PlateSpec(
                name="P-2",
                width=60.0,
                height=20.0,
                stock="LAM16-BW",
                lines=("TWO",),
                quantity=4,
            ),
        ),
    }
    values.update(overrides)
    return JobSpec(**values)  # type: ignore[arg-type]


def sheet_for(job: JobSpec, **kwargs: object) -> str:
    return setup_sheet(compile_job(job), **kwargs)  # type: ignore[arg-type]


def test_the_sheet_names_the_job() -> None:
    assert "SETUP SHEET   J1" in sheet_for(small_job())


def test_the_sheet_says_which_cutter() -> None:
    assert "cutter    V30-015" in sheet_for(small_job())


def test_the_sheet_counts_the_drawings_and_the_pieces() -> None:
    assert "plates    2 drawings, 5 pieces" in sheet_for(small_job())


def test_every_plate_gets_a_row() -> None:
    text = sheet_for(small_job())
    assert "P-1 " in text
    assert "P-2 " in text


def test_a_row_carries_the_numbers_the_setter_needs() -> None:
    text = sheet_for(small_job())
    row = next(line for line in text.splitlines() if line.startswith("P-1 "))
    assert "60x20" in row
    assert "LAM16-BW" in row
    assert "0.25" in row


def test_no_line_is_wider_than_the_paper() -> None:
    text = sheet_for(small_job(), nest=nest_pieces([], Sheet(stock="X", width=100.0, height=100.0)))
    for line in text.splitlines():
        assert len(line) <= WIDTH + 2


def test_the_sheet_adds_the_cutting_up() -> None:
    assert "cutting " in sheet_for(small_job())


def test_the_sheet_says_how_long_it_will_take() -> None:
    assert "minutes including tool changes" in sheet_for(small_job())


def test_the_stock_is_listed_with_its_count() -> None:
    assert "stock       5     LAM16-BW" in sheet_for(small_job())


def test_a_job_with_a_sheet_says_what_it_is() -> None:
    job = small_job(sheet=Sheet(stock="LAM16-BW", width=300.0, height=600.0))
    assert "sheet     LAM16-BW 300x600mm" in sheet_for(job)


def test_a_job_with_no_sheet_says_nothing_about_one() -> None:
    assert "sheet " not in sheet_for(small_job())


def test_a_spring_pass_is_called_out() -> None:
    assert "spring pass on every plate" in sheet_for(small_job(spring_pass=True))


def test_the_job_note_is_carried_through() -> None:
    assert "watch the fixture" in sheet_for(small_job(notes="watch the fixture"))


def test_a_clean_job_says_there_is_nothing_to_report() -> None:
    assert "checks    nothing to report" in sheet_for(small_job())


def test_a_job_with_errors_says_do_not_cut() -> None:
    job = small_job(
        plates=(PlateSpec(name="P-1", width=60.0, height=20.0, stock="LAM16-BW", lines=("45°C",)),)
    )
    text = sheet_for(job)
    assert "DO NOT CUT" in text
    assert "CHECKS" in text


def test_a_job_with_only_warnings_does_not_say_do_not_cut() -> None:
    job = small_job(
        plates=(
            PlateSpec(
                name="P-1",
                width=60.0,
                height=20.0,
                stock="LAM16-BW",
                lines=("RUN",),
                cap_height=2.7,
            ),
        )
    )
    text = sheet_for(job)
    assert "CHECKS" in text
    assert "DO NOT CUT" not in text


def test_the_nest_goes_on_the_sheet_when_there_is_one() -> None:
    spec = load_job(EXAMPLE)
    text = setup_sheet(compile_job(spec), nest=nest_job(spec))
    assert "nest      " in text
    assert "all on" in text


def test_a_nest_that_did_not_fit_says_what_was_left_over() -> None:
    sheet = Sheet(stock="LAM16-BW", width=60.0, height=40.0)
    nest = nest_pieces([("P-1", 500.0, 500.0)], sheet)
    text = setup_sheet(compile_job(small_job()), nest=nest)
    assert "did not fit" in text


def test_the_sheet_ends_with_a_newline() -> None:
    assert sheet_for(small_job()).endswith("\n")


def test_the_worst_severity_is_findable_on_its_own() -> None:
    assert worst_severity(compile_job(small_job())) is None
    bad = small_job(
        plates=(PlateSpec(name="P-1", width=60.0, height=20.0, stock="LAM16-BW", lines=("45°C",)),)
    )
    assert worst_severity(compile_job(bad)) is Severity.ERROR


def test_the_shipped_example_makes_a_sheet() -> None:
    text = setup_sheet(compile_job(load_job(EXAMPLE)))
    assert "MCC-7" in text
    assert "P-130" in text


def test_an_empty_job_still_makes_a_sheet() -> None:
    text = setup_sheet(compile_job(JobSpec(name="empty")))
    assert "SETUP SHEET   empty" in text
    assert "nothing to report" in text


def test_a_handed_in_estimate_is_not_worked_out_again() -> None:
    from dragpoint.estimate.cycle import estimate_job

    made = compile_job(small_job())
    time = estimate_job(made, load_time=0.0)
    text = setup_sheet(made, time=time)
    assert f"{time.minutes:.0f} minutes" in text


def test_a_row_is_padded_to_its_column_width() -> None:
    text = sheet_for(small_job())
    rows = [line for line in text.splitlines() if line.startswith("P-")]
    assert len({len(row) for row in rows}) == 1


def test_a_job_with_no_holes_has_no_drilling_block() -> None:
    assert "DRILLING" not in sheet_for(small_job())


def test_a_job_with_holes_gets_a_drilling_block() -> None:
    from dragpoint.geometry.point import Point
    from dragpoint.spec.feature import Feature

    hole = Feature.round_hole("fix1", Point(6.0, 10.0), 4.2)
    job = small_job(
        plates=(
            PlateSpec(
                name="P-1",
                width=60.0,
                height=20.0,
                stock="LAM16-BW",
                lines=("ONE",),
                features=(hole,),
            ),
        )
    )
    text = sheet_for(job)
    assert "DRILLING" in text
    assert "drills      4.2mm" in text


def test_the_drilling_block_says_it_is_a_second_setup() -> None:
    text = setup_sheet(compile_job(load_job(EXAMPLE)))
    assert "second setup, drill in the spindle" in text


def test_every_drill_size_in_the_job_is_listed_once() -> None:
    text = setup_sheet(compile_job(load_job(EXAMPLE)))
    line = next(line for line in text.splitlines() if line.startswith("drills"))
    assert line.count("4.2mm") == 1


def gauge_sheet() -> str:
    """The setup sheet for the shipped job that needs all three setups."""
    example = EXAMPLE.parent / "gauge-panel-4.toml"
    return setup_sheet(compile_job(load_job(example)))


def test_the_windows_get_a_block_of_their_own() -> None:
    text = gauge_sheet()
    assert "WINDOWS (third setup, profile cutter in the spindle)" in text
    assert "tabs a window" in text


def test_the_window_block_names_the_plate_and_the_cutter() -> None:
    text = gauge_sheet()
    assert "INST-1" in text
    assert "P-020" in text


def test_a_job_with_no_windows_has_no_window_block() -> None:
    assert "WINDOWS" not in setup_sheet(compile_job(load_job(EXAMPLE)))


def test_the_sheet_says_what_the_whole_shop_time_is() -> None:
    assert "all setups" in gauge_sheet()


def test_a_job_of_one_setup_does_not_say_all_setups() -> None:
    plate = PlateSpec(name="P-1", width=60.0, height=20.0, stock="LAM16-BW", lines=("RUN",))
    assert "all setups" not in setup_sheet(compile_job(JobSpec(name="J", plates=(plate,))))


def test_the_drilling_block_still_comes_before_the_windows() -> None:
    text = gauge_sheet()
    assert text.index("DRILLING") < text.index("WINDOWS")
