"""Getting the pieces onto the sheet.

Nesting is about the blank rather than about the engraving, so nothing here
knows what is written on a plate. It knows how big it is and how many are
wanted, and that is all it needs.
"""

from dragpoint.nest.shelf import NestResult, Placement, nest_job, nest_pieces

__all__ = ["NestResult", "Placement", "nest_job", "nest_pieces"]
