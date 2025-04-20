"""The cutter cone, which is the fact everything else in here leans on."""

from __future__ import annotations

import math

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.tool.cutter import CATALOGUE, Cutter, catalogue_cutter


def vee() -> Cutter:
    return Cutter(name="test30", tip_width=0.3, included_angle=30.0, max_depth=1.5)


def flat() -> Cutter:
    return Cutter(name="testflat", tip_width=0.5, included_angle=0.0, max_depth=2.0)


def test_the_tip_is_the_width_at_zero_depth() -> None:
    assert vee().width_at_depth(0.0) == pytest.approx(0.3)
    assert flat().width_at_depth(0.0) == pytest.approx(0.5)


def test_the_groove_widens_with_depth() -> None:
    cutter = vee()
    expected = 0.3 + 2 * 0.4 * math.tan(math.radians(15.0))
    assert cutter.width_at_depth(0.4) == pytest.approx(expected)


def test_widening_is_linear_in_depth() -> None:
    cutter = vee()
    first = cutter.width_at_depth(0.4) - cutter.width_at_depth(0.2)
    second = cutter.width_at_depth(0.8) - cutter.width_at_depth(0.6)
    assert first == pytest.approx(second)


def test_a_parallel_cutter_never_widens() -> None:
    cutter = flat()
    assert cutter.is_parallel
    assert cutter.taper == 0.0
    assert cutter.width_at_depth(1.9) == pytest.approx(0.5)


def test_a_vee_cutter_is_not_parallel() -> None:
    assert not vee().is_parallel
    assert vee().taper > 0.0


def test_depth_for_width_inverts_width_at_depth() -> None:
    cutter = vee()
    for depth in (0.0, 0.15, 0.4, 1.0, 1.5):
        assert cutter.depth_for_width(cutter.width_at_depth(depth)) == pytest.approx(depth)


def test_a_width_under_the_tip_is_impossible() -> None:
    with pytest.raises(OutOfRange, match="width"):
        vee().depth_for_width(0.1)


def test_a_width_a_hair_under_the_tip_is_taken_as_the_tip() -> None:
    assert vee().depth_for_width(0.3 - 1e-5) == pytest.approx(0.0, abs=1e-6)


def test_a_parallel_cutter_only_does_its_own_width() -> None:
    assert flat().depth_for_width(0.5) == 0.0
    with pytest.raises(OutOfRange):
        flat().depth_for_width(0.9)


def test_a_width_deeper_than_the_cutter_goes_is_refused() -> None:
    with pytest.raises(OutOfRange, match="depth"):
        vee().depth_for_width(5.0)


def test_the_widest_groove_is_the_one_at_full_depth() -> None:
    cutter = vee()
    assert cutter.widest_groove() == pytest.approx(cutter.width_at_depth(1.5))


@pytest.mark.parametrize("depth", [-0.001, 1.6, 100.0])
def test_a_depth_outside_the_cutter_is_refused(depth: float) -> None:
    with pytest.raises(OutOfRange, match="depth"):
        vee().width_at_depth(depth)


@pytest.mark.parametrize(
    ("kwargs", "what"),
    [
        ({"tip_width": 0.0}, "tip width"),
        ({"tip_width": -0.1}, "tip width"),
        ({"included_angle": -1.0}, "included angle"),
        ({"included_angle": 180.0}, "included angle"),
        ({"shank": 0.0}, "shank"),
        ({"flutes": 0}, "flutes"),
        ({"max_depth": 0.0}, "max depth"),
    ],
)
def test_an_impossible_cutter_is_refused(kwargs: dict[str, float], what: str) -> None:
    values: dict[str, object] = {
        "name": "bad",
        "tip_width": 0.3,
        "included_angle": 30.0,
        "shank": 3.175,
        "flutes": 1,
        "max_depth": 1.5,
    }
    values.update(kwargs)
    with pytest.raises(OutOfRange) as caught:
        Cutter(**values)  # type: ignore[arg-type]
    assert what in str(caught.value)


def test_a_zero_angle_cutter_is_allowed_because_that_is_a_parallel() -> None:
    assert Cutter(name="ok", tip_width=0.3, included_angle=0.0).is_parallel


def test_the_catalogue_is_keyed_by_the_name_on_the_tube() -> None:
    for name, cutter in CATALOGUE.items():
        assert cutter.name == name


def test_the_catalogue_holds_both_vees_and_parallels() -> None:
    assert any(cutter.is_parallel for cutter in CATALOGUE.values())
    assert any(not cutter.is_parallel for cutter in CATALOGUE.values())


def test_catalogue_lookup() -> None:
    assert catalogue_cutter("V30-015").tip_width == pytest.approx(0.381)


def test_an_unknown_cutter_lists_what_the_crib_holds() -> None:
    with pytest.raises(KeyError) as caught:
        catalogue_cutter("V99-999")
    assert "V30-015" in str(caught.value)


def test_str_reads_like_a_setup_sheet() -> None:
    assert str(vee()) == "test30 (30 deg, 0.3mm tip)"
    assert str(flat()) == "testflat (parallel, 0.5mm)"
