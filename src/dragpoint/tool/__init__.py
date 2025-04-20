"""The machine side: cutters, stock and how deep to go.

Nothing in here knows what a glyph is. It answers questions about grooves,
depths and materials, and the rules layer is what puts those answers next to
the geometry.
"""

from dragpoint.tool.cutter import Cutter, catalogue_cutter

__all__ = ["Cutter", "catalogue_cutter"]
