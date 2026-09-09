# Layout defaults

These are presentation defaults, not claims about photographic quality. Override them when the user provides a house style.

| Setting | Default | Rationale |
|---|---:|---|
| Band position | below image | Keeps metadata outside the photograph |
| Band height | 16% of oriented image height | Fits one heading/value row on common landscape and portrait exports |
| Horizontal padding | 4% of image width | Scales with output size |
| Band color | `#F3F0E8` | Neutral warm off-white |
| Text color | `#171717` | High contrast against the default band |
| Fields | aperture, shutter, exposure compensation, ISO, capture time, camera | Matches the skill's factual scope |
| Missing values | blank | Prevents fabricated metadata |
| Output format | PNG when unspecified | Avoids an additional lossy JPEG encode |

## Layout rules

- Preserve the EXIF-oriented photograph at its original pixel dimensions.
- Add the band; do not cover or crop the photograph.
- Divide available width evenly among selected fields.
- Render labels smaller than values.
- Keep field order stable and user-configurable.
- Reject a layout when a value cannot fit its cell instead of clipping or silently dropping it.
- Do not render GPS coordinates, serial numbers, owner names, or free-form EXIF comments.

## Color and type

The renderer accepts CSS-style colors supported by Pillow. A supplied TrueType/OpenType font is preferred for predictable typography and non-Latin text. Without one, Pillow's bundled/default font is only a portability fallback and should be reported as such.
