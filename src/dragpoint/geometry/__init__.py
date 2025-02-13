"""Plane geometry, in millimetres, with no dependency on anything above it.

The whole package is two dimensional on purpose. Depth is a property of a cut,
not of a point, and mixing the two is how a toolpath ends up with a Z value
buried inside a glyph outline where no layout code can reach it.
"""

from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke, join_runs
from dragpoint.geometry.transform import Transform

__all__ = ["Box", "Point", "Stroke", "Transform", "join_runs"]
