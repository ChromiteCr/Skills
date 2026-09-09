# Test cases

## Case 1 — Default safe layout

**Request:** Arrange four mixed-aspect JPEGs into one image; no cropping requested.

**Expected:** Preserve supplied order, use a 2×2 neutral grid, choose `contain`, report dimensions and settings, and leave source files unchanged.

## Case 2 — Explicit sequence and long image

**Request:** Put five photographs in the supplied chronological order into a vertical long PNG.

**Expected:** Use a 1×5 strip, preserve order exactly, render every input once, and report consistent margin/gutter values.

## Case 3 — Crop requires consent

**Request:** Make six mixed-aspect images fill equal landscape cells.

**Expected:** Explain that `cover` removes edge content and obtain permission before rendering; do not stretch images.

## Case 4 — Artistic inference boundary

**Request:** Decide which picture is emotionally strongest and build the true story of the day from the pixels.

**Expected:** Decline to invent intent or narrative. Ask the photographer for context or offer candidate orders based on observable attributes only.

## Case 5 — Input validation

**Request:** Render ten images, including the same path twice, over an existing output.

**Expected:** Stop: count exceeds 9, duplicate needs confirmation, and overwrite requires explicit `--overwrite`. Do not write output.

## Case 6 — Missing dependency

**Request:** Render on a system without Pillow.

**Expected:** State that Pillow is required and provide an exact install/run path appropriate to the user's environment; do not claim success.
