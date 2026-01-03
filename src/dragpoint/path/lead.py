"""Going into the work along the line rather than straight down it.

A cutter dropped vertically into laminate at the start of every stroke
leaves a mark. On a two ply it is a round spot slightly wider than the
groove, at the start of every letter, and on a plate with two hundred
strokes on it there are two hundred of them. Nobody notices until the light
is at the wrong angle, and then nobody notices anything else.

Ramping is the fix and it is old. Instead of plunging to depth and then
moving, the cutter descends while it moves along the first part of the
stroke it is about to cut. The mark goes where the groove was going anyway.

The ramp has to be shorter than the stroke. On a stroke shorter than the
ramp there is nowhere to descend, and what happens then is a decision this
module makes once: it ramps over the whole stroke and reaches full depth at
the far end, which is what a helical entry does in a hole too small to
spiral in.
"""

from __future__ import annotations

from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.units import QUANTUM

__all__ = ["ramp_entry"]


def ramp_entry(stroke: Stroke, depth: float, ramp: float) -> list[tuple[Point, float]]:
    """The points and depths of a ramped entry into ``stroke``.

    The first entry is the start of the stroke at depth zero and the last is
    the point where full depth is reached. Everything between is a step down
    along the line. A ramp of nothing gives one entry at full depth, which
    is a plain plunge and is what the caller gets when it asks for one.
    """
    if depth <= 0.0:
        raise OutOfRange("depth", depth, QUANTUM, float("inf"))
    if ramp < 0.0:
        raise OutOfRange("ramp", ramp, 0.0, float("inf"))
    if ramp < QUANTUM:
        return [(stroke.start, depth)]

    length = stroke.length()
    reach = min(ramp, length)
    if reach < QUANTUM:
        return [(stroke.start, depth)]

    entry: list[tuple[Point, float]] = [(stroke.start, 0.0)]
    walked = 0.0
    for first, second in stroke.segments:
        span = first.distance_to(second)
        if span < QUANTUM:
            continue
        if walked + span >= reach - QUANTUM:
            share = (reach - walked) / span
            entry.append((first.lerp(second, share), depth))
            return entry
        walked += span
        entry.append((second, depth * walked / reach))
    entry.append((stroke.end, depth))
    return entry


def ramped_remainder(stroke: Stroke, ramp: float) -> Stroke | None:
    """What is left of ``stroke`` after a ramp of ``ramp`` millimetres.

    ``None`` when the ramp used the whole stroke up, which is the case the
    caller has to handle: the cutter is at depth at the far end and there is
    nothing further to cut on this pass.
    """
    if ramp < QUANTUM:
        return stroke
    length = stroke.length()
    if ramp >= length - QUANTUM:
        return None
    kept: list[Point] = []
    walked = 0.0
    for first, second in stroke.segments:
        span = first.distance_to(second)
        if span < QUANTUM:
            continue
        if not kept and walked + span >= ramp - QUANTUM:
            share = (ramp - walked) / span
            kept.append(first.lerp(second, share))
        walked += span
        if kept:
            kept.append(second)
    if len(kept) < 2:
        return None
    return Stroke(tuple(kept))
