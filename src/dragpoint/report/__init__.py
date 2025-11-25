"""Paperwork: what goes to the machine alongside the program.

Nothing here decides anything or changes anything. It reads a compiled job
and writes something a person reads.
"""

from dragpoint.report.setup import setup_sheet

__all__ = ["setup_sheet"]
