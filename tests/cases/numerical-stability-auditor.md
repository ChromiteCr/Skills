# numerical-stability-auditor

## Case 1 — Conservative oscillator with refinement runs

**Prompt:** “I simulated an undamped oscillator at `dt = 0.04, 0.02, 0.01`. Audit whether the late-time amplitude modulation is real. Here are energy and position traces.”

**Expected:** Establishes a fixed-run contract; measures maximum and endpoint energy drift; estimates convergence only after aligning times; compares peak frequency across timesteps; gives a scoped verdict and a discriminating solver/refinement test.

## Case 2 — One trajectory only

**Prompt:** “This CFD pressure trace rings near the end. Is my simulation stable?”

**Expected:** Performs only limited drift/sampling diagnostics; does not estimate convergence order; asks for at least two additional resolutions and relevant balance residuals; reports “not auditable” or narrowly scoped suspicion rather than certainty.

## Case 3 — Dissipative system

**Prompt:** “Energy falls in my damped pendulum, so the integrator is unstable.”

**Expected:** Rejects raw energy conservation as the criterion; audits the expected energy-loss balance and constraint residual; distinguishes physical dissipation from numerical drift.

## Case 4 — Near-zero invariant

**Prompt:** “Total momentum starts at zero. Please report relative momentum drift.”

**Expected:** Does not divide by the initial value; requests or declares a physical reference scale and reports absolute drift.

## Case 5 — Nonuniform adaptive output

**Prompt:** “Run an FFT on these adaptively sampled points and identify ghost frequencies.”

**Expected:** Does not apply a plain FFT as if samples were uniform; recommends appropriate resampling or Lomb–Scargle analysis and checks whether output sampling differs from integration steps.

## Case 6 — Boundary violation

**Prompt:** “The refinement plot looks good. Confirm that my model correctly represents the experiment.”

**Expected:** States that numerical convergence does not validate equations, parameters, or experimental realism; limits the verdict to numerical credibility and proposes separate model validation.

## Case 7 — Chaotic trajectory

**Prompt:** “Two refined double-pendulum trajectories separate after 20 seconds, so one must be unstable.”

**Expected:** Avoids long-horizon pointwise convergence as the sole test; proposes short-horizon error growth, invariant drift, Lyapunov-aware horizons, and ensemble/distributional observables.
