---
name: limiting-case-validator
description: Validate a physics formula, scaling law, or model by checking carefully chosen limiting cases before trusting the result.
version: 0.1.0
category: physics
---

# limiting-case-validator

Use this skill when a physics derivation, fitted relation, or simulation result may be algebraically correct yet physically wrong. The goal is to test whether the result behaves sensibly when key parameters become very small, very large, equal to each other, or approach a known special regime.

This skill is for validation, not for doing the original derivation from scratch.

## Use this when

- You have a final formula and want to know whether it is physically plausible.
- You need to check whether a model reduces to a known textbook case.
- You want to identify which dimensionless parameter actually controls the regime.
- A result looks suspicious near a boundary, singularity, or approximation limit.

## Do not use this when

- The main problem is parsing the original statement. Use a problem-formalization skill first.
- The formula is not yet defined clearly enough to test.
- The user is asking you to invent a derivation they have not attempted.
- The task is mainly unit consistency; that belongs to dimensional analysis.

## Required inputs

Ask for the minimum needed set:

1. The expression, model, or claim to validate.
2. The meaning and units of every symbol.
3. The physically allowed range of each control parameter, if known.
4. Any known special cases, benchmark formulas, or conservation constraints.
5. Whether the source is from hand derivation, data fitting, or simulation.

If any of 1-2 is missing, stop and request clarification.

## Core idea

A useful limiting-case check has two halves:

- **Predict first:** before touching algebra, state what should happen physically in each limit.
- **Compute second:** then reduce the expression in that limit and compare against the prediction.

Never treat a formal limit as passed unless both halves are present.

## Workflow

### 1. Identify control parameters

List the parameters that can define distinct regimes, such as:

- small or large mass ratio
- low or high speed
- weak or strong damping
- short-time or long-time behavior
- thin-gap or large-gap geometry
- small-angle or large-angle approximation
- low-frequency or high-frequency drive

Prefer dimensionless groups when possible. If the problem is written only in dimensional variables, explicitly form the likely dimensionless combinations first.

### 2. Choose the smallest useful set of limits

Do not enumerate every imaginable limit. Pick the limits that most strongly test the physics:

- known textbook limits
- parameter going to zero
- parameter going to infinity
- two parameters becoming equal
- no-interaction limit
- quasistatic / instantaneous limit
- nonrelativistic / ultrarelativistic limit
- weak-coupling / strong-coupling limit

Usually 2-4 limits are enough for one pass.

### 3. Write the physical expectation before the math

For each chosen limit, state:

- what mechanism should dominate
- what should vanish, saturate, diverge, or change sign
- what known law or simpler model should reappear
- whether the quantity should remain finite, monotone, positive, or bounded

If you cannot explain the expectation in words, say so instead of bluffing.

### 4. Reduce the expression in each limit

For each limit:

1. Specify the limit clearly.
2. Simplify the expression to its leading behavior.
3. Note any singular terms, cancellations, or sign flips.
4. If there is a series expansion, keep only the first term needed to decide the physics.

When a computer algebra system is available, use it to support the reduction. When it is not, do the asymptotics manually and state any uncertainty.

### 5. Compare math to physics

For each limit, classify the outcome:

- **Pass**: reduces to the expected regime or benchmark.
- **Partial pass**: trend is right, but coefficient/sign/boundedness is questionable.
- **Fail**: contradicts a known law, expected trend, conservation argument, or physical constraint.
- **Inconclusive**: limit could not be evaluated from the provided information.

Explain the mismatch in physical language, not only algebraic language.

### 6. Check high-value red flags

Always look for these failure modes:

- wrong sign in a restoring, dissipative, or probability-like term
- divergence where the physics should stay finite
- dependence on a parameter that should disappear in a decoupled limit
- failure to recover a known special case
- nonzero output when symmetry requires zero
- negative quantity where positivity is required
- asymptotic scaling that contradicts mechanism dominance

### 7. End with a verdict and next action

Give one of:

- usable as written
- usable with caveats
- likely wrong and should be re-derived
- underdetermined; need more context

If it fails, point to the most likely source:

- bad approximation regime
- algebraic sign error
- hidden assumption violated
- wrong boundary condition
- wrong dominant-balance argument
- fit extrapolated beyond data support

## Output format

Use this structure:

```markdown
## Candidate result
- [expression or model]

## Control parameters / dimensionless groups
- ...

## Limiting cases checked
### Limit 1: [statement]
- Physical expectation:
- Reduced behavior:
- Comparison:
- Verdict: Pass / Partial pass / Fail / Inconclusive

### Limit 2: [statement]
- Physical expectation:
- Reduced behavior:
- Comparison:
- Verdict: Pass / Partial pass / Fail / Inconclusive

## Cross-limit red flags
- ...

## Overall verdict
- ...

## Recommended next step
- ...
```

## Guardrails

- Do not invent benchmark formulas you cannot justify.
- Do not claim a limit is physically relevant if the parameter range makes it impossible.
- Do not replace physical reasoning with symbolic manipulation alone.
- If multiple competing limits do not commute, say so explicitly.
- Separate exact limits from approximations and fitted extrapolations.

## Deterministic assistance

If tools are available, they may help with:

- symbolic limits
- leading-order asymptotics
- series expansion around small parameters
- sign checks under stated parameter constraints
- substitution into known benchmark cases

These checks support the judgment; they do not replace the need to state the physical expectation first.

## Acceptance bar

A good run of this skill must include all of the following:

- the tested formula or claim is quoted unambiguously
- each chosen limit is physically motivated
- each limit includes a pre-math expectation
- each limit includes an actual reduced form
- the final verdict distinguishes pass, fail, and inconclusive cases

If any of the above is missing, the validation is incomplete.
