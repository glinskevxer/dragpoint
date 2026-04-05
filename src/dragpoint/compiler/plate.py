"""Compiling one plate: from what was ordered to what the machine runs.

This is the only module in dragpoint that knows about every layer at once.
Everything it does is arranged in one direction, and the order is the whole
design: resolve, fit, lay out, draw, plan, order, post, and only then check.

Checking last matters. A rule about the groove cannot run before the depth is
settled, a rule about the margin cannot run before the fitter has decided how
big the lettering ended up, and a rule that ran early would be answering a
question about a plate nobody is going to cut.

Nothing here is allowed to fix anything. If the legend does not fit, it comes
out not fitting and the report says so. A compiler that quietly shrank the
lettering to make its own rules pass would be the most expensive kind of
helpful there is.
"""

from __future__ import annotations

from dataclasses import dataclass

from dragpoint.compiler.settings import MachineSetup
from dragpoint.font.face import StrokeFace
from dragpoint.font.library import load_face
from dragpoint.geometry.arc import bend
from dragpoint.geometry.box import Box
from dragpoint.geometry.stroke import Stroke, join_runs
from dragpoint.path.cut import CutList, expand_passes
from dragpoint.path.order import OrderResult, order_cuts
from dragpoint.path.plan import Toolpath, build_toolpath
from dragpoint.rules.check import PlateCheck, RuleSelection, run_rules
from dragpoint.rules.report import Report, Severity
from dragpoint.spec.job import JobSpec
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitResult, fit_lines
from dragpoint.text.layout import LaidOutText, VAlign, layout_lines
from dragpoint.text.style import TextStyle
from dragpoint.text.wrap import wrap_to_box
from dragpoint.tool.cutter import Cutter, catalogue_cutter
from dragpoint.tool.material import Material, material
from dragpoint.tool.passes import PassPlan, plan_passes
from dragpoint.units import QUANTUM

__all__ = ["EngravedPlate", "compile_plate"]


@dataclass(frozen=True, slots=True)
class EngravedPlate:
    """One plate, all the way through, with everything it was decided from."""

    spec: PlateSpec
    lines: tuple[str, ...]
    face: StrokeFace
    style: TextStyle
    fit: FitResult
    text: LaidOutText
    strokes: tuple[Stroke, ...]
    text_strokes: tuple[Stroke, ...]
    runs: tuple[Stroke, ...]
    cutter: Cutter
    stock: Material
    depth: float
    passes: PassPlan
    cuts: CutList
    order: OrderResult
    toolpath: Toolpath
    report: Report

    @property
    def name(self) -> str:
        """The plate name off the schedule."""
        return self.spec.name

    @property
    def ok(self) -> bool:
        """True when nothing in the report rose to an error."""
        return self.report.ok

    def check(self) -> PlateCheck:
        """Rebuild the bag the rules were handed.

        Handy for running one rule again by hand, and for a caller that
        wants to run the rules with a different selection without
        recompiling the plate.
        """
        return PlateCheck(
            plate=self.spec,
            lines=self.lines,
            face=self.face,
            style=self.style,
            fit=self.fit,
            text=self.text,
            strokes=self.strokes,
            text_strokes=self.text_strokes,
            cutter=self.cutter,
            stock=self.stock,
            depth=self.depth,
            passes=self.passes,
        )

    def __str__(self) -> str:
        verdict = "ok" if self.ok else "not ok"
        return (
            f"{self.spec.name}: {len(self.strokes)} strokes, "
            f"{len(self.cuts)} cuts, {self.report}, {verdict}"
        )


def rule_selection(job: JobSpec) -> RuleSelection:
    """Turn what a schedule says about the rules into a selection.

    A severity word the register has never heard of is left out rather than
    raised on, and comes back through
    :meth:`~dragpoint.rules.check.RuleSelection.unknown_names` with every
    other name that answers to nothing.
    """
    severity: dict[str, Severity] = {}
    for name, word in job.rules_severity.items():
        for level in Severity:
            if str(level) == str(word).lower():
                severity[name] = level
    return RuleSelection(
        only=frozenset(job.rules_only),
        skip=frozenset(job.rules_skip),
        severity=severity,
    )


def _single(plan: PassPlan) -> PassPlan:
    """The same plan cut down to one pass, for deciding the travel order.

    The order of the runs does not depend on how deep they are cut, so the
    optimiser is given one pass and its answer is reused for all of them.
    """
    return PassPlan(
        depths=(plan.final_depth,),
        groove_width=plan.groove_width,
        has_spring_pass=False,
    )


def _lines_of(spec: PlateSpec, face: StrokeFace) -> tuple[str, ...]:
    """The lines to set, broken up first when the plate asks for it.

    Wrapping happens before fitting, not after. A legend broken into three
    lines needs far less squeezing than the same words on one, and fitting
    first would squeeze it to nothing and then break the squeezed version.
    """
    if not spec.wrap:
        return spec.lines
    style = spec.style()
    broken: list[str] = []
    for line in spec.lines:
        broken.extend(wrap_to_box(line, face, style, spec.fit_limit(), spec.area().height))
    return tuple(broken)


