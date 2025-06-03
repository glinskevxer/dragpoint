"""From strokes on a plate to a program the machine can run.

The layer that knows about depth, order and travel. Nothing above it knows
which end of a stroke the cutter enters from, and nothing below it knows
that a stroke came from a letter.
"""

from dragpoint.path.cut import Cut, CutList, PassOrder, expand_passes

__all__ = ["Cut", "CutList", "PassOrder", "expand_passes"]
