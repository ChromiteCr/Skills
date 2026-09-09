---
name: photo-exif-frame
description: Add a configurable information band to an existing photograph using embedded EXIF facts such as aperture, shutter speed, exposure compensation, ISO, capture time, and camera. Use when a user asks to frame, label, or export a photo with shooting metadata. Do not use for interpreting photographic intent, inventing missing metadata, or editing the photograph itself.
category: photography
version: 0.1.0
status: draft
priority: P2
compatible_agents:
  - claude-code
  - openclaw
  - cursor
  - codebuddy
  - generic-llm-agent
license: MIT
---

# Photo EXIF Frame

Create a reproducible framed-photo asset while keeping facts and aesthetic choices separate. The script reads metadata and renders pixels; the agent confirms layout choices and never guesses absent EXIF values.

## Inputs

Collect or confirm:

- source image path and output path;
- band color and text color;
- fields to show, in order;
- optional font path;
- optional band-height and horizontal-padding ratios.

Defaults are documented in `references/layout-defaults.md`. If the user has not expressed a preference, state the defaults before rendering. Treat paths and style values as user-controlled inputs, not facts about the photograph.

## Workflow

1. **Protect the source.** Write to a different output path. Never overwrite the source unless the user explicitly requests it and the environment's safety policy permits that action.
2. **Inspect metadata.** Run the renderer with `--inspect` first when practical. Treat only the reported embedded values as camera-recorded facts.
3. **Resolve missing facts.** Leave missing fields blank. This version does not accept manual metadata overrides; do not edit the report to make a field appear camera-recorded.
4. **Choose the presentation.** Confirm field order, colors, font, and ratios. Do not claim that these choices reveal the image's intent.
5. **Render deterministically.** Use `scripts/render_exif_frame.py`. The script applies EXIF orientation, converts the composite to RGB, adds a band below the uncropped photograph, and writes a new image.
6. **Verify.** Inspect the output dimensions and the script's metadata report. Confirm that every displayed non-empty value appears in embedded EXIF.
7. **Report provenance.** Return source/output paths, rendered fields, blank fields, and style values.

## Commands

Inspect without rendering:

```bash
python scripts/render_exif_frame.py input.jpg --inspect
```

Render with defaults:

```bash
python scripts/render_exif_frame.py input.jpg --output framed.png
```

Customize fields and layout:

```bash
python scripts/render_exif_frame.py input.jpg \
  --output framed.png \
  --fields aperture,shutter,iso,captured,camera \
  --band-color '#F3F0E8' \
  --text-color '#171717' \
  --band-ratio 0.16 \
  --padding-ratio 0.04 \
  --font /path/to/font.ttf
```

The renderer requires Python 3 and Pillow. Use `--help` for the complete interface.

## Output contract

Return or record:

- source and output paths;
- source metadata report from the script;
- displayed field order;
- fields left blank;
- style configuration;
- output pixel dimensions;
- a warning that source EXIF is read for display but not copied into the composite output;
- other warnings, including absent EXIF or fallback fonts.

## Boundaries

- Do not infer aperture, shutter speed, ISO, date, device, location, or authorship from visible content.
- Do not invent a value merely to balance the layout.
- Do not alter crop, exposure, color, retouching, or composition; use a separate image-editing workflow for those tasks.
- Do not describe mood, meaning, or creative intent unless the photographer supplied that context.
- GPS and other sensitive EXIF fields are neither displayed nor copied by default.
- This skill creates one framed photograph. Use a series-layout workflow for arranging multiple photographs.

## Failure handling

- **No EXIF:** render requested labels with blank values and report that no embedded values were found.
- **Partial EXIF:** render known values and leave the rest blank.
- **Unsupported/corrupt image:** stop without replacing any existing output and report the decoder error.
- **Font unavailable:** require a valid font path when typography matters; otherwise allow the renderer's fallback and report it.
- **Text does not fit:** reduce the selected fields, provide a suitable font, or increase `--band-ratio`; do not silently omit facts.

## Validation cases

See `tests/cases.md`. At minimum, test full EXIF, partial/no EXIF, rotated EXIF orientation, unsafe same-path output, and narrow-image overflow before promoting the skill beyond draft.