def _lay_out(
    spec: PlateSpec,
    face: StrokeFace,
    style: TextStyle,
    lines: tuple[str, ...],
    groove: float = 0.0,
) -> LaidOutText:
    """Lay the lines out, either in the engraving area or ready to be bent.

    The area is pulled in by half the groove first. Everything above this
    layer works in centrelines, and a centreline on the edge of the area is
    a groove half over the line: a plate set hard against its margin comes
    out failing the area rule by a hundredth of a millimetre, which is true,
    unhelpful, and happens on every top aligned plate this shop cuts.

    Text that is going to be bent is laid out about the origin instead: x
    zero is the middle of the block and the first baseline is y zero, which
    is exactly what the arc map expects to be handed. Putting it in the
    engraving area first and bending afterwards would bend the alignment as
    well, and a centred legend would come out somewhere else entirely.
    """
    if spec.arc() is None:
        return layout_lines(
            lines,
            face,
            style,
            box=spec.area().grown(-groove / 2.0),
            halign=spec.halign,
            valign=spec.valign,
        )
    natural = layout_lines(lines, face, style)
    half = max(natural.widest, QUANTUM) / 2.0
    return layout_lines(
        lines,
        face,
        style,
        box=Box(-half, -1.0, half, 0.0),
        halign=spec.halign,
        valign=VAlign.BASELINE,
    )


def _text_strokes(spec: PlateSpec, text: LaidOutText) -> tuple[Stroke, ...]:
    """The lettering, bent round the arc when the plate asks for one."""
    arc = spec.arc()
    if arc is None:
        return tuple(text.strokes())
    return tuple(bend(stroke, arc) for stroke in text.strokes())


def _border_strokes(spec: PlateSpec) -> list[Stroke]:
    """The engraved border, as one closed rectangle, or nothing."""
    box = spec.border_box()
    if box is None:
        return []
    corners = box.corners
    return [Stroke(tuple(corners) + (corners[0],))]


def compile_plate(
    spec: PlateSpec,
    *,
    job: JobSpec | None = None,
    setup: MachineSetup | None = None,
    selection: RuleSelection | None = None,
) -> EngravedPlate:
    """Compile one plate into cuts, a toolpath and a report.

    ``job`` supplies the cutter and any depth override. Without one the
    plate is compiled on its own with the shop default cutter, which is
    what the single plate commands do.
    """
    machine = setup or MachineSetup()
    owner = job or JobSpec(name=spec.name, plates=(spec,))
    wanted = selection if selection is not None else rule_selection(owner)
    face = load_face(spec.face)
    stock = material(spec.stock)
    cutter = catalogue_cutter(owner.cutter_for(spec))
    depth = owner.depth_for(spec)
    if depth is None:
        depth = stock.nominal_depth

    lines = _lines_of(spec, face)
    fit = fit_lines(lines, face, spec.style(), spec.fit_limit(), spec.fit)
    text = _lay_out(spec, face, fit.style, lines, cutter.width_at_depth(depth))
    lettering = _text_strokes(spec, text)

    drawn = lettering + tuple(_border_strokes(spec))
    runs = tuple(join_runs(list(drawn)))
    passes = plan_passes(depth, stock, cutter, spring_pass=owner.spring_pass)

    # The travel order is decided over the runs, once, before the passes are
    # expanded. Ordering afterwards would have to gather the cuts of a pass
    # back together to compare them, which is the same as choosing the pass
    # order all over again and would quietly overrule the setup.
    ordered = order_cuts(
        expand_passes(runs, _single(passes)),
        start=machine.origin,
        allow_reverse=machine.allow_reverse,
        rounds=machine.optimise_rounds,
    )
    cuts = expand_passes(
        [cut.stroke for cut in ordered.cuts],
        passes,
        order=machine.pass_order,
    )
    toolpath = build_toolpath(
        cuts,
        feed=stock.feed,
        plunge_feed=stock.plunge_feed,
        safe=machine.safe,
        clearance=machine.clearance,
        hop_limit=machine.hop_limit,
        ramp=machine.ramp,
        start=machine.origin,
    )

    check = PlateCheck(
        plate=spec,
        lines=lines,
        face=face,
        style=fit.style,
        fit=fit,
        text=text,
        strokes=drawn,
        text_strokes=lettering,
        cutter=cutter,
        stock=stock,
        depth=depth,
        passes=passes,
    )
    return EngravedPlate(
        spec=spec,
        lines=lines,
        face=face,
        style=fit.style,
        fit=fit,
        text=text,
        strokes=drawn,
        text_strokes=lettering,
        runs=runs,
        cutter=cutter,
        stock=stock,
        depth=depth,
        passes=passes,
        cuts=cuts,
        order=ordered,
        toolpath=toolpath,
        report=run_rules(check, wanted),
    )
