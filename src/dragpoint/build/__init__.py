"""Putting the layers together into something a machine can run.

Every other package in dragpoint is deliberately ignorant of the ones above
it. This is the one that knows about all of them, and it is the only place
where a plate spec, a face, a cutter and a sheet of stock are in the same
room.
"""

from dragpoint.build.settings import MachineSetup

__all__ = ["MachineSetup"]
