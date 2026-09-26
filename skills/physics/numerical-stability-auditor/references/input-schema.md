# Input schema for `audit_stability.py`

The helper has two independent subcommands. CSV files must have a header row; column names are configurable.

## `trajectory`

Required columns:

- `time`: monotonically increasing sample time;
- `energy`: invariant or balance quantity to inspect;
- `signal`: representative observable for spectral inspection (optional).

Example:

```csv
time,energy,signal
0.0,10.0,0.0
0.01,10.0001,0.0628
0.02,10.0000,0.1253
```

Example invocation:

```text
python3 scripts/audit_stability.py trajectory run.csv --time-col time --invariant-col energy --signal-col signal --scale 10 --tolerance 0.001
```

`--scale` is the normalization scale. If omitted, the script uses `abs(first invariant)` and refuses relative normalization when that value is effectively zero. `--tolerance` is a relative drift threshold.

The spectral diagnostic requires at least eight uniformly sampled finite points. It reports dominant nonzero frequency, its fraction of Nyquist, and the fraction of spectral power in the top quarter of resolvable frequencies. It is an indicator only; compare multiple timesteps before calling a peak a discretization ghost.

"Uniformly sampled" is judged against the printed precision of the time column: every value written with `d` decimals may be off by half a unit in the last place, so each interval may differ from the mean interval by about `10^-d` (never less than `1e-6` of the mean interval). A time column rounded to 4 decimals therefore passes, while genuinely adaptive steps do not. The output reports `max_relative_dt_deviation`, `time_print_resolution` and `relative_uniformity_tolerance`; when the printed precision alone allows more than 1% of the interval, a `warning` says uniform sampling was assumed, not verified.

## `convergence`

Required columns:

- `step`: timestep, mesh spacing, or another positive refinement scale;
- `error`: positive scalar error against a reference, or a successive-solution difference. For differences from runs at `h_1 > h_2 > h_3 > …`, write `|u(h_i) − u(h_(i+1))|` on the row whose `step` is `h_i`, the coarser step of the pair, and keep one refinement ratio `h_i/h_(i+1)` for all runs.

Example:

```csv
step,error
0.04,0.0016
0.02,0.0004
0.01,0.0001
```

Example invocation:

```text
python3 scripts/audit_stability.py convergence errors.csv --step-col step --error-col error
```

The script sorts coarse to fine, reports pairwise observed orders, the refinement ratios, and an overall log-log slope. At least two rows are required. Two rows are what three runs give in self-convergence; the output then has one order and a `warnings` entry, because a single estimate cannot show whether the order is stable (with errors against a reference, two rows are only two resolutions: supply three or more). Unequal refinement ratios add a `warnings` entry, because they bias orders computed from successive differences. If `error` is based on successive solutions rather than an exact/reference solution, describe the result as self-convergence.

Self-convergence example from three runs with ratio 2, for a result behaving as `u(h) = 1 + h²` (`u(0.04) − u(0.02)` on the `0.04` row, `u(0.02) − u(0.01)` on the `0.02` row; the script reports order 2 and the two-row warning):

```csv
step,error
0.04,0.0012
0.02,0.0003
```

## Output and exit behavior

Output is JSON on standard output. Input/schema failures print `error: …` and return exit status 2. A tolerance crossing is reported in JSON but does not itself cause failure, because acceptance thresholds and physical interpretation belong to the audit context. `--selftest` (without a subcommand) runs the script's regression cases.
