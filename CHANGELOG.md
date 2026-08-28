# Changelog

## 1.0.0

The three setups. A plate is engraved, drilled and milled by one package
now, and everything that reads a plate reads all three.

- Window milling with tabs, and the rules that say whether a window can be cut
- Drilling grouped by diameter, one program per drill
- Numbered runs: one line on a schedule becomes twelve plates
- Composed accented capitals, and figures that can be set on one pitch
- Tip life, a whole shop time across every setup, and a priced quote
- A laser marker post, work offsets, ramped entry and fixture repeats
- `dragpoint pack`, which writes the whole folder that goes to the machine
- The rack and the faces come out of files a shop can edit

## 0.1.0

First working version. Compiles a legend plate schedule into engraving
toolpaths and tells you when it cannot.

- `.strk` stroke font format, with the house face `panelgothic`
- Shaping, line layout and a fitter that condenses before it shrinks
- Cutter and stock tables, with the depth window a two ply sheet allows
- Fifteen rules covering legibility, fitment and what the machine can do
- Travel ordering, depth passes and a toolpath with hops and safe retracts
- ISO G code and pen up pen down posts, SVG preview and release 12 DXF
- Shelf nesting, and a cycle time estimate with the block time in it
- A command line for one plate or a whole schedule
