# Validation cases

Run these cases with disposable outputs. Confirm both the JSON report and the rendered pixels.

## Case 1 — complete EXIF

Given a JPEG containing aperture, exposure time, exposure compensation, ISO, capture time, make, and model:

- `--inspect` reports all six normalized fields;
- render adds a band below the EXIF-oriented image;
- displayed values match the report;
- output width equals oriented source width;
- output height equals oriented source height plus the configured band.

## Case 2 — partial or absent EXIF

Given an image with only ISO, and then a PNG with no EXIF:

- known ISO is displayed;
- every unavailable requested field has an empty value;
- no default camera settings, dates, or device names are invented;
- command exits successfully and reports the missing fields.

## Case 3 — orientation

Given a JPEG whose EXIF orientation rotates the stored pixels:

- output is visually upright;
- dimensions in the report correspond to the oriented image;
- source file remains byte-for-byte untouched.

## Case 4 — safety boundary

Set `--output` to the source path:

- command fails before saving;
- source remains unchanged.

Also omit `--output` without `--inspect`:

- command fails with an actionable message.

## Case 5 — layout overflow

Use a narrow image, all fields, and a long camera model:

- renderer fails rather than clipping or silently removing text;
- increasing `--band-ratio`, selecting fewer fields, or supplying an appropriate font allows a valid retry.

## Case 6 — unsupported input

Given a corrupt or unsupported file:

- command returns non-zero;
- an existing output is not replaced;
- error identifies the input decoding problem without claiming metadata was read.
