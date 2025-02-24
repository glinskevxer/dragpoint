"""The stroke font: glyphs, faces, and the file format they load from.

A face here is nothing like a TrueType face. There are no outlines, no
composites and no hinting. What there is instead is a set of named glyphs
made of centreline strokes on an integer design grid, a small metrics block,
and a kerning table, which between them is everything the shaper needs.
"""

from dragpoint.font.glyph import Glyph, glyph_name_for

__all__ = ["Glyph", "glyph_name_for"]
