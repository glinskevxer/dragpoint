# dragpoint

Engraving toolpath compiler for control panel legend plates.

A legend plate is the laminated rectangle screwed next to a switch that says
PUMP 2 RUN or ESTOP. They are cut on a rotary engraver with a conical cutter,
and the width of the line the cutter leaves depends on how deep it goes. That
one fact drives everything in here.

Not a font library. There are no outlines, no beziers and no hinting. A glyph
is a list of centreline strokes and the machine follows them.

## Status

Early. Right now it parses lengths and not much else.
