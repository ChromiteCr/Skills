# Code changes

## 0.17.0 (2026-10-17)

Added a usable LUT export/readback path for the EXISTING three integer SDR recipes. cinegrade.py lut takes an explicit source, look, strength and new output directory. It writes a red-fastest 33-cube in encoded sRGB, reads the written bytes back, verifies their hash, parses them and measures every source pixel against the real integer renderer using tetrahedral interpolation and normalized Oklab Euclidean error. The strict p99 < 0.02 limit comes from AUDIT 3.5. A numerical failure preserves grade.cube and a qa_failed report with CLI exit 1; input/I/O failure exits 2. report.json is published last; occupied outputs and originals are preserved.

The new module also provides standalone unit-domain cube serialization, parsing and tetrahedral interpolation for later floating-pipeline integration. It refuses shapers, unsupported directives/domains, nonfinite values, extrapolation and malformed row counts. The integer recipe is sampled at nearest-uint8 grid nodes and is therefore only approximated between nodes; strength zero exports the exact identity. No creative coefficient or default selection was added. All spatial effects, ICC conversion and dither remain outside the LUT. Application color management and interpolation still need external verification.

Twenty-seven new SYNTHETIC tests cover six independently enumerated tetrahedra, red-fastest rows, endpoints, ties, affine transforms, nontrilinear cases, actual disk readback, malformed input, privacy, nonreplacement, I/O faults, strict error threshold and real CLI success/failure. Existing test assertions and fixtures are unchanged; only new suite registration was added. Full skill tests ran 359 unique cases successfully. Repeated entry points are not extra independent cases.

The initial tests exposed batch-dependent BLAS rounding in Oklab QA. Fixed-order matrix accumulation preserved the failed exact batch-invariance assertion. Its new integration test then exposed erroneous divide/overflow flags for a finite 729x3 grid in the existing forward Oklab BLAS path. The second repair uses the same published matrices with explicit three-term accumulation, retaining finite-result guards and all old assertions. Full-suite revalidation passed. A separate command-construction quoting error was caught before writing code and corrected; no failed validation was hidden.

An additional SYNTHETIC 17-cubed uint8 lattice (4,913 pixels, not photographs or full-domain certification), rendered at test strength 100 using unchanged bundled recipes, measured p99 Delta E OK values of 0.0016434085770841316 (neutral), 0.0016802429206397179 (warm-muted), and 0.0015568506579064607 (cool-muted). These are actual results for a deliberately constructed mathematical fixture, not observed scene data or user-confirmed creative settings. The origin, cube hashes and reports are retained locally in the owned clone evidence directory, not distributed as real-photo examples.

Scope was chosen from audit snapshot base 98e5dba4658922f833f93fcba59bd5c113c0aefa, SHA-256 39ecb93cf66123107e4f3708d81d4563cf3050069855c325430a0b82f64ea8d9. Code inspection confirmed LUT export was absent. Historical 0.4.1 code was not recovered or reproduced. Six planned floating looks, the historical pastel dark-region failure, real-photo/visual acceptance and full plan 3.5 remain pending.

SKILL.md and SKILL_INDEX.md received mechanical version updates only. A Skill Workshop proposal is required to update their reusable capability descriptions (which still say LUT is pending) and document this command. No reusable workflow or reference prose was applied. Library version is unchanged under VERSIONING.md because this is an existing skill capability increment.

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
