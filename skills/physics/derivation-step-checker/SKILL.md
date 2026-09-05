---
name: derivation-step-checker
description: Audit a physics derivation step by step for algebraic equivalence, dimensional consistency, sign changes, named physical laws, and whether each law's applicability conditions remain valid. Use when a user provides an existing derivation to verify or debug; do not use to silently produce a complete assessed derivation for them.
---

# Derivation Step Checker

Audit the derivation the user actually supplied. Keep algebraic validity separate from physical validity: a symbolic step may be correct while the invoked law is inapplicable.

## Inputs

Request only missing information that blocks the audit:

- the derivation with one transformation per numbered step;
- definitions and dimensions of symbols;
- the physical regime and assumptions (frame, system boundary, constancy, quasi-static limits, approximations);
- the desired depth: first failing step or full audit.

Do not invent omitted steps or assumptions. Mark them `unknown` and explain what evidence would resolve them.

## Workflow

1. **Normalize without repairing.** Transcribe each step as a before-equation and after-equation. Preserve the user's signs, subscripts, frames, and approximations. If a line performs several operations, split it into auditable substeps and label the split as editorial.
2. **Name the move.** For every step, record:
   - algebraic operation;
   - physical law, definition, constitutive relation, or approximation used;
   - applicability conditions required by that move.
3. **Check algebra.** Test whether the two equation residuals are equivalent, allowing an explicit nonzero multiplier. Check denominator restrictions, branch choices introduced by roots, sign reversals, and discarded solutions. A computer-algebra result is evidence, not permission to ignore domain assumptions.
4. **Check dimensions.** Require both sides of every equation and terms joined by addition to have the same dimensions. Dimensionally valid does not imply physically valid.
5. **Check physical continuity.** Re-evaluate the law's conditions at this exact step. In particular, look for assumptions that become invalid midway:
   - inertial-frame laws after a frame change;
   - fixed-mass momentum equations for variable-mass systems;
   - conservation laws after the system boundary opens;
   - quasi-static or equilibrium relations during a finite-rate process;
   - constant material parameters outside their stated regime;
   - approximations retained beyond their small-parameter range.
6. **Locate the first failure.** Do not let later algebra conceal an earlier invalid step. Classify each line as `pass`, `fail`, or `unknown`, and distinguish algebra, dimensions, and physics.
7. **Report minimally sufficient repairs.** Show the smallest correction that makes the failed step auditable. Do not rewrite the whole solution unless the user explicitly asks after seeing the audit.

## Deterministic checker

When the derivation can be represented with scalar symbolic expressions, create a JSON input following [references/input-schema.md](references/input-schema.md), then run:

```text
python scripts/check_derivation.py derivation.json
```

The checker verifies a constrained expression grammar, residual equivalence up to a declared factor, required nonzero declarations, and dimensions. It deliberately cannot decide whether a physical law applies; review that from the stated regime and assumptions.

If Python or SymPy is unavailable, perform the same checks explicitly and mark them as manual. Never claim a script passed unless it was actually run successfully.

## Output format

Start with the first failing or unresolved step, then give the table:

| Step | Algebra | Dimensions | Physics | Law / move | Required conditions | Finding |
|---|---|---|---|---|---|---|
| 1 | pass/fail/unknown | pass/fail/unknown | pass/fail/unknown | ... | ... | ... |

Finish with:

- **First break:** earliest `fail`, or `none found`;
- **Unresolved assumptions:** facts still needed;
- **Minimal repair:** one local correction or next diagnostic action;
- **Scope limit:** what was not established (for example, initial model validity or final numerical plausibility).

## Boundaries

- This skill audits an existing derivation; it does not replace a student's own assessed derivation.
- Do not treat symbolic equivalence as proof of physical correctness.
- Do not infer a missing law from the desired answer.
- Do not hide domain restrictions, frame labels, approximation order, or uncertainty behind a green status.
- For a final-answer-only plausibility review, use an answer plausibility workflow instead; for isolated unit checking, use a dimensional-analysis workflow.
