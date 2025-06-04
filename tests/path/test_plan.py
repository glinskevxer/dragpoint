"""The toolpath: heights, hops and when the machine goes all the way up."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.geometry.stroke import Stroke
from dragpoint.path.cut import Cut, CutList
from dragpoint.path.plan import Move, MoveKind, build_toolpath


def bar(x: float, y: float = 0.0, index: int = 0, length: float = 1.0) -> Cut:
    return Cut(
        stroke=Stroke.from_pairs([(x, y), (x + length, y)]),
        depth=0.3,
        pass_index=index,
    )


def test_a_rapid_may_not_carry_a_feed_rate() -> None:
    with pytest.raises(ValueError, match="no feed rate"):
        Move(MoveKind.RAPID, Point(0.0, 0.0), 5.0, feed=100.0)


def test_a_cutting_move_needs_a_feed_rate() -> None:
    with pytest.raises(ValueError, match="needs a feed rate"):
        Move(MoveKind.FEED, Point(0.0, 0.0), -0.3)


def test_a_feed_rate_of_zero_is_refused() -> None:
    with pytest.raises(OutOfRange, match="feed"):
        Move(MoveKind.FEED, Point(0.0, 0.0), -0.3, feed=0.0)


def test_only_a_feed_move_is_cutting() -> None:
    assert MoveKind.FEED.is_cutting
    assert not MoveKind.RAPID.is_cutting
    assert not MoveKind.PLUNGE.is_cutting
    assert not MoveKind.LIFT.is_cutting


def test_a_move_reads_as_a_line_of_a_program() -> None:
    move = Move(MoveKind.FEED, Point(1.0, 2.0), -0.3, feed=1200.0)
    assert str(move) == "feed to (1.0000, 2.0000) z-0.300 F1200"
    assert "rapid" in str(Move(MoveKind.RAPID, Point(0.0, 0.0), 5.0))


def test_an_empty_cut_list_makes_no_moves() -> None:
    path = build_toolpath(CutList(), feed=1200.0, plunge_feed=300.0)
    assert len(path) == 0
    assert path.bounds() is None
    assert path.deepest() == 0.0
    assert path.cut_length() == 0.0


def test_one_cut_makes_a_rapid_a_plunge_a_feed_and_a_lift() -> None:
    path = build_toolpath(CutList.of([bar(10.0)]), feed=1200.0, plunge_feed=300.0)
    kinds = [move.kind for move in path]
    assert kinds == [MoveKind.RAPID, MoveKind.PLUNGE, MoveKind.FEED, MoveKind.LIFT]


def test_the_plunge_goes_to_the_depth_of_the_cut() -> None:
    path = build_toolpath(CutList.of([bar(10.0)]), feed=1200.0, plunge_feed=300.0)
    plunge = path.of_kind(MoveKind.PLUNGE)[0]
    assert plunge.z == pytest.approx(-0.3)
    assert path.deepest() == pytest.approx(-0.3)


def test_the_path_finishes_at_the_safe_height() -> None:
    path = build_toolpath(CutList.of([bar(10.0)]), feed=1200.0, plunge_feed=300.0, safe=7.0)
    assert path.moves[-1].kind is MoveKind.LIFT
    assert path.moves[-1].z == 7.0
    assert path.highest() == 7.0


def test_a_short_hop_stays_at_the_clearance_height() -> None:
    cuts = CutList.of([bar(0.0), bar(3.0)])
    path = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, clearance=0.4, hop_limit=25.0)
    lifts = path.of_kind(MoveKind.LIFT)
    assert lifts[0].z == pytest.approx(0.4)


def test_a_long_move_goes_all_the_way_up_first() -> None:
    cuts = CutList.of([bar(0.0), bar(200.0)])
    path = build_toolpath(
        cuts, feed=1200.0, plunge_feed=300.0, safe=6.0, clearance=0.4, hop_limit=25.0
    )
    assert any(move.kind is MoveKind.LIFT and move.z == 6.0 for move in path.moves[:4])


def test_the_hop_limit_decides_which_it_is() -> None:
    cuts = CutList.of([bar(0.0), bar(30.0)])
    hopping = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, hop_limit=100.0, clearance=0.4)
    climbing = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, hop_limit=1.0, clearance=0.4)
    assert max(move.z for move in hopping.moves[1:5]) < climbing.highest()


def test_a_change_of_pass_always_goes_to_safe() -> None:
    cuts = CutList.of([bar(0.0, index=0), bar(1.0, index=1)])
    path = build_toolpath(
        cuts, feed=1200.0, plunge_feed=300.0, safe=6.0, clearance=0.4, hop_limit=1000.0
    )
    lifts = [move for move in path.moves if move.kind is MoveKind.LIFT]
    assert any(move.z == 6.0 for move in lifts[:-1])


def test_no_rapid_is_emitted_when_the_next_cut_starts_where_the_last_one_ended() -> None:
    joined = CutList.of(
        [
            Cut(stroke=Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0)]), depth=0.3, pass_index=0),
            Cut(stroke=Stroke.from_pairs([(1.0, 0.0), (2.0, 0.0)]), depth=0.3, pass_index=0),
        ]
    )
    path = build_toolpath(joined, feed=1200.0, plunge_feed=300.0, start=Point(10.0, 10.0))
    assert len(path.of_kind(MoveKind.RAPID)) == 1


def test_every_point_of_a_stroke_becomes_a_feed_move() -> None:
    long_cut = Cut(
        stroke=Stroke.from_pairs([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (2.0, 1.0)]),
        depth=0.3,
        pass_index=0,
    )
    path = build_toolpath(CutList.of([long_cut]), feed=1200.0, plunge_feed=300.0)
    assert len(path.of_kind(MoveKind.FEED)) == 3


def test_the_cut_length_matches_the_strokes() -> None:
    cuts = CutList.of([bar(0.0, length=10.0), bar(20.0, length=5.0)])
    path = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0)
    assert path.cut_length() == pytest.approx(15.0)


def test_the_rapid_length_is_the_air_time() -> None:
    cuts = CutList.of([bar(0.0, length=1.0), bar(20.0, length=1.0)])
    path = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, start=Point(0.0, 0.0))
    assert path.rapid_length() == pytest.approx(19.0)


def test_the_plunge_depth_counts_from_wherever_the_axis_was() -> None:
    cuts = CutList.of([bar(0.0), bar(20.0)])
    path = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, clearance=0.5, hop_limit=100.0)
    # Down 0.3 from the surface for the first cut, then down 0.8 from the
    # clearance hop for the second.
    assert path.plunge_depth() == pytest.approx(1.1)


def test_a_lower_clearance_means_less_plunging() -> None:
    cuts = CutList.of([bar(0.0), bar(20.0)])
    low = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, clearance=0.2, hop_limit=100.0)
    high = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0, clearance=2.0, hop_limit=100.0)
    assert low.plunge_depth() < high.plunge_depth()


def test_feeds_carry_the_cutting_feed_and_plunges_the_plunge_feed() -> None:
    path = build_toolpath(CutList.of([bar(0.0)]), feed=1200.0, plunge_feed=300.0)
    assert all(move.feed == 1200.0 for move in path.of_kind(MoveKind.FEED))
    assert all(move.feed == 300.0 for move in path.of_kind(MoveKind.PLUNGE))


def test_rapids_carry_no_feed_at_all() -> None:
    path = build_toolpath(CutList.of([bar(0.0), bar(20.0)]), feed=1200.0, plunge_feed=300.0)
    assert all(move.feed is None for move in path.of_kind(MoveKind.RAPID))


def test_the_bounds_cover_everywhere_the_head_goes() -> None:
    cuts = CutList.of([bar(0.0, length=10.0), bar(20.0, y=5.0, length=10.0)])
    box = build_toolpath(cuts, feed=1200.0, plunge_feed=300.0).bounds()
    assert box is not None
    assert box.max_x == 30.0
    assert box.max_y == 5.0


def test_a_clearance_above_the_safe_height_is_refused() -> None:
    with pytest.raises(OutOfRange, match="clearance"):
        build_toolpath(
            CutList.of([bar(0.0)]), feed=1200.0, plunge_feed=300.0, safe=1.0, clearance=2.0
        )


def test_a_clearance_of_zero_is_refused() -> None:
    with pytest.raises(OutOfRange, match="clearance"):
        build_toolpath(CutList.of([bar(0.0)]), feed=1200.0, plunge_feed=300.0, clearance=0.0)


def test_a_negative_hop_limit_is_refused() -> None:
    with pytest.raises(OutOfRange, match="hop limit"):
        build_toolpath(CutList.of([bar(0.0)]), feed=1200.0, plunge_feed=300.0, hop_limit=-1.0)


def test_str_summarises_the_program() -> None:
    path = build_toolpath(CutList.of([bar(0.0, length=10.0)]), feed=1200.0, plunge_feed=300.0)
    assert "moves" in str(path)
    assert "in the air" in str(path)
