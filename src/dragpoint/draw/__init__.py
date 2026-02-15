"""Drawings of a plate, for people rather than for machines.

A post processor writes what the machine will do. These write what the plate
will look like, which is a different question and is answered before the
machine is switched on.
"""

from dragpoint.draw.dxf import render_dxf
from dragpoint.draw.sheet import render_nest
from dragpoint.draw.specimen import render_specimen
from dragpoint.draw.svg import render_svg

__all__ = ["render_dxf", "render_nest", "render_specimen", "render_svg"]
