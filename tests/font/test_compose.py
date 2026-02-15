"""Putting a mark over a letter to get an accented capital."""

from __future__ import annotations

import pytest

from dragpoint.errors import FontSyntax
from dragpoint.font.compose import ACCENT_GAP, SIDE_BEARING, compose_glyph
from dragpoint.font.glyph import Glyph
from dragpoint.geometry.stroke import Stroke

WIDE = Glyph(
    name="E",
    advance=560,
    strokes=(
        Stroke.from_pairs([(480.0, 700.0), (80.0, 700.0), (80.0, 0.0), (480.0, 0.0)]),
        Stroke.from_pairs([(80.0, 350.0), (400.0, 350.0)]),
    ),
)

NARROW = Glyph(name="I", advance=260, strokes=(Stroke.from_pairs([(130.0, 700.0), (130.0, 0.0)]),))

MARK = Glyph(
    name="acutecomb", advance=0, strokes=(Stroke.from_pairs([(180.0, 770.0), (330.0, 910.0)]),)
)

BLANK = Glyph(name="space", advance=240)


def over(base: Glyph = WIDE, mark: Glyph = MARK, **kwargs: object) -> Glyph:
    return compose_glyph("test", base, mark, **kwargs)  # type: ignore[arg-type]


def test_the_composed_glyph_keeps_the_strokes_of_the_base() -> None:
    made = over()
    assert made.strokes[: len(WIDE.strokes)] == WIDE.strokes


def test_the_mark_is_added_on_top_of_them() -> None:
    assert over().stroke_count() == WIDE.stroke_count() + MARK.stroke_count()


def test_the_advance_is_the_advance_of_the_base() -> None:
    assert over().advance == WIDE.advance


def test_the_mark_clears_the_ink_of_the_base_by_the_gap() -> None:
    made = over()
    base_top = WIDE.ink_bounds().max_y  # type: ignore[union-attr]
    mark_bottom = min(
        point.y for stroke in made.strokes[len(WIDE.strokes) :] for point in stroke.points
    )
    assert mark_bottom == pytest.approx(base_top + ACCENT_GAP)


def test_the_gap_can_be_asked_for() -> None:
    made = over(gap=200)
    assert made.ink_bounds().max_y > over().ink_bounds().max_y  # type: ignore[union-attr]


def test_the_mark_sits_over_the_middle_of_the_base_ink() -> None:
    made = over()
    marks = made.strokes[len(WIDE.strokes) :]
    middle = sum(point.x for stroke in marks for point in stroke.points) / 2.0
    base = WIDE.ink_bounds()
    assert base is not None
    assert middle == pytest.approx(base.centre.x, abs=1.0)


def test_the_mark_stays_inside_the_side_bearings() -> None:
    made = over(NARROW)
    box = made.ink_bounds()
    assert box is not None
    assert box.min_x >= SIDE_BEARING - 0.001
    assert box.max_x <= NARROW.advance - SIDE_BEARING + 0.001


def test_a_mark_too_wide_for_the_letter_is_narrowed() -> None:
    made = over(NARROW)
    marks = made.strokes[len(NARROW.strokes) :]
    width = max(point.x for stroke in marks for point in stroke.points) - min(
        point.x for stroke in marks for point in stroke.points
    )
    assert width < 150.0


def test_a_narrowed_mark_keeps_its_height() -> None:
    made = over(NARROW)
    marks = made.strokes[len(NARROW.strokes) :]
    height = max(point.y for stroke in marks for point in stroke.points) - min(
        point.y for stroke in marks for point in stroke.points
    )
    assert height == pytest.approx(140.0)


def test_a_wide_letter_leaves_the_mark_alone() -> None:
    made = over()
    marks = made.strokes[len(WIDE.strokes) :]
    width = max(point.x for stroke in marks for point in stroke.points) - min(
        point.x for stroke in marks for point in stroke.points
    )
    assert width == pytest.approx(150.0)


def test_the_composed_glyph_says_what_it_was_made_from() -> None:
    assert over().composed_from == ("E", "acutecomb")


def test_the_composed_glyph_is_tagged_as_composed() -> None:
    assert over().has_tag("composed")


def test_the_tags_of_the_base_come_through() -> None:
    base = Glyph(
        name="E",
        advance=560,
        strokes=WIDE.strokes,
        tags=frozenset({"wide"}),
    )
    assert over(base).has_tag("wide")


def test_the_code_point_is_the_one_the_composed_glyph_asks_for() -> None:
    assert over(codepoint=0xC9).codepoint == 0xC9


def test_a_base_with_no_ink_cannot_carry_a_mark() -> None:
    with pytest.raises(FontSyntax, match="no ink to put a mark over"):
        over(BLANK)


def test_a_mark_with_no_ink_is_not_a_mark() -> None:
    with pytest.raises(FontSyntax, match="no ink in it"):
        over(mark=BLANK)


def test_a_negative_gap_is_refused() -> None:
    with pytest.raises(FontSyntax, match="in the letter"):
        over(gap=-10)
