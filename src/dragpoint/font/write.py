"""Write a face back out as .strk source.

The output is canonical: the same face always produces the same bytes, and
the bytes parse back into the same face. That is what makes a face safe to
regenerate in a build step, because a diff of the file is then a diff of the
face and not a diff of whatever order a dictionary happened to be in.

Glyphs come out ordered by code point, with the unencoded ones after them by
name. A font file that lists A next to B is one a person can read.

A composed glyph goes back out as the compose line it came in as. Writing
its strokes instead would round trip perfectly well and would quietly turn
an accented capital into a drawn one, so the next time somebody moved the E
the E acute would stay where it was.
"""

from __future__ import annotations

from dragpoint.font.face import StrokeFace
from dragpoint.font.glyph import Glyph

__all__ = ["format_number", "write_face"]

_HEADER_ORDER = (
    ("upem", "units_per_em"),
    ("cap", "cap_height"),
    ("xheight", "x_height"),
    ("ascender", "ascender"),
    ("descender", "descender"),
    ("linegap", "line_gap"),
)


def format_number(value: float) -> str:
    """Write a coordinate the shortest way that reads back the same.

    Whole numbers lose the decimal point, because the design grid is integer
    and a file full of ``40.0`` is a file nobody wants to edit. Anything that
    is not whole keeps four places, which is the grid resolution of every
    design tool that has ever handed us a face.
    """
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _glyph_sort_key(glyph: Glyph) -> tuple[int, int, str]:
    """Encoded glyphs first in code point order, then the rest by name."""
    if glyph.codepoint is None:
        return (1, 0, glyph.name)
    return (0, glyph.codepoint, glyph.name)


def _write_glyph(glyph: Glyph) -> list[str]:
    """The lines for one glyph block."""
    header = f"glyph {glyph.name} {glyph.advance}"
    if glyph.codepoint is not None:
        header += f" U+{glyph.codepoint:04X}"
    lines = [header]
    lines.extend(f"  tag {tag}" for tag in sorted(glyph.tags) if tag != "composed")
    if glyph.composed_from is not None:
        base, mark = glyph.composed_from
        lines.append(f"  compose {base} {mark}")
        return lines
    for stroke in glyph.strokes:
        points = " ".join(
            f"{format_number(point.x)},{format_number(point.y)}" for point in stroke.points
        )
        lines.append(f"  s {points}")
    return lines


def write_face(face: StrokeFace) -> str:
    """Render ``face`` as .strk source, ending with a newline."""
    lines = [f"face {face.name}"]
    for keyword, attribute in _HEADER_ORDER:
        lines.append(f"{keyword} {getattr(face.metrics, attribute)}")
    if face.fallback is not None:
        lines.append(f"fallback {face.fallback}")

    for glyph in sorted(face.glyphs.values(), key=_glyph_sort_key):
        lines.append("")
        lines.extend(_write_glyph(glyph))

    if face.kerning:
        lines.append("")
        for (left, right), value in sorted(face.kerning.items()):
            lines.append(f"kern {left} {right} {value}")

    return "\n".join(lines) + "\n"
