"""Laying the plates out on a sheet before anything is cut off it.

Shelves, tallest piece first. It is not the best packing there is and it is
the one the shop already uses by hand, which matters more than the last few
per cent: a nest an operator can look at and understand is a nest they will
cut, and a clever nest with pieces at four different heights in one row is a
nest that gets recut by eye and wastes the sheet anyway.

Within that, a piece goes on the row that suits it best rather than the first
row that will take it. The two agree while the sheet is empty and stop
agreeing as soon as one row is short of space: first fit drops a 20 mm plate
into a 40 mm row and leaves 20 mm of sheet nobody will ever use, while there
is a 22 mm row further up wanting exactly that piece. Ties go to the row with
the least length left, which keeps a nest from spreading thinly across every
row it has open.

Rotation is allowed by default and matters more than it looks. A long thin
legend plate laid across the sheet rather than along it often fits one more
row, and there is nothing on a rectangular blank that has a grain.

The kerf goes between pieces and the clamp margin goes round the outside.
Both come off the sheet before anything is placed, so a piece that fits by
the arithmetic here fits on the machine.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.spec.job import JobSpec, Sheet
from dragpoint.spec.plate import PlateSpec

__all__ = ["NestResult", "Placement", "nest_pieces", "nest_job"]

TOLERANCE = 1e-9
"""Millimetres of slop allowed when asking whether a piece fits.

