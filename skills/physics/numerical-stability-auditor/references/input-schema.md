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
python scripts/audit_stability.py trajectory run.csv --time-col time --invariant-col energy --signal-col signal --scale 10 --tolerance 0.001
```

`--scale` is the normalization scale. If omitted, the script uses `abs(first invariant)` and refuses relative normalization when that value is effectively zero. `--tolerance` is a relative drift threshold.

The spectral diagnostic requires at least eight uniformly sampled finite points. It reports dominant nonzero frequency, its fraction of Nyquist, and the fraction of spectral power in the top quarter of resolvable frequencies. It is an indicator only; compare multiple timesteps before calling a peak a discretization ghost.

## `convergence`

Required columns:

- `step`: timestep, mesh spacing, or another positive refinement scale;
- `error`: positive scalar error against a reference, or a successive-solution difference.

Example:

```csv
step,error
0.04,0.0016
0.02,0.0004
0.01,0.0001
```

Example invocation:

```text
python scripts/audit_stability.py convergence errors.csv --step-col step --error-col error
```

The script sorts coarse to fine, reports pairwise observed orders, and fits an overall log-log slope. At least three rows are required. If `error` is based on successive solutions rather than an exact/reference solution, describe the result as self-convergence.

## Output and exit behavior

Output is JSON on standard output. Input/schema failures return a nonzero exit status. A tolerance crossing is reported in JSON but does not itself cause failure, because acceptance thresholds and physical interpretation belong to the audit context.
