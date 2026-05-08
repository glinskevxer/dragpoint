"""Compiling one plate all the way through."""

from __future__ import annotations

import math

import pytest

from dragpoint.compiler.plate import compile_plate
from dragpoint.compiler.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.path.cut import PassOrder
from dragpoint.rules.check import RuleSelection
from dragpoint.rules.report import Severity
from dragpoint.spec.job import JobSpec
from dragpoint.spec.load import load_job
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign, VAlign

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


def arc_spec(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-200",
        "width": 60.0,
        "height": 60.0,
        "stock": "LAM16-BW",
        "lines": ("AUTO",),
        "arc_radius": 20.0,
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def test_a_plate_without_an_arc_has_no_arc() -> None:
    assert PlateSpec(name="P", width=60.0, height=20.0, stock="LAM16-BW").arc() is None


def test_the_arc_is_centred_on_the_plate_unless_told_otherwise() -> None:
    arc = arc_spec().arc()
    assert arc is not None
    assert arc.centre == Point(30.0, 30.0)


def test_the_arc_centre_can_be_given() -> None:
    arc = arc_spec(arc_centre=Point(10.0, 40.0)).arc()
    assert arc is not None
    assert arc.centre == Point(10.0, 40.0)


def test_the_fit_limit_is_the_arc_length_and_not_the_plate() -> None:
    plate = arc_spec(arc_sweep=90.0)
    assert plate.fit_limit() == pytest.approx(20.0 * math.pi / 2.0)


def test_a_straight_plate_is_limited_by_its_engraving_area() -> None:
    plate = PlateSpec(name="P", width=60.0, height=20.0, stock="LAM16-BW")
    assert plate.fit_limit() == plate.area().width


@pytest.mark.parametrize("radius", [0.0, -1.0])
def test_an_arc_with_no_radius_is_refused(radius: float) -> None:
    with pytest.raises(Exception, match="arc radius"):
        arc_spec(arc_radius=radius)


@pytest.mark.parametrize("sweep", [0.0, -10.0, 400.0])
def test_a_sweep_that_is_not_a_sweep_is_refused(sweep: float) -> None:
    with pytest.raises(Exception, match="arc sweep"):
        arc_spec(arc_sweep=sweep)


def test_a_bent_legend_sits_on_the_arc() -> None:
    made = compile_plate(arc_spec())
    arc = made.spec.arc()
    assert arc is not None
    reaches = [
        arc.centre.distance_to(point) for stroke in made.text_strokes for point in stroke.points
    ]
    assert min(reaches) >= arc.radius - 0.001
    assert max(reaches) <= arc.radius + made.style.cap_height + 0.001


def test_a_bent_legend_is_centred_on_the_start_angle() -> None:
    made = compile_plate(arc_spec(arc_start=90.0))
    box = made.text_strokes[0].bounds()
    for stroke in made.text_strokes[1:]:
        box = box.union(stroke.bounds())
    assert box.centre.x == pytest.approx(30.0, abs=0.6)
    assert box.max_y > 40.0


def test_the_start_angle_moves_the_legend_round() -> None:
    top = compile_plate(arc_spec(arc_start=90.0))
    bottom = compile_plate(arc_spec(arc_start=270.0, arc_clockwise=True))
    top_box = top.text_strokes[0].bounds()
    bottom_box = bottom.text_strokes[0].bounds()
    assert top_box.min_y > bottom_box.max_y


def test_bending_makes_more_points_than_the_straight_layout() -> None:
    straight = compile_plate(arc_spec(arc_radius=None, height=20.0))
    bent = compile_plate(arc_spec())
    straight_points = sum(len(stroke) for stroke in straight.text_strokes)
    bent_points = sum(len(stroke) for stroke in bent.text_strokes)
    assert bent_points > straight_points


def test_a_tighter_radius_curves_the_letters_more() -> None:
    wide = compile_plate(arc_spec(arc_radius=25.0))
    tight = compile_plate(arc_spec(arc_radius=10.0, height=40.0))
    wide_span = wide.text_strokes[0].bounds().width
    tight_span = tight.text_strokes[0].bounds().width
    assert tight_span != wide_span


def test_the_lettering_is_kept_apart_from_everything_that_is_cut() -> None:
    made = compile_plate(arc_spec(border=2.0, margin=3.0))
    assert len(made.strokes) == len(made.text_strokes) + 1
    assert all(stroke in made.strokes for stroke in made.text_strokes)


def test_the_rules_look_at_the_bent_lettering() -> None:
    made = compile_plate(arc_spec())
    check = made.check()
    assert check.text_strokes == made.text_strokes
    assert check.text_strokes != tuple(check.text.strokes())


def test_a_legend_round_a_bore_stays_on_the_plate() -> None:
    made = compile_plate(arc_spec())
    assert made.ok, str(made.report)


def test_a_legend_too_far_round_is_pulled_in_by_the_fitter() -> None:
    made = compile_plate(arc_spec(lines=("EMERGENCY STOP PUSHBUTTON",), arc_sweep=90.0))
    assert made.style.condense < 1.0


def test_lettering_can_face_inward() -> None:
    outward = compile_plate(arc_spec())
    inward = compile_plate(arc_spec(arc_inward=True))
    arc = outward.spec.arc()
    assert arc is not None
    out_reach = max(
        arc.centre.distance_to(point) for stroke in outward.text_strokes for point in stroke.points
    )
    in_reach = max(
        arc.centre.distance_to(point) for stroke in inward.text_strokes for point in stroke.points
    )
    assert in_reach < out_reach


def test_a_plate_that_does_not_wrap_keeps_the_lines_it_was_given() -> None:
    made = compile_plate(plate_spec(lines=("ISOLATE BEFORE WORKING ON THIS PANEL",)))
    assert made.lines == ("ISOLATE BEFORE WORKING ON THIS PANEL",)


def test_a_wrapping_plate_breaks_a_long_legend() -> None:
    made = compile_plate(
        plate_spec(lines=("ISOLATE BEFORE WORKING ON THIS PANEL",), height=40.0, wrap=True)
    )
    assert len(made.lines) > 1
    assert " ".join(made.lines) == "ISOLATE BEFORE WORKING ON THIS PANEL"


def test_wrapping_happens_before_fitting() -> None:
    words = ("ISOLATE BEFORE WORKING ON THIS PANEL",)
    squeezed = compile_plate(plate_spec(lines=words, height=40.0))
    wrapped = compile_plate(plate_spec(lines=words, height=40.0, wrap=True))
    assert wrapped.style.condense > squeezed.style.condense


def test_wrapping_uses_the_height_it_has() -> None:
    words = ("ISOLATE BEFORE WORKING ON THIS PANEL",)
    short = compile_plate(plate_spec(lines=words, height=12.0, wrap=True))
    tall = compile_plate(plate_spec(lines=words, height=40.0, wrap=True))
    assert len(tall.lines) > len(short.lines)


def test_the_missing_glyph_rule_reads_the_lines_that_were_set() -> None:
    made = compile_plate(plate_spec(lines=("45\u00b0C AND RISING",), height=40.0, wrap=True))
    found = made.report.by_rule("legend-missing-glyph")
    assert not found.clean
    assert found.violations[0].subject == "P-101 line 1"


def test_a_top_aligned_legend_leaves_the_groove_room_at_the_edge() -> None:
    made = compile_plate(
        plate_spec(
            name="P-TOP",
            lines=("METER",),
            width=120.0,
            height=60.0,
            cap_height=4.0,
            valign=VAlign.TOP,
        )
    )
    assert made.ok, str(made.report)


def test_a_bottom_aligned_legend_does_as_well() -> None:
    made = compile_plate(
        plate_spec(
            name="P-BOT",
            lines=("METER",),
            width=120.0,
            height=60.0,
            cap_height=4.0,
            valign=VAlign.BOTTOM,
        )
    )
    assert made.ok, str(made.report)


def test_the_lettering_sits_inside_the_area_by_half_a_groove() -> None:
    made = compile_plate(
        plate_spec(
            name="P-TOP",
            lines=("METER",),
            width=120.0,
            height=60.0,
            cap_height=4.0,
            valign=VAlign.TOP,
        )
    )
    box = made.text.ink_bounds()
    area = made.spec.area()
    assert box is not None
    assert area.max_y - box.max_y >= made.passes.groove_width / 2.0 - 1e-9


def test_a_wider_groove_pulls_the_lettering_further_in() -> None:
    def top_of(cutter: str) -> float:
        made = compile_plate(
            plate_spec(
                name="P-TOP",
                lines=("METER",),
                width=120.0,
                height=60.0,
                cap_height=4.0,
                valign=VAlign.TOP,
                cutter=cutter,
            )
        )
        box = made.text.ink_bounds()
        assert box is not None
        return box.max_y

    assert top_of("V90-030") < top_of("V10-005")


def test_a_left_aligned_legend_leaves_the_same_room() -> None:
    made = compile_plate(
        plate_spec(name="P-L", lines=("METER",), halign=HAlign.LEFT, cap_height=3.0)
    )
    box = made.text.ink_bounds()
    assert box is not None
    assert box.min_x - made.spec.area().min_x >= made.passes.groove_width / 2.0 - 1e-9


def test_nothing_is_dropped_by_default() -> None:
    plain = compile_plate(plate_spec(lines=("PUMP HOUSE",), arc_radius=60.0, width=100.0))
    points = sum(len(run.points) for run in plain.runs)
    assert points == sum(len(stroke.points) for stroke in plain.runs)


def test_a_tolerance_drops_points_off_a_bent_legend() -> None:
    spec = plate_spec(lines=("PUMP HOUSE",), arc_radius=60.0, width=100.0, cap_height=5.0)
    plain = compile_plate(spec)
    simple = compile_plate(spec, setup=MachineSetup(simplify=0.05))
    assert sum(len(run.points) for run in simple.runs) < sum(len(run.points) for run in plain.runs)


def test_a_bigger_tolerance_drops_more() -> None:
    spec = plate_spec(lines=("PUMP HOUSE",), arc_radius=60.0, width=100.0, cap_height=5.0)
    fine = compile_plate(spec, setup=MachineSetup(simplify=0.01))
    coarse = compile_plate(spec, setup=MachineSetup(simplify=0.2))
    assert sum(len(run.points) for run in coarse.runs) < sum(len(run.points) for run in fine.runs)


def test_simplifying_keeps_the_ends_where_they_were() -> None:
    spec = plate_spec(lines=("PUMP HOUSE",), arc_radius=60.0, width=100.0, cap_height=5.0)
    plain = compile_plate(spec)
    simple = compile_plate(spec, setup=MachineSetup(simplify=0.05))
    assert len(simple.runs) == len(plain.runs)
    for before, after in zip(plain.runs, simple.runs, strict=True):
        assert after.start == before.start
        assert after.end == before.end


def test_a_straight_legend_has_nothing_to_drop() -> None:
    spec = plate_spec(lines=("RUN",))
    plain = compile_plate(spec)
    simple = compile_plate(spec, setup=MachineSetup(simplify=0.05))
    assert sum(len(run.points) for run in simple.runs) == sum(len(run.points) for run in plain.runs)


def test_the_toolpath_gets_shorter_to_write_as_well() -> None:
    spec = plate_spec(lines=("PUMP HOUSE",), arc_radius=60.0, width=100.0, cap_height=5.0)
    plain = compile_plate(spec)
    simple = compile_plate(spec, setup=MachineSetup(simplify=0.05))
    assert len(simple.toolpath) < len(plain.toolpath)


def test_a_negative_tolerance_is_refused() -> None:
    with pytest.raises(OutOfRange, match="simplify"):
        MachineSetup(simplify=-1.0)


def test_the_setting_says_so_when_it_is_on() -> None:
    assert "simplify 0.05mm" in str(MachineSetup(simplify=0.05))
    assert "simplify" not in str(MachineSetup())
