# Code changes

## 0.15.0 (2026-10-16)

Added stage-scoped pixel-count QA to the existing render, candidates and compare receipts. The new gamut_mapping object reports encoded-sRGB channel clamping before strength mixing, with each affected pixel counted once. The strict greater-than-10% warning follows AUDIT-AND-IDEAS.md 3.5 and is also surfaced by CLI summaries. Existing integer transform pixels, two-result grade_pixels API, channel counts and legacy warning lists are preserved. Empty image arrays are rejected because their pixel fraction is undefined.

The independent linear-sRGB gamut mapper remains separate. The new counters exclude source ICC losses, output-detail recovery and visual acceptance. All added fixtures and stress recipes are SYNTHETIC mathematical tests, not photographs or user-confirmed creative settings. No historical prototype was recovered.

SKILL.md has only a mechanical version update. A Skill Workshop proposal is still needed to describe the additive QA fields in the reusable skill documentation; no workflow text was applied in this run. Existing pre-0.15.0 history remains in SKILL.md.
