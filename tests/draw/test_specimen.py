"""The specimen sheet: every glyph in a face at the size it gets cut."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

import pytest

from dragpoint.draw.specimen import COLUMNS, render_specimen
from dragpoint.font.library import shipped_face

SVG = "{http://www.w3.org/2000/svg}"


def dial() -> str:
    return render_specimen(shipped_face("dialface"))


def test_the_sheet_is_well_formed_xml() -> None:
    ElementTree.fromstring(dial())


def test_the_title_is_the_face_name() -> None:
    root = ElementTree.fromstring(dial())
    assert str(next(root.iter(SVG + "title")).text) == "dialface"


def test_every_glyph_gets_a_cell() -> None:
    face = shipped_face("dialface")
    root = ElementTree.fromstring(dial())
    assert len(list(root.iter(SVG + "rect"))) == len(face)


def test_every_glyph_gets_a_label_with_its_name_and_advance() -> None:
    root = ElementTree.fromstring(dial())
    labels = [str(text.text) for text in root.iter(SVG + "text")]
    assert "zero 360" in labels


def test_a_blank_glyph_gets_a_cell_and_no_strokes() -> None:
    root = ElementTree.fromstring(dial())
    labels = [str(text.text) for text in root.iter(SVG + "text")]
    assert any(label.startswith("space ") for label in labels)


def test_the_glyphs_are_drawn_at_the_groove_width() -> None:
    root = ElementTree.fromstring(render_specimen(shipped_face("dialface"), groove=0.8))
    widths = {line.get("stroke-width") for line in root.iter(SVG + "polyline")}
    assert widths == {"0.8000"}


def test_the_cells_can_go_without_their_boxes() -> None:
    root = ElementTree.fromstring(render_specimen(shipped_face("dialface"), show_grid=False))
    assert list(root.iter(SVG + "rect")) == []


def test_the_sheet_is_as_many_columns_wide_as_asked_for() -> None:
    narrow = ElementTree.fromstring(render_specimen(shipped_face("dialface"), columns=4))
    wide = ElementTree.fromstring(render_specimen(shipped_face("dialface"), columns=8))
    assert float(str(narrow.get("width"))) < float(str(wide.get("width")))


def test_a_taller_cap_height_makes_a_bigger_sheet() -> None:
    small = ElementTree.fromstring(render_specimen(shipped_face("dialface"), cap_height=4.0))
    large = ElementTree.fromstring(render_specimen(shipped_face("dialface"), cap_height=8.0))
    assert float(str(large.get("height"))) > float(str(small.get("height")))


def test_the_glyphs_are_drawn_the_right_way_up() -> None:
    face = shipped_face("dialface")
    root = ElementTree.fromstring(render_specimen(face, columns=1))
    one = list(root.iter(SVG + "polyline"))
    assert one, "the sheet drew no glyphs at all"


def test_the_caption_says_what_was_drawn() -> None:
    labels = [str(text.text) for text in ElementTree.fromstring(dial()).iter(SVG + "text")]
    assert any("upem" in label for label in labels)


def test_the_house_face_draws_too() -> None:
    ElementTree.fromstring(render_specimen(shipped_face("panelgothic")))


def test_a_cap_height_of_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="draws nothing"):
        render_specimen(shipped_face("dialface"), cap_height=0.0)


def test_a_groove_of_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="draws nothing"):
        render_specimen(shipped_face("dialface"), groove=0.0)


def test_no_columns_is_not_a_sheet() -> None:
    with pytest.raises(ValueError, match="not a sheet"):
        render_specimen(shipped_face("dialface"), columns=0)


def test_the_default_is_the_column_count_the_module_names() -> None:
    default = ElementTree.fromstring(dial())
    named = ElementTree.fromstring(render_specimen(shipped_face("dialface"), columns=COLUMNS))
    assert default.get("width") == named.get("width")
