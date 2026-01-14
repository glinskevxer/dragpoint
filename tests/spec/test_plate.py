"""The plate spec: inert data, validated at the edges."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.geometry.box import Box
from dragpoint.geometry.point import Point
from dragpoint.spec.feature import Feature
from dragpoint.spec.plate import PlateSpec
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign, VAlign


def plate(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-101",
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("PUMP 2", "RUN"),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def test_the_defaults_are_the_ones_the_shop_uses() -> None:
    spec = plate()
    assert spec.face == "panelgothic"
    assert spec.cap_height == 3.0
    assert spec.margin == 2.0
    assert spec.halign is HAlign.CENTRE
    assert spec.valign is VAlign.MIDDLE
    assert spec.fit is FitPolicy.CONDENSE
    assert spec.quantity == 1
    assert spec.depth is None
    assert spec.cutter is None


def test_the_outline_sits_on_the_origin() -> None:
    assert plate().outline() == Box(0.0, 0.0, 60.0, 20.0)


def test_the_engraving_area_is_the_blank_less_the_margin() -> None:
    assert plate().area() == Box(2.0, 2.0, 58.0, 18.0)
    assert plate(margin=0.0).area() == plate().outline()


def test_the_border_box_is_inset_by_its_own_number() -> None:
    assert plate(border=1.5).border_box() == Box(1.5, 1.5, 58.5, 18.5)
    assert plate().border_box() is None


def test_the_style_carries_every_text_setting_through() -> None:
    style = plate(cap_height=4.0, tracking=0.3, condense=0.8, slant=15.0, mirror=True).style()
    assert style.cap_height == 4.0
    assert style.tracking == 0.3
    assert style.condense == 0.8
    assert style.slant == 15.0
    assert style.mirror


def test_a_plate_needs_a_name() -> None:
    with pytest.raises(ValueError, match="needs a name"):
        plate(name="")


@pytest.mark.parametrize(
    ("overrides", "what"),
    [
        ({"width": 0.0}, "width"),
        ({"height": -1.0}, "height"),
        ({"margin": -0.5}, "margin"),
        ({"quantity": 0}, "quantity"),
        ({"depth": 0.0}, "depth"),
        ({"margin": 10.0}, "margin"),
        ({"border": -1.0}, "border"),
        ({"border": 10.0}, "border"),
    ],
)
def test_the_impossible_is_refused(overrides: dict[str, object], what: str) -> None:
    with pytest.raises(OutOfRange) as caught:
        plate(**overrides)
    assert what in str(caught.value)


def test_a_margin_that_eats_the_plate_names_the_plate() -> None:
    with pytest.raises(OutOfRange, match="P-101 margin"):
        plate(margin=10.0)


def test_a_line_with_a_newline_in_it_is_refused() -> None:
    with pytest.raises(ValueError, match="newline"):
        plate(lines=("TOP\nBOTTOM",))


def test_feature_lookup_by_name() -> None:
    hole = Feature.round_hole("fix1", Point(5.0, 10.0), 4.0)
    spec = plate(features=(hole,))
    assert spec.feature("fix1") is hole


def test_an_unknown_feature_lists_the_ones_that_are_there() -> None:
    spec = plate(features=(Feature.round_hole("fix1", Point(5.0, 10.0), 4.0),))
    with pytest.raises(KeyError) as caught:
        spec.feature("fix9")
    assert "fix1" in str(caught.value)


def test_a_plate_with_no_features_says_none() -> None:
    with pytest.raises(KeyError, match="none"):
        plate().feature("fix1")


def test_a_feature_off_the_edge_is_reported_not_refused() -> None:
    outside = Feature.round_hole("stray", Point(80.0, 10.0), 4.0)
    inside = Feature.round_hole("fix1", Point(5.0, 10.0), 4.0)
    spec = plate(features=(inside, outside))
    assert [item.name for item in spec.features_outside_the_blank()] == ["stray"]


def test_a_feature_touching_the_edge_is_still_on_the_plate() -> None:
    edge = Feature.round_hole("edge", Point(2.0, 10.0), 4.0)
    assert plate(features=(edge,)).features_outside_the_blank() == ()


def test_a_plate_with_nothing_on_it_knows_it_is_blank() -> None:
    assert plate(lines=()).is_blank_plate
    assert plate(lines=("", "  ")).is_blank_plate
    assert not plate().is_blank_plate


def test_a_blank_plate_with_a_border_is_not_blank() -> None:
    assert not plate(lines=(), border=1.5).is_blank_plate


def test_tags_come_off_the_schedule() -> None:
    spec = plate(tags=frozenset({"urgent", "remake"}))
    assert spec.has_tag("urgent")
    assert not spec.has_tag("stock")


def test_str_reads_like_a_schedule_row() -> None:
    assert str(plate()) == "P-101 60x20mm LAM16-BW: PUMP 2 / RUN"
    assert str(plate(lines=())) == "P-101 60x20mm LAM16-BW: blank"


def test_a_plain_plate_is_not_sequenced() -> None:
    assert not plate(lines=("RUN",)).sequenced


def test_a_plate_whose_legend_counts_is_sequenced() -> None:
    assert plate(lines=("VLV-{n:03}",), quantity=6).sequenced


def test_a_plain_plate_stands_for_itself() -> None:
    spec = plate(lines=("RUN",), quantity=6)
    assert spec.pieces() == (spec,)


def test_a_numbered_run_comes_out_one_plate_per_piece() -> None:
    pieces = plate(lines=("VLV-{n:03}",), quantity=4).pieces()
    assert len(pieces) == 4
    assert [piece.lines[0] for piece in pieces] == [
        "VLV-001",
        "VLV-002",
        "VLV-003",
        "VLV-004",
    ]


def test_every_piece_of_a_run_is_a_plate_of_one() -> None:
    assert {piece.quantity for piece in plate(lines=("{n}",), quantity=4).pieces()} == {1}


def test_a_piece_carries_its_number_in_its_name() -> None:
    pieces = plate(name="TAG", lines=("{n}",), quantity=3).pieces()
    assert [piece.name for piece in pieces] == ["TAG-1", "TAG-2", "TAG-3"]


def test_a_run_can_start_somewhere_other_than_one() -> None:
    pieces = plate(lines=("VLV-{n}",), quantity=3, sequence_start=101).pieces()
    assert [piece.lines[0] for piece in pieces] == ["VLV-101", "VLV-102", "VLV-103"]


def test_the_total_on_a_piece_is_the_whole_run() -> None:
    pieces = plate(lines=("{n} OF {of}",), quantity=12).pieces()
    assert pieces[0].lines[0] == "1 OF 12"


def test_a_piece_keeps_the_name_the_schedule_gave_the_run() -> None:
    pieces = plate(name="TAG", lines=("{plate}-{n}",), quantity=2).pieces()
    assert pieces[1].lines[0] == "TAG-2"


def test_everything_else_about_a_piece_is_the_plate_it_came_from() -> None:
    spec = plate(lines=("{n}",), quantity=3, cap_height=4.0, stock="LAM32-RW")
    piece = spec.pieces()[0]
    assert piece.cap_height == 4.0
    assert piece.stock == "LAM32-RW"
    assert piece.width == spec.width
