"""The rules that decide whether a plate can actually be cut.

Every rule answers one question and reports what it measured. Nothing here
changes any geometry: a rule that could quietly fix a plate would hide the
fact that the plate was wrong, and the drawing office needs to know.
"""

from dragpoint.rules import fitment as _fitment
from dragpoint.rules import legibility as _legibility
from dragpoint.rules import process as _process
from dragpoint.rules.check import PlateCheck, RuleSelection, rule_names, run_rules
from dragpoint.rules.report import Report, Severity, Violation

__all__ = [
    "PlateCheck",
    "Report",
    "RuleSelection",
    "Severity",
    "Violation",
    "rule_names",
    "run_rules",
]

# Importing the rule modules is what puts them in the register. Without this
# a caller who imports only `dragpoint.rules` gets an empty register and a
# plate that passes every check there is, which is the worst way to fail.
_RULE_MODULES = (_legibility, _fitment, _process)
