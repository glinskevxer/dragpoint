"""Turning a string into positioned glyphs on the plate.

This is the layer where font units become millimetres. Above it nothing
knows about the design grid and below it nothing knows about plates.
"""

from dragpoint.text.style import TextStyle

__all__ = ["TextStyle"]
