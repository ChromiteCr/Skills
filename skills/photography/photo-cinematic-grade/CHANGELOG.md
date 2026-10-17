# Code changes

## 0.16.0 (2026-10-17)

Added the standalone numerical API quantization_banding_qa in scripts/banding_qa.py for plan 3.5. Given actual aligned encoded-sRGB floating references and their uint8 quantized arrays before and after grading, it measures RMS quantization residuals in code values and their signed increase. A strict increase above the plan value of 0.35 warns; the report never supplies whole-photo or perceptual acceptance.

The caller must explicitly supply patch_size. The implementation selects the complete source tile with the smallest mean squared RGB neighbor differences, with raster-order ties, and measures both residuals at the same coordinates. It reports the examined area, selected area and excluded incomplete edges. This tile selection is a new engineering definition, not a recovered prototype algorithm or a photographer-validated method. There is no guessed scale, smoothing coefficient, color recipe or claim that the relatively smoothest tile is actually a smooth scene region.

Lost source quantization error cannot be inferred from an 8-bit photograph. Reference lineage is caller-supplied and explicitly disclosed. Dividing decoded RGB8 by 255 can only support a subsequent encoding-stage measurement, not a zero-loss claim about the source photograph. RMS does not describe error spatial correlation; dither, grain and visual banding still require separate review.

The legacy render/candidates/compare pixels and reports are unchanged; the new function is not wired to CLI because that pipeline does not retain its pre-quantization references. CLI integration belongs with the future floating pipeline. Twenty new SYNTHETIC tests cover hand-calculated residuals, warning boundary, source-only region selection, edge exclusions, invalid data and real quantize_srgb8 API integration. All constructed pixels, seeds and patch sizes are test inputs, not real photographs or user-confirmed creative settings.

SKILL.md and the index received mechanical version changes only. Reusable documentation for this numerical API still needs a Skill Workshop proposal and approval; no workflow or reference prose was applied. Actual photo/visual acceptance and the complete plan 3.5 end-to-end guard remain pending.

## 0.15.0 (2026-10-16)

Added stage-scoped pixel-count QA to the existing render, candidates and compare receipts. The new gamut_mapping object reports encoded-sRGB channel clamping before strength mixing, with each affected pixel counted once. The strict greater-than-10% warning follows AUDIT-AND-IDEAS.md 3.5 and is also surfaced by CLI summaries. Existing integer transform pixels, two-result grade_pixels API, channel counts and legacy warning lists are preserved. Empty image arrays are rejected because their pixel fraction is undefined.

The independent linear-sRGB gamut mapper remains separate. The new counters exclude source ICC losses, output-detail recovery and visual acceptance. All added fixtures and stress recipes are SYNTHETIC mathematical tests, not photographs or user-confirmed creative settings. No historical prototype was recovered.

SKILL.md has only a mechanical version update. A Skill Workshop proposal is still needed to describe the additive QA fields in the reusable skill documentation; no workflow text was applied in this run. Existing pre-0.15.0 history remains in SKILL.md.
