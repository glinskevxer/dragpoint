"""Commands about the faces.

The one that gets used is ``font measure``. Somebody has a legend and a
plate and wants to know whether one goes on the other, and the answer is a
number rather than a picture.
"""

from __future__ import annotations

from pathlib import Path

import click

from dragpoint.cli.common import echo_json, handled, write_out
from dragpoint.font.library import load_face, shipped_names
from dragpoint.font.write import write_face
from dragpoint.text.fit import FitPolicy, fit_lines, measure_lines
from dragpoint.text.style import TextStyle
from dragpoint.units import parse_length

__all__ = ["font"]


@click.group()
def font() -> None:
    """Look at the faces."""


@font.command("list")
def list_faces() -> None:
    """List the faces that ship with dragpoint."""
    for name in shipped_names():
        face = load_face(name)
        click.echo(
            f"{name:<16} {len(face):>4} glyphs  "
            f"{face.metrics.units_per_em} upem  cap {face.metrics.cap_height}"
        )


@font.command("show")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Print the metrics as JSON.")
def show(name: str, as_json: bool) -> None:
    """Show one face and what it covers."""
    with handled():
        face = load_face(name)
    metrics = face.metrics
    if as_json:
        echo_json(
            {
                "name": face.name,
                "glyphs": len(face),
                "units_per_em": metrics.units_per_em,
                "cap_height": metrics.cap_height,
                "x_height": metrics.x_height,
                "ascender": metrics.ascender,
                "descender": metrics.descender,
                "line_gap": metrics.line_gap,
                "fallback": face.fallback,
                "kern_pairs": len(face.kerning),
                "names": list(face.names()),
            }
        )
        return
    click.echo(f"{face.name}: {len(face)} glyphs, {len(face.kerning)} kern pairs")
    click.echo(
        f"  upem {metrics.units_per_em}  cap {metrics.cap_height}  "
        f"x {metrics.x_height}  asc {metrics.ascender}  desc {metrics.descender}"
    )
    click.echo(f"  fallback {face.fallback or 'none'}")
    click.echo("  " + " ".join(face.names()))


@font.command("measure")
@click.argument("text", nargs=-1, required=True)
@click.option("--face", "face_name", default="panelgothic", show_default=True)
@click.option("--cap-height", default="3mm", show_default=True, help="Lettering height.")
@click.option("--tracking", default="0mm", show_default=True, help="Extra space per glyph.")
@click.option("--condense", default=1.0, show_default=True, help="Horizontal squeeze.")
@click.option("--width", "limit", default=None, help="Fit the legend into this width.")
@click.option(
    "--fit",
    type=click.Choice([policy.value for policy in FitPolicy]),
    default=FitPolicy.NONE.value,
    show_default=True,
)
def measure(
    text: tuple[str, ...],
    face_name: str,
    cap_height: str,
    tracking: str,
    condense: float,
    limit: str | None,
    fit: str,
) -> None:
    """Measure how wide a legend comes out.

    Each argument is a line. With a width and a fit policy it also says what
    the fitter would do to make it fit.
    """
    with handled():
        face = load_face(face_name)
        style = TextStyle(
            cap_height=parse_length(cap_height),
            tracking=parse_length(tracking),
            condense=condense,
        )
        width = measure_lines(list(text), face, style)
        click.echo(f"{width:.3f}mm wide at {style}")
        missing = sorted({character for line in text for character in face.missing(line)})
        if missing:
            listed = " ".join(repr(item) for item in missing)
            click.echo(f"{face.name} cannot draw {listed}")
        if limit is None:
            return
        result = fit_lines(list(text), face, style, parse_length(limit), FitPolicy(fit))
        click.echo(str(result))


@font.command("dump")
@click.argument("name")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
def dump(name: str, out: Path | None) -> None:
    """Write a face back out in canonical .strk form."""
    with handled():
        face = load_face(name)
    write_out(write_face(face), out)
