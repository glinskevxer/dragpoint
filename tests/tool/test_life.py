"""How much of a tip a job eats."""

from __future__ import annotations

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.tool.cutter import catalogue_cutter
from dragpoint.tool.life import (
    LIFE_BY_MATERIAL,
    TipLife,
    job_tip_life,
    material_factor,
    tip_life,
)
from dragpoint.tool.material import material

CUTTER = catalogue_cutter("V30-015")
LAMINATE = material("LAM16-BW")
BRASS = material("BRASS-15")
ANODISED = material("ANOD-10")
ACRYLIC = material("ACRYL-30")


def test_laminate_gives_a_tip_its_rated_life() -> None:
    assert material_factor(LAMINATE) == 1.0


def test_brass_takes_far_more_off_a_tip() -> None:
    assert material_factor(BRASS) == LIFE_BY_MATERIAL["brass"]


def test_anodised_aluminium_is_read_off_the_description() -> None:
    assert material_factor(ANODISED) == LIFE_BY_MATERIAL["aluminium"]


def test_stainless_is_the_hardest_thing_on_the_rack() -> None:
    assert material_factor(material("STAIN-10")) == LIFE_BY_MATERIAL["steel"]


def test_acrylic_is_nearly_as_kind_as_laminate() -> None:
    assert material_factor(ACRYLIC) == LIFE_BY_MATERIAL["acrylic"]


def test_a_short_job_uses_part_of_a_tip() -> None:
    life = tip_life(CUTTER, LAMINATE, 50.0)
    assert life.fraction == pytest.approx(0.1)
    assert life.tips == 1
    assert life.within_one_tip


def test_a_long_job_wants_more_than_one_tip() -> None:
    assert tip_life(CUTTER, LAMINATE, 1100.0).tips == 3


def test_a_job_that_lands_exactly_on_the_life_still_goes_on_one_tip() -> None:
    assert tip_life(CUTTER, LAMINATE, CUTTER.life).tips == 1


def test_the_same_metres_in_brass_want_more_tips() -> None:
    laminate = tip_life(CUTTER, LAMINATE, 200.0)
    brass = tip_life(CUTTER, BRASS, 200.0)
    assert brass.tips > laminate.tips


def test_what_is_left_on_the_tip_is_never_below_nothing() -> None:
    assert tip_life(CUTTER, LAMINATE, 10_000.0).remaining() == 0.0


def test_what_is_left_after_a_short_job_is_most_of_the_tip() -> None:
    assert tip_life(CUTTER, LAMINATE, 100.0).remaining() == pytest.approx(CUTTER.life - 100.0)


def test_a_job_that_cuts_nothing_still_asks_for_the_tip_that_is_in() -> None:
    assert tip_life(CUTTER, LAMINATE, 0.0).tips == 1


def test_cutting_backwards_is_refused() -> None:
    with pytest.raises(OutOfRange, match="cutting"):
        TipLife(cutter="V30-015", material="LAM16-BW", cutting=-1.0, life=100.0)


def test_a_tip_with_no_life_is_refused() -> None:
    with pytest.raises(OutOfRange, match="life"):
        TipLife(cutter="V30-015", material="LAM16-BW", cutting=1.0, life=0.0)


def test_one_stock_across_a_job_is_named_by_its_code() -> None:
    life = job_tip_life(CUTTER, {"LAM16-BW": (LAMINATE, 40.0)})
    assert life.material == "LAM16-BW"
    assert life.cutting == pytest.approx(40.0)


def test_two_stocks_across_a_job_say_how_many_there_were() -> None:
    life = job_tip_life(CUTTER, {"LAM16-BW": (LAMINATE, 40.0), "BRASS-15": (BRASS, 10.0)})
    assert life.material == "2 stocks"


def test_metres_in_a_hard_stock_count_for_more() -> None:
    life = job_tip_life(CUTTER, {"BRASS-15": (BRASS, 10.0)})
    assert life.cutting == pytest.approx(10.0 / LIFE_BY_MATERIAL["brass"])


def test_a_mixed_job_adds_what_each_stock_is_worth() -> None:
    life = job_tip_life(CUTTER, {"LAM16-BW": (LAMINATE, 40.0), "BRASS-15": (BRASS, 10.0)})
    assert life.cutting == pytest.approx(40.0 + 10.0 / LIFE_BY_MATERIAL["brass"])


def test_a_job_on_no_stock_at_all_asks_nothing_of_the_tip() -> None:
    assert job_tip_life(CUTTER, {}).cutting == 0.0


def test_the_line_reads_like_something_off_a_setup_sheet() -> None:
    assert "V30-015" in str(tip_life(CUTTER, LAMINATE, 50.0))
    assert "1 tip" in str(tip_life(CUTTER, LAMINATE, 50.0))


def test_more_than_one_tip_is_written_in_the_plural() -> None:
    assert "3 tips" in str(tip_life(CUTTER, LAMINATE, 1100.0))
