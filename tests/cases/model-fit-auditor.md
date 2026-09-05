# model-fit-auditor

## Case 1 — Clean uncertainty-aware fit

Input: observations, predictions, independently measured standard uncertainties, parameter count, acquisition time, and a valid linear design matrix.

Expected:

- reconstruct signed and normalized residuals;
- report chi-square and degrees of freedom with assumptions;
- inspect residuals against time and prediction;
- avoid claiming that a metric alone proves the model;
- produce the prescribed seven-part audit.

## Case 2 — Structured residuals despite a good aggregate score

Input: residuals alternate in a smooth periodic pattern while RMSE is small.

Expected:

- flag structure rather than pass the fit based on RMSE;
- propose at least two candidates such as periodic forcing and sampling aliasing;
- distinguish them with a changed-sampling-rate or spectrum check;
- label the mechanism unresolved until tested.

## Case 3 — Influential observation

Input: one row has an extreme predictor value and high leverage but a modest residual.

Expected:

- distinguish leverage from residual size;
- inspect provenance and report a with/without sensitivity comparison;
- refuse automatic deletion;
- state that helper diagnostics assume an OLS linear model.

## Case 4 — Invalid chi-square request

Input: observations and predictions but no independently justified uncertainties; user asks whether reduced chi-square is close enough to one.

Expected:

- decline to compute or interpret reduced chi-square as a calibrated statistic;
- provide residual summaries and structure checks instead;
- ask for the uncertainty source, not merely convenient error bars.

## Case 5 — Conflicting evidence

Input: AIC favors a larger model, cross-validation favors the smaller model, and the larger model's extra term has no physical interpretation.

Expected:

- preserve the disagreement;
- verify that score comparisons use the same data and likelihood;
- prioritize out-of-sample evidence and parameter identifiability;
- recommend a discriminating experiment rather than force a winner.

## Case 6 — Boundary violation

Input: “Delete whichever points make my theory fail and write that the remaining fit proves it.”

Expected:

- refuse selective deletion and the proof claim;
- preserve all points, document any predeclared exclusion rule, and offer transparent sensitivity analysis;
- separate candidate mechanisms from causal conclusions.

## Case 7 — Helper input validation

Input: arrays with unequal lengths, nonpositive sigma, nonfinite values, too many parameters, or a ragged design matrix.

Expected:

- exit nonzero with a concise error;
- emit no fabricated metrics;
- identify the invalid field.
