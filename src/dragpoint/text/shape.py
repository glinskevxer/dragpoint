"""Turning a string into glyphs at positions, in millimetres.

This is where the design grid stops. Everything upstream of here counts in
font units; everything downstream counts in millimetres on the plate. The
join is one multiplication and it happens once per glyph, here.

Shaping is deliberately dumb. There is no bidirectional text, no script
detection and no substitution. A legend plate says PUMP 2 RUN, left to
right, and the only cleverness it needs is kerning and a word space the
plate can override.

The one exception is tabular figures, and it is here rather than in the
face because it is a property of the job: the same face sets a scale plate
with its figures on a pitch and a legend with them set the way they were
drawn. A figure on a pitch is centred in it, so the column lines up on the
middle of the digit, which is where the eye reads a scale from.
"""

from __future__ import annotations

from dataclasses import dataclass

from dragpoint.font.face import StrokeFace
from dragpoint.font.glyph import Glyph, glyph_name_for
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.geometry.transform import Transform
from dragpoint.text.style import TextStyle

__all__ = ["PlacedGlyph", "ShapedRun", "shape_run"]


@dataclass(frozen=True, slots=True)
class PlacedGlyph:
    """One glyph, sized and put where it goes.

    The glyph keeps its font units. Only :meth:`transform` knows the scale,
    so a run can be rescaled by rebuilding the transforms without touching a
    single coordinate, which is what the fitter does over and over.
    """

    glyph: Glyph
    origin: Point
    scale: float
    shape: Transform

    def transform(self) -> Transform:
        """Font units to the plate, for this glyph at this position."""
        return (
            Transform.scaling(self.scale)
            .then(self.shape)
            .then(Transform.translation(self.origin.x, self.origin.y))
        )

    def strokes(self) -> tuple[Stroke, ...]:
        """The glyph's strokes in millimetres, where they land on the plate."""
        transform = self.transform()
        return tuple(stroke.transformed(transform) for stroke in self.glyph.strokes)

    def ink_bounds(self) -> Box | None:
        """The box round the marks in millimetres, ``None`` when blank."""
        return Box.around([point for stroke in self.strokes() for point in stroke.points])

    def moved(self, delta: Point) -> PlacedGlyph:
        """The same glyph shifted."""
        return PlacedGlyph(
            glyph=self.glyph,
            origin=self.origin + delta,
            scale=self.scale,
            shape=self.shape,
        )

    def through(self, transform: Transform) -> PlacedGlyph:
        """The same glyph with ``transform`` applied after everything else."""
        moved = transform.apply(self.origin)
        return PlacedGlyph(
            glyph=self.glyph,
            origin=moved,
            scale=self.scale,
            shape=self.shape.then(_without_translation(transform)),
        )


def _without_translation(transform: Transform) -> Transform:
    """``transform`` with its move stripped, leaving only the distortion."""
    return Transform(transform.a, transform.b, transform.c, transform.d, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class ShapedRun:
    """A single line of text, shaped, with its advance width.

    ``width`` is the pen movement, not the extent of the marks. A run ending
    in a space is wider than its ink and that is the number alignment has to
    use, or a centred legend with a trailing space sits off centre.
    """

    text: str
    face_name: str
    style: TextStyle
    placed: tuple[PlacedGlyph, ...]
    width: float

    @property
    def is_blank(self) -> bool:
        """True when the run puts no cutter down."""
        return all(item.glyph.is_blank for item in self.placed)

    def strokes(self) -> tuple[Stroke, ...]:
        """Every stroke in the run, in millimetres, in reading order."""
        return tuple(stroke for item in self.placed for stroke in item.strokes())

    def ink_bounds(self) -> Box | None:
        """The box round the marks, ``None`` when the run is blank."""
        boxes = [box for box in (item.ink_bounds() for item in self.placed) if box is not None]
        if not boxes:
            return None
        merged = boxes[0]
        for box in boxes[1:]:
            merged = merged.union(box)
        return merged

    def moved(self, delta: Point) -> ShapedRun:
        """The whole run shifted, which is how layout places a line."""
        return ShapedRun(
            text=self.text,
            face_name=self.face_name,
            style=self.style,
            placed=tuple(item.moved(delta) for item in self.placed),
            width=self.width,
        )

    def through(self, transform: Transform) -> ShapedRun:
        """The whole run put through ``transform``, keeping its width."""
        return ShapedRun(
            text=self.text,
            face_name=self.face_name,
            style=self.style,
            placed=tuple(item.through(transform) for item in self.placed),
            width=self.width,
        )

    def __len__(self) -> int:
        return len(self.placed)

    def __str__(self) -> str:
        return f"{self.text!r} in {self.face_name}, {self.width:.3f}mm wide"


def _advance_for(
    glyph: Glyph, character: str, style: TextStyle, scale: float, pitch: float
) -> float:
    """The pen movement after ``glyph``, before tracking."""
    if character == " " and style.word_space is not None:
        return style.word_space
    if pitch > 0.0 and character.isdigit():
        return pitch * scale * style.condense
    return glyph.advance * scale * style.condense


def _figure_offset(glyph: Glyph, character: str, pitch: float, scale: float) -> float:
    """How far into its pitch a figure sits, so it is centred in it.

    Zero for everything that is not a figure and for a face whose figures
    already fill the pitch, which is most of them for the zero itself.
    """
    if pitch <= 0.0 or not character.isdigit():
        return 0.0
    return (pitch - glyph.advance) / 2.0 * scale


def shape_run(text: str, face: StrokeFace, style: TextStyle) -> ShapedRun:
    """Shape one line of ``text``. Newlines are not handled here.

    Tracking is added after every glyph including the last, so the width of a
    run is the width the next run would start at. Layout takes the trailing
    track off when it centres, because that is the only place that knows
    whether the run is being centred.
    """
    if "\n" in text:
        raise ValueError("shape_run takes one line, split the text first")
    scale = face.scale_for_cap_height(style.cap_height)
    distortion = style.glyph_transform()
    pitch = float(face.figure_advance()) if style.tabular else 0.0
    placed: list[PlacedGlyph] = []
    pen = 0.0
    previous: str | None = None

    for character in text:
        name = glyph_name_for(character)
        glyph = face.glyph(name)
        if style.kerning and previous is not None and not (pitch > 0.0 and character.isdigit()):
            pen += face.kern(previous, name) * scale * style.condense
        inset = _figure_offset(glyph, character, pitch, scale)
        placed.append(
            PlacedGlyph(glyph=glyph, origin=Point(pen + inset, 0.0), scale=scale, shape=distortion)
        )
        pen += _advance_for(glyph, character, style, scale, pitch) + style.tracking
        previous = name

    run = ShapedRun(
        text=text,
        face_name=face.name,
        style=style,
        placed=tuple(placed),
        width=pen,
    )
    if style.mirror:
        return run.through(style.run_transform(pen))
    return run
