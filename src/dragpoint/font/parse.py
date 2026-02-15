"""The .strk source format and the parser that reads it.

The format is a line oriented text file because the faces in this shop are
edited by hand as often as they are generated. A binary format would need a
tool to fix a single glyph, and the person who has to fix a single glyph at
seven in the morning does not want a tool.

A file looks like this::

    face panelgothic
    upem 1000
    cap 700
    xheight 500
    ascender 750
    descender -200

    glyph A 600 U+0041
      tag wide
      s 40,0 300,700 560,0
      s 140,250 460,250

    glyph Aacute 600 U+00C1
      compose A acute

    kern A V -60

Header keys come first, then glyph blocks, then kern lines. Indentation
inside a glyph block is conventional, not structural: a ``s`` or ``tag`` line
belongs to the glyph most recently opened however it is indented, which keeps
the parser out of the whitespace business entirely.

A ``compose`` line stands in for the strokes and names a base and a mark.
It is resolved once the whole file has been read, so a composed glyph may
name a base defined further down, and a glyph composed from a composed glyph
works as long as nothing composes itself in a circle.
"""

from __future__ import annotations

from dataclasses import dataclass

from dragpoint.errors import FontSyntax
from dragpoint.font.compose import compose_glyph
from dragpoint.font.face import FaceMetrics, StrokeFace
from dragpoint.font.glyph import Glyph, is_valid_glyph_name
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke

__all__ = ["parse_face"]

_HEADER_KEYS = {
    "upem": "units_per_em",
    "cap": "cap_height",
    "xheight": "x_height",
    "ascender": "ascender",
    "descender": "descender",
    "linegap": "line_gap",
}

_REQUIRED_HEADER = ("upem", "cap", "xheight", "ascender", "descender")


@dataclass
class _GlyphDraft:
    """A glyph being built up line by line."""

    name: str
    advance: int
    codepoint: int | None
    line: int
    strokes: list[Stroke]
    tags: set[str]
    compose: tuple[str, str] | None = None


def parse_face(text: str, source: str = "<string>") -> StrokeFace:
    """Read a ``.strk`` file into a face.

    Every failure names the line it happened on. A face with four hundred
    glyphs is not something anyone finds a typo in by reading.
    """
    face_name: str | None = None
    header: dict[str, int] = {}
    fallback: str | None = None
    drafts: list[_GlyphDraft] = []
    kerns: list[tuple[str, str, int, int]] = []
    current: _GlyphDraft | None = None

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        keyword, _, rest = line.partition(" ")
        rest = rest.strip()
        if keyword == "face":
            if face_name is not None:
                raise FontSyntax(source, number, "the face name is set twice")
            if not rest:
                raise FontSyntax(source, number, "face needs a name")
            face_name = rest
        elif keyword in _HEADER_KEYS:
            if current is not None:
                raise FontSyntax(source, number, f"{keyword} must come before the first glyph")
            header[keyword] = _int(source, number, keyword, rest)
        elif keyword == "fallback":
            fallback = rest
        elif keyword == "glyph":
            current = _start_glyph(source, number, rest)
            drafts.append(current)
        elif keyword == "s":
            if current is None:
                raise FontSyntax(source, number, "a stroke line with no glyph open")
            current.strokes.append(_parse_stroke(source, number, rest))
        elif keyword == "compose":
            if current is None:
                raise FontSyntax(source, number, "a compose line with no glyph open")
            current.compose = _parse_compose(source, number, rest)
        elif keyword == "tag":
            if current is None:
                raise FontSyntax(source, number, "a tag line with no glyph open")
            if not rest:
                raise FontSyntax(source, number, "tag needs a name")
            current.tags.add(rest)
        elif keyword == "kern":
            kerns.append(_parse_kern(source, number, rest))
        else:
            raise FontSyntax(source, number, f"unknown keyword {keyword!r}")

    if face_name is None:
        raise FontSyntax(source, 0, "the file never says what the face is called")
    missing = [key for key in _REQUIRED_HEADER if key not in header]
    if missing:
        raise FontSyntax(source, 0, f"header is missing {', '.join(missing)}")

    return _assemble(source, face_name, header, fallback, drafts, kerns)


def _assemble(
    source: str,
    face_name: str,
    header: dict[str, int],
    fallback: str | None,
    drafts: list[_GlyphDraft],
    kerns: list[tuple[str, str, int, int]],
) -> StrokeFace:
    """Turn the parsed pieces into a face, reporting where each problem was."""
    try:
        metrics = FaceMetrics(**{_HEADER_KEYS[key]: value for key, value in header.items()})
    except ValueError as exc:
        raise FontSyntax(source, 0, str(exc)) from exc

    glyphs: dict[str, Glyph] = {}
    for draft in drafts:
        if draft.name in glyphs:
            raise FontSyntax(source, draft.line, f"glyph {draft.name} appears twice")
        if draft.compose is not None:
            continue
        glyphs[draft.name] = Glyph(
            name=draft.name,
            advance=draft.advance,
            strokes=tuple(draft.strokes),
            codepoint=draft.codepoint,
            tags=frozenset(draft.tags),
        )
    _resolve_composed(source, drafts, glyphs)

    kerning: dict[tuple[str, str], int] = {}
    for left, right, value, line in kerns:
        if left not in glyphs:
            raise FontSyntax(source, line, f"kern names {left!r}, which is not a glyph here")
        if right not in glyphs:
            raise FontSyntax(source, line, f"kern names {right!r}, which is not a glyph here")
        kerning[(left, right)] = value

    try:
        return StrokeFace(
            name=face_name,
            metrics=metrics,
            glyphs=glyphs,
            kerning=kerning,
            fallback=fallback,
        )
    except ValueError as exc:
        raise FontSyntax(source, 0, str(exc)) from exc


