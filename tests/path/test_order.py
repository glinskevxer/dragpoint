"""Travel ordering: shorter rapids, same cuts, passes kept apart."""

from __future__ import annotations

import random

import pytest

from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList
from dragpoint.path.order import ORIGIN, _flip_delta, order_cuts, travel_of


def bar(x: float, y: float, index: int = 0, length: float = 1.0) -> Cut:
    return Cut(
        stroke=Stroke.from_pairs([(x, y), (x + length, y)]),
        depth=0.3,
        pass_index=index,
    )


def scattered() -> CutList:
    return CutList.of([bar(0.0, 0.0), bar(50.0, 0.0), bar(5.0, 0.0), bar(45.0, 0.0)])


def test_an_empty_list_orders_to_nothing() -> None:
    result = order_cuts(CutList())
    assert len(result.cuts) == 0
    assert result.saved == 0.0


def test_one_cut_is_left_alone() -> None:
    single = CutList.of([bar(10.0, 0.0)])
    result = order_cuts(single)
    assert result.cuts.cuts == single.cuts
    assert result.saved == 0.0


def test_ordering_keeps_every_cut() -> None:
    result = order_cuts(scattered())
    assert len(result.cuts) == 4
    assert result.cuts.cut_length() == pytest.approx(scattered().cut_length())


def test_ordering_shortens_the_travel() -> None:
    result = order_cuts(scattered())
    assert result.after < result.before
    assert result.saved > 0.0
    assert 0.0 < result.saved_fraction <= 1.0


def test_the_reported_after_is_the_travel_of_what_came_back() -> None:
    result = order_cuts(scattered())
    assert result.after == pytest.approx(travel_of(result.cuts))


def test_a_list_already_in_order_is_not_made_worse() -> None:
    tidy = CutList.of([bar(0.0, 0.0), bar(2.0, 0.0), bar(4.0, 0.0), bar(6.0, 0.0)])
    result = order_cuts(tidy)
    assert result.after <= result.before + 1e-9


def test_a_cut_may_be_entered_from_its_far_end() -> None:
    there = Cut(stroke=Stroke.from_pairs([(10.0, 0.0), (0.0, 0.0)]), depth=0.3, pass_index=0)
    result = order_cuts(CutList.of([there]), start=Point(0.0, 0.0))
    assert len(result.cuts) == 1


def test_reversal_makes_a_row_of_bars_a_boustrophedon() -> None:
    rows = CutList.of([bar(0.0, float(row) * 5.0, length=20.0) for row in range(4)])
    result = order_cuts(rows, start=Point(0.0, 0.0))
    starts = [cut.start.x for cut in result.cuts]
    assert starts != [0.0, 0.0, 0.0, 0.0]
    assert result.after < result.before


def test_forbidding_reversal_keeps_every_cut_the_way_round_it_was() -> None:
    rows = CutList.of([bar(0.0, float(row) * 5.0, length=20.0) for row in range(4)])
    result = order_cuts(rows, start=Point(0.0, 0.0), allow_reverse=False)
    assert all(cut.start.x == 0.0 for cut in result.cuts)


def test_forbidding_reversal_costs_travel() -> None:
    rows = CutList.of([bar(0.0, float(row) * 5.0, length=20.0) for row in range(4)])
    free = order_cuts(rows, start=Point(0.0, 0.0))
    fixed = order_cuts(rows, start=Point(0.0, 0.0), allow_reverse=False)
    assert free.after < fixed.after


def test_passes_are_never_mixed() -> None:
    mixed = CutList.of(
        [
            bar(0.0, 0.0, index=0),
            bar(50.0, 0.0, index=0),
            bar(1.0, 0.0, index=1),
            bar(51.0, 0.0, index=1),
        ]
    )
    result = order_cuts(mixed)
    indices = [cut.pass_index for cut in result.cuts]
    assert indices == [0, 0, 1, 1]


def test_a_later_pass_starts_where_the_earlier_one_finished() -> None:
    mixed = CutList.of(
        [
            bar(0.0, 0.0, index=0),
            bar(50.0, 0.0, index=0),
            bar(0.0, 0.0, index=1),
            bar(50.0, 0.0, index=1),
        ]
    )
    result = order_cuts(mixed)
    first_pass_end = result.cuts[1].end
    second_pass_start = result.cuts[2].start
    assert first_pass_end.distance_to(second_pass_start) < 60.0


