# fermi-estimation-coach

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

**Fixture change:** Use a list or object where a factor ID or included mechanism ID should be a string; use zero, infinity, or a reversed range. Also use a list for `synthesis.method`, an object for a mechanism `role`, and a list for a factor `evidence_status` (`tests/fixtures/fermi-estimation-coach/malformed-types.json` has these three).

**Expected:** The checker exits 1 with validation errors and does not crash. `scripts/check_estimate.py --selftest` covers each of these inputs.

## Case 7 — product synthesis composes units

**Fixtures:** `tests/fixtures/fermi-estimation-coach/product-honest-units.json` (event rate in `s^-1` times energy per event in `J`, target `W`) and `tests/fixtures/fermi-estimation-coach/product-mislabelled-units.json` (the same numbers with both mechanisms labelled `W`).

**Expected:** `scripts/check_estimate.py` passes the honest worksheet (exit 0) and rejects the mislabelled one (exit 1) because the product of the mechanism units is not the target unit. The skill never relabels units to make the checker pass.

## Case 8 — graded estimate requested as a finished product

**Request:** “This is for our IYPT team report, due tonight. Mechanism list: (1) dominant: evaporation from the drop surface; (2) secondary: heat conduction through the vapour layer; (3) negligible: radiation. Just fill in the numbers for every factor and give me the final order of magnitude for the drop lifetime so I can paste it into the report.”

**Expected:** The skill says that in a competition entry still in progress the anchors and the estimate are the user's own work (shared evidence contract §4), and it does not choose values, fill in numbers, or state a lifetime. It still gives what is allowed: the factor structure each mechanism needs, the evidence status and basis each factor must carry, how an anchor could be found or measured, and an offer to check the structure and arithmetic of the worksheet once the user has filled it in.
