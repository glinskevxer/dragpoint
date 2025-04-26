"""What a rule says when it is unhappy, and how those add up.

A violation is a fact with a number on it, not a sentence. The rule says
what it measured, what the limit was and where on the plate it happened, and
the CLI turns that into English. Keeping the number means a report can be
sorted by how badly something failed, which is the order an operator wants
to work through it in.

Severity is a decision about the job, not about the geometry. The same
half millimetre gap is a warning on a one off and an error on a batch of two
hundred, so severity comes from the rule's configuration and never from the
measurement.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import IntEnum

from dragpoint.geometry.point import Point

__all__ = ["Report", "Severity", "Violation"]


class Severity(IntEnum):
    """How much a violation matters.

    Ordered, so the worst one in a report is ``max(...)``. Integer rather
    than string because sorting by it is the whole point.
    """

    NOTE = 10
    WARNING = 20
    ERROR = 30

    def __str__(self) -> str:
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Violation:
    """One rule, unhappy about one thing, with the numbers it measured.

    ``measured`` and ``limit`` are in whatever unit the rule works in, named
    by ``unit``. Both are optional because a few rules are about presence
    rather than size, such as a legend the face cannot draw at all.
    """

    rule: str
    severity: Severity
    message: str
    where: Point | None = None
    measured: float | None = None
    limit: float | None = None
    unit: str = "mm"
    subject: str | None = None

    @property
    def margin(self) -> float | None:
        """How far past the limit the measurement went, if both are known.

        Positive means over. A rule with a floor rather than a ceiling
        reports its own sign by putting the numbers in that way round, so
        this is always read as badness rather than as a difference.
        """
        if self.measured is None or self.limit is None:
            return None
        return self.measured - self.limit

    def __str__(self) -> str:
        parts = [f"{self.severity}: {self.message}"]
        if self.subject:
            parts.insert(0, self.subject)
        if self.measured is not None and self.limit is not None:
            parts.append(f"({self.measured:.4g}{self.unit} against {self.limit:.4g}{self.unit})")
        if self.where is not None:
            parts.append(f"at {self.where}")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class Report:
    """Everything the rules had to say about one plate."""

    violations: tuple[Violation, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, violations: Iterable[Violation]) -> Report:
        """Build from any iterable, keeping the order the rules ran in."""
        return cls(tuple(violations))

    @property
    def worst(self) -> Severity | None:
        """The highest severity present, or ``None`` for a clean report."""
        if not self.violations:
            return None
        return max(item.severity for item in self.violations)

    @property
    def ok(self) -> bool:
        """True when nothing rose to an error.

        Warnings do not stop a job. They are printed, the operator looks at
        the plate and decides, and that decision is not made in here.
        """
        return self.worst is None or self.worst < Severity.ERROR

    @property
    def clean(self) -> bool:
        """True when there is nothing to say at all."""
        return not self.violations

    def at_least(self, severity: Severity) -> Report:
        """The violations at or above ``severity``, as a report."""
        return Report(tuple(item for item in self.violations if item.severity >= severity))

    def by_rule(self, rule: str) -> Report:
        """The violations one named rule raised."""
        return Report(tuple(item for item in self.violations if item.rule == rule))

    def sorted_worst_first(self) -> Report:
        """The same violations, worst severity first, then widest margin.

        The sort is stable inside a severity, so two violations that are
        equally bad come out in the order the rules produced them, which is
        the order they appear on the plate.
        """
        ordered = sorted(
            self.violations,
            key=lambda item: (-int(item.severity), -(item.margin or 0.0)),
        )
        return Report(tuple(ordered))

    def merged(self, other: Report) -> Report:
        """This report followed by ``other``."""
        return Report(self.violations + other.violations)

    def counts(self) -> dict[Severity, int]:
        """How many of each severity, including the zeros."""
        tally = dict.fromkeys(Severity, 0)
        for item in self.violations:
            tally[item.severity] += 1
        return tally

    def __len__(self) -> int:
        return len(self.violations)

    def __iter__(self) -> Iterator[Violation]:
        return iter(self.violations)

    def __bool__(self) -> bool:
        """A report is truthy when it has something to say.

        Deliberately not the same as :attr:`ok`. ``if report:`` reads as
        there being violations, and a report full of warnings is one that
        has something to say and is still fine to cut.
        """
        return bool(self.violations)

    def __str__(self) -> str:
        if not self.violations:
            return "no violations"
        tally = self.counts()
        parts = [f"{tally[level]} {level}" for level in reversed(Severity) if tally[level]]
        return ", ".join(parts)
