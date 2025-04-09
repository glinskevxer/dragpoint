"""Stacking shaped lines into a block and putting the block in a box.

A legend plate is usually one line and sometimes four. What makes this worth
a module is not the stacking, it is the alignment: a plate whose text is
centred to the plate rather than to the engraving area sits visibly off
centre once the fixing holes are drilled, and that is a scrap plate.

The measured width of a line is its advance width less one trailing track.
Tracking is added after every glyph, including the last, because that is what
makes the next run start in the right place. When a line is being centred
that trailing space is not part of what the eye sees, so it comes off first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from dragpoint.font.face import StrokeFace
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.text.shape import ShapedRun, shape_run
from dragpoint.text.style import TextStyle

__all__ = ["HAlign", "LaidOutText", "VAlign", "layout_lines", "visual_width"]


class HAlign(StrEnum):
    """Where a line sits across the box it was given."""

    LEFT = "left"
    CENTRE = "centre"
    RIGHT = "right"


class VAlign(StrEnum):
    """Where the stack of lines sits up the box it was given.

    ``BASELINE`` puts the first baseline on the top edge of the box and lets
    the rest fall below it, which is what a drawing means when it dimensions
    to a baseline rather than to the lettering.
    """

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"
    BASELINE = "baseline"


def visual_width(run: ShapedRun) -> float:
    """The width of a run with the trailing track taken off.

    Never negative. A run of one glyph with heavy negative tracking would
    otherwise measure as less than nothing and centre itself off the plate.
    """
    if not run.placed:
        return 0.0
    return max(0.0, run.width - run.style.tracking)


@dataclass(frozen=True, slots=True)
class LaidOutText:
    """A stack of positioned lines, and the box they were laid into."""

    lines: tuple[ShapedRun, ...]
    box: Box | None
    line_pitch: float

    def strokes(self) -> tuple[Stroke, ...]:
        """Every stroke in the block, top line first."""
        return tuple(stroke for line in self.lines for stroke in line.strokes())

    def ink_bounds(self) -> Box | None:
        """The box round every mark in the block."""
        merged: Box | None = None
        for line in self.lines:
            box = line.ink_bounds()
            if box is None:
                continue
            merged = box if merged is None else merged.union(box)
        return merged

    def moved(self, delta: Point) -> LaidOutText:
        """The whole block shifted."""
        return LaidOutText(
            lines=tuple(line.moved(delta) for line in self.lines),
            box=None if self.box is None else self.box.moved(delta),
            line_pitch=self.line_pitch,
        )

    @property
    def widest(self) -> float:
        """The widest line, measured the way alignment measures it."""
        return max((visual_width(line) for line in self.lines), default=0.0)

    def __len__(self) -> int:
        return len(self.lines)

    def __str__(self) -> str:
        return f"{len(self.lines)} lines, widest {self.widest:.3f}mm"


def _x_offset(align: HAlign, box: Box, width: float) -> float:
    """Where the left end of a line of ``width`` goes."""
    if align is HAlign.LEFT:
        return box.min_x
    if align is HAlign.RIGHT:
        return box.max_x - width
    return box.min_x + (box.width - width) / 2.0


def _first_baseline(
    align: VAlign, box: Box, count: int, pitch: float, face: StrokeFace, scale: float
) -> float:
    """The y of the first baseline for the whole stack."""
    ascender = face.metrics.ascender * scale
    descender = face.metrics.descender * scale
    block_height = (count - 1) * pitch + (ascender - descender)
    if align is VAlign.BASELINE:
        return box.max_y
    if align is VAlign.TOP:
        return box.max_y - ascender
    if align is VAlign.BOTTOM:
        return box.min_y - descender + (count - 1) * pitch
    slack = (box.height - block_height) / 2.0
    return box.max_y - slack - ascender


def layout_lines(
    lines: Sequence[str],
    face: StrokeFace,
    style: TextStyle,
    *,
    box: Box | None = None,
    halign: HAlign = HAlign.LEFT,
    valign: VAlign = VAlign.TOP,
) -> LaidOutText:
    """Shape and stack ``lines``, aligned inside ``box``.

    With no box the block is laid out from the origin: the first baseline on
    y zero and every line starting at x zero, whatever the alignment says.
    That is the form the fitter measures, because measuring a block that has
    already been pushed around by an alignment tells you nothing about how
    wide it wants to be.
    """
    scale = face.scale_for_cap_height(style.cap_height)
    pitch = style.resolved_line_pitch(face)
    shaped = [shape_run(line, face, style) for line in lines]

    if box is None:
        placed = tuple(run.moved(Point(0.0, -index * pitch)) for index, run in enumerate(shaped))
        return LaidOutText(lines=placed, box=None, line_pitch=pitch)

    baseline = _first_baseline(valign, box, len(shaped), pitch, face, scale)
    placed_lines: list[ShapedRun] = []
    for index, run in enumerate(shaped):
        offset = _x_offset(halign, box, visual_width(run))
        placed_lines.append(run.moved(Point(offset, baseline - index * pitch)))
    return LaidOutText(lines=tuple(placed_lines), box=box, line_pitch=pitch)
