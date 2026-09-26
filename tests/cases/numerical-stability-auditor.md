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

## Case 8 — Self-convergence from exactly three runs

**Prompt:** "No exact solution exists. I ran at `dt = 0.04, 0.02, 0.01`; the peak amplitudes are in `tests/fixtures/numerical-stability-auditor/three_runs_observable.csv`. What order am I getting?"

**Expected:** Builds two successive differences and puts each on the row of the coarser step (`0.04: 0.00096`, `0.02: 0.00024`); runs the `convergence` subcommand, which accepts the two rows, reports order 2.0 and a warning; calls the result self-convergence, not accuracy; says a fourth run (`dt = 0.005`) is needed to see whether the order is stable. Must not pad the table with an invented row or pair a difference with the finer step.

## Case 9 — Time column rounded to 4 decimals

**Prompt:** "Check `tests/fixtures/numerical-stability-auditor/rounded_time_oddeven.csv` (`dt = 1/30 s`, time written to 4 decimals) for ghost frequencies."

**Expected:** Runs `trajectory ... --signal-col signal`; the spectral check runs (`available: true`, `time_print_resolution` 0.0001) instead of being skipped for non-uniform sampling; reports about 28% of the power in the top quarter of frequencies, consistent with an odd-even mode near Nyquist; treats it as a suspect to test by halving `dt`, not as a proven artifact.

