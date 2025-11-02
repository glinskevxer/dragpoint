"""Compiling one plate all the way through."""

from __future__ import annotations

import pytest

from dragpoint.compiler.plate import compile_plate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.path.cut import PassOrder
from dragpoint.rules.check import RuleSelection
from dragpoint.rules.report import Severity
from dragpoint.spec.job import JobSpec
from dragpoint.spec.load import load_job
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitPolicy

from .conftest import EXAMPLE, plate_spec


def test_a_plain_plate_compiles_and_passes() -> None:
    made = compile_plate(plate_spec())
    assert made.name == "P-101"
    assert made.ok
    assert made.report.at_least(Severity.ERROR).clean


def test_the_lettering_ends_up_the_size_the_plate_asked_for() -> None:
    made = compile_plate(plate_spec(lines=("RUN",), cap_height=3.5))
    assert made.style.cap_height == 3.5
    box = made.text.ink_bounds()
    assert box is not None
    assert box.height == pytest.approx(3.5)


def test_the_strokes_are_the_laid_out_text() -> None:
    made = compile_plate(plate_spec())
    assert len(made.strokes) > 0
    box = made.text.ink_bounds()
    assert box is not None
    assert made.spec.area().contains_box(box, tolerance=0.5)


def test_the_stock_decides_the_depth_when_nobody_else_does() -> None:
    made = compile_plate(plate_spec())
    assert made.depth == made.stock.nominal_depth


def test_a_plate_can_name_its_own_depth() -> None:
    made = compile_plate(plate_spec(depth=0.3))
    assert made.depth == 0.3


def test_a_job_depth_applies_when_the_plate_is_quiet() -> None:
    spec = plate_spec()
    job = JobSpec(name="J", plates=(spec,), depth=0.35)
    assert compile_plate(spec, job=job).depth == 0.35


def test_the_job_decides_the_cutter() -> None:
    spec = plate_spec()
    job = JobSpec(name="J", plates=(spec,), cutter="V60-020")
    assert compile_plate(spec, job=job).cutter.name == "V60-020"


def test_a_plate_can_name_its_own_cutter() -> None:
    spec = plate_spec(cutter="V10-005")
    job = JobSpec(name="J", plates=(spec,), cutter="V60-020")
    assert compile_plate(spec, job=job).cutter.name == "V10-005"


def test_the_cuts_cover_every_pass() -> None:
    made = compile_plate(plate_spec(stock="LAM32-RW", depth=0.9))
    assert made.passes.cutting_passes == 3
    assert made.cuts.pass_count() == 3
    assert len(made.cuts) == len(made.runs) * 3


def test_a_spring_pass_is_added_when_the_job_asks_for_one() -> None:
    spec = plate_spec()
    job = JobSpec(name="J", plates=(spec,), spring_pass=True)
    assert compile_plate(spec, job=job).passes.has_spring_pass


def test_the_pass_order_comes_off_the_machine_setup() -> None:
    spec = plate_spec(stock="LAM32-RW", depth=0.9)
    by_pass = compile_plate(spec, setup=MachineSetup(pass_order=PassOrder.BY_PASS))
    by_stroke = compile_plate(spec, setup=MachineSetup(pass_order=PassOrder.BY_STROKE))
    assert by_pass.cuts.cut_length() == pytest.approx(by_stroke.cuts.cut_length())
    assert [cut.pass_index for cut in list(by_pass.cuts)[:3]] == [0, 0, 0]
    assert [cut.pass_index for cut in list(by_stroke.cuts)[:3]] == [0, 1, 2]


def test_both_pass_orders_cut_the_runs_in_the_same_travel_order() -> None:
    spec = plate_spec(stock="LAM32-RW", depth=0.9)
    by_pass = compile_plate(spec, setup=MachineSetup(pass_order=PassOrder.BY_PASS))
    by_stroke = compile_plate(spec, setup=MachineSetup(pass_order=PassOrder.BY_STROKE))
    first_pass = [cut.stroke for cut in by_pass.cuts.by_pass(0)]
    every_third = [cut.stroke for cut in by_stroke.cuts if cut.pass_index == 0]
    assert first_pass == every_third


def test_the_travel_optimiser_earns_its_keep() -> None:
    made = compile_plate(plate_spec())
    assert made.order.after <= made.order.before