def test_the_starting_point_is_taken_into_account() -> None:
    two = CutList.of([bar(0.0, 0.0), bar(50.0, 0.0)])
    from_left = order_cuts(two, start=Point(-5.0, 0.0))
    from_right = order_cuts(two, start=Point(60.0, 0.0))
    assert from_left.cuts[0].bounds().min_x < from_right.cuts[0].bounds().min_x


def test_two_opt_can_be_turned_off() -> None:
    plain = order_cuts(scattered(), rounds=0)
    improved = order_cuts(scattered(), rounds=3)
    assert improved.after <= plain.after


def test_two_opt_beats_nearest_neighbour_on_a_case_built_for_it() -> None:
    trap = CutList.of(
        [
            bar(0.0, 0.0),
            bar(10.0, 0.0),
            bar(20.0, 0.0),
            bar(4.0, 30.0),
            bar(14.0, 30.0),
        ]
    )
    greedy = order_cuts(trap, rounds=0)
    polished = order_cuts(trap, rounds=4)
    assert polished.after <= greedy.after


def test_ordering_never_changes_the_tags_or_the_depths() -> None:
    tagged = CutList.of(
        [
            Cut(
                stroke=Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)]),
                depth=0.3,
                pass_index=0,
                tag="border",
            ),
            Cut(
                stroke=Stroke.from_pairs([(9.0, 0.0), (10.0, 0.0)]),
                depth=0.3,
                pass_index=0,
                tag="legend",
            ),
        ]
    )
    result = order_cuts(tagged)
    assert sorted(cut.tag for cut in result.cuts) == ["border", "legend"]
    assert result.cuts.depths() == (0.3,)


def test_str_reads_like_a_line_of_a_run_summary() -> None:
    text = str(order_cuts(scattered()))
    assert text.startswith("travel ")
    assert "saved" in text


def scatter(count: int, seed: int = 7) -> CutList:
    """A plate's worth of short cuts, thrown about the way a legend is."""
    rng = random.Random(seed)
    cuts = []
    for _ in range(count):
        x = rng.uniform(0.0, 120.0)
        y = rng.uniform(0.0, 40.0)
        cuts.append(
            Cut(
                stroke=Stroke.from_pairs(
                    [(x, y), (x + rng.uniform(-4.0, 4.0), y + rng.uniform(-4.0, 4.0))]
                ),
                depth=0.3,
                pass_index=0,
            )
        )
    return CutList.of(cuts)


def full_cost(cuts: CutList, start: Point = ORIGIN) -> float:
    """Travel measured the long way, walking every leg."""
    total = 0.0
    here = start
    for cut in cuts:
        total += here.distance_to(cut.start)
        here = cut.end
    return total


def test_the_saving_is_measured_the_same_way_a_walk_measures_it() -> None:
    result = order_cuts(scatter(20))
    assert result.after == pytest.approx(full_cost(result.cuts))


def test_turning_a_span_round_saves_what_the_delta_says_it_saves() -> None:
    group = list(scatter(8))
    start = ORIGIN
    for first in range(6):
        for last in range(first + 1, 7):
            delta = _flip_delta(group, first, last, start)
            turned = group[:first] + [cut.reversed() for cut in group[first : last + 1][::-1]]
            turned += group[last + 1 :]
            walked = full_cost(CutList.of(turned), start) - full_cost(CutList.of(group), start)
            assert delta == pytest.approx(walked)


def test_ordering_a_busy_plate_shortens_the_travel_a_lot() -> None:
    result = order_cuts(scatter(60))
    assert result.saved_fraction > 0.4


def test_the_ordering_keeps_every_cut() -> None:
    cuts = scatter(30)
    result = order_cuts(cuts)
    assert len(result.cuts) == len(cuts)
    starts = {(cut.start, cut.end) for cut in cuts}
    for cut in result.cuts:
        assert (cut.start, cut.end) in starts or (cut.end, cut.start) in starts


def test_more_rounds_never_makes_it_longer() -> None:
    cuts = scatter(25)
    one = order_cuts(cuts, rounds=1)
    four = order_cuts(cuts, rounds=4)
    assert four.after <= one.after + 1e-9


def test_cuts_that_may_not_be_turned_round_keep_their_direction() -> None:
    cuts = scatter(15)
    fixed = order_cuts(cuts, allow_reverse=False)
    was = {(cut.start, cut.end) for cut in cuts}
    assert all((cut.start, cut.end) in was for cut in fixed.cuts)


def test_ordering_without_turning_still_shortens_the_travel() -> None:
    fixed = order_cuts(scatter(15), allow_reverse=False)
    assert fixed.after < fixed.before
