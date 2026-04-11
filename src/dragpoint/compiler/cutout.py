"""Milling the windows out, which is a third setup and a third program.

A meter window in a panel legend is not engraving and it is not drilling. It
is a profile cut with a parallel cutter, all the way through the sheet, and
it has the one problem neither of the others has: as the last pass finishes,
the piece in the middle comes loose. On a 3 mm laminate window that piece is
the size of a matchbox, it lifts on the cutter, and it takes the edge of the
window with it on the way out.

Tabs are the answer and they are old. Four short bridges, one in the middle
of each side, left a few tenths thick so the middle stays put until somebody
snaps it out with a screwdriver. They are on the last pass only, because
every pass above them is not through yet and a tab in mid air does nothing.

The cutter goes across a tab rather than over it. Lifting clear would leave
the bridge full thickness, and a full thickness bridge in 3 mm laminate does
not snap, it tears, and it takes a chip out of the window edge on the way.
So the last pass climbs to the tab height, cuts across at that depth and
drops back down, which leaves three tenths of material and a window that
comes out with a thumb.

The path is the window, inset by the cutter radius, because the cutter has
width and the window is the size on the drawing. Getting that the wrong way
round makes every window a cutter diameter too big, which on a 0.5 mm cutter
is a window that rattles and on a 3 mm cutter is scrap.

Climb or conventional is not a decision here. These are through cuts in a
sheet held on tape, the difference is a burr on one side or the other, and
the burr comes off with a scraper either way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dragpoint.compiler.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.geometry.box import Box
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList
from dragpoint.path.plan import Toolpath, build_toolpath
from dragpoint.spec.feature import Feature, milled_features
from dragpoint.spec.plate import PlateSpec
from dragpoint.tool.cutter import DEFAULT_PROFILE_CUTTER, Cutter, catalogue_cutter
from dragpoint.tool.material import Material, material
from dragpoint.units import QUANTUM

__all__ = [
    "DEFAULT_TAB_WIDTH",
    "CutoutPlan",
    "cutout_plate",
    "cuttable",
    "offcut_area",
    "window_boxes",
    "window_path",
]

DEFAULT_TAB_WIDTH = 2.0
"""Millimetres of each tab, which is what a screwdriver snaps without a mark."""

DEFAULT_TAB_HEIGHT = 0.3
"""Millimetres of sheet left under a tab."""

BREAKTHROUGH = 0.3
"""Millimetres past the back, so the cut is through everywhere but the tabs."""


def cuttable(spec: PlateSpec) -> tuple[Feature, ...]:
    """The features on a plate that get milled out, in schedule order."""
    return milled_features(spec.features)


def window_path(window: Feature, radius: float) -> Stroke:
    """The path the cutter centre takes round one window.

    Inset by the radius and closed, starting and ending at the middle of the
    bottom edge. Starting at a corner would put the entry mark where the two
    passes meet, which is the one place on a window anybody looks at.
    """
    box = window.bounds().grown(-radius)
    if box.width < QUANTUM or box.height < QUANTUM:
        raise OutOfRange("window", min(window.width, window.height), 2.0 * radius, math.inf)
    middle = (box.min_x + box.max_x) / 2.0
    return Stroke.from_pairs(
        [
            (middle, box.min_y),
            (box.max_x, box.min_y),
            (box.max_x, box.max_y),
            (box.min_x, box.max_y),
            (box.min_x, box.min_y),
            (middle, box.min_y),
        ]
    )


@dataclass(frozen=True, slots=True)
class CutoutPlan:
    """Every window on one plate, and the program that mills them."""

    plate: PlateSpec
    stock: Material
    cutter: Cutter
    windows: tuple[Feature, ...]
    depth: float
    passes: int
    tab_width: float
    tab_height: float
    cuts: CutList
    toolpath: Toolpath

    @property
    def name(self) -> str:
        """The plate these windows belong to."""
        return self.plate.name

    @property
    def tabs_per_window(self) -> int:
        """How many bridges hold each piece in, which is one a side."""
        return 4 if self.tab_width > 0.0 else 0

    def area(self) -> float:
        """Square millimetres of blank that comes out as offcut."""
        return sum(window.width * window.height for window in self.windows)

    def __len__(self) -> int:
        return len(self.windows)

    def __str__(self) -> str:
        if not self.windows:
            return f"{self.name}: nothing to mill"
        return (
            f"{self.name}: {len(self.windows)} windows, {self.passes} passes "
            f"to {self.depth:.2f}mm with {self.cutter.name}"
        )


def cutout_plate(
    spec: PlateSpec,
    *,
    stock: Material | None = None,
    setup: MachineSetup | None = None,
    cutter: Cutter | None = None,
    tab_width: float = DEFAULT_TAB_WIDTH,
    tab_height: float = DEFAULT_TAB_HEIGHT,
) -> CutoutPlan:
    """Work out the window milling for one plate."""
    if tab_width < 0.0:
        raise OutOfRange("tab width", tab_width, 0.0, math.inf)
    if tab_height < 0.0:
        raise OutOfRange("tab height", tab_height, 0.0, math.inf)
    machine = setup or MachineSetup()
    sheet = stock if stock is not None else material(spec.stock)
    tool = cutter if cutter is not None else catalogue_cutter(DEFAULT_PROFILE_CUTTER)
    windows = cuttable(spec)
    depth = sheet.thickness + BREAKTHROUGH
    steps = max(1, math.ceil(depth / sheet.max_depth_per_pass - QUANTUM))

    cuts: list[Cut] = []
    for window in windows:
        path = window_path(window, tool.tip_width / 2.0)
        for index in range(steps):
            reached = min(depth, sheet.max_depth_per_pass * (index + 1))
            last = index == steps - 1
            for piece, bridge in _pieces(path, tab_width if last else 0.0):
                cuts.append(
                    Cut(
                        stroke=piece,
                        depth=_bridge_depth(reached, tab_height) if bridge else reached,
                        pass_index=index,
                    )
                )
    return CutoutPlan(
        plate=spec,
        stock=sheet,
        cutter=tool,
        windows=windows,
        depth=depth,
        passes=steps,
        tab_width=tab_width,
        tab_height=tab_height,
        cuts=CutList(tuple(cuts)),
        toolpath=build_toolpath(
            CutList(tuple(cuts)),
            feed=sheet.feed,
            plunge_feed=sheet.plunge_feed,
            safe=machine.safe,
            clearance=machine.clearance,
            start=machine.origin,
        ),
    )


def _bridge_depth(reached: float, tab_height: float) -> float:
    """How deep the cutter goes while it is crossing a tab.

    Never out of the work altogether. A tab taller than the pass is a tab on
    a sheet thinner than the tab, which is somebody asking for the window to
    stay in one piece, and the shallowest cut this package has a name for is
    what they get.
    """
    return max(QUANTUM, reached - tab_height)


def _pieces(path: Stroke, tab_width: float) -> list[tuple[Stroke, bool]]:
    """The path cut into runs, each saying whether it is a bridge.

    With no tabs there is one run, the whole way round, and it is not a
    bridge. With them there is one tab where the path opens and closes,
    which is the middle of the bottom edge, and one in the middle of every
    side between, so a rectangular window comes out held on four.

    A side shorter than three tabs is left whole. Two tabs a couple of
    millimetres apart on a short side is not a bridge, it is a perforation.
    """
    if tab_width < QUANTUM:
        return [(path, False)]
    segments = [(first, second) for first, second in path.segments if first != second]
    if len(segments) < 2:
        return [(path, False)]
    kept: list[tuple[Stroke, bool]] = []
    last = len(segments) - 1
    for index, (first, second) in enumerate(segments):
        span = first.distance_to(second)
        share = min(0.5, tab_width / 2.0 / span)
        if index == 0:
            kept.append((Stroke((first, first.lerp(second, share))), True))
            kept.append((Stroke((first.lerp(second, share), second)), False))
        elif index == last:
            kept.append((Stroke((first, first.lerp(second, 1.0 - share))), False))
            kept.append((Stroke((first.lerp(second, 1.0 - share), second)), True))
        elif span < 3.0 * tab_width:
            kept.append((Stroke((first, second)), False))
        else:
            around = (span - tab_width) / (2.0 * span)
            middle = Stroke((first.lerp(second, around), first.lerp(second, 1.0 - around)))
            kept.append((Stroke((first, first.lerp(second, around))), False))
            kept.append((middle, True))
            kept.append((Stroke((first.lerp(second, 1.0 - around), second)), False))
    return _joined(kept)


def _joined(runs: list[tuple[Stroke, bool]]) -> list[tuple[Stroke, bool]]:
    """Runs of the same kind that meet end to end put back together.

    The path is cut segment by segment, so the piece after a tab and the
    piece before the next one are two runs that share a corner. The machine
    wants them as one, or it lifts at every corner of every window. A bridge
    is never merged into what it touches, because it is cut at a different
    depth and that is the whole point of it.
    """
    if not runs:
        return []
    joined = [runs[0]]
    for run, bridge in runs[1:]:
        last, was_bridge = joined[-1]
        if not bridge and not was_bridge and last.end.distance_to(run.start) < QUANTUM:
            joined[-1] = (Stroke(last.points + run.points[1:]), False)
        else:
            joined.append((run, bridge))
    return joined


def offcut_area(spec: PlateSpec) -> float:
    """Square millimetres of one blank that the windows take out of it.

    Here rather than on the spec because it is a machining question: what a
    nest needs is the size of the blank, and what a cost needs is how much
    of the blank ends up in the bin.
    """
    return sum(window.width * window.height for window in cuttable(spec))


def window_boxes(spec: PlateSpec) -> tuple[Box, ...]:
    """The windows as boxes, for anything that wants to draw or check them."""
    return tuple(window.bounds() for window in cuttable(spec))
