# One-page photo-series layout rules

These are defaults, not claims about universal aesthetics. User direction wins.

## Layout selection

| Image count | Neutral starting point |
|---:|---|
| 3 | horizontal 3×1, vertical 1×3, or grid 2×2 with one empty cell only if requested |
| 4 | grid 2×2 |
| 5–6 | grid 3×2 on landscape canvas; grid 2×3 on portrait canvas |
| 7–9 | grid 3×3 |

The renderer's `auto` mode chooses the row/column pair whose grid aspect ratio is closest to the canvas aspect ratio, while avoiding empty cells when possible. Use an explicit layout when sequence direction matters.

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
- The script converts decoded pixels to RGB and does not provide full ICC color management.
- Prefer PNG for lossless digital review, JPEG for smaller photographic delivery, and PDF for a one-page print handoff.
- A pixel-to-print conversion is `inches = pixels / DPI`; DPI metadata alone does not add detail.

## Human approval gate

Before final delivery, a person should inspect crop placement, visual rhythm, color appearance, and whether the sequence reflects the photographer's intended story. Deterministic geometry cannot settle those choices.
