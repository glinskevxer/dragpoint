"""Resolving a face reference, and the shipped face parsing at all."""

from __future__ import annotations

from pathlib import Path

import pytest

from dragpoint.errors import FaceNotFound
from dragpoint.font.library import (
    load_face,
    load_face_file,
    shipped_face,
    shipped_names,
)
from dragpoint.font.write import write_face


def test_panelgothic_ships() -> None:
    assert "panelgothic" in shipped_names()


def test_the_shipped_face_parses_and_has_the_metrics_it_claims() -> None:
    face = shipped_face("panelgothic")
    assert face.name == "panelgothic"
    assert face.metrics.units_per_em == 1000
    assert face.metrics.cap_height == 700
    assert face.metrics.x_height == 500
    assert face.metrics.descender == -200


def test_the_shipped_face_covers_the_capitals_and_the_figures() -> None:
    face = shipped_face("panelgothic")
    assert face.missing("ABCDEFGHIJKLMNOPQRSTUVWXYZ") == ()
    assert face.missing("0123456789") == ()
    assert face.missing(" .,-/()+=%#&") == ()


def test_the_shipped_face_kerns_the_pairs_a_legend_actually_hits() -> None:
    face = shipped_face("panelgothic")
    assert face.kern("A", "V") < 0
    assert face.kern("L", "T") < 0
    assert face.kern("A", "B") == 0


def test_the_shipped_face_is_cached_and_handed_back_by_identity() -> None:
    assert shipped_face("panelgothic") is shipped_face("panelgothic")


def test_the_shipped_face_round_trips_through_the_writer() -> None:
    from dragpoint.font.parse import parse_face

    face = shipped_face("panelgothic")
    again = parse_face(write_face(face))
    assert again.names() == face.names()
    for name in face.names():
        assert again.glyph(name) == face.glyph(name)


def test_an_unknown_shipped_name_lists_the_ones_that_do_ship() -> None:
    with pytest.raises(FaceNotFound) as caught:
        shipped_face("nosuchface")
    assert "panelgothic" in str(caught.value)


def test_load_face_falls_through_to_the_shipped_face() -> None:
    assert load_face("panelgothic").name == "panelgothic"


def test_load_face_prefers_a_file_that_exists(tmp_path: Path) -> None:
    local = tmp_path / "panelgothic.strk"
    local.write_text(
        "face local\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    assert load_face("panelgothic", search=tmp_path).name == "local"
    assert load_face("panelgothic").name == "panelgothic"


def test_load_face_adds_the_suffix_when_the_spec_leaves_it_off(tmp_path: Path) -> None:
    (tmp_path / "housecut.strk").write_text(
        "face housecut\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    assert load_face("housecut", search=tmp_path).name == "housecut"


def test_load_face_accepts_a_path_with_the_suffix_already_on_it(tmp_path: Path) -> None:
    target = tmp_path / "housecut.strk"
    target.write_text(
        "face housecut\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    assert load_face(str(target)).name == "housecut"


def test_load_face_file_refuses_a_directory(tmp_path: Path) -> None:
    with pytest.raises(FaceNotFound):
        load_face_file(tmp_path)


def test_load_face_file_refuses_something_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(FaceNotFound):
        load_face_file(tmp_path / "gone.strk")


def test_a_face_file_is_not_cached_because_a_file_changes(tmp_path: Path) -> None:
    target = tmp_path / "housecut.strk"
    target.write_text(
        "face first\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    assert load_face_file(target).name == "first"
    target.write_text(
        "face second\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n",
        encoding="utf-8",
    )
    assert load_face_file(target).name == "second"
