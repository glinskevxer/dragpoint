"""Reading a job out of a TOML file.

TOML because the schedules are written by hand and read by hand. The one
thing this loader does that a plain TOML load does not is lengths: every
distance can be written with a unit, so a schedule from a customer working
in inches stays in inches all the way to the machine.

Every error names the table it happened in. A schedule with sixty plates in
it needs to say which plate, and ``plate[41] "P-227" feature[2]`` is a place
a person can find in a file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from dragpoint.errors import DragpointError, SpecError
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature, FeatureKind
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign, VAlign
from dragpoint.units import parse_length

__all__ = ["load_job", "parse_job"]

_PLATE_LENGTHS = (
    "cap_height",
    "tracking",
    "word_space",
    "line_pitch",
    "margin",
    "border",
    "depth",
    "arc_radius",
)
_PLATE_PLAIN = (
    "face",
    "stock",
    "condense",
    "slant",
    "kerning",
    "tabular",
    "mirror",
    "quantity",
    "sequence_start",
    "notes",
    "arc_start",
    "arc_sweep",
    "arc_clockwise",
    "arc_inward",
    "wrap",
)


def load_job(path: Path | str) -> JobSpec:
    """Read a job from a TOML file on disk."""
    resolved = Path(path)
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise SpecError(str(resolved), "", f"cannot read the file: {exc}") from exc
    return parse_job(raw, str(resolved))


def parse_job(raw: bytes | str, source: str = "<string>") -> JobSpec:
    """Read a job from TOML text or bytes."""
    payload = raw.encode("utf-8") if isinstance(raw, str) else raw
    try:
        document = tomllib.loads(payload.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise SpecError(source, "", f"not readable as TOML: {exc}") from exc

    _reject_unknown(source, "", document, {"job", "defaults", "plate"})
    job_table = _table(source, "job", document.get("job", {}))
    defaults = _table(source, "defaults", document.get("defaults", {}))
    _reject_unknown(
        source,
        "job",
        job_table,
        {"name", "cutter", "post", "spring_pass", "depth", "notes", "sheet", "rules"},
    )

    plates = tuple(
        _read_plate(source, index, entry, defaults)
        for index, entry in enumerate(_plate_entries(source, document))
    )
    sheet = _read_sheet(source, job_table.get("sheet"))

    try:
        return JobSpec(
            name=_require_str(source, "job", job_table, "name"),
            plates=plates,
            sheet=sheet,
            cutter=str(job_table.get("cutter", "V30-015")),
            post=str(job_table.get("post", "iso")),
            spring_pass=bool(job_table.get("spring_pass", False)),
            depth=_optional_length(source, "job", job_table, "depth"),
            notes=str(job_table.get("notes", "")),
            **_read_rules(source, job_table.get("rules")),
        )
    except (ValueError, KeyError, DragpointError) as exc:
        raise SpecError(source, "job", str(exc)) from exc


def _plate_entries(source: str, document: dict[str, Any]) -> list[dict[str, Any]]:
    """The ``[[plate]]`` array, checked to be an array of tables."""
    entries = document.get("plate", [])
    if not isinstance(entries, list):
        raise SpecError(source, "plate", "expected an array of tables, use [[plate]]")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SpecError(source, f"plate[{index}]", "expected a table")
    return entries


def _read_rules(source: str, table: Any) -> dict[str, Any]:
    """The optional ``[job.rules]`` table."""
    if table is None:
        return {}
    where = "job.rules"
    values = _table(source, where, table)
    _reject_unknown(source, where, values, {"only", "skip", "severity"})
    severity = values.get("severity", {})
    if not isinstance(severity, dict):
        raise SpecError(source, where, "severity takes a table of rule names to words")
    return {
        "rules_only": tuple(_read_names(source, where, values, "only")),
        "rules_skip": tuple(_read_names(source, where, values, "skip")),
        "rules_severity": {str(name): str(word) for name, word in severity.items()},
    }


def _read_names(source: str, where: str, table: dict[str, Any], key: str) -> list[str]:
    """A list of rule names."""
    raw = table.get(key, [])
    if not isinstance(raw, list):
        raise SpecError(source, where, f"{key} takes a list of rule names")
    return [str(name) for name in raw]


def _read_sheet(source: str, table: Any) -> Sheet | None:
    """The optional ``[job.sheet]`` table."""
    if table is None:
        return None
    where = "job.sheet"
    values = _table(source, where, table)
    _reject_unknown(source, where, values, {"stock", "width", "height", "margin", "kerf"})
    try:
        return Sheet(
            stock=_require_str(source, where, values, "stock"),
            width=_require_length(source, where, values, "width"),
            height=_require_length(source, where, values, "height"),
            margin=_length_or(source, where, values, "margin", 5.0),
            kerf=_length_or(source, where, values, "kerf", 1.5),
        )
    except (ValueError, DragpointError) as exc:
        raise SpecError(source, where, str(exc)) from exc


def _read_plate(
    source: str,
    index: int,
    entry: dict[str, Any],
    defaults: dict[str, Any],
) -> PlateSpec:
    """One ``[[plate]]`` table, with the defaults filled in underneath."""
    name = str(entry.get("name", f"plate{index + 1}"))
    where = f'plate[{index}] "{name}"'
    merged: dict[str, Any] = dict(defaults)
    merged.update(entry)
    _reject_unknown(
        source,
        where,
        merged,
        {
            "name",
            "size",
            "width",
            "height",
            "lines",
            "halign",
            "valign",
            "fit",
            "cutter",
            "feature",
            "tags",
            "arc_centre",
            *_PLATE_LENGTHS,
            *_PLATE_PLAIN,
        },
    )

    width, height = _read_size(source, where, merged)
    features = tuple(
        _read_feature(source, where, position, table)
        for position, table in enumerate(_feature_entries(source, where, merged))
    )

    values: dict[str, Any] = {
        "name": name,
        "width": width,
        "height": height,
        "stock": _require_str(source, where, merged, "stock"),
        "lines": _read_lines(source, where, merged),
        "halign": _read_enum(source, where, merged, "halign", HAlign, HAlign.CENTRE),
        "valign": _read_enum(source, where, merged, "valign", VAlign, VAlign.MIDDLE),
        "fit": _read_enum(source, where, merged, "fit", FitPolicy, FitPolicy.CONDENSE),
        "features": features,
        "cutter": _optional_str(merged, "cutter"),
        "arc_centre": _read_point(source, where, merged, "arc_centre")
        if "arc_centre" in merged
        else None,
        "tags": frozenset(str(tag) for tag in merged.get("tags", ())),
    }
    for key in _PLATE_LENGTHS:
        if key in merged:
            values[key] = _require_length(source, where, merged, key)
    for key in _PLATE_PLAIN:
        if key in merged and key != "stock":
            values[key] = merged[key]

    try:
        return PlateSpec(**values)
    except (ValueError, TypeError, DragpointError) as exc:
        raise SpecError(source, where, str(exc)) from exc


def _read_size(source: str, where: str, table: dict[str, Any]) -> tuple[float, float]:
    """``size = [w, h]`` or a separate width and height."""
    if "size" in table:
        raw = table["size"]
        if not isinstance(raw, list) or len(raw) != 2:
            raise SpecError(source, where, "size takes exactly two lengths")
        return (
            _length(source, where, "size", raw[0]),
            _length(source, where, "size", raw[1]),
        )
    return (
        _require_length(source, where, table, "width"),
        _require_length(source, where, table, "height"),
    )


def _read_lines(source: str, where: str, table: dict[str, Any]) -> tuple[str, ...]:
    """``lines`` is a list of strings, and a bare string is one line."""
    raw = table.get("lines", ())
    if isinstance(raw, str):
        return (raw,)
    if not isinstance(raw, list):
        raise SpecError(source, where, "lines takes a list of strings")
    for item in raw:
        if not isinstance(item, str):
            raise SpecError(source, where, f"lines holds {item!r}, which is not a string")
    return tuple(raw)


def _feature_entries(source: str, where: str, table: dict[str, Any]) -> list[dict[str, Any]]:
    """The ``[[plate.feature]]`` array."""
    entries = table.get("feature", [])
    if not isinstance(entries, list):
        raise SpecError(source, where, "feature takes an array of tables, use [[plate.feature]]")
    for item in entries:
        if not isinstance(item, dict):
            raise SpecError(source, where, "every feature must be a table")
    return entries


def _read_feature(source: str, plate_where: str, index: int, table: dict[str, Any]) -> Feature:
    """One ``[[plate.feature]]`` table."""
    where = f"{plate_where} feature[{index}]"
    _reject_unknown(
        source,
        where,
        table,
        {"name", "kind", "at", "diameter", "width", "height", "clearance"},
    )
    name = _require_str(source, where, table, "name")
    kind = _read_enum(source, where, table, "kind", FeatureKind, FeatureKind.HOLE)
    centre = _read_point(source, where, table)
    clearance = _length_or(source, where, table, "clearance", 0.5)
    try:
        if "diameter" in table:
            return Feature.round_hole(
                name,
                centre,
                _require_length(source, where, table, "diameter"),
                kind=kind,
                clearance=clearance,
            )
        return Feature.rectangle(
            name,
            centre,
            _require_length(source, where, table, "width"),
            _require_length(source, where, table, "height"),
            kind=kind,
            clearance=clearance,
        )
    except (ValueError, DragpointError) as exc:
        raise SpecError(source, where, str(exc)) from exc


def _read_point(source: str, where: str, table: dict[str, Any], key: str = "at") -> Point:
    """``at = [x, y]``, or any other key that holds a pair of lengths."""
    raw = table.get(key)
    if not isinstance(raw, list) or len(raw) != 2:
        raise SpecError(source, where, f"{key} takes exactly two lengths")
    return Point(_length(source, where, key, raw[0]), _length(source, where, key, raw[1]))


def _table(source: str, where: str, value: Any) -> dict[str, Any]:
    """Insist that ``value`` is a table."""
    if not isinstance(value, dict):
        raise SpecError(source, where or "document", "expected a table")
    return value


def _reject_unknown(source: str, where: str, table: dict[str, Any], allowed: set[str]) -> None:
    """Refuse a key nobody reads.

    A typed key that is silently ignored is the worst failure this loader
    could have, because the plate comes out looking right and is not what
    was ordered.
    """
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise SpecError(source, where or "document", f"unknown key {unknown[0]!r}")


def _require_str(source: str, where: str, table: dict[str, Any], key: str) -> str:
    """A string that has to be there."""
    if key not in table:
        raise SpecError(source, where, f"{key} is missing")
    value = table[key]
    if not isinstance(value, str):
        raise SpecError(source, where, f"{key} should be a string, got {value!r}")
    return value


def _optional_str(table: dict[str, Any], key: str) -> str | None:
    """A string that may be absent."""
    value = table.get(key)
    return None if value is None else str(value)


def _length(source: str, where: str, key: str, value: Any) -> float:
    """One length, with or without a unit."""
    try:
        return parse_length(value)
    except Exception as exc:
        raise SpecError(source, where, f"{key}: {exc}") from exc


def _require_length(source: str, where: str, table: dict[str, Any], key: str) -> float:
    """A length that has to be there."""
    if key not in table:
        raise SpecError(source, where, f"{key} is missing")
    return _length(source, where, key, table[key])


def _optional_length(source: str, where: str, table: dict[str, Any], key: str) -> float | None:
    """A length that may be absent."""
    if key not in table:
        return None
    return _length(source, where, key, table[key])


def _length_or(source: str, where: str, table: dict[str, Any], key: str, fallback: float) -> float:
    """A length with a default."""
    if key not in table:
        return fallback
    return _length(source, where, key, table[key])


def _read_enum(
    source: str,
    where: str,
    table: dict[str, Any],
    key: str,
    kind: type[HAlign] | type[VAlign] | type[FitPolicy] | type[FeatureKind],
    fallback: Any,
) -> Any:
    """One of a fixed set of words."""
    if key not in table:
        return fallback
    raw = table[key]
    try:
        return kind(str(raw).lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in kind)
        raise SpecError(source, where, f"{key} is {raw!r}, expected one of {allowed}") from exc
