"""Splitting a cut into depth passes.

Passes are divided evenly, not taken at the maximum until a remainder is
left. An even split is slightly more passes on paper and much better on the
plate: a last pass of two hundredths does not cut, it rubs, and on laminate
that rubbing melts the cap back over the groove it just opened.

The plan is built once per depth and shared by every stroke that goes to
that depth, so it is worth being a value rather than a calculation repeated
per stroke.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.tool.cutter import Cutter
from dragpoint.tool.material import Material
from dragpoint.units import QUANTUM

__all__ = ["PassPlan", "plan_passes"]


@dataclass(frozen=True, slots=True)
class PassPlan:
    """The depths, in order, that the cutter goes to.

    ``depths`` is cumulative from the surface, so the last entry is the
    finished depth. A spring pass repeats that last depth, which is why the
    list can hold the same number twice and why nothing here assumes the
    depths strictly increase.
    """

    depths: tuple[float, ...]
    groove_width: float
    has_spring_pass: bool = False

    def __post_init__(self) -> None:
        if not self.depths:
            raise ValueError("a pass plan needs at least one pass")
        for depth in self.depths:
            if depth <= 0.0:
                raise ValueError(f"a pass to depth {depth} cuts nothing")
        for first, second in zip(self.depths, self.depths[1:], strict=False):
            if second < first - QUANTUM:
                raise ValueError("passes must go deeper, never back up")

    @property
    def final_depth(self) -> float:
        """The finished depth of cut."""
        return self.depths[-1]

    @property
    def cutting_passes(self) -> int:
        """Passes that remove material, so not the spring pass."""
        return len(self.depths) - (1 if self.has_spring_pass else 0)

    def step_of(self, index: int) -> float:
        """How much deeper pass ``index`` goes than the one before it."""
        if index == 0:
            return self.depths[0]
        return self.depths[index] - self.depths[index - 1]

    def __len__(self) -> int:
        return len(self.depths)

    def __iter__(self) -> Iterator[float]:
        return iter(self.depths)

    def __str__(self) -> str:
        spring = " plus a spring pass" if self.has_spring_pass else ""
        return (
            f"{self.cutting_passes} passes to {self.final_depth:.3f}mm{spring}, "
            f"groove {self.groove_width:.3f}mm"
        )


def plan_passes(
    depth: float,
    stock: Material,
    cutter: Cutter,
    *,
    spring_pass: bool = False,
) -> PassPlan:
    """Work out the passes to reach ``depth`` in ``stock`` with ``cutter``.

    Both the stock and the cutter get a say and both can veto. The stock
    knows the window the sheet allows and how much it will give up per pass;
    the cutter knows how far it can reach at all.
    """
    stock.require_depth(depth)
    if depth > cutter.max_depth:
        raise OutOfRange(f"depth for {cutter.name}", depth, 0.0, cutter.max_depth)
    count = stock.passes_for(depth)
    if count < 1:
        raise OutOfRange("depth", depth, QUANTUM, stock.depth_window()[1])
    step = depth / count
    depths = [step * (index + 1) for index in range(count)]
    if spring_pass:
        depths.append(depth)
    return PassPlan(
        depths=tuple(depths),
        groove_width=cutter.width_at_depth(depth),
        has_spring_pass=spring_pass,
    )
