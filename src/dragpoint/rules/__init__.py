"""The rules that decide whether a plate can actually be cut.

Every rule answers one question and reports what it measured. Nothing here
changes any geometry: a rule that could quietly fix a plate would hide the
fact that the plate was wrong, and the drawing office needs to know.
"""

from dragpoint.rules.report import Report, Severity, Violation

__all__ = ["Report", "Severity", "Violation"]
