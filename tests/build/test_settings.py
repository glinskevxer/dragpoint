"""Machine settings."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from dragpoint.build.settings import MachineSetup
from dragpoint.errors import OutOfRange
from dragpoint.geometry.point import Point
from dragpoint.path.cut import PassOrder


def test_the_defaults_are_the_ones_the_machine_is_set_to() -> None:
    setup = MachineSetup()
    assert setup.safe == 5.0
    assert setup.clearance == 0.5
    assert setup.hop_limit == 25.0
    assert setup.pass_order is PassOrder.BY_PASS
    assert setup.allow_reverse
    assert not setup.spring_pass
    assert setup.origin == Point(0.0, 0.0)


@pytest.mark.parametrize(
    ("kwargs", "what"),
    [
        ({"clearance": 0.0}, "clearance"),
        ({"clearance": -1.0}, "clearance"),
        ({"safe": 0.5}, "safe height"),
        ({"safe": 0.1}, "safe height"),
        ({"hop_limit": -1.0}, "hop limit"),
        ({"optimise_rounds": -1}, "optimise rounds"),
        ({"rapid_rate": 0.0}, "rapid rate"),
    ],
)
def test_an_impossible_setup_is_refused(kwargs: dict[str, Any], what: str) -> None:
    with pytest.raises(OutOfRange) as caught:
        MachineSetup(**kwargs)
    assert what in str(caught.value)


def test_a_safe_height_equal_to_the_clearance_is_refused() -> None:
    with pytest.raises(OutOfRange, match="safe height"):
        MachineSetup(safe=0.5, clearance=0.5)


def test_the_optimiser_can_be_turned_off_by_rounds() -> None:
    assert MachineSetup().optimises
    assert not MachineSetup(optimise_rounds=0).optimises


def test_without_optimising_keeps_everything_else() -> None:
    setup = MachineSetup(safe=8.0, spring_pass=True, optimise_rounds=4)
    plain = setup.without_optimising()
    assert not plain.optimises
    assert plain.safe == 8.0
    assert plain.spring_pass
    assert setup.optimise_rounds == 4


def test_at_origin_moves_the_start_and_nothing_else() -> None:
    setup = MachineSetup(safe=8.0)
    moved = setup.at_origin(Point(10.0, 20.0))
    assert moved.origin == Point(10.0, 20.0)
    assert moved.safe == 8.0
    assert setup.origin == Point(0.0, 0.0)


def test_a_copy_goes_back_through_the_checks() -> None:
    with pytest.raises(OutOfRange, match="clearance"):
        replace(MachineSetup(), clearance=0.0)


def test_str_reads_like_a_setup_sheet() -> None:
    assert str(MachineSetup()) == "safe 5mm, clearance 0.5mm, hop over 25mm, by-pass"


def test_str_names_the_settings_that_are_not_the_default() -> None:
    text = str(MachineSetup(allow_reverse=False, spring_pass=True))
    assert "no reversing" in text
    assert "spring pass" in text
