"""Cuts and cut lists, and the two ways passes and strokes can nest."""

from __future__ import annotations

import pytest

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList, PassOrder, expand_passes
from dragpoint.tool.cutter import catalogue_cutter
from dragpoint.tool.material import material
from dragpoint.tool.passes import PassPlan, plan_passes


def strokes() -> list[Stroke]:
    return [
        Stroke.from_pairs([(0.0, 0.0), (10.0, 0.0)]),
        Stroke.from_pairs([(0.0, 5.0), (10.0, 5.0)]),
    ]


def three_passes() -> PassPlan:
    return plan_passes(0.9, material("LAM32-RW"), catalogue_cutter("V30-015"))


def test_a_cut_that_removes_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="removes nothing"):
        Cut(stroke=strokes()[0], depth=0.0, pass_index=0)


def test_a_negative_pass_index_is_refused() -> None:
    with pytest.raises(ValueError, match="not a pass"):
        Cut(stroke=strokes()[0], depth=0.3, pass_index=-1)


def test_a_cut_knows_its_ends_and_its_length() -> None:
    cut = Cut(stroke=strokes()[0], depth=0.3, pass_index=0)
    assert cut.start == Point(0.0, 0.0)
    assert cut.end == Point(10.0, 0.0)
    assert cut.length() == 10.0
    assert cut.bounds().width == 10.0


def test_reversing_a_cut_keeps_the_depth_and_the_pass() -> None:
    cut = Cut(stroke=strokes()[0], depth=0.3, pass_index=2, tag="border")
    back = cut.reversed()
    assert back.start == cut.end
    assert back.depth == 0.3
    assert back.pass_index == 2
    assert back.tag == "border"


def test_str_reads_like_a_line_of_a_program_listing() -> None:
    cut = Cut(stroke=strokes()[0], depth=0.25, pass_index=1)
    assert str(cut) == "legend pass 1 at 0.250mm, 10.00mm"


def test_an_empty_list_measures_zero() -> None:
    empty = CutList()
    assert len(empty) == 0
    assert empty.cut_length() == 0.0
    assert empty.travel_length() == 0.0
    assert empty.bounds() is None
    assert empty.depths() == ()
    assert empty.pass_count() == 0


def test_cut_length_adds_the_cuts_up() -> None:
    cuts = expand_passes(strokes(), three_passes())
    assert cuts.cut_length() == pytest.approx(60.0)


def test_travel_counts_the_moves_between_cuts() -> None:
    first = Cut(stroke=strokes()[0], depth=0.3, pass_index=0)
    second = Cut(stroke=strokes()[1], depth=0.3, pass_index=0)
    listing = CutList.of([first, second])
    assert listing.travel_length() == pytest.approx(Point(10.0, 0.0).distance_to(Point(0.0, 5.0)))


def test_travel_counts_the_move_to_the_first_cut_when_a_start_is_given() -> None:
    listing = CutList.of([Cut(stroke=strokes()[0], depth=0.3, pass_index=0)])
    assert listing.travel_length() == 0.0
    assert listing.travel_length(Point(0.0, 4.0)) == pytest.approx(4.0)


def test_by_pass_nests_every_stroke_inside_each_pass() -> None:
    cuts = expand_passes(strokes(), three_passes(), order=PassOrder.BY_PASS)
    assert len(cuts) == 6
    assert [cut.pass_index for cut in cuts] == [0, 0, 1, 1, 2, 2]


def test_by_stroke_nests_every_pass_inside_each_stroke() -> None:
    cuts = expand_passes(strokes(), three_passes(), order=PassOrder.BY_STROKE)
    assert len(cuts) == 6
    assert [cut.pass_index for cut in cuts] == [0, 1, 2, 0, 1, 2]


def test_the_two_orders_cut_the_same_metal() -> None:
    by_pass = expand_passes(strokes(), three_passes(), order=PassOrder.BY_PASS)
    by_stroke = expand_passes(strokes(), three_passes(), order=PassOrder.BY_STROKE)
    assert by_pass.cut_length() == pytest.approx(by_stroke.cut_length())
    assert by_pass.depths() == by_stroke.depths()


def test_by_pass_walks_the_plate_more_than_by_stroke() -> None:
    apart = [
        Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)]),
        Stroke.from_pairs([(100.0, 0.0), (101.0, 0.0)]),
    ]
    by_pass = expand_passes(apart, three_passes(), order=PassOrder.BY_PASS)
    by_stroke = expand_passes(apart, three_passes(), order=PassOrder.BY_STROKE)
    assert by_pass.travel_length() > by_stroke.travel_length()


def test_depths_come_back_shallowest_first() -> None:
    cuts = expand_passes(strokes(), three_passes())
    assert cuts.depths() == pytest.approx((0.3, 0.6, 0.9))


def test_pass_count_counts_distinct_passes() -> None:
    assert expand_passes(strokes(), three_passes()).pass_count() == 3


def test_by_pass_selects_one_pass_in_order() -> None:
    cuts = expand_passes(strokes(), three_passes())
    first = cuts.by_pass(0)
    assert len(first) == 2
    assert all(cut.pass_index == 0 for cut in first)


def test_tags_are_carried_and_selectable() -> None:
    legend = expand_passes(strokes(), three_passes(), tag="legend")
    border = expand_passes(strokes()[:1], three_passes(), tag="border")
    both = legend.then(border)
    assert both.tags() == ("border", "legend")
    assert len(both.by_tag("border")) == 3
    assert len(both) == 9


def test_then_keeps_both_sides_in_order() -> None:
    left = CutList.of([Cut(stroke=strokes()[0], depth=0.3, pass_index=0, tag="a")])
    right = CutList.of([Cut(stroke=strokes()[1], depth=0.3, pass_index=0, tag="b")])
    assert [cut.tag for cut in left.then(right)] == ["a", "b"]


def test_indexing_and_iteration() -> None:
    cuts = expand_passes(strokes(), three_passes())
    assert cuts[0].pass_index == 0
    assert len(list(cuts)) == 6


def test_bounds_cover_every_cut() -> None:
    box = expand_passes(strokes(), three_passes()).bounds()
    assert box is not None
    assert box.height == 5.0


def test_str_summarises_the_list() -> None:
    cuts = expand_passes(strokes(), three_passes())
    assert str(cuts) == "6 cuts over 3 passes, 60.0mm of cutting"


def test_expanding_no_strokes_gives_no_cuts() -> None:
    assert len(expand_passes([], three_passes())) == 0
