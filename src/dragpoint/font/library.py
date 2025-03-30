"""Finding a face by name, whether it ships with us or lives on disk.

A plate spec names a face as a bare word. That word means one of the faces
that ships inside the package unless it resolves to a file, and a file wins
only when it actually exists, so a customer face called ``panelgothic.strk``
sitting in the job folder does not silently shadow the shipped one from a
different directory.

Shipped faces are cached. They are immutable and a job with forty plates
would otherwise reparse the same eight hundred lines forty times.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from pathlib import Path

from dragpoint.errors import FaceNotFound
from dragpoint.font.face import StrokeFace
from dragpoint.font.parse import parse_face

__all__ = ["load_face", "load_face_file", "shipped_face", "shipped_names"]

_PACKAGE = "dragpoint.font.faces"
_SUFFIX = ".strk"


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

    for candidate in candidates:
        if candidate.is_file():
            return load_face_file(candidate)
    return shipped_face(name)
