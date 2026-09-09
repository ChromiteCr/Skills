---
name: photo-series-layout
description: Arrange 3–9 finished photographs into a cohesive one-page series, contact sheet, long image, or PDF. Use when a user wants to sequence and present a photo set with consistent frames, gutters, and canvas treatment. Preserve the photographer's chosen order unless they explicitly ask for sequencing suggestions; do not infer artistic intent from pixels alone.
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
---

# Photo Series Layout

Turn a small set of finished photographs into one coherent page without silently changing their meaning, order, or content.

## Scope

Use this skill when the user has **3–9 photographs** and wants one of these outputs:

- a one-page grid or strip;
- a single long image;
- a one-page PDF;
- a layout plan that another renderer can implement.

Do not use it to select the best photographs, retouch images, invent captions, or infer a photographer's intent. If the user needs EXIF framing first, treat each framed image as an input asset and do not add a second frame here.

## Inputs

Collect or derive only what is needed:

1. ordered image paths;
2. output path and format (`PNG`, `JPEG`, or one-page `PDF`);
3. layout intent: `auto`, `grid`, `horizontal`, or `vertical`;
4. canvas target, if any (pixels, aspect ratio, or print size plus DPI);
5. background, outer margin, gutter, and fit mode (`contain` or `cover`);
6. whether reordering suggestions are wanted.

If paths or output format are missing, ask. For unspecified visual settings, state the defaults before rendering. Never invent image order.

## Workflow

### 1. Establish the sequence

Treat the supplied order as authoritative.

If the user explicitly requests help sequencing, offer at most three **candidate** orders based only on observable or supplied attributes:

- chronological or event order;
- light-to-dark or warm-to-cool progression;
- repeated-form or visual-rhythm progression.

Label the basis of each candidate and ask the user to choose. Do not claim a narrative or emotional arc the photographer did not provide.

### 2. Choose a layout family

Read [references/layout-rules.md](references/layout-rules.md), then choose:

- `horizontal`: a left-to-right sequence, usually 3–5 images;
- `vertical`: a top-to-bottom sequence or long image;
- `grid`: equal cells for comparison or contact-sheet presentation;
- `auto`: let the renderer choose a compact grid from image count and canvas shape.

Prefer one consistent cell shape. Use an asymmetric layout only when the user identifies a lead image and approves the hierarchy; the bundled renderer intentionally does not invent asymmetric prominence.

### 3. Decide cropping policy

Use `contain` by default: preserve every photograph and allow background bars within cells.

Use `cover` only with explicit permission because it crops. Before rendering, say that edge content may be removed. Never stretch an image.

Apply EXIF orientation, convert all inputs to a common RGB output space, and preserve source files unchanged.

### 4. Render deterministically

The bundled renderer requires Python 3 and Pillow:

```bash
python scripts/layout_photos.py \
  --output series.png \
  --layout auto \
  --fit contain \
  image-01.jpg image-02.jpg image-03.jpg
```

For a vertical long image:

```bash
python scripts/layout_photos.py \
  --output series.pdf \
  --layout vertical \
  --cell-width 1800 \
  --cell-height 1200 \
  --margin 120 \
  --gutter 48 \
  image-01.jpg image-02.jpg image-03.jpg
```

Run `python scripts/layout_photos.py --help` for all options. Pass input paths as separate arguments; do not build an unquoted shell string from user-supplied paths.

If Pillow is unavailable, provide the exact command and dependency requirement rather than pretending the file was rendered.

### 5. Inspect the result

Check all of the following:

- every requested input appears exactly once;
- order matches the approved sequence;
- no image is stretched;
- `contain` loses no image area;
- `cover` cropping is acceptable to the user;
- margins and gutters are consistent;
- text, logos, or extra decoration were not introduced;
- output dimensions and format match the request.

For print, additionally confirm physical size at the requested DPI and recommend a print-preview check. Do not claim color accuracy without a color-managed proofing workflow.

## Output report

Return:

- output path and pixel dimensions;
- ordered input list;
- layout, fit mode, margin, gutter, and background used;
- any crop warning or degraded behavior;
- one concise note on what still requires human visual approval.

## Failure handling

- Fewer than 3 or more than 9 inputs: stop and ask whether to change the set; do not silently drop images.
- Missing, unreadable, or unsupported image: identify it and stop before writing output.
- Duplicate path: stop unless duplication is intentional and confirmed.
- Existing output: require `--overwrite`; never replace it silently.
- Mixed aspect ratios: default to `contain`, not aggressive cropping.
- Multi-page request: explain that this skill and renderer produce one page; propose splitting only after the user approves the grouping.
