"""What the drawing office says it wants, before anything is worked out.

A spec is data. It holds no geometry beyond the shapes it was given, does no
layout and never looks at a cutter. Everything derived lives downstream of
here so that a spec can be read back out and compared with what came in.
"""

from dragpoint.spec.feature import Feature, FeatureKind
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.plate import PlateSpec
from dragpoint.spec.sheetload import load_csv_job

__all__ = [
    "Feature",
    "FeatureKind",
    "JobSpec",
    "PlateSpec",
    "Sheet",
    "load_csv_job",
]
