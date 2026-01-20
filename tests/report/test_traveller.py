"""The card that goes round the shop with one plate."""

from __future__ import annotations

from dragpoint.compiler.plate import compile_plate
from dragpoint.geometry.point import Point
from dragpoint.report.traveller import SIGN_OFF, traveller_card, travellers
from dragpoint.spec.feature import Feature
from dragpoint.spec.plate import PlateSpec


def made(**overrides: object) -> object:
    values: dict[str, object] = {
        "name": "P-1",
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("PUMP 2", "RUN"),
    }
    values.update(overrides)
    return compile_plate(PlateSpec(**values))  # type: ignore[arg-type]


def card(**overrides: object) -> str:
    return traveller_card(made(**overrides))  # type: ignore[arg-type]


def test_the_card_names_the_plate() -> None:
    assert "TRAVELLER   P-1" in card()


def test_the_card_says_what_the_blank_is() -> None:
    assert "60 x 20 mm, LAM16-BW" in card()


def test_the_card_says_how_many_there_are() -> None:
    assert "quantity  6" in card(quantity=6)


def test_the_card_says_what_it_will_read() -> None:
    text = card()
    assert "PUMP 2" in text
    assert "RUN" in text


def test_a_plate_with_nothing_on_it_says_so() -> None:
    assert "nothing is engraved" in card(lines=())


def test_a_wrapped_line_shows_what_was_asked_for_as_well() -> None:
    text = card(lines=("PUMP TWO RUNNING NOW",), wrap=True, cap_height=4.0)
    assert "asked for" in text


def test_a_condensed_legend_is_flagged_on_the_card() -> None:
    text = card(lines=("PUMP TWO RUNNING",), cap_height=5.0)
    assert "condensed to" in text


def test_the_card_carries_the_numbers_the_setter_needs() -> None:
    text = card()
    assert "V30-015" in text
    assert "0.25 mm in 1 passes" in text
    assert "12000 rpm" in text


def test_the_card_says_how_wide_the_groove_will_be() -> None:
    assert "mm wide at depth" in card()


def test_the_card_says_how_long_one_takes_and_how_long_the_lot_takes() -> None:
    assert "for the quantity" in card(quantity=20)


def test_a_note_on_the_order_reaches_the_bench() -> None:
    assert "urgent, ring when done" in card(notes="urgent, ring when done")


def test_the_tags_reach_the_bench_as_well() -> None:
    assert "rework" in card(tags=frozenset({"rework"}))


def test_a_plate_with_no_holes_has_no_drilling_block() -> None:
    assert "drilling" not in card()


def test_a_plate_with_holes_lists_them() -> None:
    holes = (Feature.round_hole("fix", Point(5.0, 10.0), 4.5),)
    text = card(features=holes, lines=("RUN",))
    assert "drilling" in text
    assert "4.5 mm" in text


def test_a_clean_plate_says_the_checks_passed() -> None:
    assert "checks    all passed" in card()


def test_a_plate_that_failed_a_check_says_what_it_was() -> None:
    text = card(lines=("PUMP TWO RUNNING NOW AND FOR EVER",), cap_height=6.0)
    assert "checks" in text
    assert "all passed" not in text


def test_a_plate_with_an_error_says_not_to_cut_it() -> None:
    text = card(lines=("µ",))
    assert "DO NOT CUT" in text


def test_every_sign_off_box_is_on_the_card() -> None:
    text = card()
    for label in SIGN_OFF:
        assert label in text


def test_the_boxes_are_empty_for_somebody_to_tick() -> None:
    assert "[    ]" in card()


def test_a_card_ends_with_a_newline_because_it_gets_printed() -> None:
    assert card().endswith("\n")


def test_a_stack_of_cards_is_one_per_plate() -> None:
    plates = (made(name="P-1"), made(name="P-2"))
    text = travellers(plates)  # type: ignore[arg-type]
    assert text.count("TRAVELLER") == 2


def test_the_cards_in_a_stack_are_separated_by_a_page_break() -> None:
    plates = (made(name="P-1"), made(name="P-2"))
    assert "\f" in travellers(plates)  # type: ignore[arg-type]


def test_a_stack_of_no_plates_is_nothing() -> None:
    assert travellers(()) == ""
