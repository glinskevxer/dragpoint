"""How far a tip goes before it stops cutting, and what that costs a job.

A carbide tip does not fail. It rounds off, slowly, and the groove it leaves
gets wider and rougher until somebody looking at a plate says the letters
have gone furry. By then the last hundred plates were furry too and nobody
was looking.

The trade number is metres cut, and it is only ever approximate: it depends
on the material, on the speed, and on whether the last operator crashed it
into a clamp. The catalogue carries a figure per cutter for the laminate
this shop cuts most, and a material multiplier scales it for everything
else, because brass eats tips at a rate laminate never approaches.

None of this tracks a real tip. The package has no idea which cutter is in
the spindle or what it has done this week, and pretending to know would be
worse than useless. What it can say is how much cutting one job needs and
how that compares with one tip, which is enough to tell a planner that the
job wants two.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.tool.cutter import Cutter
from dragpoint.tool.material import Material

__all__ = ["LIFE_BY_MATERIAL", "TipLife", "job_tip_life", "tip_life"]

LIFE_BY_MATERIAL = {
    "laminate": 1.0,
    "acrylic": 0.8,
    "aluminium": 0.35,
    "brass": 0.2,
    "steel": 0.05,
}
"""How much of a tip's rated life each family of stock actually gives.

One is the two ply laminate the rating is quoted against. The rest come from
the same place every machining number comes from, which is somebody writing
down what happened last time.
"""

SOFT_WORDS = ("laminate", "acrylic")
"""Words in a stock description that mean the tip is in for an easy time."""

METAL_WORDS = {
    "aluminium": "aluminium",
    "anodised": "aluminium",
    "brass": "brass",
    "stainless": "steel",
    "steel": "steel",
}
"""Words in a stock description that name a metal, and which metal.

Matching on the description rather than on the stock code is deliberate. A
shop adds stock to its own rack file with its own codes, and the description
is the field a person writes a sentence in.
"""


@dataclass(frozen=True, slots=True)
class TipLife:
    """What one job asks of one cutter, against what a tip will give."""

    cutter: str
    material: str
    cutting: float
    life: float

    def __post_init__(self) -> None:
        if self.cutting < 0.0:
            raise OutOfRange("cutting", self.cutting, 0.0, math.inf)
        if self.life <= 0.0:
            raise OutOfRange("life", self.life, 1e-6, math.inf)

    @property
    def fraction(self) -> float:
        """How much of one tip the job uses. Over one means more than one."""
        return self.cutting / self.life

    @property
    def tips(self) -> int:
        """How many tips the job needs, rounded up, and never fewer than one."""
        return max(1, math.ceil(self.fraction - 1e-9))

    @property
    def within_one_tip(self) -> bool:
        """True when the job goes through on the tip that is already in."""
        return self.tips == 1

    def remaining(self) -> float:
        """Metres of life left on the tip after this job, floored at nothing."""
        return max(0.0, self.life - self.cutting)

    def __str__(self) -> str:
        return (
            f"{self.cutter} in {self.material}: {self.cutting:.1f}m of {self.life:.1f}m, "
            f"{self.tips} tip" + ("" if self.tips == 1 else "s")
        )


def tip_life(cutter: Cutter, stock: Material, cutting: float) -> TipLife:
    """What ``cutting`` metres of groove in ``stock`` asks of ``cutter``."""
    return TipLife(
        cutter=cutter.name,
        material=stock.name,
        cutting=cutting,
        life=cutter.life * material_factor(stock),
    )


def job_tip_life(cutter: Cutter, cutting: Mapping[str, tuple[Material, float]]) -> TipLife:
    """One cutter across a whole job, however many stocks it went through.

    A metre of brass takes five times as much off a tip as a metre of
    laminate, so the metres are converted into the laminate metres they are
    worth and added up. The answer is in those same laminate metres, which
    is the only unit a tip is rated in.
    """
    worth = 0.0
    stocks: list[str] = []
    for stock, metres in cutting.values():
        factor = material_factor(stock)
        worth += metres / factor if factor > 0.0 else metres
        if stock.name not in stocks:
            stocks.append(stock.name)
    named = stocks[0] if len(stocks) == 1 else f"{len(stocks)} stocks"
    return TipLife(cutter=cutter.name, material=named, cutting=worth, life=cutter.life)


def material_factor(stock: Material) -> float:
    """How much of a tip's rated life this stock gives.

    Anything the description does not name is treated as laminate, because
    the rack is mostly laminate and a wrong guess in that direction shows up
    as a job that needed a second tip rather than a job that stopped.
    """
    words = stock.description.lower()
    for word, family in METAL_WORDS.items():
        if word in words:
            return LIFE_BY_MATERIAL[family]
    for word in SOFT_WORDS:
        if word in words:
            return LIFE_BY_MATERIAL[word]
    return LIFE_BY_MATERIAL["laminate"]
