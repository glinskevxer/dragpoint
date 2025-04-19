"""Fitting a legend to the width it has to live in."""

from __future__ import annotations

import pytest

from dragpoint.font.face import StrokeFace
from dragpoint.font.library import shipped_face
from dragpoint.text.fit import (
    PREFERRED_CAP_HEIGHTS,
    FitPolicy,
    fit_lines,
    measure_lines,
)
from dragpoint.text.style import TextStyle


@pytest.fixture
def face() -> StrokeFace:
    return shipped_face("panelgothic")


LONG = ["EMERGENCY STOP PUSHBUTTON"]


def test_measure_is_the_widest_line(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0)
    assert measure_lines(["I", "MMMM"], face, style) == pytest.approx(
        measure_lines(["MMMM"], face, style)
    )


def test_a_legend_that_already_fits_is_left_alone(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0)
    result = fit_lines(["RUN"], face, style, 50.0, FitPolicy.BOTH)
    assert result.fits
    assert result.style == style
    assert result.stopped_at is None
    assert result.overrun == 0.0


def test_the_none_policy_changes_nothing_even_when_it_does_not_fit(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0)
    result = fit_lines(LONG, face, style, 20.0, FitPolicy.NONE)
    assert not result.fits
    assert result.style == style
    assert result.overrun > 0.0


def test_condensing_lands_on_or_inside_the_limit(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0)
    result = fit_lines(LONG, face, style, 40.0, FitPolicy.CONDENSE)
    assert result.fits
    assert result.style.condense < 1.0
    assert result.width <= 40.0


def test_condensing_rounds_down_to_a_whole_percent(face: StrokeFace) -> None:
    result = fit_lines(LONG, face, TextStyle(cap_height=3.0), 40.0, FitPolicy.CONDENSE)
    hundredths = result.style.condense * 100.0
    assert hundredths == pytest.approx(round(hundredths), abs=1e-9)


def test_condensing_leaves_the_cap_height_alone(face: StrokeFace) -> None:
    result = fit_lines(LONG, face, TextStyle(cap_height=3.0), 40.0, FitPolicy.CONDENSE)
    assert result.style.cap_height == 3.0


def test_condensing_stops_at_the_floor_and_says_so(face: StrokeFace) -> None:
    result = fit_lines(LONG, face, TextStyle(cap_height=3.0), 10.0, FitPolicy.CONDENSE)
    assert not result.fits
    assert result.style.condense == pytest.approx(0.6)
    assert result.stopped_at == "condense"


def test_a_tighter_floor_can_be_asked_for(face: StrokeFace) -> None:
    result = fit_lines(
        LONG, face, TextStyle(cap_height=3.0), 20.0, FitPolicy.CONDENSE, min_condense=0.3
    )
    assert result.style.condense < 0.6


def test_the_floor_never_goes_below_what_a_style_will_accept(face: StrokeFace) -> None:
    result = fit_lines(
        LONG, face, TextStyle(cap_height=3.0), 1.0, FitPolicy.CONDENSE, min_condense=0.01
    )
    assert result.style.condense >= 0.2


def test_shrinking_picks_a_height_off_the_shop_list(face: StrokeFace) -> None:
    result = fit_lines(LONG, face, TextStyle(cap_height=6.0), 40.0, FitPolicy.SHRINK)
    assert result.style.cap_height in PREFERRED_CAP_HEIGHTS
    assert result.style.condense == 1.0


def test_shrinking_picks_the_largest_height_that_fits(face: StrokeFace) -> None:
    style = TextStyle(cap_height=8.0)
    result = fit_lines(LONG, face, style, 40.0, FitPolicy.SHRINK)
    assert result.fits
    bigger = [h for h in PREFERRED_CAP_HEIGHTS if h > result.style.cap_height and h <= 8.0]
    for height in bigger:
        assert measure_lines(LONG, face, style.at_cap_height(height)) > 40.0


def test_shrinking_never_goes_above_the_height_it_was_given(face: StrokeFace) -> None:
    result = fit_lines(["I"], face, TextStyle(cap_height=2.0), 40.0, FitPolicy.SHRINK)
    assert result.style.cap_height == 2.0


def test_shrinking_stops_at_the_smallest_allowed_height(face: StrokeFace) -> None:
    result = fit_lines(LONG, face, TextStyle(cap_height=6.0), 4.0, FitPolicy.SHRINK)
    assert not result.fits
    assert result.style.cap_height == 1.5
    assert result.stopped_at == "cap height"


def test_a_height_floor_above_every_listed_height_leaves_the_height_alone(
    face: StrokeFace,
) -> None:
    result = fit_lines(
        LONG, face, TextStyle(cap_height=3.0), 4.0, FitPolicy.SHRINK, min_cap_height=20.0
    )
    assert result.style.cap_height == 3.0


def test_both_squeezes_before_it_shrinks(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0)
    result = fit_lines(LONG, face, style, 40.0, FitPolicy.BOTH)
    assert result.fits
    assert result.style.cap_height == 3.0
    assert result.style.condense < 1.0


def test_both_shrinks_when_squeezing_is_not_enough(face: StrokeFace) -> None:
    result = fit_lines(LONG, face, TextStyle(cap_height=6.0), 20.0, FitPolicy.BOTH)
    assert result.fits
    assert result.style.cap_height < 6.0


def test_both_relaxes_the_squeeze_after_it_shrinks(face: StrokeFace) -> None:
    squeezed = fit_lines(LONG, face, TextStyle(cap_height=6.0), 20.0, FitPolicy.CONDENSE)
    both = fit_lines(LONG, face, TextStyle(cap_height=6.0), 20.0, FitPolicy.BOTH)
    assert both.style.condense > squeezed.style.condense


def test_tracking_is_not_squeezed_away(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0, tracking=0.5)
    result = fit_lines(["PUMP RUN"], face, style, 20.0, FitPolicy.CONDENSE)
    assert result.style.tracking == 0.5
    assert result.width <= 20.0


def test_a_legend_of_only_tracking_cannot_be_squeezed(face: StrokeFace) -> None:
    style = TextStyle(cap_height=3.0, tracking=10.0)
    result = fit_lines(["AAAA"], face, style, 5.0, FitPolicy.CONDENSE)
    assert not result.fits
    assert result.style.condense >= 0.2


def test_an_empty_legend_fits_anything(face: StrokeFace) -> None:
    result = fit_lines([""], face, TextStyle(cap_height=3.0), 1.0, FitPolicy.BOTH)
    assert result.fits
    assert result.width == 0.0


def test_no_lines_at_all_fits(face: StrokeFace) -> None:
    assert fit_lines([], face, TextStyle(cap_height=3.0), 1.0, FitPolicy.BOTH).fits


def test_a_limit_of_zero_is_refused(face: StrokeFace) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        fit_lines(LONG, face, TextStyle(cap_height=3.0), 0.0)


def test_str_reads_as_a_verdict(face: StrokeFace) -> None:
    fitting = fit_lines(["RUN"], face, TextStyle(cap_height=3.0), 50.0)
    assert str(fitting).endswith("fits")
    over = fit_lines(LONG, face, TextStyle(cap_height=3.0), 5.0, FitPolicy.NONE)
    assert "over by" in str(over)
