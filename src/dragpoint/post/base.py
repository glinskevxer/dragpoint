"""The post processor register, and what every post is given.

A post takes a finished toolpath and writes the file one particular control
wants. Nothing in a post decides anything about the cut: by the time a post
runs, the depths, the order and the feeds are settled, and a post that
changed one of them would be making a machining decision inside a file
writer, where nobody would ever look for it.

Two posts ship. The ISO one writes G code for the controls that take it. The
plotter one writes the pen up and pen down language the older engraving
machines speak, which has no Z axis at all and expresses depth as a tool
setting made once at the top of the file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dragpoint.path.plan import Toolpath

__all__ = [
    "POSTS",
    "PostDef",
    "PostOptions",
    "post",
    "post_names",
    "render",
]


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

    def __post_init__(self) -> None:
        if not 0 <= self.decimals <= 6:
            raise ValueError(f"decimals of {self.decimals} is not a sane number of places")
        if self.spindle < 0:
            raise ValueError(f"a spindle speed of {self.spindle} is not a speed")
        if self.tool < 0:
            raise ValueError(f"a tool number of {self.tool} is not a tool")

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
