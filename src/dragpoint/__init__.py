"""dragpoint compiles legend plate artwork into engraving toolpaths.

The shop this was written for cuts control panel legend plates: the little
laminated rectangles screwed next to a switch that say PUMP 2 RUN or ESTOP.
They are engraved with a conical cutter that gets wider the deeper it goes,
which is the fact that makes the whole job interesting. Nothing here is a
general purpose font library. Everything is centreline strokes and cutter
geometry, because that is what a rotary engraver actually follows.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
