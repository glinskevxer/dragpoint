"""Turning the command line options into a plate spec and a setup."""

from __future__ import annotations

from typing import Any

import pytest

from dragpoint.cli.options import _size, plate_from_options, setup_from_options
from dragpoint.geometry.point import Point
from dragpoint.path.cut import PassOrder
from dragpoint.text.fit import FitPolicy
from dragpoint.text.layout import HAlign, VAlign


def defaults(**overrides: Any) -> dict[str, Any]:
    """What click hands a command body when nothing is given."""
    values: dict[str, Any] = {
        "lines": ("RUN",),
        "name": "PLATE",
        "size": "60x20mm",
        "stock": "LAM16-BW",
        "face": "panelgothic",
        "cap_height": "3mm",
        "tracking": "0mm",
        "condense": 1.0,
        "slant": 0.0,
        "mirror": False,
        "wrap": False,
        "fit": "condense",
        "halign": "centre",
        "valign": "middle",
        "margin": "2mm",
        "border": None,
        "depth": None,
        "cutter": None,
        "safe": "5mm",
        "clearance": "0.5mm",
        "hop": "25mm",
        "ramp": "0mm",
        "no_optimise": False,
        "pass_order": "by-pass",
        "rapid_rate": 6000.0,
        "arc_radius": None,
        "arc_start": 90.0,
        "arc_sweep": 180.0,
        "arc_clockwise": False,
        "arc_inward": False,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("60x20mm", (60.0, 20.0)),
        ("60mmx20mm", (60.0, 20.0)),
        ("2x1in", (50.8, 25.4)),
        ("60X20mm", (60.0, 20.0)),
        ("60*20mm", (60.0, 20.0)),
    ],
)
def test_a_size_reads_the_way_people_write_one(text: str, expected: tuple[float, float]) -> None:
    assert _size(text) == pytest.approx(expected)


def test_a_unit_on_the_second_number_applies_to_both() -> None:
    assert _size("2x1in")[0] == pytest.approx(50.8)


@pytest.mark.parametrize("text", ["wide", "60mm", "60x20x10mm"])
def test_something_that_is_not_a_size_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="not a size"):
        _size(text)


def test_the_defaults_make_the_plate_the_shop_cuts_most() -> None:
    spec = plate_from_options(defaults())
    assert spec.name == "PLATE"
    assert spec.width == 60.0
    assert spec.height == 20.0
    assert spec.stock == "LAM16-BW"
    assert spec.lines == ("RUN",)
    assert spec.cap_height == 3.0
    assert spec.margin == 2.0
    assert spec.halign is HAlign.CENTRE
    assert spec.valign is VAlign.MIDDLE
    assert spec.fit is FitPolicy.CONDENSE
    assert spec.border is None
    assert spec.depth is None
    assert spec.cutter is None


def test_every_length_option_takes_a_unit() -> None:
    spec = plate_from_options(
        defaults(
            cap_height="0.125in", tracking="10thou", margin="0.25in", border="3mm", depth="15thou"
        )
    )
    assert spec.cap_height == pytest.approx(3.175)
    assert spec.tracking == pytest.approx(0.254)
    assert spec.margin == pytest.approx(6.35)
    assert spec.border == 3.0
    assert spec.depth == pytest.approx(0.381)


def test_the_words_map_onto_the_enumerations() -> None:
    spec = plate_from_options(defaults(halign="left", valign="bottom", fit="both"))
    assert spec.halign is HAlign.LEFT
    assert spec.valign is VAlign.BOTTOM
    assert spec.fit is FitPolicy.BOTH


def test_the_shape_options_come_through() -> None:
    spec = plate_from_options(defaults(condense=0.8, slant=15.0, mirror=True))
    assert spec.condense == 0.8
    assert spec.slant == 15.0
    assert spec.mirror


def test_the_setup_defaults_match_the_machine() -> None:
    setup = setup_from_options(defaults())
    assert setup.safe == 5.0
    assert setup.clearance == 0.5
    assert setup.hop_limit == 25.0
    assert setup.ramp == 0.0
    assert setup.pass_order is PassOrder.BY_PASS
    assert setup.optimises
    assert setup.origin == Point(0.0, 0.0)


def test_the_optimiser_flag_turns_the_rounds_off() -> None:
    assert not setup_from_options(defaults(no_optimise=True)).optimises


def test_the_pass_order_comes_through() -> None:
    setup = setup_from_options(defaults(pass_order="by-stroke"))
    assert setup.pass_order is PassOrder.BY_STROKE


def test_the_heights_take_units() -> None:
    setup = setup_from_options(defaults(safe="0.5in", clearance="20thou", hop="2in", ramp="1mm"))
    assert setup.safe == pytest.approx(12.7)
    assert setup.clearance == pytest.approx(0.508)
    assert setup.hop_limit == pytest.approx(50.8)
    assert setup.ramp == pytest.approx(1.0)


def test_a_plate_with_no_arc_option_has_no_arc() -> None:
    assert plate_from_options(defaults()).arc() is None


def test_the_arc_options_come_through() -> None:
    spec = plate_from_options(
        defaults(size="60x60mm", arc_radius="0.75in", arc_start=45.0, arc_clockwise=True)
    )
    assert spec.arc_radius == pytest.approx(19.05)
    assert spec.arc_start == 45.0
    assert spec.arc_clockwise
    assert spec.arc() is not None


def test_lettering_can_be_asked_to_face_inward() -> None:
    spec = plate_from_options(defaults(size="60x60mm", arc_radius="20mm", arc_inward=True))
    arc = spec.arc()
    assert arc is not None
    assert not arc.outward


def test_wrapping_is_off_unless_it_is_asked_for() -> None:
    assert not plate_from_options(defaults()).wrap
    assert plate_from_options(defaults(wrap=True)).wrap
