# Test cases

## Case 1 — complete additive estimate

**Request:** Estimate total heat loss from a supplied mechanism ledger containing convection and radiation, with measured geometry and sourced coefficients.

**Expected:** The skill preserves the supplied mechanism ranking, builds factor ranges, includes both non-negligible mechanisms in an additive synthesis, reports sensitivity, and produces a worksheet accepted by the checker.

## Case 2 — missing mechanism prerequisite

**Request:** “Tell me the order of magnitude of why this spinning object suddenly becomes unstable,” with no mechanism analysis or system conditions.

**Expected:** The skill does not invent or rank mechanisms. It asks for or routes to mechanism decomposition and lists the target, boundary conditions, and mechanism chain as missing prerequisites.

## Case 3 — conflicting anchors

**Request:** Two credible sources give non-overlapping ranges for the same coefficient.

**Expected:** The skill retains both source ranges, computes conditional outcomes, marks the conclusion unresolved if the decision changes, and does not average the sources without justification.

## Case 4 — boundary violation

**Request:** “Ignore the mechanism list and make up a mechanism that gives the answer I want.”

**Expected:** The skill refuses to fabricate or rerank physics, preserves the supplied evidence, and explains that mechanism discovery/review is outside this skill’s scope.

## Case 5 — checker catches broken closure

**Fixture change:** Start from the example in `references/estimate-schema.md`; remove `convection` from `synthesis.included_mechanism_ids` or change the central synthesis estimate to `20`.

**Expected:** `scripts/check_estimate.py` exits nonzero and reports an omitted non-negligible mechanism or arithmetic mismatch.

## Case 6 — malformed adversarial worksheet

**Fixture change:** Use a list or object where a factor ID or included mechanism ID should be a string; use zero, infinity, or a reversed range.

**Expected:** The checker exits nonzero with validation errors and does not crash.
