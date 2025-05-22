"""What a rule gets to look at, and the register of rules.

A rule is a function from one :class:`PlateCheck` to some violations. It gets
the finished geometry and every decision that produced it, because most of
the interesting rules are about the relationship between two of those and not
about either on its own. Stroke separation is only a question once the cutter
and the depth are both known; a legend that is too small to read is only a
question once the fitter has had its way with the height.

Rules register themselves by decorator, and the register is ordered by
registration so a report reads in the order the rules were written down. That
is deliberate: sorting a report by severity is something the reader asks for,
not something the rules impose.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from dragpoint.font.face import StrokeFace
from dragpoint.geometry.box import Box
from dragpoint.geometry.stroke import Stroke
from dragpoint.rules.report import Report, Severity, Violation
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitResult
from dragpoint.text.layout import LaidOutText
from dragpoint.text.style import TextStyle
from dragpoint.tool.cutter import Cutter
from dragpoint.tool.material import Material
from dragpoint.tool.passes import PassPlan

__all__ = [
    "REGISTRY",
    "PlateCheck",
    "RuleDef",
    "rule",
    "rule_names",
    "run_rules",
]


@dataclass(frozen=True, slots=True)
class PlateCheck:
    """Everything known about one plate once it has been laid out."""

    plate: PlateSpec
    face: StrokeFace
    style: TextStyle
    fit: FitResult
    text: LaidOutText
    strokes: tuple[Stroke, ...]
    cutter: Cutter
    stock: Material
    depth: float
    passes: PassPlan

    @property
    def groove_width(self) -> float:
        """The width of the mark this plate will actually carry."""
        return self.cutter.width_at_depth(self.depth)

    @property
    def area(self) -> Box:
        """The box the engraving has to stay inside."""
        return self.plate.area()

    def ink_bounds(self) -> Box | None:
        """The box round everything that gets cut, ``None`` for a blank plate."""
        points = [point for stroke in self.strokes for point in stroke.points]
        return Box.around(points)

    def __str__(self) -> str:
        return f"{self.plate.name} on {self.stock.name} with {self.cutter.name}"


RuleFunction = Callable[["PlateCheck"], Iterable[Violation]]


@dataclass(frozen=True, slots=True)
class RuleDef:
    """One registered rule."""

    name: str
    description: str
    severity: Severity
    check: RuleFunction

    def __str__(self) -> str:
        return f"{self.name} ({self.severity}): {self.description}"


REGISTRY: dict[str, RuleDef] = {}
"""Every rule, in registration order."""


def rule(
    name: str,
    description: str,
    severity: Severity = Severity.ERROR,
) -> Callable[[RuleFunction], RuleFunction]:
    """Register a rule under ``name``.

    The function comes back unchanged so it can still be called directly,
    which is what the tests do. Registering the same name twice is a
    programming error and is refused rather than silently replaced.
    """

    def register(function: RuleFunction) -> RuleFunction:
        if name in REGISTRY:
            raise ValueError(f"a rule called {name!r} is already registered")
        REGISTRY[name] = RuleDef(
            name=name,
            description=description,
            severity=severity,
            check=function,
        )
        return function

    return register


def rule_names() -> tuple[str, ...]:
    """Every registered rule name, in registration order."""
    return tuple(REGISTRY)


@dataclass(frozen=True, slots=True)
class RuleSelection:
    """Which rules run and at what severity.

    An empty ``only`` means every rule. ``severity`` overrides the level a
    named rule reports at, which is how a job says a warning is an error for
    this customer without anybody editing the rule.
    """

    only: frozenset[str] = field(default_factory=frozenset)
    skip: frozenset[str] = field(default_factory=frozenset)
    severity: Mapping[str, Severity] = field(default_factory=dict)

    def wants(self, name: str) -> bool:
        """True when the named rule should run."""
        if name in self.skip:
            return False
        return not self.only or name in self.only

    def level_for(self, definition: RuleDef) -> Severity:
        """The severity this selection wants for ``definition``."""
        return self.severity.get(definition.name, definition.severity)

    def unknown_names(self) -> tuple[str, ...]:
        """Names mentioned that no rule answers to, sorted.

        Reported rather than raised. A job that skips a rule which was
        renamed should still cut, and the operator should be told.
        """
        mentioned = set(self.only) | set(self.skip) | set(self.severity)
        return tuple(sorted(mentioned - set(REGISTRY)))


def run_rules(check: PlateCheck, selection: RuleSelection | None = None) -> Report:
    """Run the rules over one plate and collect what they say.

    A rule reports its own severity through the definition, not through the
    violation it builds, so a rule body cannot decide it is more important
    than the register says it is.
    """
    wanted = selection or RuleSelection()
    found: list[Violation] = []
    for definition in REGISTRY.values():
        if not wanted.wants(definition.name):
            continue
        level = wanted.level_for(definition)
        for violation in definition.check(check):
            found.append(_at_level(violation, definition.name, level))
    return Report.of(found)


def _at_level(violation: Violation, name: str, severity: Severity) -> Violation:
    """Stamp the rule name and severity the register decided on."""
    return Violation(
        rule=name,
        severity=severity,
        message=violation.message,
        where=violation.where,
        measured=violation.measured,
        limit=violation.limit,
        unit=violation.unit,
        subject=violation.subject,
    )
