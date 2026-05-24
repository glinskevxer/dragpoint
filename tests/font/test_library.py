"""Resolving a face reference, and the shipped face parsing at all."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dragpoint.errors import FaceNotFound
from dragpoint.font.library import (
    FACE_PATH_VARIABLE,
    face_path,
    load_face,
    load_face_file,
    local_names,
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


def test_the_dial_face_ships_as_well() -> None:
    assert "dialface" in shipped_names()


def test_the_dial_face_draws_the_figures_and_not_the_letters() -> None:
    face = shipped_face("dialface")
    assert face.missing("0123456789 .,-/+") == ()
    assert face.missing("ABC") == ("A", "B", "C")


def test_the_dial_face_is_narrower_than_the_house_face() -> None:
    dial = shipped_face("dialface")
    house = shipped_face("panelgothic")
    assert dial.glyph("zero").advance < house.glyph("zero").advance


def test_the_two_faces_share_a_grid_so_they_mix_on_one_plate() -> None:
    dial = shipped_face("dialface")
    house = shipped_face("panelgothic")
    assert dial.metrics.units_per_em == house.metrics.units_per_em
    assert dial.metrics.cap_height == house.metrics.cap_height


def test_the_dial_face_has_no_fallback_because_it_is_not_an_alphabet() -> None:
    assert shipped_face("dialface").fallback is None


def test_a_plate_can_ask_for_the_dial_face() -> None:
    from dragpoint.compiler.plate import compile_plate
    from dragpoint.spec.plate import PlateSpec

    made = compile_plate(
        PlateSpec(
            name="SCALE",
            width=60.0,
            height=14.0,
            stock="LAM16-BW",
            lines=("0 20 40 60 80",),
            face="dialface",
        )
    )
    assert made.ok, str(made.report)
    assert made.face.name == "dialface"


def test_the_house_face_draws_the_accented_capitals_export_work_needs() -> None:
    face = shipped_face("panelgothic")
    accented = "".join(chr(code) for code in (0xC9, 0xC8, 0xCA, 0xCB, 0xD1, 0xDC, 0xD6, 0xC0))
    assert face.missing(accented) == ()


def test_an_accented_capital_is_the_letter_plus_a_mark() -> None:
    face = shipped_face("panelgothic")
    assert face.glyph("Eacute").stroke_count() == face.glyph("E").stroke_count() + 1


def test_an_accented_capital_is_no_wider_than_the_letter() -> None:
    face = shipped_face("panelgothic")
    assert face.glyph("Eacute").advance == face.glyph("E").advance


def test_the_mark_sits_above_the_capital_line() -> None:
    face = shipped_face("panelgothic")
    box = face.glyph("Eacute").ink_bounds()
    assert box is not None
    assert box.max_y > face.metrics.cap_height


def test_the_marks_themselves_take_up_no_room_on_the_line() -> None:
    face = shipped_face("panelgothic")
    assert face.glyph("acutecomb").advance == 0


HOUSE_FACE = "face housecut\nupem 100\ncap 70\nxheight 50\nascender 70\ndescender 0\n"


def shop_faces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *names: str) -> Path:
    """A directory of shop faces, on the search path."""
    (tmp_path / "faces").mkdir(exist_ok=True)
    for name in names:
        (tmp_path / "faces" / f"{name}.strk").write_text(
            HOUSE_FACE.replace("housecut", name), encoding="utf-8"
        )
    monkeypatch.setenv(FACE_PATH_VARIABLE, str(tmp_path / "faces"))
    return tmp_path / "faces"


def test_with_nothing_set_there_is_no_search_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FACE_PATH_VARIABLE, raising=False)
    assert face_path() == ()
    assert local_names() == ()


def test_the_search_path_comes_out_of_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    where = shop_faces(tmp_path, monkeypatch, "housecut")
    assert face_path() == (where,)


def test_a_face_on_the_search_path_is_found_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shop_faces(tmp_path, monkeypatch, "housecut")
    assert load_face("housecut").name == "housecut"


def test_the_faces_on_the_path_are_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shop_faces(tmp_path, monkeypatch, "housecut", "dialcut")
    assert local_names() == ("dialcut", "housecut")


def test_two_directories_are_both_searched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    for where, name in ((first, "onecut"), (second, "twocut")):
        where.mkdir()
        (where / f"{name}.strk").write_text(HOUSE_FACE.replace("housecut", name), encoding="utf-8")
    monkeypatch.setenv(FACE_PATH_VARIABLE, os.pathsep.join([str(first), str(second)]))
    assert local_names() == ("onecut", "twocut")
    assert load_face("twocut").name == "twocut"


def test_an_empty_entry_is_not_the_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FACE_PATH_VARIABLE, os.pathsep)
    assert face_path() == ()


def test_a_directory_that_is_not_there_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(FACE_PATH_VARIABLE, str(tmp_path / "gone"))
    assert local_names() == ()


def test_a_shop_face_wins_over_a_shipped_one_of_the_same_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shop_faces(tmp_path, monkeypatch, "panelgothic")
    assert load_face("panelgothic").metrics.units_per_em == 100


def test_a_face_next_to_the_spec_still_wins_over_the_search_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shop_faces(tmp_path, monkeypatch, "housecut")
    beside = tmp_path / "job"
    beside.mkdir()
    (beside / "housecut.strk").write_text(
        HOUSE_FACE.replace("housecut", "beside"), encoding="utf-8"
    )
    assert load_face("housecut", search=beside).name == "beside"


def test_a_name_nobody_has_anywhere_is_still_a_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FACE_PATH_VARIABLE, raising=False)
    with pytest.raises(FaceNotFound):
        load_face("nosuchface")
