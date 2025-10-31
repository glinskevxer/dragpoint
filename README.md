# dragpoint

Engraving toolpath compiler for control panel legend plates.

A legend plate is the laminated rectangle screwed next to a switch that says
PUMP 2 RUN or ESTOP. They are cut on a rotary engraver with a conical cutter,
and the width of the line the cutter leaves depends on how deep it goes.

That one fact drives everything in here. A legend that reads perfectly as
centrelines on a screen closes up into a smudge at 0.4 mm deep with a 30
degree cutter, and the only way to know is to work out the groove width and
measure the gaps against it. dragpoint does that, and refuses to post a
program for a plate that will come out as scrap.

This is not a font library. There are no outlines, no beziers and no hinting.
A glyph is a list of centreline strokes and the machine follows them.

## What it does

- Reads a job schedule in TOML, or takes one plate off the command line
- Shapes and lays out the legend, condensing it to fit before it shrinks it
- Works out the depth from the stock, and the passes from the depth
- Checks fifteen rules that between them decide whether the plate can be cut
- Orders the cuts to shorten the rapids, then builds the toolpath
- Posts ISO G code or the pen up pen down dialect the older machines take
- Draws the plate as SVG or DXF, with every groove at its real width
- Nests the pieces on a sheet and estimates the cycle time

## Install

```
pip install -e ".[dev]" -c constraints.txt
```

Python 3.11 or later. The only runtime dependency is click.

## Quick start

One plate, checked and posted:

```
dragpoint plate check --size 60x20mm "FEED PUMP 1" RUN
dragpoint plate post --size 60x20mm --out P-101.nc "FEED PUMP 1" RUN
```

A whole schedule:

```
dragpoint job check examples/mcc-panel-7.toml
dragpoint job post examples/mcc-panel-7.toml --out programs/
dragpoint job nest examples/mcc-panel-7.toml
dragpoint job time examples/mcc-panel-7.toml
```

What the shop holds:

```
dragpoint crib cutters
dragpoint crib stock
dragpoint crib rules
```

Every distance anywhere takes a unit. `--cap-height 0.125in`, `--depth
15thou` and `size = ["60mm", "20mm"]` all work, and so does a bare number,
which is read as millimetres.

## Exit codes

`0` nothing worse than a warning. `1` a rule reported an error, so the plate
would be scrap. `2` the command could not be carried out at all.

A warning never fails a command. It is printed, the operator looks at the
plate and decides, and that decision is not the compiler's.

## The idea

Everything is a stack and every import goes downwards:

```
errors > units > geometry > font > text > tool > spec > rules
       > path > post > compiler > draw > cli
```

`dragpoint.tools.check_layers` enforces exactly that, so an import that
breaks it fails the build rather than the review.

The compiler is the only module that knows about every layer. It resolves,
fits, lays out, plans, orders, posts, and only then checks, and it is not
allowed to fix anything it finds. A legend that does not fit comes out not
fitting, with the reason written beside it.

## Documents

- [Architecture](docs/architecture.md) - the stack, generated from the code
- [Commands](docs/commands.md) - every command, generated from the command line
- [Rules](docs/rules.md) - every rule, generated from the register
- [The crib](docs/crib.md) - cutters and stock, with the groove widths worked out

All four are generated and CI fails if any of them has drifted.

## Development

```
python -m pytest -q
python -m ruff check . && python -m ruff format --check .
python -m mypy
python -m dragpoint.tools.release_check --verbose
```

`check.sh` runs everything CI runs, in one go.
