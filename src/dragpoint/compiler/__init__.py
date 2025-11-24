"""Putting the layers together into something a machine can run.

Called the compiler and not the build, because pytest skips any directory
called build by default and so does most of the rest of the toolchain. A
package that quietly does not get its tests run is worse than a package with
an awkward name.

Every other package in dragpoint is deliberately ignorant of the ones above
it. This is the one that knows about all of them, and it is the only place
where a plate spec, a face, a cutter and a sheet of stock are in the same
room.
"""

from dragpoint.compiler.drill import DrillPlan, drill_plate
from dragpoint.compiler.job import EngravedJob, compile_job
from dragpoint.compiler.plate import EngravedPlate, compile_plate
from dragpoint.compiler.settings import MachineSetup

__all__ = [
    "DrillPlan",
    "EngravedJob",
    "EngravedPlate",
    "MachineSetup",
    "compile_job",
    "drill_plate",
    "compile_plate",
]
