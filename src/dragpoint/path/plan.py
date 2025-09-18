"""The finished toolpath: every move the machine makes, in order.

Z is measured from the surface of the work and up is positive, so a cut at
0.25 mm deep happens at z minus 0.25. The two heights above the work are not
the same thing and confusing them is expensive in both directions.

``clearance`` is the little hop between one cut and the next. It has to
clear the chips and nothing else, so it is a fraction of a millimetre and
the machine barely slows down for it.

``safe`` is high enough to cross the whole plate over a clamp, a finished
plate or a lump of swarf. Retracting to it between every letter is what
makes a program take twice as long as it needs to; not retracting to it when
crossing the bed is what breaks cutters.

The rule this uses is distance. A short hop stays at clearance; anything
longer than the hop limit goes up to safe first. Between passes it always
goes to safe, because that is where the operator will be watching from.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from dragpoint.errors import OutOfRange
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.path.cut import CutList
from dragpoint.units import QUANTUM

__all__ = ["Move", "MoveKind", "Toolpath", "build_toolpath"]

DEFAULT_SAFE = 5.0
"""Millimetres above the work, high enough to cross a clamp."""

DEFAULT_CLEARANCE = 0.5
"""Millimetres above the work for a hop between two nearby cuts."""

DEFAULT_HOP_LIMIT = 25.0
"""Millimetres of travel past which the head goes up to the safe height."""

ORIGIN = Point(0.0, 0.0)
"""Where the head is taken to be before the first move."""


class MoveKind(StrEnum):
    """What the machine is doing on this move."""

    RAPID = "rapid"
    LIFT = "lift"
    PLUNGE = "plunge"
    FEED = "feed"

    @property
    def is_cutting(self) -> bool:
        """True when material is coming off."""
        return self is MoveKind.FEED


@dataclass(frozen=True, slots=True)
class Move:
    """One line of the program: where to go, how high, and how fast.

    ``feed`` is millimetres per minute, or ``None`` for a rapid. A rapid
    with a feed rate would be a contradiction and the post processors would
    have to decide which to believe.
    """

    kind: MoveKind
    to: Point
    z: float
    feed: float | None = None

    def __post_init__(self) -> None:
        if self.kind is MoveKind.RAPID and self.feed is not None:
            raise ValueError("a rapid has no feed rate")
        if self.kind is not MoveKind.RAPID and self.feed is None:
            raise ValueError(f"a {self.kind} move needs a feed rate")
        if self.feed is not None and self.feed <= 0.0:
            raise OutOfRange("feed", self.feed, QUANTUM, float("inf"))

    def __str__(self) -> str:
        speed = "rapid" if self.feed is None else f"F{self.feed:g}"
        return f"{self.kind} to {self.to} z{self.z:.3f} {speed}"


@dataclass(frozen=True, slots=True)
class Toolpath:
    """Every move for one plate, with the heights it was built at."""

    moves: tuple[Move, ...] = ()
    safe: float = DEFAULT_SAFE
    clearance: float = DEFAULT_CLEARANCE

    def __len__(self) -> int:
        return len(self.moves)

    def __iter__(self) -> Iterator[Move]:
        return iter(self.moves)

    def __getitem__(self, index: int) -> Move:
        return self.moves[index]

    def of_kind(self, kind: MoveKind) -> tuple[Move, ...]:
        """Every move of one kind, in order."""
        return tuple(move for move in self.moves if move.kind is kind)

    def bounds(self) -> Box | None:
        """The box the toolpath covers in x and y."""
        return Box.around(move.to for move in self.moves)

    def deepest(self) -> float:
        """The lowest z reached, which is negative for anything that cuts."""
        return min((move.z for move in self.moves), default=0.0)

    def highest(self) -> float:
        """The highest z reached."""
        return max((move.z for move in self.moves), default=0.0)

    def length_of(self, kind: MoveKind, start: Point = ORIGIN) -> float:
        """Distance travelled in x and y on moves of one kind."""
        total = 0.0
        here = start
        for move in self.moves:
            if move.kind is kind:
                total += here.distance_to(move.to)
            here = move.to
        return total

    def cut_length(self, start: Point = ORIGIN) -> float:
        """Distance cut, which is what the feed rate is billed at."""
        return self.length_of(MoveKind.FEED, start)

    def rapid_length(self, start: Point = ORIGIN) -> float:
        """Distance moved in the air."""
        return self.length_of(MoveKind.RAPID, start)

    def plunge_depth(self) -> float:
        """Total distance the Z axis travels downwards under feed."""
        total = 0.0
        here = 0.0
        for move in self.moves:
            if move.kind is MoveKind.PLUNGE and move.z < here:
                total += here - move.z
            here = move.z
        return total

    def __str__(self) -> str:
        return (
            f"{len(self.moves)} moves, {self.cut_length():.1f}mm cutting, "
            f"{self.rapid_length():.1f}mm in the air"
        )


def build_toolpath(
    cuts: CutList,
    *,
    feed: float,
    plunge_feed: float,
    safe: float = DEFAULT_SAFE,
    clearance: float = DEFAULT_CLEARANCE,
    hop_limit: float = DEFAULT_HOP_LIMIT,
    start: Point = ORIGIN,
) -> Toolpath:
    """Turn an ordered list of cuts into moves.

    The list is taken in the order it arrives. Reordering is
    :func:`dragpoint.path.order.order_cuts` and it happens first, because a
    toolpath that reordered itself would have to decide what a lift means
    before it knew where the next cut was.
    """
    if safe <= clearance:
        raise OutOfRange("clearance", clearance, 0.0, safe)
    if clearance <= 0.0:
        raise OutOfRange("clearance", clearance, QUANTUM, safe)
    if hop_limit < 0.0:
        raise OutOfRange("hop limit", hop_limit, 0.0, float("inf"))

    moves: list[Move] = []
    here = start
    height = safe
    current_pass: int | None = None

    for cut in cuts:
        crossing = here.distance_to(cut.start)
        between_passes = current_pass is not None and cut.pass_index != current_pass
        wanted = safe if between_passes or crossing > hop_limit else clearance
        if height < wanted:
            moves.append(Move(MoveKind.LIFT, here, wanted, plunge_feed))
            height = wanted
        if crossing > QUANTUM:
            moves.append(Move(MoveKind.RAPID, cut.start, height))
            here = cut.start
        moves.append(Move(MoveKind.PLUNGE, cut.start, -cut.depth, plunge_feed))
        height = -cut.depth
        for point in cut.stroke.points[1:]:
            moves.append(Move(MoveKind.FEED, point, -cut.depth, feed))
        here = cut.end
        current_pass = cut.pass_index

    if moves:
        moves.append(Move(MoveKind.LIFT, here, safe, plunge_feed))
    return Toolpath(moves=tuple(moves), safe=safe, clearance=clearance)
