"""Deciding what order to cut in, and which end to start each cut from.

A plate of lettering is a few hundred short strokes with a rapid move between
every pair of them. Cut them in the order they were shaped and the machine
spends more time in the air than in the material, tracing the reading order
of the legend across the plate and back again for every letter.

This is a travelling salesman with a twist: every stop can be entered from
either end, and entering from the far end is often what makes the next move
short. Nearest neighbour gets most of it, and a couple of rounds of two opt
gets most of the rest. Neither is optimal and neither needs to be. The
saving that matters is the first one, from an ordering nobody chose to an
ordering somebody did.

Passes are never mixed. Reordering across a pass boundary would have the
machine cutting at two depths in one sweep, which is not what the pass plan
asked for and would need a Z move between every cut instead of between
every pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from dragpoint.geometry.point import Point
from dragpoint.path.cut import Cut, CutList

__all__ = ["OrderResult", "order_cuts", "travel_of"]

ORIGIN = Point(0.0, 0.0)
"""Where the head is taken to be before the first cut."""


@dataclass(frozen=True, slots=True)
class OrderResult:
    """The reordered cuts, and what the reordering was worth."""

    cuts: CutList
    before: float
    after: float

    @property
    def saved(self) -> float:
        """Millimetres of rapid travel saved. Never negative."""
        return max(0.0, self.before - self.after)

    @property
    def saved_fraction(self) -> float:
        """The saving as a fraction of what it started at."""
        if self.before <= 0.0:
            return 0.0
        return self.saved / self.before

    def __str__(self) -> str:
        return (
            f"travel {self.before:.1f}mm to {self.after:.1f}mm, "
            f"saved {self.saved:.1f}mm ({self.saved_fraction:.0%})"
        )


def travel_of(cuts: CutList, start: Point = ORIGIN) -> float:
    """Rapid travel for a list in the order it is in."""
    return cuts.travel_length(start)


def order_cuts(
    cuts: CutList,
    *,
    start: Point = ORIGIN,
    allow_reverse: bool = True,
    rounds: int = 2,
) -> OrderResult:
    """Reorder ``cuts`` to shorten the travel between them.

    ``allow_reverse`` lets a cut be entered from either end. Turning it off
    is what a job does when the cut direction matters, which on a rotary
    engraver it does not, but on a drag engraver it can: a diamond point
    dragged the other way round a curve leaves a different burr.
    """
    if len(cuts) < 2:
        return OrderResult(cuts=cuts, before=travel_of(cuts, start), after=travel_of(cuts, start))

    before = travel_of(cuts, start)
    ordered: list[Cut] = []
    here = start
    for index in _pass_order(cuts):
        group = list(cuts.by_pass(index))
        group = _nearest_neighbour(group, here, allow_reverse)
        group = _two_opt(group, here, allow_reverse, rounds)
        ordered.extend(group)
        here = group[-1].end
    result = CutList(tuple(ordered))
    return OrderResult(cuts=result, before=before, after=travel_of(result, start))


def _pass_order(cuts: CutList) -> list[int]:
    """The pass indices in the order they first appear."""
    seen: list[int] = []
    for cut in cuts:
        if cut.pass_index not in seen:
            seen.append(cut.pass_index)
    return seen


def _nearest_neighbour(group: list[Cut], start: Point, allow_reverse: bool) -> list[Cut]:
    """Walk to whichever end of whichever cut is closest, every time."""
    remaining = list(group)
    ordered: list[Cut] = []
    here = start
    while remaining:
        best_index = 0
        best_cost = float("inf")
        best_flip = False
        for index, cut in enumerate(remaining):
            forward = here.distance_to(cut.start)
            if forward < best_cost:
                best_index, best_cost, best_flip = index, forward, False
            if allow_reverse:
                backward = here.distance_to(cut.end)
                if backward < best_cost:
                    best_index, best_cost, best_flip = index, backward, True
        chosen = remaining.pop(best_index)
        chosen = chosen.reversed() if best_flip else chosen
        ordered.append(chosen)
        here = chosen.end
    return ordered


def _leg_cost(here: Point, cut: Cut) -> float:
    """The rapid move from ``here`` to the start of ``cut``."""
    return here.distance_to(cut.start)


def _sequence_cost(group: list[Cut], start: Point) -> float:
    """Total rapid travel for a sequence."""
    total = 0.0
    here = start
    for cut in group:
        total += _leg_cost(here, cut)
        here = cut.end
    return total


def _two_opt(group: list[Cut], start: Point, allow_reverse: bool, rounds: int) -> list[Cut]:
    """Reverse sub sequences while that shortens the travel.

    Reversing a run of cuts means running them backwards and entering each
    of them from its other end, so a two opt move here is two changes at
    once. With ``allow_reverse`` off only the order changes, which is a
    weaker move and finds less.
    """
    if rounds <= 0 or len(group) < 3:
        return group
    best = list(group)
    best_cost = _sequence_cost(best, start)
    for _ in range(rounds):
        improved = False
        for first in range(len(best) - 1):
            for last in range(first + 1, len(best)):
                candidate = _reversed_span(best, first, last, allow_reverse)
                cost = _sequence_cost(candidate, start)
                if cost < best_cost - 1e-9:
                    best, best_cost = candidate, cost
                    improved = True
        if not improved:
            break
    return best


def _reversed_span(group: list[Cut], first: int, last: int, allow_reverse: bool) -> list[Cut]:
    """A copy of ``group`` with the span from ``first`` to ``last`` turned round."""
    span = group[first : last + 1][::-1]
    if allow_reverse:
        span = [cut.reversed() for cut in span]
    return group[:first] + span + group[last + 1 :]