def test_the_optimiser_can_be_turned_off() -> None:
    plain = compile_plate(plate_spec(), setup=MachineSetup().without_optimising())
    tidy = compile_plate(plate_spec())
    assert tidy.order.after <= plain.order.after


def test_the_toolpath_covers_every_cut() -> None:
    made = compile_plate(plate_spec())
    assert made.toolpath.cut_length(MachineSetup().origin) == pytest.approx(made.cuts.cut_length())


def test_the_runs_are_the_strokes_with_the_joints_glued_up() -> None:
    made = compile_plate(plate_spec())
    assert len(made.runs) <= len(made.strokes)
    drawn = sum(stroke.length() for stroke in made.strokes)
    cut = sum(stroke.length() for stroke in made.runs)
    assert cut == pytest.approx(drawn)


def test_the_toolpath_takes_its_feeds_from_the_stock() -> None:
    made = compile_plate(plate_spec())
    feeds = {move.feed for move in made.toolpath if move.feed is not None}
    assert made.stock.feed in feeds
    assert made.stock.plunge_feed in feeds


def test_a_border_is_cut_as_a_closed_rectangle() -> None:
    plain = compile_plate(plate_spec())
    bordered = compile_plate(plate_spec(border=1.5, margin=3.0))
    assert len(bordered.strokes) == len(plain.strokes) + 1
    ring = max(bordered.strokes, key=lambda stroke: stroke.length())
    assert ring.is_closed()


def test_a_border_is_not_measured_against_the_text_margin() -> None:
    made = compile_plate(plate_spec(lines=("RUN",), border=1.5, margin=6.0))
    assert made.report.by_rule("engraving-inside-area").clean
    assert made.report.by_rule("border-on-plate").clean


def test_a_border_hanging_off_the_plate_is_reported() -> None:
    made = compile_plate(plate_spec(border=0.0, margin=3.0))
    assert not made.report.by_rule("border-on-plate").clean


def test_a_blank_plate_compiles_to_nothing_and_is_still_ok() -> None:
    made = compile_plate(plate_spec(lines=()))
    assert made.strokes == ()
    assert len(made.cuts) == 0
    assert len(made.toolpath) == 0
    assert made.ok


def test_a_legend_that_will_not_fit_comes_out_not_fitting() -> None:
    made = compile_plate(
        plate_spec(lines=("EMERGENCY STOP PUSHBUTTON ISOLATOR",), width=25.0, fit=FitPolicy.NONE)
    )
    assert not made.fit.fits
    assert not made.ok
    assert not made.report.by_rule("legend-overrun").clean


def test_the_compiler_never_quietly_fixes_anything() -> None:
    spec = plate_spec(lines=("EMERGENCY STOP PUSHBUTTON",), width=25.0, fit=FitPolicy.NONE)
    made = compile_plate(spec)
    assert made.style.cap_height == spec.cap_height
    assert made.style.condense == spec.condense


def test_the_rules_can_be_narrowed() -> None:
    spec = plate_spec(lines=("45°C",))
    everything = compile_plate(spec)
    narrowed = compile_plate(spec, selection=RuleSelection(only=frozenset({"stroke-merge"})))
    assert not everything.report.by_rule("legend-missing-glyph").clean
    assert narrowed.report.by_rule("legend-missing-glyph").clean


def test_the_check_can_be_rebuilt_from_the_result() -> None:
    made = compile_plate(plate_spec())
    check = made.check()
    assert check.plate is made.spec
    assert check.depth == made.depth
    assert check.strokes == made.strokes


def test_every_plate_in_the_shipped_example_compiles() -> None:
    job = load_job(EXAMPLE)
    for spec in job.plates:
        made = compile_plate(spec, job=job)
        assert made.report.at_least(Severity.ERROR).clean, f"{spec.name}: {made.report}"


def test_str_says_what_came_out() -> None:
    text = str(compile_plate(plate_spec()))
    assert text.startswith("P-101: ")
    assert text.endswith("ok")


def test_a_plate_with_a_stock_that_is_not_on_the_rack_says_so() -> None:
    with pytest.raises(KeyError, match="no stock"):
        compile_plate(PlateSpec(name="P", width=50.0, height=20.0, stock="NOPE-99"))


def test_a_plate_with_a_cutter_that_is_not_in_the_crib_says_so() -> None:
    with pytest.raises(KeyError, match="no cutter"):
        compile_plate(plate_spec(cutter="V99-999"))
