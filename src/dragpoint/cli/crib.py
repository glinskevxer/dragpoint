"""What the shop holds: cutters, stock, posts and rules.

All four are lists somebody asks for when a job will not do what they want,
and the answer is nearly always that the thing they typed is not the thing
that is there. So every one of these prints the whole list rather than
answering yes or no.
"""

from __future__ import annotations

from pathlib import Path

import click

from dragpoint.cli.common import echo_json, handled
from dragpoint.post.base import POSTS
from dragpoint.rules.check import REGISTRY
from dragpoint.tool.cutter import CATALOGUE
from dragpoint.tool.material import MATERIALS, Material, load_rack

__all__ = ["crib"]


@click.group()
def crib() -> None:
    """List what the shop holds."""


@crib.command("cutters")
@click.option("--json", "as_json", is_flag=True, help="Print as JSON.")
def cutters(as_json: bool) -> None:
    """List the cutters in the crib."""
    if as_json:
        echo_json(
            {
                name: {
                    "tip_width": cutter.tip_width,
                    "included_angle": cutter.included_angle,
                    "shank": cutter.shank,
                    "flutes": cutter.flutes,
                    "max_depth": cutter.max_depth,
                    "parallel": cutter.is_parallel,
                }
                for name, cutter in CATALOGUE.items()
            }
        )
        return
    for name in sorted(CATALOGUE):
        cutter = CATALOGUE[name]
        click.echo(
            f"{name:<10} tip {cutter.tip_width:>6.3f}mm  "
            f"angle {cutter.included_angle:>5.1f}  "
            f"max depth {cutter.max_depth:>5.2f}mm  "
            f"widest {cutter.widest_groove():>6.3f}mm"
        )


@crib.command("stock")
@click.option("--json", "as_json", is_flag=True, help="Print as JSON.")
@click.option(
    "--rack",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Read the rack from this file instead of the shipped one.",
)
def stock(as_json: bool, rack: Path | None) -> None:
    """List the stock on the rack."""
    sheets: dict[str, Material] = MATERIALS
    if rack is not None:
        with handled():
            sheets = load_rack(rack)
    if as_json:
        echo_json(
            {
                name: {
                    "description": sheet.description,
                    "thickness": sheet.thickness,
                    "cap": sheet.cap,
                    "nominal_depth": sheet.nominal_depth,
                    "window": list(sheet.depth_window()),
                    "feed": sheet.feed,
                    "plunge_feed": sheet.plunge_feed,
                    "spindle": sheet.spindle,
                }
                for name, sheet in sheets.items()
            }
        )
        return
    for name in sorted(sheets):
        sheet = sheets[name]
        low, high = sheet.depth_window()
        click.echo(
            f"{name:<10} {sheet.thickness:>4.1f}mm  "
            f"depth {low:>5.2f} to {high:>5.2f}mm  "
            f"nominal {sheet.nominal_depth:>5.2f}mm  {sheet.description}"
        )


@crib.command("posts")
def posts() -> None:
    """List the post processors."""
    for name in sorted(POSTS):
        click.echo(str(POSTS[name]))


@crib.command("rules")
@click.option("--json", "as_json", is_flag=True, help="Print as JSON.")
def rules(as_json: bool) -> None:
    """List the rules a plate is checked against."""
    if as_json:
        echo_json(
            {
                name: {
                    "description": definition.description,
                    "severity": str(definition.severity),
                }
                for name, definition in REGISTRY.items()
            }
        )
        return
    for definition in REGISTRY.values():
        click.echo(f"{definition.name:<24} {definition.severity:<8} {definition.description}")
