"""One stroke at one depth, and the list of them that makes a plate.

Up to here a stroke is a line on a drawing. From here it is a thing the
machine does: at a depth, on a pass, in an order, with a lift either side of
it. The cut is the smallest unit the post processors know about.

Multi pass cutting has two orders and the choice is not cosmetic. Cutting the
whole plate to the first depth and then going round again keeps the Z axis
still for the length of a pass and gives the laminate time to cool, but it
walks the whole plate once per pass. Cutting each stroke to full depth before
moving on walks the plate once, and drives the Z axis up and down at every
letter. Laminate wants the first, brass wants the second, and neither is a
default that suits both.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum

from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.tool.passes import PassPlan

__all__ = ["Cut", "CutList", "PassOrder", "expand_passes"]


class PassOrder(StrEnum):
    """Which way round the passes and the strokes are nested."""

    BY_PASS = "by-pass"
    BY_STROKE = "by-stroke"


@dataclass(frozen=True, slots=True)
class Cut:
    """One stroke, cut once, at one depth.

    ``pass_index`` counts from zero and is kept even after ordering, so a
    post processor can tell that two cuts along the same line are the same
    line twice rather than two lines that happen to coincide.
    """

    stroke: Stroke
    depth: float
    pass_index: int
    tag: str = "legend"

    def __post_init__(self) -> None:
        if self.depth <= 0.0:
            raise ValueError(f"a cut to depth {self.depth} removes nothing")
        if self.pass_index < 0:
            raise ValueError(f"a pass index of {self.pass_index} is not a pass")

    @property
    def start(self) -> Point:
        """Where the cutter goes down."""
        return self.stroke.start

    @property
    def end(self) -> Point:
        """Where the cutter comes up."""
        return self.stroke.end

    def length(self) -> float:
        """How far the cutter travels while cutting."""
        return self.stroke.length()

    def bounds(self) -> Box:
        """The box round this cut."""
        return self.stroke.bounds()

    def reversed(self) -> Cut:
        """The same cut, entered from the other end."""
        return Cut(
            stroke=self.stroke.reversed(),
            depth=self.depth,
            pass_index=self.pass_index,
            tag=self.tag,
        )

    def __str__(self) -> str:
        return f"{self.tag} pass {self.pass_index} at {self.depth:.3f}mm, {self.length():.2f}mm"


@dataclass(frozen=True, slots=True)
class CutList:
    """Every cut for one plate, in the order the machine will do them."""

    cuts: tuple[Cut, ...] = ()

    @classmethod
    def of(cls, cuts: Iterable[Cut]) -> CutList:
        """Build from any iterable, keeping the order given."""
        return cls(tuple(cuts))

    def cut_length(self) -> float:
        """Total distance cut, which is what the feed rate is billed at."""
        return sum(cut.length() for cut in self.cuts)

    def travel_length(self, start: Point | None = None) -> float:
        """Total distance moved between cuts, in the order they are in.

        The move from ``start`` to the first cut counts. A program that
        begins at the machine origin and starts cutting in the far corner
        has paid for that move whether or not anyone counted it.
        """
        total = 0.0
        here = start
        for cut in self.cuts:
            if here is not None:
                total += here.distance_to(cut.start)
            here = cut.end
        return total

    def bounds(self) -> Box | None:
        """The box round every cut, ``None`` when there are none."""
        merged: Box | None = None
        for cut in self.cuts:
            box = cut.bounds()
            merged = box if merged is None else merged.union(box)
        return merged

    def depths(self) -> tuple[float, ...]:
        """Every distinct depth, shallowest first."""
        return tuple(sorted({cut.depth for cut in self.cuts}))

    def pass_count(self) -> int:
        """How many distinct passes are in the list."""
        return len({cut.pass_index for cut in self.cuts})

    def by_pass(self, index: int) -> CutList:
        """Just the cuts on one pass, in order."""
        return CutList(tuple(cut for cut in self.cuts if cut.pass_index == index))

    def by_tag(self, tag: str) -> CutList:
        """Just the cuts carrying one tag, in order."""
        return CutList(tuple(cut for cut in self.cuts if cut.tag == tag))

    def tags(self) -> tuple[str, ...]:
        """Every tag present, sorted."""
        return tuple(sorted({cut.tag for cut in self.cuts}))

    def then(self, other: CutList) -> CutList:
        """This list followed by another."""
        return CutList(self.cuts + other.cuts)

    def __len__(self) -> int:
        return len(self.cuts)

    def __iter__(self) -> Iterator[Cut]:
        return iter(self.cuts)

    def __getitem__(self, index: int) -> Cut:
        return self.cuts[index]

    def __str__(self) -> str:
        return (
            f"{len(self.cuts)} cuts over {self.pass_count()} passes, "
            f"{self.cut_length():.1f}mm of cutting"
        )


def expand_passes(
    strokes: Sequence[Stroke],
    plan: PassPlan,
    *,
    order: PassOrder = PassOrder.BY_PASS,
    tag: str = "legend",
) -> CutList:
    """Turn strokes and a pass plan into the cuts that make them.

    The order the cuts come out in is the order they will be done in unless
    something downstream reorders them, and the travel optimiser only ever
    reorders inside a pass, so this is where the nesting is decided.
    """
    cuts: list[Cut] = []
    if order is PassOrder.BY_PASS:
        for index, depth in enumerate(plan):
            for stroke in strokes:
                cuts.append(Cut(stroke=stroke, depth=depth, pass_index=index, tag=tag))
    else:
        for stroke in strokes:
            for index, depth in enumerate(plan):
                cuts.append(Cut(stroke=stroke, depth=depth, pass_index=index, tag=tag))
    return CutList(tuple(cuts))
