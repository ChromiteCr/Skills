---
name: dimensional-analysis-checker
description: 当有一条推导、模型方程、标度律或最终公式，想在相信它之前先过最便宜的一关时使用。逐项查量纲：先统一记号、建符号量纲表，再按加减两侧同量纲、等式两边一致、指数对数三角函数的宗量无量纲逐条核对，指出第一处不一致；每个通过的项还要说出它代表什么物理贡献，说不出的项就是没理解的项。结论里写明量纲通过不等于物理正确。
category: physics/checking
version: 0.1.0
status: draft
priority: P0
compatible_agents:
  - claude-code
  - codex
  - cursor
  - codebuddy
  - nestudy
  - generic-llm-agent
display_name: 量纲检查器
outputs:
  - chat
max_rounds: 16
suggest_hint: 相信这条公式之前，先用「量纲检查器」逐项查一遍量纲
---

# dimensional-analysis-checker

## Purpose

Use this skill when a user has a physics equation, derivation step, scaling law, or model expression and wants to know whether the dimensions make sense **before** trusting the result.

This skill does **not** prove that a derivation is fully correct. It answers a narrower question first: do the units and dimensions constrain the expression the way physics says they should?

## When to use

Use this skill when the user wants to:

- check a derived formula term by term
- catch missing factors, extra factors, or impossible sums
- verify a scaling law or constitutive relation
- compare two candidate formulas and rule out dimensionally impossible ones
- inspect a modeling paper draft for inconsistent symbol usage or undeclared units

## When not to use

Do **not** use this skill as the only validation step when the user needs:

- limiting-case checks
- numerical plausibility checks
- a full derivation from first principles
- experimental uncertainty propagation
- proof that the physics assumptions themselves are appropriate

If the algebra is dimensionally valid but still physically wrong, say so plainly and hand off to a limiting-case, mechanism, or derivation review workflow.

## Inputs

Ask for the smallest set that makes checking possible:

1. the expression, equation, or derivation step to inspect
2. a symbol table with meaning and units/dimensions for each symbol
3. the unit system if it matters (SI, Gaussian/CGS, natural units, nondimensionalized variables, etc.)
4. any declared constants or dimensionless coefficients
5. if symbols were reused across sections, which definition is intended here

If the user does not provide a symbol table, build one explicitly from the prompt and mark guessed entries as `assumed`.

## Outputs

Return a compact report with these sections:

1. `Scope` — what was checked and under which unit system
2. `Dimension map` — symbol → meaning → dimension/unit → status
3. `Checks` — each equation or term marked `pass`, `fail`, or `ambiguous`
4. `Findings` — the exact mismatch, leftover factor, or undefined symbol
5. `Physical meaning audit` — what each surviving term represents physically
6. `Next move` — smallest correction or follow-up check to run next

## Core workflow

### Step 1: Normalize notation first

Before checking dimensions:

- rewrite the target expression in a consistent notation
- expand overloaded symbols (`R` radius vs resistance, `T` period vs temperature)
- note any hidden conventions such as radians treated as dimensionless
- separate true constants from fitted coefficients

If notation is ambiguous, do **not** silently choose one meaning. Mark the result `ambiguous` until the symbol is disambiguated.

### Step 2: Build a dimension map

For every symbol that appears, create a table with:

- symbol
- physical meaning in this context
- dimension in base quantities when possible (for example `[M L T^-2]`)
- stated unit if supplied
- evidence status: `given`, `derived`, or `assumed`

Prefer base-dimension form over only unit names because it exposes hidden inconsistencies faster.

### Step 3: Check homogeneity where physics requires it

Apply the strongest valid test for the structure at hand:

- **sum/difference:** every addend must have identical dimensions
- **equality:** left-hand side and right-hand side must match
- **exponentials/logs/trig arguments:** the argument must be dimensionless unless the user is explicitly using a known convention and states it
- **powers/roots:** the dimensional consequences must be explicit
- **vector equations:** dimensions must match componentwise; note separately if geometric meaning is still unclear

When a formula mixes terms with different dimensions, point to the first exact place the mismatch appears.

### Step 4: Inspect dimensionless groups and leftover factors

After the basic check:

- identify dimensionless groups that naturally emerge
- flag parameters that should cancel but do not
- flag terms that are dimensionally allowed but physically suspicious
- note when the expression implies a hidden scale the user never introduced

