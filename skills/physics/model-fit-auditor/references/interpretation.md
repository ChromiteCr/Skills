# Diagnostic interpretation notes

These notes define the assumptions behind the bundled helper. They are guardrails, not universal acceptance thresholds.

## Quantities

For observations `y_i`, predictions `ŷ_i`, and residuals `r_i = y_i - ŷ_i`:

- bias: `mean(r_i)`;
- RMSE: `sqrt(mean(r_i²))`;
- chi-square: `Σ(r_i/σ_i)²` when `σ_i` are valid standard uncertainties;
- reduced chi-square: `χ²/(n-k)` when the number of residual degrees of freedom is defensible;
- fallback AIC: `n ln(RSS/n) + 2k`;
- fallback BIC: `n ln(RSS/n) + k ln(n)`.

The fallback AIC/BIC expressions assume independent Gaussian residuals with common unknown variance and omit constants shared by models fitted to the same response data. They are not valid for arbitrary likelihoods.

## Leverage and Cook's distance

With a full-rank design matrix `X`, leverage is the diagonal of `H = X(XᵀX)⁻¹Xᵀ`. The helper does not invert `XᵀX`: it builds an orthonormal basis of the column space with a pivoted QR factorization (after centering non-constant columns when an intercept column exists, and scaling every column to unit norm, neither of which changes `H`), so the leverages sum to the rank. The helper computes Cook's distance using residual mean square and the number of design columns; for a rank-deficient design it uses the numerical rank instead and says so. These calculations describe an ordinary least-squares linear-model approximation. For nonlinear, constrained, robust, Bayesian, or weighted fits, use diagnostics derived for the actual fitting method.

Rules such as leverage greater than `2p/n` or Cook's distance greater than `4/n` merely select observations for inspection. They do not justify exclusion.

## Residual-variable scans

The helper reports Pearson correlation between residuals and each supplied variable and between absolute residuals and each variable. Correlation can reveal a linear trend or changing scale, but:

- a small value does not exclude curvature, periodicity, or clustered structure;
- a large value does not prove a physical mechanism;
- repeated scans create multiple-comparison risk;
- acquisition order and batch labels should be inspected even when other variables look clean.

The sign-runs count is a lightweight serial-structure prompt. It is not a formal independence test.

## Honest conclusions

Use one of three verdicts:

- **adequate for stated use:** no material diagnostic failure within the checked range and precision;
- **conditionally adequate:** useful only within named ranges, batches, or tolerances;
- **not supported:** residual structure, instability, or unmodeled uncertainty invalidates the intended use.

Always state what data or model feature could change the verdict.
