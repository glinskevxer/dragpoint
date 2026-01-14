"""Legends that count, and the four placeholders that make them."""

from __future__ import annotations

import pytest

from dragpoint.errors import SpecError
from dragpoint.text.sequence import expand_sequence, is_sequenced, sequence_lines


def test_a_line_with_no_placeholder_is_not_sequenced() -> None:
    assert not is_sequenced(("PUMP RUNNING", "STOP"))


def test_a_line_with_a_placeholder_is() -> None:
    assert is_sequenced(("VLV-{n}",))


def test_one_sequenced_line_sequences_the_whole_legend() -> None:
    assert is_sequenced(("TERMINAL", "{n}"))


def test_a_doubled_brace_is_not_a_placeholder() -> None:
    assert not is_sequenced(("SET {{A}}",))


def test_the_number_becomes_the_piece() -> None:
    assert expand_sequence("VLV-{n}", piece=7, quantity=12) == "VLV-7"


def test_the_number_takes_a_format() -> None:
    assert expand_sequence("VLV-{n:03}", piece=7, quantity=12) == "VLV-007"


def test_the_total_is_how_many_there_are() -> None:
    assert expand_sequence("{n} OF {of}", piece=3, quantity=12) == "3 OF 12"


def test_the_plate_name_comes_through() -> None:
    assert expand_sequence("{plate} {n}", piece=2, quantity=4, plate="TAG") == "TAG 2"


def test_two_placeholders_on_one_line_both_get_filled() -> None:
    assert expand_sequence("{n:02}/{of:02}", piece=9, quantity=24) == "09/24"


def test_a_doubled_brace_comes_out_single() -> None:
    assert expand_sequence("SET {{A}} {n}", piece=1, quantity=1) == "SET {A} 1"


def test_a_line_with_nothing_in_it_survives() -> None:
    assert expand_sequence("", piece=1, quantity=1) == ""


def test_a_placeholder_nobody_recognises_is_a_message() -> None:
    with pytest.raises(SpecError, match="not a placeholder"):
        expand_sequence("{serial}", piece=1, quantity=1)


def test_the_message_says_what_the_placeholders_are() -> None:
    with pytest.raises(SpecError, match=r"\{n\}.*\{of\}.*\{plate\}"):
        expand_sequence("{serial}", piece=1, quantity=1)


def test_a_format_on_the_plate_name_is_refused() -> None:
    with pytest.raises(SpecError, match="takes no format"):
        expand_sequence("{plate:03}", piece=1, quantity=1, plate="TAG")


def test_a_format_that_means_nothing_is_a_message() -> None:
    with pytest.raises(SpecError, match="not a format"):
        expand_sequence("{n:qq}", piece=1, quantity=1)


def test_a_run_of_no_pieces_is_refused() -> None:
    with pytest.raises(SpecError, match="nothing to number"):
        expand_sequence("{n}", piece=1, quantity=0)


def test_space_round_the_name_is_allowed() -> None:
    assert expand_sequence("{ n }", piece=5, quantity=9) == "5"


def test_every_line_of_a_legend_is_expanded() -> None:
    lines = sequence_lines(("VLV-{n:03}", "{n} OF {of}"), piece=4, quantity=24)
    assert lines == ("VLV-004", "4 OF 24")


def test_a_legend_that_does_not_count_comes_back_unchanged() -> None:
    lines = ("PUMP RUNNING", "STOP")
    assert sequence_lines(lines, piece=2, quantity=6) == lines
