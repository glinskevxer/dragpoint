"""Text styles: the limits, and the order the distortions compose in."""

from __future__ import annotations

import math
from typing import Any

import pytest

from dragpoint.errors import OutOfRange
from dragpoint.font.library import shipped_face
from dragpoint.geometry.point import Point
from dragpoint.text.style import TextStyle


def test_a_plain_style_scales_by_cap_height() -> None:
    face = shipped_face("panelgothic")
    style = TextStyle(cap_height=3.5)
    assert style.scale(face) == pytest.approx(0.005)


def test_the_line_pitch_comes_from_the_face_unless_overruled() -> None:
    face = shipped_face("panelgothic")
    style = TextStyle(cap_height=3.5)
    assert style.resolved_line_pitch(face) == pytest.approx(1050 * 0.005)
    assert TextStyle(cap_height=3.5, line_pitch=4.0).resolved_line_pitch(face) == 4.0


@pytest.mark.parametrize(
    ("kwargs", "what"),
    [
        ({"cap_height": 0.0}, "cap height"),
        ({"cap_height": -1.0}, "cap height"),
        ({"cap_height": 3.0, "condense": 0.05}, "condense"),
        ({"cap_height": 3.0, "condense": 4.0}, "condense"),
        ({"cap_height": 3.0, "slant": 60.0}, "slant"),
        ({"cap_height": 3.0, "slant": -60.0}, "slant"),
        ({"cap_height": 3.0, "word_space": -1.0}, "word space"),
        ({"cap_height": 3.0, "line_pitch": 0.0}, "line pitch"),
        ({"cap_height": 3.0, "tracking": -4.0}, "tracking"),
    ],
)
def test_the_limits_are_enforced(kwargs: dict[str, Any], what: str) -> None:
    with pytest.raises(OutOfRange) as caught:
        TextStyle(**kwargs)
    assert what in str(caught.value)


def test_tracking_may_be_negative_down_to_a_cap_height() -> None:
    assert TextStyle(cap_height=3.0, tracking=-2.9).tracking == -2.9


def test_the_extremes_of_condense_and_slant_are_allowed() -> None:
    assert TextStyle(cap_height=3.0, condense=0.2).condense == 0.2
    assert TextStyle(cap_height=3.0, condense=3.0).condense == 3.0
    assert TextStyle(cap_height=3.0, slant=45.0).slant == 45.0


def test_a_plain_style_has_no_glyph_transform_to_speak_of() -> None:
    transform = TextStyle(cap_height=3.0).glyph_transform()
    assert transform.apply(Point(2.0, 5.0)) == Point(2.0, 5.0)


def test_condense_squeezes_x_and_leaves_y() -> None:
    transform = TextStyle(cap_height=3.0, condense=0.5).glyph_transform()
    assert transform.apply(Point(2.0, 5.0)) == Point(1.0, 5.0)


def test_slant_leans_the_stem_by_the_angle_asked_for() -> None:
    transform = TextStyle(cap_height=3.0, slant=15.0).glyph_transform()
    moved = transform.apply(Point(0.0, 10.0))
    assert moved.x == pytest.approx(10.0 * math.tan(math.radians(15.0)))
    assert moved.y == 10.0


def test_condense_happens_before_slant_so_the_lean_angle_survives() -> None:
    style = TextStyle(cap_height=3.0, condense=0.5, slant=20.0)
    moved = style.glyph_transform().apply(Point(0.0, 10.0))
    assert moved.x == pytest.approx(10.0 * math.tan(math.radians(20.0)))


def test_mirror_flips_last() -> None:
    style = TextStyle(cap_height=3.0, condense=0.5, mirror=True)
    assert style.glyph_transform().apply(Point(2.0, 5.0)) == Point(-1.0, 5.0)
    assert style.glyph_transform().is_mirrored


def test_the_copy_helpers_change_one_thing_each() -> None:
    style = TextStyle(cap_height=3.0, tracking=0.2, slant=10.0)
    assert style.condensed_to(0.8).condense == 0.8
    assert style.condensed_to(0.8).slant == 10.0
    assert style.at_cap_height(5.0).cap_height == 5.0
    assert style.at_cap_height(5.0).tracking == 0.2
    assert style.with_tracking(0.5).tracking == 0.5
    assert style.cap_height == 3.0


def test_a_copy_is_validated_too() -> None:
    with pytest.raises(OutOfRange):
        TextStyle(cap_height=3.0).condensed_to(0.01)


def test_str_names_only_what_is_not_the_default() -> None:
    assert str(TextStyle(cap_height=3.0)) == "3mm cap"
    busy = TextStyle(cap_height=2.5, condense=0.8, slant=15.0, tracking=0.1, mirror=True)
    assert str(busy) == "2.5mm cap, condensed 0.8, slant 15, tracking 0.1mm, mirrored"
    assert "unkerned" in str(TextStyle(cap_height=3.0, kerning=False))
