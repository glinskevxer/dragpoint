"""Unit parsing, because a plate spec written in inches is the normal case."""

from __future__ import annotations

import math

import pytest

from dragpoint.errors import BadLength, BadUnit, OutOfRange
from dragpoint.units import (
    MM_PER_INCH,
    QUANTUM,
    format_length,
    parse_length,
    quantise,
    require_range,
    same_length,
    to_unit,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1mm", 1.0),
        ("1 mm", 1.0),
        (" 2.5mm ", 2.5),
        ("1cm", 10.0),
        ("0.5m", 500.0),
        ("1000um", 1.0),
        ("1in", MM_PER_INCH),
        ('0.5"', MM_PER_INCH / 2),
        ("1inch", MM_PER_INCH),
        ("2inches", 2 * MM_PER_INCH),
        ("10thou", 0.254),
        ("10mil", 0.254),
        ("1e1mm", 10.0),
        ("-3mm", -3.0),
        (".5mm", 0.5),
        ("5.mm", 5.0),
    ],
)
def test_parse_length_reads_the_suffixes_the_shop_types(text: str, expected: float) -> None:
    assert parse_length(text) == pytest.approx(expected)


def test_a_bare_number_takes_the_default_unit() -> None:
    assert parse_length("0.375", default_unit="in") == pytest.approx(9.525)
    assert parse_length("0.375") == pytest.approx(0.375)


def test_numbers_come_through_untouched() -> None:
    assert parse_length(3) == 3.0
    assert parse_length(3.5, default_unit="in") == pytest.approx(88.9)


def test_a_boolean_is_not_a_length() -> None:
    with pytest.raises(BadLength) as caught:
        parse_length(True)
    assert "boolean" in str(caught.value)


@pytest.mark.parametrize("text", ["", "mm", "one", "1..2mm", "1 2 mm", "nan"])
def test_junk_is_rejected_as_a_length(text: str) -> None:
    with pytest.raises(BadLength):
        parse_length(text)


def test_an_unknown_suffix_names_the_ones_that_are_known() -> None:
    with pytest.raises(BadUnit) as caught:
        parse_length("4furlong")
    message = str(caught.value)
    assert "furlong" in message
    assert "thou" in message


def test_infinity_is_not_a_length() -> None:
    with pytest.raises(BadLength):
        parse_length(str(math.inf))


def test_to_unit_round_trips() -> None:
    for mm in (0.0, 1.0, 25.4, 1234.5):
        for unit in ("mm", "in", "thou", "um"):
            assert parse_length(f"{to_unit(mm, unit)}{unit}") == pytest.approx(mm)


@pytest.mark.parametrize(
    ("mm", "unit", "expected"),
    [
        (1.0, "mm", "1mm"),
        (25.4, "in", "1in"),
        (0.254, "thou", "10thou"),
        (0.0, "mm", "0mm"),
        (1.23456, "mm", "1.2346mm"),
    ],
)
def test_format_length_drops_trailing_zeros(mm: float, unit: str, expected: str) -> None:
    assert format_length(mm, unit) == expected


def test_format_length_of_a_value_below_the_quantum_reads_as_zero() -> None:
    assert format_length(1e-9) == "0mm"
    assert format_length(-1e-9) == "0mm"


def test_quantise_snaps_to_the_machine_resolution() -> None:
    assert quantise(1.000049) == pytest.approx(1.0)
    assert quantise(1.00006) == pytest.approx(1.0001)
    assert quantise(2.5, 0.5) == pytest.approx(2.5)
    assert quantise(2.6, 0.5) == pytest.approx(2.5)


def test_a_quantum_of_zero_is_refused() -> None:
    with pytest.raises(OutOfRange):
        quantise(1.0, 0.0)


def test_same_length_is_the_quantum_and_not_an_epsilon() -> None:
    assert same_length(1.0, 1.0 + QUANTUM / 2)
    assert not same_length(1.0, 1.0 + QUANTUM * 2)


def test_require_range_returns_the_value_it_accepted() -> None:
    assert require_range("depth", 0.3, 0.0, 1.0) == 0.3
    with pytest.raises(OutOfRange) as caught:
        require_range("depth", 1.5, 0.0, 1.0)
    assert "depth is 1.5" in str(caught.value)


def test_a_simple_fraction_of_an_inch_reads() -> None:
    assert parse_length("7/8in") == pytest.approx(22.225)


def test_a_whole_number_and_a_fraction_read_together() -> None:
    assert parse_length("1 1/2in") == pytest.approx(38.1)


def test_a_fraction_with_no_unit_takes_the_default() -> None:
    assert parse_length("3/8") == pytest.approx(0.375)
    assert parse_length("3/8", default_unit="in") == pytest.approx(9.525)


def test_a_negative_fraction_reads() -> None:
    assert parse_length("-1 1/4in") == pytest.approx(-31.75)


def test_space_round_the_slash_is_allowed() -> None:
    assert parse_length("7 / 8 in") == pytest.approx(22.225)


def test_a_fraction_in_quote_marks_is_inches() -> None:
    assert parse_length('7/8"') == pytest.approx(22.225)


def test_no_space_means_the_numerator_is_the_whole_number() -> None:
    assert parse_length("11/2in") == pytest.approx(139.7)


def test_a_fraction_over_nothing_is_a_message() -> None:
    with pytest.raises(BadLength, match="over nothing"):
        parse_length("1/0in")


def test_a_fraction_in_a_unit_nobody_knows_is_a_message() -> None:
    with pytest.raises(BadUnit):
        parse_length("1/2furlong")


def test_a_decimal_still_reads_the_way_it_always_did() -> None:
    assert parse_length("0.875in") == pytest.approx(22.225)


def test_a_fraction_reads_the_same_as_its_decimal() -> None:
    assert parse_length("7/8in") == pytest.approx(parse_length("0.875in"))
