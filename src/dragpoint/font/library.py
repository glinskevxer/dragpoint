"""Finding a face by name, whether it ships with us or lives on disk.

A plate spec names a face as a bare word. That word means one of the faces
that ships inside the package unless it resolves to a file, and a file wins
only when it actually exists, so a customer face called ``panelgothic.strk``
sitting in the job folder does not silently shadow the shipped one from a
different directory.

Shipped faces are cached. They are immutable and a job with forty plates
would otherwise reparse the same eight hundred lines forty times.

A shop keeps its own faces somewhere, and naming them by path in every
schedule is how a folder gets moved and forty schedules stop working. So
there is a search path in the environment: ``DRAGPOINT_FACES``, the same
shape as any other path variable, and a name is looked for in each of its
directories in turn before the shipped faces are tried. Files on disk are
not cached, because a face somebody is editing is a face that changes.
"""

from __future__ import annotations

import os
from functools import cache
from importlib import resources
from pathlib import Path

from dragpoint.errors import FaceNotFound
from dragpoint.font.face import StrokeFace
from dragpoint.font.parse import parse_face

__all__ = [
    "FACE_PATH_VARIABLE",
    "face_path",
    "load_face",
    "load_face_file",
    "local_names",
    "shipped_face",
    "shipped_names",
]

_PACKAGE = "dragpoint.font.faces"
_SUFFIX = ".strk"

FACE_PATH_VARIABLE = "DRAGPOINT_FACES"
"""The environment variable holding directories of a shop's own faces."""


def face_path() -> tuple[Path, ...]:
    """The directories the environment says to look in, in order.

    Empty entries are skipped rather than read as the current directory. A
    variable that ends in a separator is the normal way to write one and it
    should not quietly add the working directory to the search.
    """
    raw = os.environ.get(FACE_PATH_VARIABLE, "")
    return tuple(Path(entry) for entry in raw.split(os.pathsep) if entry.strip())


def local_names() -> tuple[str, ...]:
    """Every face on the search path, sorted, without duplicates.

    A name in two directories is one name: the first one on the path is the
    one that would be loaded, which is what a path means.
    """
    found: list[str] = []
    for directory in face_path():
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            name = entry.name
            if name.endswith(_SUFFIX) and name[: -len(_SUFFIX)] not in found:
                found.append(name[: -len(_SUFFIX)])
    return tuple(sorted(found))


def shipped_names() -> tuple[str, ...]:
    """The faces built into this package, sorted."""
    names = []
    for entry in resources.files(_PACKAGE).iterdir():
        if entry.name.endswith(_SUFFIX):
            names.append(entry.name[: -len(_SUFFIX)])
    return tuple(sorted(names))


@cache
def shipped_face(name: str) -> StrokeFace:
    """Load one of the faces that ships with the package.

    Cached, and the face is immutable, so every caller can hold on to the
    same object. Nothing here copies it.
    """
    if name not in shipped_names():
        raise FaceNotFound(name, shipped_names())
    handle = resources.files(_PACKAGE).joinpath(name + _SUFFIX)
    return parse_face(handle.read_text(encoding="utf-8"), f"{_PACKAGE}/{name}{_SUFFIX}")


def load_face_file(path: Path | str) -> StrokeFace:
    """Load a face from a path, not cached because a file on disk changes."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FaceNotFound(str(path), shipped_names())
    return parse_face(resolved.read_text(encoding="utf-8"), str(resolved))


def load_face(name: str, *, search: Path | None = None) -> StrokeFace:
    """Resolve a face reference the way a plate spec means it.

    A bare word is a shipped face. Anything that names an existing file is
    that file. ``search`` is the directory the spec was loaded from, so a
    face sitting next to the spec is found without an absolute path.

    The order is what makes this safe to use. Next to the spec first, then a
    path or a name relative to where the command was run, then the search
    path from the environment, then the faces that ship. A shop face and a
    shipped face with the same name are both findable and the local one
    wins, which is what somebody who copied a face and edited it meant.
    """
    candidates: list[Path] = []
    if search is not None:
        candidates.append(search / name)
        if not name.endswith(_SUFFIX):
            candidates.append(search / (name + _SUFFIX))
    direct = Path(name)
    candidates.append(direct)
    if not name.endswith(_SUFFIX):
        candidates.append(Path(name + _SUFFIX))
    for directory in face_path():
        candidates.append(directory / name)
        if not name.endswith(_SUFFIX):
            candidates.append(directory / (name + _SUFFIX))

    for candidate in candidates:
        if candidate.is_file():
            return load_face_file(candidate)
    return shipped_face(name)
