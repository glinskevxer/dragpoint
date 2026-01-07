"""The nest drawn as a sheet somebody can part up."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

import pytest

from dragpoint.draw.sheet import render_nest
from dragpoint.nest.shelf import nest_pieces
from dragpoint.spec.job import Sheet

SVG = "{http://www.w3.org/2000/svg}"

SHEET = Sheet(stock="LAM16-BW", width=300.0, height=200.0, margin=10.0, kerf=2.0)


def nest(*pieces: tuple[str, float, float], sheet: Sheet = SHEET) -> str:
    return render_nest(nest_pieces(pieces, sheet))


def test_the_drawing_is_well_formed_xml() -> None:
    ElementTree.fromstring(nest(("P-1", 60.0, 20.0), ("P-2", 40.0, 30.0)))


def test_the_document_is_as_wide_as_the_sheet() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0)))
    assert root.get("width") == "300.00"


def test_the_document_is_taller_than_the_sheet_to_hold_the_caption() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0)))
    assert float(str(root.get("height"))) > 200.0


def test_the_scale_multiplies_the_document_and_not_the_view_box() -> None:
    result = nest_pieces([("P-1", 60.0, 20.0)], SHEET)
    root = ElementTree.fromstring(render_nest(result, scale=2.0))
    assert root.get("width") == "600.00"
    assert str(root.get("viewBox")).startswith("0 0 300.0000")


def test_a_scale_of_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="draws nothing"):
        render_nest(nest_pieces([("P-1", 60.0, 20.0)], SHEET), scale=0.0)


def test_every_piece_that_fitted_is_drawn() -> None:
    text = nest(("P-1", 60.0, 20.0), ("P-2", 40.0, 30.0), ("P-3", 25.0, 25.0))
    root = ElementTree.fromstring(text)
    filled = [rect for rect in root.iter(SVG + "rect") if rect.get("fill") != "none"]
    assert len(filled) == 3


def test_the_sheet_and_the_clamp_margin_are_drawn_empty() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0)))
    empty = [rect for rect in root.iter(SVG + "rect") if rect.get("fill") == "none"]
    assert len(empty) == 2


def test_the_clamp_margin_can_be_left_off() -> None:
    result = nest_pieces([("P-1", 60.0, 20.0)], SHEET)
    root = ElementTree.fromstring(render_nest(result, show_margin=False))
    empty = [rect for rect in root.iter(SVG + "rect") if rect.get("fill") == "none"]
    assert len(empty) == 1


def test_a_piece_is_drawn_where_the_nest_put_it() -> None:
    result = nest_pieces([("P-1", 60.0, 20.0)], SHEET)
    placed = result.placements[0]
    root = ElementTree.fromstring(render_nest(result))
    rects = [rect for rect in root.iter(SVG + "rect") if rect.get("fill") != "none"]
    assert float(str(rects[0].get("x"))) == pytest.approx(placed.origin.x)
    assert float(str(rects[0].get("y"))) == pytest.approx(placed.origin.y)


def test_a_turned_piece_is_drawn_in_a_different_colour() -> None:
    tall = Sheet(stock="LAM16-BW", width=200.0, height=60.0, margin=5.0, kerf=2.0)
    result = nest_pieces([("P-1", 30.0, 120.0)], tall)
    assert result.placements[0].rotated
    root = ElementTree.fromstring(render_nest(result))
    fills = {rect.get("fill") for rect in root.iter(SVG + "rect")}
    assert "#f0e4d0" in fills


def test_a_turned_piece_says_so_on_its_label() -> None:
    tall = Sheet(stock="LAM16-BW", width=200.0, height=60.0, margin=5.0, kerf=2.0)
    root = ElementTree.fromstring(render_nest(nest_pieces([("P-1", 30.0, 120.0)], tall)))
    assert [text.text for text in root.iter(SVG + "text") if str(text.text).endswith(" T")]


def test_every_piece_of_a_plate_is_numbered_on_its_label() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0), ("P-1", 60.0, 20.0)))
    labels = [str(text.text) for text in root.iter(SVG + "text")]
    assert "P-1 #1" in labels
    assert "P-1 #2" in labels


def test_labels_can_be_left_off_and_the_caption_stays() -> None:
    result = nest_pieces([("P-1", 60.0, 20.0)], SHEET)
    root = ElementTree.fromstring(render_nest(result, show_labels=False))
    assert len(list(root.iter(SVG + "text"))) == 1


def test_a_piece_too_small_to_hold_a_label_does_not_get_one() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0), ("tiny", 4.0, 4.0)))
    labels = [str(text.text) for text in root.iter(SVG + "text")]
    assert not [label for label in labels if label.startswith("tiny")]


def test_the_caption_says_what_the_nest_came_to() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0)))
    caption = [str(text.text) for text in root.iter(SVG + "text")][-1]
    assert "LAM16-BW" in caption
    assert "all on" in caption


def test_the_pieces_that_did_not_fit_are_named_under_the_sheet() -> None:
    small = Sheet(stock="LAM16-BW", width=80.0, height=40.0, margin=5.0, kerf=2.0)
    text = render_nest(nest_pieces([("P-1", 60.0, 20.0), ("P-2", 60.0, 20.0)], small))
    assert "not on the sheet: P-2 x1" in text


def test_an_empty_nest_still_draws_the_sheet() -> None:
    root = ElementTree.fromstring(render_nest(nest_pieces([], SHEET)))
    assert len(list(root.iter(SVG + "rect"))) == 2


def test_the_title_names_the_stock_and_the_size() -> None:
    root = ElementTree.fromstring(nest(("P-1", 60.0, 20.0)))
    assert str(next(root.iter(SVG + "title")).text) == "LAM16-BW 300x200mm"


def test_a_plate_name_with_an_ampersand_in_it_is_escaped() -> None:
    text = nest(("P&Q", 60.0, 20.0))
    assert "P&amp;Q" in text
    ElementTree.fromstring(text)
