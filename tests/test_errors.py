"""The exceptions, and the sentences they turn into."""

from __future__ import annotations

import pytest

from dragpoint.errors import (
    BadLength,
    BadUnit,
    DragpointError,
    FaceNotFound,
    FontSyntax,
    MissingGlyph,
    OutOfRange,
    SpecError,
)

EVERY = (BadLength, BadUnit, FaceNotFound, FontSyntax, MissingGlyph, OutOfRange, SpecError)


@pytest.mark.parametrize("kind", EVERY)
def test_everything_descends_from_the_one_base(kind: type[DragpointError]) -> None:
    assert issubclass(kind, DragpointError)
    assert issubclass(kind, Exception)


def test_a_bad_unit_lists_the_ones_that_work() -> None:
    error = BadUnit("furlong", ("mm", "in", "thou"))
    assert error.suffix == "furlong"
    assert str(error) == "unknown unit 'furlong', expected one of mm, in, thou"


def test_a_bad_length_carries_the_text_and_the_reason() -> None:
    error = BadLength("wide", "expected a number")
    assert error.text == "wide"
    assert str(error) == "cannot read 'wide' as a length: expected a number"


def test_a_range_error_says_what_was_out_of_it() -> None:
    error = OutOfRange("depth", 1.5, 0.0, 1.0)
    assert error.what == "depth"
    assert error.value == 1.5
    assert str(error) == "depth is 1.5, outside 0 to 1"


def test_a_missing_glyph_names_the_face() -> None:
    error = MissingGlyph("Z", "panelgothic")
    assert error.name == "Z"
    assert str(error) == "face panelgothic has no glyph named 'Z'"


def test_a_font_syntax_error_carries_the_line() -> None:
    error = FontSyntax("face.strk", 12, "unknown keyword")
    assert error.line == 12
    assert str(error) == "face.strk:12: unknown keyword"


def test_a_font_syntax_error_on_line_zero_is_about_the_whole_file() -> None:
    assert str(FontSyntax("face.strk", 0, "no header")) == "face.strk: no header"


def test_a_face_not_found_lists_the_shipped_ones() -> None:
    error = FaceNotFound("nosuch", ("panelgothic",))
    assert "panelgothic" in str(error)
    assert error.name == "nosuch"


def test_a_spec_error_names_the_table_it_happened_in() -> None:
    error = SpecError("job.toml", 'plate[2] "P-9"', "width is missing")
    assert str(error) == 'job.toml [plate[2] "P-9"]: width is missing'


def test_a_spec_error_about_the_whole_file_names_only_the_file() -> None:
    assert str(SpecError("job.toml", "", "not TOML")) == "job.toml: not TOML"


@pytest.mark.parametrize(
    "error",
    [
        BadUnit("x", ("mm",)),
        BadLength("x", "why"),
        OutOfRange("x", 1.0, 0.0, 0.5),
        MissingGlyph("x", "face"),
        FontSyntax("f", 1, "why"),
        FaceNotFound("x", ("a",)),
        SpecError("f", "w", "why"),
    ],
)
def test_every_error_can_be_caught_as_the_base(error: DragpointError) -> None:
    with pytest.raises(DragpointError):
        raise error


@pytest.mark.parametrize(
    "error",
    [
        BadUnit("x", ("mm",)),
        BadLength("x", "why"),
        OutOfRange("x", 1.0, 0.0, 0.5),
        MissingGlyph("x", "face"),
        FontSyntax("f", 1, "why"),
        FaceNotFound("x", ("a",)),
        SpecError("f", "w", "why"),
    ],
)
def test_no_error_prints_as_a_bare_tuple(error: DragpointError) -> None:
    text = str(error)
    assert not text.startswith("(")
    assert len(text) > 5
