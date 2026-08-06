"""Pricing a job: material, machining and setting."""

from __future__ import annotations

import pytest

from dragpoint.compiler.job import compile_job
from dragpoint.errors import OutOfRange
from dragpoint.estimate.price import DEFAULT_RATE, SQUARE_METRE, Quote, quote_job
from dragpoint.spec.job import JobSpec
from dragpoint.spec.plate import PlateSpec
from dragpoint.tool.material import material


def spec(**overrides: object) -> PlateSpec:
    values: dict[str, object] = {
        "name": "P-1",
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("RUN",),
    }
    values.update(overrides)
    return PlateSpec(**values)  # type: ignore[arg-type]


def priced(*plates: PlateSpec, **settings: float) -> Quote:
    return quote_job(compile_job(JobSpec(name="J", plates=plates or (spec(),))), **settings)


def test_a_job_is_priced_in_three_parts_that_add_up() -> None:
    quote = priced()
    assert quote.total == pytest.approx(quote.material + quote.machining + quote.setting)


def test_the_material_is_the_blank_area_at_the_rack_price() -> None:
    quote = priced(spec(quantity=10))
    sheet = material("LAM16-BW")
    assert sheet.price is not None
    assert quote.material == pytest.approx(60.0 * 20.0 * 10 / SQUARE_METRE * sheet.price)


def test_the_area_is_the_blank_and_not_the_lettering() -> None:
    assert priced(spec(quantity=4)).area == pytest.approx(60.0 * 20.0 * 4)


def test_a_dearer_stock_costs_more_for_the_same_plate() -> None:
    cheap = priced(spec(stock="LAM16-BW"))
    dear = priced(spec(stock="BRASS-15", depth=0.15))
    assert dear.material > cheap.material


def test_the_machining_goes_up_with_the_rate() -> None:
    assert priced(rate=90.0).machining == pytest.approx(2.0 * priced(rate=45.0).machining)


def test_the_default_rate_is_the_one_the_shop_charges() -> None:
    assert priced().machining == pytest.approx(priced(rate=DEFAULT_RATE).machining)


def test_the_setting_is_charged_once_a_cutter() -> None:
    one = priced(spec(name="P-1"), setting=10.0)
    two = priced(spec(name="P-1"), spec(name="P-2", cutter="V20-010"), setting=10.0)
    assert two.setting == pytest.approx(2.0 * one.setting)


def test_a_drilled_job_pays_for_the_drill_going_in() -> None:
    from dragpoint.geometry.point import Point
    from dragpoint.spec.feature import Feature

    plain = priced(spec(name="P-1"), setting=10.0)
    drilled = priced(
        spec(name="P-1", features=(Feature.round_hole("fix", Point(10.0, 10.0), 4.0),)),
        setting=10.0,
    )
    assert drilled.setting > plain.setting


def test_the_price_a_piece_is_the_total_over_the_pieces() -> None:
    quote = priced(spec(quantity=5))
    assert quote.each == pytest.approx(quote.total / 5.0)


def test_a_job_of_nothing_prices_nothing_a_piece() -> None:
    quote = quote_job(compile_job(JobSpec(name="empty")))
    assert quote.pieces == 0
    assert quote.each == 0.0


def test_a_priced_job_says_it_is_complete() -> None:
    quote = priced()
    assert quote.complete
    assert quote.unpriced_stock == ()
    assert "LAM16-BW" in quote.priced_stock


def test_a_stock_with_no_price_is_named_rather_than_guessed() -> None:
    quote = priced(spec(stock="STAIN-10", depth=0.08, cutter="V10-005"))
    assert not quote.complete
    assert quote.unpriced_stock == ("STAIN-10",)


def test_an_unpriced_stock_is_left_out_of_the_material_rather_than_guessed() -> None:
    assert priced(spec(stock="STAIN-10", depth=0.08, cutter="V10-005")).material == 0.0


def test_an_unpriced_stock_still_costs_machine_time() -> None:
    assert priced(spec(stock="STAIN-10", depth=0.08, cutter="V10-005")).machining > 0.0


def test_a_negative_rate_is_refused() -> None:
    with pytest.raises(OutOfRange, match="rate"):
        priced(rate=-1.0)


def test_a_negative_setting_charge_is_refused() -> None:
    with pytest.raises(OutOfRange, match="setting"):
        priced(setting=-1.0)


def test_the_quote_reads_like_a_line_on_an_order() -> None:
    quote = priced(spec(quantity=3))
    assert "J: 3 pieces" in str(quote)
    assert "each" in str(quote)


def test_the_quote_says_when_a_stock_could_not_be_priced() -> None:
    assert "no price for" not in str(priced())
    assert "no price for STAIN-10" in str(
        priced(spec(stock="STAIN-10", depth=0.08, cutter="V10-005"))
    )
