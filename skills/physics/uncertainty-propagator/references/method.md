# Method and interpretation notes

## Scope

This reference covers first-order propagation of standard uncertainty and a Monte Carlo cross-check. It is a calculation aid, not a substitute for a defensible measurement model, calibration record, or systematic-error study.

## Linear covariance propagation

For outputs `y = f(x)` and input covariance `Σ_x`, evaluate the Jacobian `J` at the input estimates and calculate:

`Σ_y = J Σ_x Jᵀ`.

For scalar `y`, this is:

`u²(y) = Σ_i c_i²u²(x_i) + 2Σ_{i<j}c_i c_j cov(x_i,x_j)`.

The signed covariance sum can raise or lower total variance. Therefore, percentages based only on diagonal terms need not add to 100% of total propagated variance.

First-order propagation is most trustworthy when the model is smooth over the likely input region and its local linear approximation is adequate. It can fail near poles, thresholds, clipping, branch changes, or strong curvature.

## Monte Carlo comparison

Draw input vectors from the declared joint distribution, evaluate the model, and summarize the resulting outputs. The included helper supports multivariate normal inputs only. A bounded, log-normal, triangular, discrete, or otherwise non-normal input requires a different sampler or an explicit transformation; do not pretend Gaussian draws represent it.

Investigate when any of these occur:

- many draws are invalid or outside the physical domain;
- the output is visibly skewed or multimodal;
- Monte Carlo and linear standard uncertainties differ materially;
- the Monte Carlo mean differs materially from `f(E[x])`;
- results change appreciably with sample count or seed.

“Materially” depends on the decision. As a diagnostic default, flag a relative difference above 10%, but do not treat 10% as a universal scientific threshold.

## Sensitivity and measurement priority

For scalar output, useful quantities are:

- signed coefficient: `c_i = ∂f/∂x_i`;
- diagonal variance term: `v_i = c_i²u_i²`;
- elasticity: `e_i = (x_i/y)c_i`, when `x_i` and `y` are nonzero; signed, as the helper script reports it; rank inputs by `|e_i|`;
- predicted gain from reducing one independent standard uncertainty by factor `r`: `(1-r²)v_i` reduction in variance.

With correlations, changing one uncertainty can also change covariance terms. Trace correlations to shared calibration, environment, or data reduction before claiming an isolated improvement.

For multiple outputs, the Jacobian singular values describe locally amplified and weakly observed combinations. A large condition number warns that some combinations are difficult to distinguish. Scale variables and outputs to physically meaningful dimensionless forms before interpreting a condition number; raw mixed-unit conditioning can be misleading.

## Reporting discipline

State:

- whether reported uncertainty is standard or expanded;
- coverage factor and interval construction when used;
- units and coherent-unit conversion;
- covariance/correlation source;
- distribution assumptions;
- whether model uncertainty and systematic bias are excluded;
- Monte Carlo sample count and seed for reproducibility.

## Further reading

- JCGM 100:2008, *Evaluation of measurement data — Guide to the expression of uncertainty in measurement* (GUM): https://www.bipm.org/en/committees/jc/jcgm/publications
- JCGM 101:2008, *Supplement 1 to the GUM — Propagation of distributions using a Monte Carlo method*: https://www.bipm.org/en/committees/jc/jcgm/publications

URLs checked: 2026-09-04. Confirm current editions before making regulated or high-stakes claims.
