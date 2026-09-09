# Test cases

## Case 1 — complete portrait brief

Input describes a cyclist silhouette against a pale wall, one red wheel reflection, 1080×1350 screen output, supplied title and credit.

Expected: produce an evidence/choice split, preserve silhouette and reflection, render with no more than three colors, and pass `poster_tool.py validate`.

## Case 2 — image unavailable and intent missing

User says only “turn my night photo into an art poster,” while the agent cannot inspect the image.

Expected: request subject silhouette, dominant masses, must-keep detail, dimensions, and copy. Do not invent neon colors, location, mood, or story.

## Case 3 — conflicting palette request

User names five colors as mandatory but also requests a strict three-color poster.

Expected: surface the contradiction and ask which constraint wins, or offer two explicitly separate three-color directions. Do not silently discard colors.

## Case 4 — boundary violation

User asks for a faithful beauty retouch and detailed face reconstruction.

Expected: explain that this skill creates minimal geometric reinterpretations and route to an image-retouching workflow; do not claim the poster workflow can preserve facial fidelity.

## Case 5 — invalid deterministic output

Specification places a shape outside the canvas, uses a fourth color, and sets foreground equal to background.

Expected: renderer or validator exits nonzero and reports bounds, palette, and contrast problems. The agent fixes the specification before claiming completion.
