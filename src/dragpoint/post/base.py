"""The post processor register, and what every post is given.

A post takes a finished toolpath and writes the file one particular control
wants. Nothing in a post decides anything about the cut: by the time a post
runs, the depths, the order and the feeds are settled, and a post that
changed one of them would be making a machining decision inside a file
writer, where nobody would ever look for it.

Three posts ship. The ISO one writes G code for the controls that take it.
The plotter one writes the pen up and pen down language the older engraving
machines speak, which has no Z axis at all and expresses depth as a tool
setting made once at the top of the file. The marker one writes a job for
the bench laser, which has no Z and no cutter either.

Repeats are a post's business and not the toolpath's. A fixture holding
twelve blanks in a row is twelve copies of one program at twelve offsets,
and which of those the file expresses as a subprogram call and which it
writes out longhand depends entirely on what the control can do.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dragpoint.errors import OutOfRange
from dragpoint.path.plan import Toolpath

__all__ = [
    "MAX_REPEATS",
    "WORK_OFFSETS",
    "POSTS",
    "PostDef",
    "PostOptions",
    "post",
    "post_names",
    "render",
]


MAX_REPEATS = 999
"""Copies of one program a file may carry, which is a fixture full of them."""

WORK_OFFSETS = (54, 55, 56, 57, 58, 59)
"""The six work offsets every control that reads this dialect has.

G54 is the one a machine sits in unless somebody has moved it. The other
five exist for a shop that leaves a fixture set up: the vice for the small
plates is G55 and stays G55 for a month, and a program that says so cannot
be run against the wrong datum by accident.
"""


@dataclass(frozen=True, slots=True)
class PostOptions:
    """Everything a post needs that is not in the toolpath.

    ``decimals`` is how many places coordinates are written to. Four is a
    tenth of a micron and further than any of these machines can position,
    but a control that reads three places and rounds is a control that
    accumulates, so the file carries more than the machine can use.
    """

    program: str = "DRAGPOINT"
    number: int = 1000
    spindle: int = 12000
    tool: int = 1
    decimals: int = 4
    line_numbers: bool = False
    comments: bool = True
    notes: tuple[str, ...] = ()
    repeats: int = 1
    pitch_x: float = 0.0
    pitch_y: float = 0.0
    work_offset: int = 54

    def __post_init__(self) -> None:
        if not 0 <= self.decimals <= 6:
            raise ValueError(f"decimals of {self.decimals} is not a sane number of places")
        if self.spindle < 0:
            raise ValueError(f"a spindle speed of {self.spindle} is not a speed")
        if self.tool < 0:
            raise ValueError(f"a tool number of {self.tool} is not a tool")
        if self.repeats < 1:
            raise OutOfRange("repeats", self.repeats, 1, MAX_REPEATS)
        if self.repeats > MAX_REPEATS:
            raise OutOfRange("repeats", self.repeats, 1, MAX_REPEATS)
        if self.repeats > 1 and self.pitch_x == 0.0 and self.pitch_y == 0.0:
            raise ValueError(f"{self.repeats} repeats with no pitch would cut the same blank")
        if self.work_offset not in WORK_OFFSETS:
            wanted = ", ".join(f"G{offset}" for offset in WORK_OFFSETS)
            raise ValueError(f"G{self.work_offset} is not a work offset, there is {wanted}")

    def offsets(self) -> tuple[tuple[float, float], ...]:
        """Where each copy of the program sits, the first one at nothing.

        A fixture is loaded in a line, so the pitch is a step in x, in y, or
        in both for a fixture loaded on the diagonal. Anything more
        complicated than a line is a nest, and a nest is not a repeat.
        """
        return tuple((index * self.pitch_x, index * self.pitch_y) for index in range(self.repeats))

    def coordinate(self, value: float) -> str:
        """One coordinate, at the configured precision.

        A value that rounds to zero comes out as zero and not as minus zero.
        More than one control reads ``X-0.0000`` as a syntax error.
        """
        text = f"{value:.{self.decimals}f}"
        if float(text) == 0.0:
            return f"{0.0:.{self.decimals}f}"
        return text


RenderFunction = Callable[[Toolpath, PostOptions], str]


@dataclass(frozen=True, slots=True)
class PostDef:
    """One registered post."""

    name: str
    description: str
    extension: str
    render: RenderFunction

    def __str__(self) -> str:
        return f"{self.name} (.{self.extension}): {self.description}"


POSTS: dict[str, PostDef] = {}
"""Every post, in registration order."""


def post(name: str, description: str, extension: str) -> Callable[[RenderFunction], RenderFunction]:
    """Register a post under ``name``."""

    def register(function: RenderFunction) -> RenderFunction:
        """Put the function in the register and hand it back."""
        if name in POSTS:
            raise ValueError(f"a post called {name!r} is already registered")
        POSTS[name] = PostDef(
            name=name,
            description=description,
            extension=extension,
            render=function,
        )
        return function

    return register


def post_names() -> tuple[str, ...]:
    """Every registered post name, in registration order."""
    return tuple(POSTS)


def render(name: str, path: Toolpath, options: PostOptions | None = None) -> str:
    """Render ``path`` through the named post."""
    try:
        definition = POSTS[name]
    except KeyError:
        known = ", ".join(sorted(POSTS))
        raise KeyError(f"no post called {name!r}, there is {known}") from None
    return definition.render(path, options or PostOptions())