Sheet sizes and plate sizes come out of the same arithmetic, so a piece that
exactly fills what is left of a row misses by a rounding bit about half the
time. Half the time is not a decision anybody wants a nest making.
"""


@dataclass(frozen=True, slots=True)
class Placement:
    """One piece, where it goes on the sheet."""

    plate: str
    piece: int
    origin: Point
    width: float
    height: float
    rotated: bool = False

    def bounds(self) -> Box:
        """The box this piece occupies, kerf not included."""
        return Box.from_size(self.width, self.height, self.origin)

    @property
    def area(self) -> float:
        """Square millimetres of sheet this piece takes."""
        return self.width * self.height

    def __str__(self) -> str:
        turned = " turned" if self.rotated else ""
        return f"{self.plate} #{self.piece} at {self.origin}{turned}"


@dataclass(frozen=True, slots=True)
class NestResult:
    """What fitted, what did not, and how well the sheet was used."""

    sheet: Sheet
    placements: tuple[Placement, ...]
    left_over: tuple[tuple[str, int], ...]

    @property
    def placed(self) -> int:
        """How many pieces went on."""
        return len(self.placements)

    @property
    def missed(self) -> int:
        """How many pieces did not."""
        return sum(count for _, count in self.left_over)

    @property
    def complete(self) -> bool:
        """True when everything asked for went on the sheet."""
        return not self.left_over

    def used_area(self) -> float:
        """Square millimetres of piece, kerf not counted."""
        return sum(item.area for item in self.placements)

    def utilisation(self) -> float:
        """Used area over the area inside the clamps."""
        usable = self.sheet.usable_area
        if usable <= 0.0:
            return 0.0
        return self.used_area() / usable

    def rows(self) -> int:
        """How many shelves the nest used."""
        return len({item.origin.y for item in self.placements})

    def row_waste(self) -> float:
        """Square millimetres lost above pieces standing shorter than their row.

        This is the number best fit exists to bring down, and it is the one
        that does not show in the utilisation figure: a row is as tall as the
        tallest thing in it whether or not anything else reaches the top.
        """
        tallest: dict[float, float] = {}
        for item in self.placements:
            tallest[item.origin.y] = max(tallest.get(item.origin.y, 0.0), item.height)
        return sum((tallest[item.origin.y] - item.height) * item.width for item in self.placements)

    def bounds(self) -> Box | None:
        """The box the whole nest occupies."""
        merged: Box | None = None
        for item in self.placements:
            box = item.bounds()
            merged = box if merged is None else merged.union(box)
        return merged

    def for_plate(self, name: str) -> tuple[Placement, ...]:
        """Every piece of one plate, in the order they were placed."""
        return tuple(item for item in self.placements if item.plate == name)

    def __len__(self) -> int:
        return len(self.placements)

    def __iter__(self) -> Iterator[Placement]:
        return iter(self.placements)

    def __str__(self) -> str:
        verdict = "all on" if self.complete else f"{self.missed} left over"
        return (
            f"{self.placed} pieces in {self.rows()} rows, "
            f"{self.utilisation():.0%} of the sheet, {verdict}"
        )


@dataclass
class _Shelf:
    """One row being filled from the left."""

    bottom: float
    height: float
    used: float = 0.0

    def offset(self, kerf: float) -> float:
        """The gap in front of the next piece, which is nothing at the wall."""
        return kerf if self.used else 0.0

    def room(self, left: float, limit_x: float, kerf: float) -> float:
        """Millimetres of row left, the parting cut already taken off."""
        return limit_x - (left + self.used + self.offset(kerf))

    def takes(self, width: float, height: float, room: float) -> bool:
        """True when a piece of this size goes in what is left of the row."""
        return height <= self.height + TOLERANCE and width <= room + TOLERANCE

    def waste(self, height: float) -> float:
        """Millimetres of row height a piece this tall leaves above it."""
        return self.height - height


def nest_pieces(
    pieces: Sequence[tuple[str, float, float]],
    sheet: Sheet,
    *,
    allow_rotation: bool = True,
    best_fit: bool = True,
) -> NestResult:
    """Nest ``(name, width, height)`` pieces onto ``sheet``.

    Pieces are placed tallest first, which is what makes shelves work: a
    short piece dropped into a tall row wastes the difference for the whole
    length of the row, and sorting means the tall ones have already gone.

    ``best_fit`` picks the row that suits each piece rather than the first
    that takes it. Turning it off gives the plain first fit nest, which is
    there to be compared against and is occasionally what a job wants when
    the rows have to come off the sheet in the order they were asked for.
    """
    ordered = sorted(pieces, key=lambda piece: (-max(piece[1], piece[2]), piece[0]))
    left = sheet.margin
    bottom = sheet.margin
    limit_x = sheet.margin + sheet.usable_width
    limit_y = sheet.margin + sheet.usable_height

    shelves: list[_Shelf] = []
    placements: list[Placement] = []
    missed: dict[str, int] = {}
    counts: dict[str, int] = {}

    for name, width, height in ordered:
        counts[name] = counts.get(name, 0) + 1
        placed = _place(
            name,
            counts[name],
            width,
            height,
            shelves,
            sheet,
            left,
            limit_x,
            allow_rotation,
            best_fit,
        )
        if placed is None:
            new_shelf = _open_shelf(shelves, bottom, width, height, sheet, limit_y, allow_rotation)
            if new_shelf is None:
                missed[name] = missed.get(name, 0) + 1
                continue
            shelves.append(new_shelf)
            placed = _place(
                name,
                counts[name],
                width,
                height,
                shelves[-1:],
                sheet,
                left,
                limit_x,
                allow_rotation,
                best_fit,
            )
        if placed is None:
            missed[name] = missed.get(name, 0) + 1
            continue
        placements.append(placed)

    return NestResult(
        sheet=sheet,
        placements=tuple(placements),
        left_over=tuple(sorted(missed.items())),
    )


def _place(
    name: str,
    piece: int,
    width: float,
    height: float,
    shelves: list[_Shelf],
    sheet: Sheet,
    left: float,
    limit_x: float,
    allow_rotation: bool,
    best_fit: bool,
) -> Placement | None:
    """Put a piece on the row that suits it, and say where it went.

    The winner is the row leaving the least height above the piece, and on a
    tie the row with the least length left. Only the winning row is touched,
    which is why the candidates are collected before anything is changed.
    """
    best: tuple[tuple[float, float], _Shelf, Placement, float] | None = None
    for shelf in shelves:
        offset = shelf.offset(sheet.kerf)
        room = shelf.room(left, limit_x, sheet.kerf)
        start = left + shelf.used + offset
        for turned, (across, up) in _orientations(width, height, allow_rotation):
            if not shelf.takes(across, up, room):
                continue
            score = (shelf.waste(up), room - across)
            if best is not None and score >= best[0]:
                continue
            best = (
                score,
                shelf,
                Placement(
                    plate=name,
                    piece=piece,
                    origin=Point(start, shelf.bottom),
                    width=across,
                    height=up,
                    rotated=turned,
                ),
                offset + across,
            )
        if best is not None and not best_fit:
            break
    if best is None:
        return None
    _, shelf, placement, taken = best
    shelf.used += taken
    return placement


def _open_shelf(
    shelves: list[_Shelf],
    bottom: float,
    width: float,
    height: float,
    sheet: Sheet,
    limit_y: float,
    allow_rotation: bool,
) -> _Shelf | None:
    """Start a new shelf above the last one, if there is room for one."""
    top = bottom
    for shelf in shelves:
        top = max(top, shelf.bottom + shelf.height + sheet.kerf)
    for _, (across, up) in _orientations(width, height, allow_rotation):
        if top + up <= limit_y + TOLERANCE and across <= sheet.usable_width + TOLERANCE:
            return _Shelf(bottom=top, height=up)
    return None


def _orientations(
    width: float, height: float, allow_rotation: bool
) -> list[tuple[bool, tuple[float, float]]]:
    """The ways round a piece may go, the way it came first."""
    if not allow_rotation or abs(width - height) < TOLERANCE:
        return [(False, (width, height))]
    return [(False, (width, height)), (True, (height, width))]


def nest_job(job: JobSpec, *, allow_rotation: bool = True, best_fit: bool = True) -> NestResult:
    """Nest every piece in a job onto the sheet the job names."""
    if job.sheet is None:
        raise ValueError(f"job {job.name} does not say what sheet it comes off")
    return nest_pieces(
        _pieces(job.plates),
        job.sheet,
        allow_rotation=allow_rotation,
        best_fit=best_fit,
    )


def _pieces(plates: Sequence[PlateSpec]) -> list[tuple[str, float, float]]:
    """One entry per piece, quantities expanded."""
    return [
        (plate.name, plate.width, plate.height) for plate in plates for _ in range(plate.quantity)
    ]
