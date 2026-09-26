# Layout defaults

These are presentation defaults, not claims about photographic quality. Override them when the user provides a house style.

| Setting | Default | Rationale |
|---|---:|---|
| Band position | below image | Keeps metadata outside the photograph |
| Band height | 16% of oriented image height | Room for one label row and one value row. The type size is set by the cell width, so on portrait images the text is smaller than the band allows; a lower ratio such as 0.10 gives a tighter band |
| Type size | values start at 19% of the band height, labels at 0.63 of the value size (at least 9 px); both shrink until the longest text fits its cell, with 0.6 of the value size between columns | Measured with Helvetica: the six default fields fit 6000×4000 (92 px values), 4000×6000 (62 px), a 3024×4032 phone portrait with "Apple iPhone 15 Pro Max" (38 px), and 800×1200 (12 px) |
| Readable minimum | 12 px or 0.6% of the output's long edge, whichever is larger | Below it the renderer stops instead of drawing text nobody can read; fewer fields or a narrower font fix it, a taller band does not |
| Horizontal padding | 4% of image width | Scales with output size |
| Band color | `#F3F0E8` | Neutral warm off-white |
| Text color | `#171717` | High contrast against the default band |
| Fields | aperture, shutter, exposure compensation, ISO, capture time, camera | Matches the skill's factual scope |
| Missing values | blank | Prevents fabricated metadata |
| Capture time | DateTimeOriginal, shown as `YYYY-MM-DD HH:MM:SS` | IFD0 DateTime is the last edit or export time, not a capture time |
| Exposure compensation | thirds and halves as fractions (`-2/3 EV`), otherwise one decimal | How cameras and photographers write it |
| Output format | PNG when unspecified; JPEG at quality 95 with 4:4:4 chroma | Avoids an additional lossy JPEG encode; the JPEG path keeps the thin type sharp |
| Colour | the source's RGB ICC profile is embedded ("keep"); CMYK and grey profiles are converted to sRGB; untagged input is tagged sRGB | A Display P3 photo keeps its saturated colours; band and text colours are sRGB values converted into the output profile |

## Layout rules

- Preserve the EXIF-oriented photograph at its original pixel dimensions.
- Add the band; do not cover or crop the photograph.
- Divide available width evenly among selected fields.
- Render labels smaller than values.
- Keep field order stable and user-configurable.
- Shrink the type until every value fits its cell; reject the layout only when that would go below the readable minimum, never clip or silently drop a value.
- Do not render GPS coordinates, serial numbers, owner names, or free-form EXIF comments.

## Color and type

The renderer accepts CSS-style colors supported by Pillow, read as sRGB. A supplied TrueType/OpenType font is preferred for predictable typography; it must have every glyph the text needs (checked when fontTools is installed). Without one, the renderer uses the first installed system font that covers the text (Helvetica or Arial on macOS, DejaVu Sans on Linux, a Chinese font such as Hiragino Sans GB when a value needs one). Pillow's built-in font is only a portability fallback and is reported in the warnings; on Pillow older than 10.1 it cannot be sized, so the renderer stops and asks for `--font`.