A dimensionally valid term still needs a sentence explaining what contribution it stands for physically.

### Step 5: Run the physical meaning audit

For each surviving term or grouped contribution, ask:

- what mechanism does this term represent?
- is that mechanism supposed to be present in the stated model?
- if this term vanished, what physical limit would that correspond to?
- if this term dominates, what regime would that imply?

If a term passes units but nobody can say what it means, call it out. That usually signals cargo-cult algebra or a missing modeling assumption.

### Step 6: Report confidence honestly

Use these outcome labels:

- `pass` — dimensionally consistent under stated assumptions
- `fail` — definite inconsistency found
- `ambiguous` — cannot judge cleanly because notation, units, or conventions are underspecified
- `partial pass` — some steps check out, but at least one symbol or conversion remains unresolved

## Deterministic path vs fallback path

### If code execution is available

Prefer this repository's own checker first — it is standard-library only, so it runs anywhere:

```bash
python3 ../_shared/scripts/dimcheck.py expressions.dim
```

Write the dimension map into a `[symbols]` section and the expressions into `[check]`,
with the declared dimension after a `;`. Use `[compare]` to assert that several terms
share a dimension. It reports the first mismatch, refuses to add unlike terms, rejects
dimensional arguments to `exp`/`log`/trig, and errors on any symbol that was never
declared — which doubles as a check for quantities that appeared out of nowhere.
Exit status is non-zero when anything fails. `--selftest` verifies the checker itself.

Reach for SymPy or another CAS only for what `dimcheck.py` deliberately does not do:

- simplifying and enumerating candidate dimensionless groups
- solving the dimension matrix for its rank (the `k` in Buckingham's `n − k`)
- algebraic simplification of the expression itself

### If no code execution is available

Use a manual table method:

1. rewrite each symbol in base dimensions
2. multiply/add exponents term by term
3. compare addends and both sides of the equation
4. record the first mismatch explicitly

The skill should still work without any vendor-specific runtime.

## Guardrails

- Do not invent units for a symbol without marking them `assumed`.
- Do not pretend dimensional validity proves physical correctness.
- Do not hide ambiguity caused by natural-unit or nondimensional conventions.
- Do not finish the user's full homework solution if they only asked for a check.
- If the expression is actually a fitted empirical law, say that dimensional consistency may constrain form but not prove mechanism.

## Handoff guidance

Hand off to another skill or workflow when:

- the expression passes units but fails a limiting case
- the mechanism list is unclear even though the dimensions work
- the user needs uncertainty propagation rather than unit checking
- the main problem is symbol collision across a longer document

Recommended neighbors (status matters — do not describe the output of a skill that does not exist yet):

- `physics-mechanism-decomposer` — available; open-phenomenon mechanism ranking
- `problem-formalization-coach` — available; when the real problem is that a law was used
  without stating why it applies
- `limiting-case-validator` — **planned**; regime checks. Until it exists, do the limits by hand:
  send each parameter to 0 and to infinity in turn and check that the expression returns to a
  known special case
- `derivation-step-checker` — **planned**; algebra plus law-by-law validation

## References

Shared physics material lives one level up, loaded on demand:

- `../_shared/dimensionless-groups.md` — Buckingham's theorem (including the two ways `k` is
  miscounted), the standard groups, and the discipline for comparing magnitudes
- `../_shared/law-applicability-table.md` — when a dimensionally valid term still violates the
  conditions of the law it came from
- `../_shared/physics-evidence-contract.md` — status tags, significant figures, which constants
  are exact by definition and which must be cited with a date
- `../_shared/scripts/dimcheck.py` — the deterministic checker

## Example prompts

- "Check whether this drag-force model is dimensionally consistent."
- "I derived an oscillation period formula; find the first unit mismatch if there is one."
- "These two heat-transfer terms are being added together. Is that legal dimensionally?"
- "Here is a modeling draft equation set. Build a symbol table and flag suspicious leftover parameters."

## Minimal response template

```text
Scope
- Checked: ...
- Unit system: ...

Dimension map
- symbol: meaning | dimension/unit | status

Checks
- Eq. (1): pass/fail/ambiguous
- Eq. (2): ...

Findings
- First mismatch: ...
- Suspicious leftover factor: ...

Physical meaning audit
- Term A represents ...
- Term B represents ...

Next move
- ...
```

## Changelog

- 0.1.0 — Initial cross-agent version with explicit manual fallback and evidence-status reporting.
