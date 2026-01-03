"""From strokes on a plate to a program the machine can run.

The layer that knows about depth, order and travel. Nothing above it knows
which end of a stroke the cutter enters from, and nothing below it knows
that a stroke came from a letter.
"""

from dragpoint.path.cut import Cut, CutList, PassOrder, expand_passes
from dragpoint.path.lead import ramp_entry
from dragpoint.path.order import OrderResult, order_cuts
from dragpoint.path.plan import Move, MoveKind, Toolpath, build_toolpath

__all__ = [
    "Cut",
    "CutList",
    "Move",
    "MoveKind",
    "OrderResult",
    "PassOrder",
    "Toolpath",
    "build_toolpath",
    "expand_passes",
    "order_cuts",
    "ramp_entry",
]