def _parse_compose(source: str, number: int, rest: str) -> tuple[str, str]:
    """Read a ``compose`` line into the two names it points at."""
    parts = rest.split()
    if len(parts) != 2:
        raise FontSyntax(source, number, "compose takes a base glyph and a mark glyph")
    return (parts[0], parts[1])


def _resolve_composed(source: str, drafts: list[_GlyphDraft], glyphs: dict[str, Glyph]) -> None:
    """Build every composed glyph, in whatever order they can be built.

    A pass that builds nothing while composed glyphs are still waiting means
    they are waiting on each other or on something that is not there, and
    either way the file is wrong and says which glyph it stopped on.
    """
    waiting = [draft for draft in drafts if draft.compose is not None]
    while waiting:
        made_one = False
        for draft in list(waiting):
            base_name, mark_name = draft.compose or ("", "")
            base = glyphs.get(base_name)
            mark = glyphs.get(mark_name)
            if base is None or mark is None:
                continue
            if draft.strokes:
                raise FontSyntax(
                    source, draft.line, f"{draft.name} has both strokes and a compose line"
                )
            glyphs[draft.name] = compose_glyph(
                draft.name,
                base,
                mark,
                codepoint=draft.codepoint,
                source=source,
                line=draft.line,
            ).with_advance(draft.advance)
            waiting.remove(draft)
            made_one = True
        if not made_one:
            stuck = waiting[0]
            base_name, mark_name = stuck.compose or ("", "")
            raise FontSyntax(
                source,
                stuck.line,
                f"{stuck.name} composes {base_name} and {mark_name}, and one of them "
                "is not a glyph this file can build",
            )


def _start_glyph(source: str, number: int, rest: str) -> _GlyphDraft:
    """Read a ``glyph`` line into a draft."""
    parts = rest.split()
    if len(parts) < 2:
        raise FontSyntax(source, number, "glyph needs a name and an advance")
    name = parts[0]
    if not is_valid_glyph_name(name):
        raise FontSyntax(source, number, f"{name!r} is not a usable glyph name")
    advance = _int(source, number, "advance", parts[1])
    if advance < 0:
        raise FontSyntax(source, number, f"glyph {name} has a negative advance")
    codepoint: int | None = None
    if len(parts) > 2:
        codepoint = _codepoint(source, number, parts[2])
    if len(parts) > 3:
        raise FontSyntax(source, number, "glyph takes a name, an advance and a code point")
    return _GlyphDraft(
        name=name,
        advance=advance,
        codepoint=codepoint,
        line=number,
        strokes=[],
        tags=set(),
    )


def _parse_stroke(source: str, number: int, rest: str) -> Stroke:
    """Read an ``s`` line into a stroke."""
    points: list[Point] = []
    for token in rest.split():
        x_text, comma, y_text = token.partition(",")
        if not comma:
            raise FontSyntax(source, number, f"{token!r} is not an x,y pair")
        points.append(
            Point(
                _float(source, number, "x", x_text),
                _float(source, number, "y", y_text),
            )
        )
    if len(points) < 2:
        raise FontSyntax(source, number, "a stroke needs at least two points")
    return Stroke(tuple(points))


def _parse_kern(source: str, number: int, rest: str) -> tuple[str, str, int, int]:
    """Read a ``kern`` line into a pair and a value."""
    parts = rest.split()
    if len(parts) != 3:
        raise FontSyntax(source, number, "kern takes a left glyph, a right glyph and a value")
    return parts[0], parts[1], _int(source, number, "kern value", parts[2]), number


def _codepoint(source: str, number: int, token: str) -> int:
    """Read a ``U+XXXX`` token."""
    if not token.upper().startswith("U+"):
        raise FontSyntax(source, number, f"{token!r} is not a U+ code point")
    try:
        return int(token[2:], 16)
    except ValueError as exc:
        raise FontSyntax(source, number, f"{token!r} is not a U+ code point") from exc


def _int(source: str, number: int, what: str, token: str) -> int:
    """Read an integer, refusing the float that a design tool might emit."""
    try:
        return int(token)
    except ValueError as exc:
        raise FontSyntax(source, number, f"{what} should be a whole number, got {token!r}") from exc


def _float(source: str, number: int, what: str, token: str) -> float:
    """Read a coordinate."""
    try:
        return float(token)
    except ValueError as exc:
        raise FontSyntax(source, number, f"{what} should be a number, got {token!r}") from exc
