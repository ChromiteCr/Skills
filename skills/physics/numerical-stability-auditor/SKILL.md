---
name: numerical-stability-auditor
description: Audit whether a physics simulation is numerically trustworthy using invariant drift, step-size convergence, and suspicious high-frequency content. Use when reviewing ODE/PDE, particle, rigid-body, circuit, wave, or other time-stepping results; when a result changes with timestep; or before interpreting simulated behavior as physics.
---

# Numerical Stability Auditor

Judge numerical credibility before explaining simulated behavior. Separate evidence of discretization failure from evidence about the modeled physics.

## Boundaries

This skill audits numerical outputs; it does not prove that the governing equations, parameters, boundary conditions, or implementation represent reality. It does not replace method-specific stability theory, code review, experimental validation, or an exact solution when one exists.

Do not label every oscillation a numerical artifact. A suspicious feature remains a hypothesis until a refinement or method-change test distinguishes it from physical dynamics.

## Inputs

Ask only for missing information that changes the audit:

- governing quantity or invariant expected to be conserved, if any;
- integrator/discretization and nominal order, when known;
- timestep or mesh scale for at least three otherwise comparable runs;
- identical initial/boundary conditions and comparison time or observable;
- trajectory columns for time, invariant, and a representative signal;
- known forcing, damping, discontinuities, events, or adaptive-step behavior;
- acceptance tolerance or downstream decision, if one exists.

If only one run exists, perform a limited diagnostic and explicitly request refinement runs. Never infer convergence order from one or two resolutions.

## Workflow

### 1. Establish the comparison contract

Write down what must stay fixed across runs: equations, parameters, initial and boundary conditions, solver family, stopping criterion, output sampling, random seed or ensemble definition, and comparison time. Note intentional differences.

Choose diagnostics that match the physics:

- conservative system: relative energy, momentum, charge, mass, or norm drift;
- dissipative system: deviation from the expected balance law, not “conservation”;
- constrained system: constraint residual;
- forced system: input-output balance;
- chaotic or stochastic system: distributional or ensemble observables rather than long-horizon pointwise agreement.

### 2. Locate invariant or balance-law failure

For each run, report:

- endpoint signed drift;
- maximum absolute drift;
- drift trend (bounded oscillation, monotone, episodic jump, or unresolved);
- first time the tolerance is crossed;
- the physical stage or numerical event at that time.

Normalize only by a physically meaningful scale. If the initial invariant is zero or near zero, use a declared reference scale and report absolute drift too.

A drift curve is also a process diagnostic: align the onset of drift with collisions, switching, contact, remeshing, boundary interaction, stiffness, or event handling. Do not hide cancellation by reporting endpoint drift alone.

### 3. Test refinement convergence

Use at least three step sizes or mesh scales with a common refinement ratio when practical. Compare the same scalar observable, norm, event time, or error against an exact/reference solution.

If errors `e(h)` are available, estimate observed order

`p = log(e_coarse / e_fine) / log(h_coarse / h_fine)`.

If no exact solution exists, use successive-solution differences and state that the result is self-convergence, not accuracy proof. Interpolate onto common times or locations before comparison; do not compare mismatched samples as if aligned.

Classify the outcome:

- **convergent**: error decreases consistently and observed order is plausible;
- **pre-asymptotic**: error decreases but order is unstable;
- **stalled**: refinement no longer improves the result;
- **divergent/unstable**: error grows, values become non-finite, or constraints fail;
- **inconclusive**: too few runs or comparison contract is broken.

Do not demand textbook order across discontinuities, limiters, event times, chaotic divergence, or mixed temporal/spatial error. Explain the expected order reduction.

### 4. Hunt discretization ghost frequencies

For uniformly sampled signals, remove the mean (and preferably trend), inspect the spectrum, and compare refined runs. Flag, but do not automatically condemn:

- a peak that moves in proportion to the Nyquist frequency as timestep changes;
- large power concentrated near Nyquist;
- odd-even or checkerboard modes;
- a frequency absent after method, timestep, or mesh refinement;
- new high-frequency power appearing when invariant drift begins.

A physical peak should normally remain at a stable physical frequency under refinement. Account for forcing frequencies, natural modes, aliasing, output downsampling, and nonuniform sampling. Use Lomb–Scargle or resampling for nonuniform data rather than a plain FFT.

### 5. Cross-check causality

For each suspicious feature, propose the cheapest discriminating test:

1. halve timestep or mesh spacing;
2. change solver/order while holding the model fixed;
3. tighten nonlinear/linear solver tolerances;
4. increase output sampling without changing integration;
5. isolate the stage where drift starts;
6. compare against an exact benchmark or manufactured solution.

State what outcome would support “physical” versus “numerical.”

### 6. Issue a verdict

Use one of:

- **credible within tested range**;
- **credible only for specified observables/timescales**;
- **numerically suspect**;
- **not auditable with supplied evidence**.

Never say “stable” without naming the diagnostic, tested range, and tolerance.

## Deterministic helper

Use `scripts/audit_stability.py` for CSV-based invariant drift, uniform-sampling spectral indicators, and three-or-more-point convergence estimates. The script uses only the Python standard library.

Read `references/input-schema.md` before invoking it. Treat its output as measurements, not a verdict: thresholds are user-supplied or context-dependent, and spectral flags require refinement evidence.

## Output format

Return:

1. **Verdict and scope** — one sentence with tested range.
2. **Comparison contract** — fixed and changed fields.
3. **Evidence table** — invariant/balance drift, convergence, spectral signs.
4. **Failure onset** — time/stage where credibility first degrades.
5. **Physical vs numerical hypotheses** — evidence for each.
6. **Next discriminating test** — cheapest test and expected outcomes.
7. **Limitations** — missing runs, assumptions, and untested dimensions.

## Quality gate

Before finishing, verify that:

- at least three resolutions support any convergence-order claim;
- compared runs differ only in declared numerical controls;
- sample grids were aligned or interpolation was disclosed;
- near-zero invariants use an explicit normalization scale;
- spectral claims account for sampling and Nyquist frequency;
- physical oscillations are not called artifacts without a refinement test;
- the verdict names observable, timespan, range, and tolerance;
- numerical credibility is not confused with model validity.
