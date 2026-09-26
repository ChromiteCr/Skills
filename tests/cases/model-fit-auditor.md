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

## Case 8 — Helper leverage with raw SI and epoch units

Input: run the helper on `tests/fixtures/model-fit-auditor/wavelength_metres.json` (intercept plus wavelength in metres, 400–700 nm) and on `tests/fixtures/model-fit-auditor/epoch_seconds_n8.json` (intercept plus Unix epoch seconds, 8 rows).

Expected:

- both runs exit 0 with an `influence` block whose `rank` is 2 and whose leverages sum to 2;
- first leverage 0.3182 for the wavelength file and 0.4167 for the epoch file, the same values the data give in nanometres or in seconds from the first row;
- the audit never reports the design matrix as rank-deficient for either file.

## Case 9 — Residuals drift with acquisition time

Input: a fit of resistance against temperature whose residuals grow steadily with acquisition time; the user says "the residuals have structure, so my model is missing physics, right?"

Expected:

- lists all three candidates: the model (a missing temperature term), the measurement process (warm-up or zero drift in the meter), and the uncertainty model (error bars that ignore drift);
- proposes a check that separates them, such as re-measuring a fixed reference resistor over the same time span or randomizing the temperature order;
- hands the raw time-ordered data to `dataset-systematic-error-hunter` for the drift scan;
- does not declare missing physics and does not add a parameter to absorb the trend.

## Case 10 — Whole-paper critique is out of scope

Input: "Here is our full modeling paper. Play the judge and tell us whether the conclusions hold up."

Expected:

- says that a critique of the whole solution (assumptions, validation, sensitivity, reproducibility) belongs to `model-critique-coach`;
- offers to audit a specific fit from the paper here if the user supplies observations, predictions and the parameter count.

