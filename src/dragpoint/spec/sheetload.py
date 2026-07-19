"""Reading a plate schedule out of a spreadsheet export.

Nobody in a drawing office writes TOML. They write a spreadsheet, one row a
plate, and they send it as a CSV with whatever column headings they happened
to type that day. Refusing it is not an option: the alternative is somebody
retyping four hundred rows, and the transcription errors cost more than the
whole job.

So the headings are matched loosely. ``qty``, ``quantity`` and ``no`` all
mean the same thing, capitals and spaces are ignored, and a column nobody
recognises is left alone rather than treated as a fault, because a schedule
usually carries a drawing number and a delivery date that mean nothing here.

Line columns are the one thing that has to be in order. ``line1``, ``line2``
and ``line3`` are the lines of the legend, top to bottom, and a blank one in
the middle is a blank line rather than a line that has gone missing.

Hole columns work the same way and carry three numbers each: where the hole
goes and how big it is, written ``6,12.5 4.2`` or ``1/4,1/2in 1/8in``. It is
a cramped little format and it is the one a drawing office will actually
fill in, which beats a format nobody uses. Anything it cannot read names the
row and the column rather than guessing.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dragpoint.errors import DragpointError, SpecError
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature
from dragpoint.spec.job import JobSpec
from dragpoint.spec.plate import PlateSpec
from dragpoint.units import parse_length

__all__ = ["load_csv_job", "parse_csv_plates"]

ALIASES: dict[str, str] = {
    "plate": "name",
    "platename": "name",
    "drawing": "name",
    "qty": "quantity",
    "no": "quantity",
    "number": "quantity",
    "off": "quantity",
    "start": "sequence_start",
    "first": "sequence_start",
    "from": "sequence_start",
    "material": "stock",
    "sheet": "stock",
    "cap": "cap_height",
    "capheight": "cap_height",
    "lettering": "cap_height",
    "height": "height",
    "width": "width",
    "size": "size",
    "text": "line1",
    "legend": "line1",
}
"""Column headings the trade uses, and what each of them means here."""

LENGTHS = ("width", "height", "cap_height", "margin", "border", "depth", "tracking")
"""Columns read as lengths, so they take a unit if one is written."""

WORDS = ("name", "stock", "face", "cutter", "notes")
"""Columns read as plain text."""

HOLE_PREFIX = "hole"
"""What a hole column is called, with a number after it: hole1, hole2."""


def _key(heading: str) -> str:
    """The name this package uses for a column heading."""
    plain = "".join(character for character in heading.lower() if character.isalnum())
    return ALIASES.get(plain, plain)


def _lines_of(row: Mapping[str, str]) -> tuple[str, ...]:
    """The legend, from the numbered line columns, in order.

    Trailing blanks come off, because a spreadsheet with five line columns
    and a two line legend has three empty cells on the end of every row and
    they are not three blank lines.
    """
    numbered = sorted(
        (int(key[4:]), value)
        for key, value in row.items()
        if key.startswith("line") and key[4:].isdigit()
    )
    lines = [value.strip() for _, value in numbered]
    while lines and not lines[-1]:
        lines.pop()
    return tuple(lines)


def _holes_of(source: str, where: str, row: Mapping[str, str]) -> tuple[Feature, ...]:
    """The fixing holes, from the numbered hole columns, in order.

    Each cell is a centre and a diameter: two numbers with a comma between
    them, a space, then one more. An empty cell is a plate that does not
    have that hole, which is the normal case on a mixed schedule.

    The diameter is the last thing in the cell rather than the second thing
    in it, because a centre written in fractions has a space in the middle
    of it and ``1/2,1 1/2in 1/8in`` has to mean what a fitter would read it
    as.
    """
    numbered = sorted(
        (int(key[len(HOLE_PREFIX) :]), key, value)
        for key, value in row.items()
        if key.startswith(HOLE_PREFIX) and key[len(HOLE_PREFIX) :].isdigit()
    )
    holes: list[Feature] = []
    for index, key, value in numbered:
        if not value.strip():
            continue
        holes.append(_hole(source, where, key, value, index))
    return tuple(holes)


def _hole(source: str, where: str, key: str, value: str, index: int) -> Feature:
    """One hole cell, read into a feature."""
    parts = value.strip().rsplit(maxsplit=1)
    if len(parts) != 2:
        raise SpecError(
            source, where, f"{key}: {value!r} is not a centre and a diameter, write it as 6,12 4.2"
        )
    centre, diameter = parts
    if "," not in centre:
        raise SpecError(source, where, f"{key}: {centre!r} is not a centre, write it as 6,12")
    across, _, up = centre.partition(",")
    unit = "".join(character for character in up if character.isalpha())
    first = across if any(character.isalpha() for character in across) else across + unit
    return Feature.round_hole(
        f"{HOLE_PREFIX}{index}",
        Point(
            _length(source, where, key, first),
            _length(source, where, key, up),
        ),
        _length(source, where, key, diameter),
    )


def _size_of(source: str, where: str, row: Mapping[str, str]) -> tuple[float, float]:
    """The plate size, from either a size column or a width and a height."""
    if row.get("size"):
        parts = row["size"].lower().replace("*", "x").split("x")
        if len(parts) != 2:
            raise SpecError(source, where, f"{row['size']!r} is not a size")
        unit = "".join(character for character in parts[1] if character.isalpha())
        first = parts[0] if any(c.isalpha() for c in parts[0]) else parts[0] + unit
        return _length(source, where, "size", first), _length(source, where, "size", parts[1])
    for key in ("width", "height"):
        if not row.get(key):
            raise SpecError(source, where, f"{key} is missing")
    return (
        _length(source, where, "width", row["width"]),
        _length(source, where, "height", row["height"]),
    )


def _length(source: str, where: str, key: str, text: str) -> float:
    """One length out of a cell."""
    try:
        return parse_length(text.strip())
    except DragpointError as exc:
        raise SpecError(source, where, f"{key}: {exc}") from exc


def _plate_of(
    source: str, number: int, row: Mapping[str, str], defaults: Mapping[str, Any]
) -> PlateSpec:
    """One row as a plate."""
    name = row.get("name", "").strip() or f"row{number}"
    where = f"row {number} ({name})"
    values: dict[str, Any] = dict(defaults)
    width, height = _size_of(source, where, row)
    values.update({"name": name, "width": width, "height": height})

    for key in WORDS:
        if key != "name" and row.get(key, "").strip():
            values[key] = row[key].strip()
    for key in LENGTHS:
        if key in ("width", "height") or not row.get(key, "").strip():
            continue
        values[key] = _length(source, where, key, row[key])
    for whole in ("quantity", "sequence_start"):
        if not row.get(whole, "").strip():
            continue
        try:
            values[whole] = int(float(row[whole]))
        except ValueError as bad:
            raise SpecError(
                source, where, f"{whole.replace('_', ' ')}: {row[whole]!r} is not a number"
            ) from bad
    lines = _lines_of(row)
    if lines:
        values["lines"] = lines
    holes = _holes_of(source, where, row)
    if holes:
        values["features"] = holes

    if "stock" not in values:
        raise SpecError(source, where, "stock is missing and there is no default")
    try:
        return PlateSpec(**values)
    except (ValueError, TypeError, DragpointError) as exc:
        raise SpecError(source, where, str(exc)) from exc


def parse_csv_plates(
    text: str,
    *,
    source: str = "<string>",
    defaults: Mapping[str, Any] | None = None,
) -> tuple[PlateSpec, ...]:
    """Read plates out of a CSV export."""
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return ()
    headings = [_key(cell) for cell in rows[0]]
    if "name" not in headings and "size" not in headings and "width" not in headings:
        raise SpecError(source, "heading", "no column says what a plate is called or how big")
    plates: list[PlateSpec] = []
    for number, row in enumerate(rows[1:], start=2):
        padded = list(row) + [""] * (len(headings) - len(row))
        cells = dict(zip(headings, padded, strict=False))
        plates.append(_plate_of(source, number, cells, defaults or {}))
    return tuple(plates)


def load_csv_job(
    path: Path | str,
    *,
    name: str | None = None,
    defaults: Mapping[str, Any] | None = None,
    **job_settings: Any,
) -> JobSpec:
    """Read a whole job from a CSV export.

    The job has no name in a spreadsheet, so it takes the file's name unless
    the caller says otherwise. That is what everybody means anyway: the file
    is called MCC-7.csv because the job is MCC-7.
    """
    resolved = Path(path)
    try:
        text = resolved.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SpecError(str(resolved), "", f"cannot read the file: {exc}") from exc
    plates = parse_csv_plates(text, source=str(resolved), defaults=defaults)
    try:
        return JobSpec(name=name or resolved.stem, plates=plates, **job_settings)
    except (ValueError, DragpointError) as exc:
        raise SpecError(str(resolved), "job", str(exc)) from exc
