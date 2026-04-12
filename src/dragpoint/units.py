"""Length units for a shop that never settled on one system.

Everything inside dragpoint is millimetres held as a float. The shop floor is
not: plate stock arrives in imperial gauges, cutter tips are sold in
thousandths of an inch, and the controller on the second machine only speaks
metric. So anything arriving from a plate spec, a material table or the
command line goes through :func:`parse_length`, and anything printed back to a
human goes through :func:`format_length` with the unit that human asked for.

The quantum is deliberate. A rotary engraver positions to about a micron on a
good day and the post processors round to four decimal places of a
millimetre, so two lengths that differ by less than :data:`QUANTUM` are the
same length as far as this package is concerned.

Fractions are read too, because customer drawings are full of them. A bore
comes over as 7/8in and a plate as 1 1/2 x 3in, and retyping those as
decimals is a transcription step nobody should be doing by hand: 0.875 is
one keystroke away from 0.075, and both look like a number.
"""

from __future__ import annotations

import math
import re

from dragpoint.errors import BadLength, BadUnit, OutOfRange

__all__ = [
    "MM_PER_INCH",
    "QUANTUM",
    "UNITS",
    "format_length",
    "parse_length",
    "quantise",
    "require_range",
    "same_length",
    "to_unit",
]

MM_PER_INCH = 25.4
"""Exact by definition since 1959, and the reason nothing here needs a table."""

QUANTUM = 1e-4
"""Millimetres. Below this two lengths are the same length."""

UNITS: dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "um": 0.001,
    "in": MM_PER_INCH,
    "thou": MM_PER_INCH / 1000.0,
    "mil": MM_PER_INCH / 1000.0,
}
"""Suffix to millimetres. ``mil`` and ``thou`` are the same thing; both are in
use here because the cutter catalogue says ``mil`` and the shop says ``thou``.
"""

_LENGTH_RE = re.compile(
    r"""^\s*
    (?P<value>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
    \s*
    (?P<unit>[a-zA-Z"']*)
    \s*$""",
    re.VERBOSE,
)

_FRACTION_RE = re.compile(
    r"""^\s*
    (?P<sign>[+-]?)
    (?:(?P<whole>\d+)\s+)?
    (?P<numerator>\d+)\s*/\s*(?P<denominator>\d+)
    \s*
    (?P<unit>[a-zA-Z"']*)
    \s*$""",
    re.VERBOSE,
)
"""A fraction, with an optional whole number in front of it.

``1 1/2in`` and ``7/8in`` and a bare ``3/8``. The space between the whole
number and the fraction is required, because ``11/2`` is eleven halves on
every drawing anybody has ever sent us.
"""

_ALIASES = {
    '"': "in",
    "''": "in",
    "inch": "in",
    "inches": "in",
    "micron": "um",
    "microns": "um",
    "\u00b5m": "um",
}


def parse_length(text: str | float | int, *, default_unit: str = "mm") -> float:
    """Read ``text`` as a length in millimetres.

    A bare number is taken to be in ``default_unit``, which is how a material
    table written entirely in inches stays readable. Anything else needs a
    suffix.
    """
    if isinstance(text, int | float):
        if isinstance(text, bool):
            raise BadLength(repr(text), "a boolean is not a length")
        return to_unit_factor(default_unit) * float(text)
    fraction = _FRACTION_RE.match(text)
    if fraction is not None:
        return _fraction_length(text, fraction, default_unit)
    match = _LENGTH_RE.match(text)
    if match is None:
        raise BadLength(text, "expected a number with an optional unit suffix")
    raw = match.group("value")
    try:
        value = float(raw)
    except ValueError as exc:  # pragma: no cover - the regex already rejects these
        raise BadLength(text, str(exc)) from exc
    if not math.isfinite(value):
        raise BadLength(text, "not a finite number")
    unit = match.group("unit") or default_unit
    return value * to_unit_factor(unit)


def _fraction_length(text: str, found: re.Match[str], default_unit: str) -> float:
    """A matched fraction turned into millimetres."""
    denominator = int(found.group("denominator"))
    if denominator == 0:
        raise BadLength(text, "a fraction over nothing is not a length")
    whole = int(found.group("whole") or 0)
    value = whole + int(found.group("numerator")) / denominator
    if found.group("sign") == "-":
        value = -value
    return value * to_unit_factor(found.group("unit") or default_unit)


def to_unit_factor(unit: str) -> float:
    """Millimetres per ``unit``, resolving the aliases the shop actually types."""
    key = _ALIASES.get(unit, unit).lower()
    if key not in UNITS:
        raise BadUnit(unit, tuple(sorted(UNITS)))
    return UNITS[key]


def to_unit(mm: float, unit: str) -> float:
    """Convert ``mm`` out of millimetres into ``unit``."""
    return mm / to_unit_factor(unit)


def format_length(mm: float, unit: str = "mm", *, places: int = 4) -> str:
    """Render ``mm`` in ``unit`` with the suffix attached."""
    value = to_unit(mm, unit)
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    if text.lstrip("-") in {"", "0"}:
        # A negative that rounds away still prints "-0.0000", and a leading
        # minus on a zero has confused more than one operator reading a
        # setup sheet.
        text = "0"
    return f"{text}{_ALIASES.get(unit, unit).lower()}"


def quantise(mm: float, quantum: float = QUANTUM) -> float:
    """Snap ``mm`` to the nearest multiple of ``quantum``.

    Rounding happens once, on the way out. Snapping inside the geometry would
    accumulate, and a stroke that has been through six transforms would end up
    somewhere the plate spec never asked for.
    """
    if quantum <= 0.0:
        raise OutOfRange("quantum", quantum, QUANTUM, math.inf)
    return round(mm / quantum) * quantum


def same_length(left: float, right: float, quantum: float = QUANTUM) -> bool:
    """True when two lengths are indistinguishable on this machine."""
    return abs(left - right) < quantum


def require_range(what: str, value: float, low: float, high: float) -> float:
    """Return ``value`` if it sits in ``[low, high]``, else raise."""
    if not math.isfinite(value) or value < low or value > high:
        raise OutOfRange(what, value, low, high)
    return value
