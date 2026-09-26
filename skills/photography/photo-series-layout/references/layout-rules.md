# One-page photo-series layout rules

These are defaults, not claims about universal aesthetics. User direction wins.

## Layout selection

Grids are written **columns × rows** here and in the renderer's report ("4 columns x 2 rows").

The renderer's `auto` mode (the default):

1. For every column count c = 1…N, it takes r = ⌈N ÷ c⌉ rows, so no row is empty.
2. It keeps the grids with the fewest empty cells. A single row or column always has none, so `auto` never leaves an empty cell.
3. Among those, it picks the grid whose page shape at the nominal cell size (`--cell-width` × `--cell-height`, margin and gutter included) is closest to the target shape: the canvas (`--canvas-width` : `--canvas-height`) when one is given, otherwise one cell's shape (4:3 with the default 1200×900 cells). Closeness is |ln(grid ratio ÷ target ratio)|; ties go to fewer rows.

What `auto` picks with the default cells, margin, and gutter:

| Photos | No canvas | Portrait canvas 1080×1350 | Wide canvas 3000×1000 |
|---:|---|---|---|
| 3 | 3 × 1 | 1 × 3 | 3 × 1 |
| 4 | 2 × 2 | 2 × 2 | 4 × 1 |
| 5 | 5 × 1 | 1 × 5 | 5 × 1 |
| 6 | 3 × 2 | 2 × 3 | 3 × 2 |
| 7 | 7 × 1 | 1 × 7 | 7 × 1 |
| 8 | 4 × 2 | 2 × 4 | 4 × 2 |
| 9 | 3 × 3 | 3 × 3 | 3 × 3 |

For 5 and 7 photos the only grids without an empty cell are single strips. The renderer then prints the `--columns` value of the most compact alternative (for 5 photos, `--columns 3`: 3 × 2 with one empty cell at the end); use it only after the user approves the empty cell.

The other layouts: `horizontal` is N × 1 and `vertical` is 1 × N. `grid` is a roughly square contact sheet with ⌈√N⌉ columns, so 3, 5, 7, and 8 photos leave empty cells at the end. `--columns C` sets the column count directly. Use an explicit layout when sequence direction matters.

## Spacing

- Start with outer margin at 4% of the shorter canvas side.
- Start with gutter at 1.5% of the shorter canvas side.
- Keep one outer-margin value and one gutter value throughout.
- For borderless exports, set margin to zero deliberately; do not let it happen by accident.

The script uses pixel values because output is deterministic. Convert percentages to pixels before rendering when matching a fixed canvas.

## Cell and fit policy

- Use equal-sized cells for a neutral presentation.
- `contain` preserves the whole image and may leave bars matching the canvas background.
- `cover` fills the cell but crops evenly from opposite edges; use only with permission.
- Never change an image's aspect ratio to fill a cell.
- Do not upscale low-resolution images for print without warning the user.

## Sequence and hierarchy

- Preserve supplied order by default.
- Horizontal grids are read left-to-right, then top-to-bottom.
- Vertical strips are read top-to-bottom.
- Do not infer a lead image. A larger lead image requires explicit user designation and a renderer that supports asymmetric cells.
- Empty cells can look like missing content; avoid them unless they are an intentional pause approved by the user.

## Color and output

- Default background: white (`#ffffff`); black is a common alternative, not an automatic choice.
- The script writes one colour space. When every photo has the same RGB profile (for example all Display P3 from one iPhone), the page keeps that profile and embeds it. When profiles differ, or one is CMYK or grey, every photo is converted to sRGB (relative colorimetric) and sRGB is embedded; untagged photos count as sRGB. The background colour is given in sRGB and converted along with the page, so white stays white.
- PDF output is always sRGB: Pillow's PDF writer stores pixels as DeviceRGB without a profile, which viewers read as sRGB.
- This is colour conversion, not proofing. Print colour still depends on the printer's profile and a proof.
- Prefer PNG for lossless digital review, JPEG for smaller photographic delivery, and PDF for a one-page print handoff.
- A pixel-to-print conversion is `inches = pixels / DPI`; DPI metadata alone does not add detail.

## Human approval gate

Before final delivery, a person should inspect crop placement, visual rhythm, color appearance, and whether the sequence reflects the photographer's intended story. Deterministic geometry cannot settle those choices.
