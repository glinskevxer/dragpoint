"""What a job costs, which is the number the customer sees.

There are three parts to it and they are kept apart on purpose. The material
is what the blanks cost, the machining is what the time costs, and the
setting is what it costs to stand at the machine changing the cutter and
loading the first one. A quote that adds them up and prints one figure is a
quote nobody can argue with, and every quote gets argued with.

Nothing here decides a margin or a discount or a minimum charge. Those are
commercial decisions and they change by customer and by week, and a package
that had opinions about them would be a package the office worked around.

Material is priced by area, off the rack, and the area is the blank rather
than the piece: a 60 by 20 plate cut out of a sheet costs a 60 by 20 piece
of sheet whatever shape the letters are. The offcut round it is real and it
is not this job's problem, which is what nesting is for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.compiler.job import EngravedJob
from dragpoint.errors import OutOfRange
from dragpoint.estimate.setups import job_work
from dragpoint.tool.material import material

__all__ = ["DEFAULT_RATE", "DEFAULT_SETTING", "Quote", "quote_job"]

DEFAULT_RATE = 45.0
"""Money an hour on the machine, which is what this shop charges."""

DEFAULT_SETTING = 15.0
"""Money for setting one cutter, which is a fixed charge for the standing."""

SQUARE_METRE = 1_000_000.0
"""Square millimetres in a square metre, because stock is priced by the metre."""


@dataclass(frozen=True, slots=True)
class Quote:
    """What one job comes to, in three parts and a total."""

    job: str
    pieces: int
    area: float
    material: float
    machining: float
    setting: float
    priced_stock: tuple[str, ...]
    unpriced_stock: tuple[str, ...]

    @property
    def total(self) -> float:
        """Every part of it added up."""
        return self.material + self.machining + self.setting

    @property
    def each(self) -> float:
        """The total over the pieces, which is what a customer asks for."""
        return self.total / self.pieces if self.pieces else 0.0

    @property
    def complete(self) -> bool:
        """True when every stock in the job had a price on the rack."""
        return not self.unpriced_stock

    def __str__(self) -> str:
        line = (
            f"{self.job}: {self.pieces} pieces, {self.total:.2f} "
            f"({self.each:.2f} each, {self.area / SQUARE_METRE:.3f}m2 of stock)"
        )
        if self.unpriced_stock:
            line += f", no price for {', '.join(self.unpriced_stock)}"
        return line


def quote_job(
    job: EngravedJob,
    *,
    rate: float = DEFAULT_RATE,
    setting: float = DEFAULT_SETTING,
) -> Quote:
    """Price one compiled job.

    The machining charge counts every setup, because a plate that goes
    across the machine three times is on the machine three times. The
    setting charge counts the cutters rather than the setups: the drill goes
    in once for the whole job, not once per plate.
    """
    if rate < 0.0:
        raise OutOfRange("rate", rate, 0.0, math.inf)
    if setting < 0.0:
        raise OutOfRange("setting", setting, 0.0, math.inf)

    work, seconds = job_work(job)
    area = 0.0
    cost = 0.0
    priced: list[str] = []
    unpriced: list[str] = []
    for plate in job:
        blank = plate.spec.width * plate.spec.height * plate.spec.quantity
        area += blank
        sheet = material(plate.spec.stock)
        if sheet.price is None:
            if sheet.name not in unpriced:
                unpriced.append(sheet.name)
            continue
        if sheet.name not in priced:
            priced.append(sheet.name)
        cost += blank / SQUARE_METRE * sheet.price

    return Quote(
        job=job.name,
        pieces=job.piece_count(),
        area=area,
        material=cost,
        machining=seconds / 3600.0 * rate,
        setting=setting * _cutters(job, work),
        priced_stock=tuple(sorted(priced)),
        unpriced_stock=tuple(sorted(unpriced)),
    )


def _cutters(job: EngravedJob, work: tuple[object, ...]) -> int:
    """How many tools have to be set for this job.

    The engraving cutters, plus a drill if anything is drilled, plus a
    profile cutter if anything is milled. One of each however many plates
    need it, because the tool goes in once and stays in.
    """
    tools = len({life.cutter for life in job.tip_lives()})
    tools += any(getattr(item, "drilling", None) is not None for item in work)
    tools += any(getattr(item, "milling", None) is not None for item in work)
    return max(1, tools)
