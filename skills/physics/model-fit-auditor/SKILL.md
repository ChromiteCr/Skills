---
name: model-fit-auditor
description: Audit a fitted physical model using residuals, uncertainty-aware goodness of fit, leverage and influence, information criteria, and residual structure. Use when a user has observations plus model predictions or fit output and needs to decide whether the fit is trustworthy, overfit, dominated by influential points, or missing a physical mechanism. Do not use to choose a model before data exist or to silently remove outliers.
---

# Model Fit Auditor

Audit whether a fitted model is an honest description of the data. Treat structured residuals as evidence that the model, measurement process, or uncertainty model is incomplete—not as permission to invent a mechanism.

## Inputs

Ask only for missing inputs that affect the audit:

- observed values `y_i` and fitted predictions `ŷ_i`;
- number of fitted parameters `k` (state whether it includes an intercept);
- measurement standard uncertainties `σ_i`, when known;
- independent variables and their units;
- model equation, fitting method, constraints, and data transformations;
- design matrix, if leverage and influence are requested;
- provenance of exclusions, repeated measurements, and preprocessing.

If raw data cannot be shared, accept a residual table or fit report and explicitly mark which checks cannot be reproduced.

## Boundaries

- Do not delete, winsorize, or reweight points without showing results both before and after and recording the physical justification.
- Do not call a point an “outlier” solely because its residual is large.
- Do not interpret reduced chi-square when supplied uncertainties are absent, arbitrary, fitted from the same residuals, or omit important correlations.
- Do not compare AIC/BIC values computed from different response data, likelihood definitions, or preprocessing pipelines.
- Do not infer causation from a residual pattern. Offer candidate mechanisms and discriminating checks.
- For correlated errors, censored data, hierarchical models, non-Gaussian likelihoods, or errors in predictors, require a likelihood appropriate to that structure; the bundled script is only a first-pass diagnostic.

## Workflow

### 1. Establish the fit contract

Write a compact record before judging the fit:

```text
response and units:
independent variables and units:
model and parameter count:
fit objective / likelihood:
uncertainty source:
constraints / priors:
excluded data and reasons:
```

Mark unknown fields as `unknown`; never fill them by inference.

### 2. Reconstruct residuals

Use signed residuals `r_i = y_i - ŷ_i`. Preserve row order and identifiers. When valid `σ_i` are available, also compute normalized residuals `z_i = r_i/σ_i`.

Check:

1. sample count and finite values;
2. matching lengths and units;
3. residual sign convention;
4. whether predictions are in the same transformed or untransformed space as observations;
5. whether repeated observations are being treated as independent.

### 3. Inspect goodness of fit without a single-number verdict

Report at least:

- bias (mean residual);
- RMSE and residual range;
- `χ² = Σ(r_i/σ_i)²` and `χ²/ν`, only when uncertainties justify it, with `ν = n-k`;
- AIC/BIC only under a stated likelihood; for the script’s fallback, this is an independent Gaussian model with a common unknown variance;
- uncertainty and limitations of every statistic.

A reduced chi-square far from one is a prompt to inspect the model and uncertainty estimates, not an automatic pass/fail threshold.

### 4. Find structure in residuals

Inspect residuals against every independent variable, prediction magnitude, acquisition order/time, instrument channel, and experimental batch when available.

Classify visible or computed patterns:

| Pattern | Candidate explanation | Discriminating check |
|---|---|---|
| nonzero offset | calibration zero, omitted constant term | independent zero/reference measurement |
| monotonic trend | wrong functional dependence, drift, range-dependent calibration | split by time; fit a physically motivated alternative |
| curvature | missing nonlinear term or regime transition | plot local slope; collect data across transition |
| fan shape | variance grows with signal, wrong weighting | residual scale by prediction bins; model heteroscedasticity |
| periodicity | forcing, vibration, aliasing, sampling artifact | spectrum and changed sampling-rate test |
| clusters by batch | apparatus state or environmental confounder | batch-stratified residuals and calibration logs |
| long runs of one sign | serial correlation or slow drift | acquisition-order plot and autocorrelation check |

For each claimed structure, state: evidence, at least two plausible causes when feasible, and one observation that could separate them.

### 5. Audit leverage, influence, and exclusions

When a valid design matrix is available, compute leverage and Cook’s distance. Treat common cutoffs such as `2p/n` or `4/n` as review heuristics, not laws.

For every influential point:

1. verify transcription, units, and apparatus notes;
2. identify why it is influential (extreme predictor, small uncertainty, large residual, or combination);
3. report the fit with and without it as a sensitivity analysis;
4. retain it unless a documented measurement failure or predeclared rule justifies exclusion.

### 6. Check overfitting and model comparison

Prefer out-of-sample validation, repeated experiments, or physically meaningful holdouts. If only in-sample data exist:

- compare parameter count with independent information in the data;
- flag weakly identified or strongly correlated parameters;
- compare residual structure, not only AIC/BIC;
- reject extra terms that lack a physical interpretation unless clearly labeled as empirical;
- avoid declaring a winner when score differences are small relative to modeling assumptions.

### 7. Translate diagnostics into physics

Build a mechanism ledger:

```text
residual evidence | candidate physical process | predicted signature | decisive next check | confidence
```

A valid candidate must predict more than “the fit improves”: it should specify a sign, scaling, regime, frequency, time dependence, or control-variable response. If no mechanism is supported, say `unresolved`.

### 8. Produce the audit

Use this output order:

1. **Verdict** — fit is adequate for the stated use, conditionally adequate, or not supported;
2. **Fit contract and data limitations**;
3. **Reproducible metrics**;
4. **Residual structure**;
5. **Influential observations and sensitivity**;
6. **Candidate missing mechanisms** with discriminating tests;
7. **Next actions**, prioritized by information gain and cost.

Separate observations from interpretations. Never hide failed checks.

## Deterministic helper

`scripts/audit_fit.py` accepts JSON and emits JSON diagnostics without vendor-specific services or third-party packages:

```sh
python scripts/audit_fit.py fit.json
```

Minimal input:

```json
{"observed":[1.0,2.1,2.9],"predicted":[1.1,2.0,3.0],"parameter_count":2}
```

Optional keys are `sigma`, `variables` (a mapping of variable name to numeric values), and `design_matrix` (rows including any intercept column). See `references/interpretation.md` before treating heuristic flags as conclusions.

## Failure modes

- **Metric worship:** declaring success from R² or reduced chi-square while residuals remain structured.
- **Outlier laundering:** deleting inconvenient points until a model passes.
- **Mechanism storytelling:** naming a physical cause that makes no distinct prediction.
- **Invalid score comparison:** comparing AIC/BIC across different datasets or likelihoods.
- **Uncertainty theater:** using guessed error bars as if independently measured.
- **Tool overreach:** presenting the helper’s linear-model influence diagnostics as valid for every nonlinear fit.
