"""The post register and the options every post is handed."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from dragpoint.path.plan import Toolpath
from dragpoint.post.base import (
    POSTS,
    PostDef,
    PostOptions,
    post,
    post_names,
    render,
)


@pytest.fixture
def clean_registry() -> Iterator[dict[str, PostDef]]:
    """An empty register for the test, and the real one back afterwards."""
    saved = dict(POSTS)
    POSTS.clear()
    try:
        yield POSTS
    finally:
        POSTS.clear()
        POSTS.update(saved)


def test_the_defaults_are_the_ones_the_shop_uses() -> None:
    options = PostOptions()
    assert options.program == "DRAGPOINT"
    assert options.decimals == 4
    assert options.spindle == 12000
    assert options.tool == 1
    assert not options.line_numbers
    assert options.comments


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"decimals": -1}, "places"),
        ({"decimals": 9}, "places"),
        ({"spindle": -1}, "speed"),
        ({"tool": -1}, "tool"),
    ],
)
def test_impossible_options_are_refused(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        PostOptions(**kwargs)


def test_a_coordinate_carries_the_places_asked_for() -> None:
    assert PostOptions(decimals=4).coordinate(1.5) == "1.5000"
    assert PostOptions(decimals=2).coordinate(1.5) == "1.50"
    assert PostOptions(decimals=0).coordinate(1.5) == "2"


def test_a_coordinate_that_rounds_away_never_carries_a_minus() -> None:
    assert PostOptions(decimals=3).coordinate(-0.0001) == "0.000"
    assert PostOptions(decimals=3).coordinate(-0.0) == "0.000"
    assert PostOptions(decimals=3).coordinate(-1.5) == "-1.500"


def test_a_post_registers_itself(clean_registry: dict[str, PostDef]) -> None:
    @post("demo", "a demonstration", "txt")
    def demo(path: Toolpath, options: PostOptions) -> str:
        return "hello"

    assert post_names() == ("demo",)
    assert POSTS["demo"].extension == "txt"
    assert demo(Toolpath(), PostOptions()) == "hello"


def test_registering_the_same_name_twice_is_refused(clean_registry: dict[str, PostDef]) -> None:
    @post("demo", "first", "txt")
    def first(path: Toolpath, options: PostOptions) -> str:
        return "one"

    with pytest.raises(ValueError, match="already registered"):

        @post("demo", "second", "txt")
        def second(path: Toolpath, options: PostOptions) -> str:
            return "two"


def test_the_register_keeps_the_order_posts_were_written_in(
    clean_registry: dict[str, PostDef],
) -> None:
    for name in ("third", "first", "second"):

        @post(name, name, "txt")
        def anything(path: Toolpath, options: PostOptions) -> str:
            return ""

    assert post_names() == ("third", "first", "second")


def test_render_goes_through_the_named_post(clean_registry: dict[str, PostDef]) -> None:
    @post("demo", "a demonstration", "txt")
    def demo(path: Toolpath, options: PostOptions) -> str:
        return f"program {options.program}"

    assert render("demo", Toolpath(), PostOptions(program="X")) == "program X"


def test_render_makes_default_options_when_it_is_given_none(
    clean_registry: dict[str, PostDef],
) -> None:
    @post("demo", "a demonstration", "txt")
    def demo(path: Toolpath, options: PostOptions) -> str:
        return options.program

    assert render("demo", Toolpath()) == "DRAGPOINT"


def test_an_unknown_post_lists_the_ones_that_are_there(
    clean_registry: dict[str, PostDef],
) -> None:
    @post("demo", "a demonstration", "txt")
    def demo(path: Toolpath, options: PostOptions) -> str:
        return ""

    with pytest.raises(KeyError) as caught:
        render("nope", Toolpath())
    assert "demo" in str(caught.value)


def test_a_post_definition_reads_as_a_line_of_help() -> None:
    definition = PostDef(
        name="iso",
        description="ISO G code",
        extension="nc",
        render=lambda path, options: "",
    )
    assert str(definition) == "iso (.nc): ISO G code"
