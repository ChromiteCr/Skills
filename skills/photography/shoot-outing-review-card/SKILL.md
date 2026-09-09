---
name: shoot-outing-review-card
description: Turn one photography outing into a shareable review card with a cover image, EXIF habit summaries, and a capture timeline. Use when the user wants to review a shoot, visualize focal-length/aperture/shutter habits, or make an outing recap from a folder of photos.
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

# Shoot Outing Review Card

Create an evidence-based visual recap of one photography outing. The card helps a photographer notice capture habits; it does not judge whether those habits are good or infer artistic intent.

## Inputs

Ask for only what is missing:

- image files from one outing (JPEG or TIFF; RAW files need JPEG previews),
- output path,
- optional title, subtitle, cover image, and accent color.

If the files may be shared outside the user's device, confirm whether filenames or dates are sensitive. Never display GPS coordinates, camera serial numbers, owner names, or free-text EXIF comments.

## Workflow

1. **Confirm the set.** Treat the supplied files as one outing unless the capture times span more than 24 hours. If they do, report the span and ask whether to split it; do not silently combine separate outings.
2. **Read facts.** Run `scripts/make_review_card.py` to read capture time, focal length, 35 mm equivalent focal length when present, f-number, exposure time, ISO, and camera model.
3. **Audit coverage.** Report how many files were readable and the coverage of each EXIF field. A statistic based on fewer than 3 observations or less than 30% coverage is labelled `insufficient data`, not interpreted.
4. **Choose the cover.** Prefer the user-selected file. Otherwise the script deterministically chooses the earliest landscape-oriented image, falling back to the earliest readable image. Do not claim that the automatic choice is the “best” photo.
5. **Summarize habits.** Describe only visible distributions, for example “18–35 mm accounts for 62% of images.” Do not turn correlation into a story about intention or skill.
6. **Render and inspect.** Generate the PNG, then check that the title, sample counts, missing-data notes, labels, and timeline are legible. Preserve the JSON sidecar as the auditable source for every number shown.

## Deterministic tool

Requires Python 3.9+ and Pillow.

```bash
python scripts/make_review_card.py \
  IMG_001.jpg IMG_002.jpg IMG_003.jpg \
  --output outing-review.png \
  --title "Sunday walk" \
  --subtitle "Riverside · 7 September 2026" \
  --accent "#E98A4B"
```

Useful options:

```text
--cover PATH          select the cover explicitly
--width PX            output width (default 1600; minimum 900)
--json PATH           JSON sidecar path (default: output name + .json)
--no-camera-model     omit camera model from the card
```

The script exits non-zero when no readable image is supplied, the selected cover is not in the input set, the color is invalid, or the output cannot be written. It warns—but still produces a card—when EXIF is sparse.

## Output contract

Return:

1. the PNG review card;
2. a UTF-8 JSON sidecar containing input counts, time span, EXIF coverage, histogram bins/counts, cover-selection method, and warnings;
3. a short factual note containing:
   - files included / files skipped,
   - capture-time span,
   - strongest distribution only when its field passes the coverage threshold,
   - any sparse or absent fields.

Do not fabricate missing EXIF. Use `unknown`, omit the affected chart, or label it `insufficient data`.

## Interpretation rules

- Use 35 mm-equivalent focal length when available for all included observations; otherwise use actual focal length and label it clearly. Do not mix the two scales in one histogram.
- Aperture buckets are based on recorded f-numbers, not inferred depth of field.
- Shutter buckets describe exposure duration, not subject motion.
- A timeline shows capture density, not importance or effort.
- Duplicate timestamps remain separate captures; this is a habit card, not a unique-scene count.
- Edited exports can carry rewritten or stripped metadata. State this limitation whenever coverage is incomplete.

## Boundaries

- This skill summarizes an outing. For framing one photo with its EXIF, use `photo-exif-frame`; for arranging several selected works, use `photo-series-layout`.
- It does not rank photographs, identify the photographer's style, diagnose technique, or infer emotion.
- It does not upload files or query external services.
- It does not alter source images.

## Minimum verification

Before delivery, verify:

- output PNG opens and has the requested dimensions;
- JSON parses and its `included + skipped` equals the input count;
- every chart states both `n` and coverage;
- no private EXIF fields appear;
- an EXIF-free image produces a card with explicit missing-data labels rather than invented values.
