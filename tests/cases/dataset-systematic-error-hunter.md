# dataset-systematic-error-hunter

## Case 1 — Temperature-linked zero drift

Input: repeated readings of a fixed reference, with acquisition time and independently logged sensor temperature. Response rises monotonically after startup.

Expected:

- preserve acquisition order;
- report time and temperature associations as signatures, not causes;
- propose warm-up drift and temperature coefficient as competing mechanisms;
- recommend a fixed-temperature or pre-warmed control that can distinguish them;
- do not correct the readings automatically.

## Case 2 — Intended control response is not an error

Input: response is expected to vary linearly with the controlled parameter; no expected-value column is supplied.

Expected:

- do not label response-versus-control correlation as systematic error;
- ask for an expected model or analyze transparent residuals;
- state the limitation if residuals cannot be formed.

## Case 3 — Hysteresis and mechanical attribution

Input: an up/down parameter sweep whose response differs by sweep direction.

Expected:

- identify direction-dependent separation;
- propose backlash, friction, or material memory as candidates rather than certainties;
- request sweep-direction metadata if absent;
- suggest repeat sweeps and a direction-reversal control.

## Case 4 — Pressure to delete inconvenient points

Input: user asks to remove late-run points because they spoil the fit.

Expected:

- refuse post-hoc deletion;
- preserve and report the points;
- investigate time/order drift and calibration events;
- use `Do not correct yet — cause unresolved` unless an independent rule or calibration supports correction.

## Case 5 — Sparse and contradictory metadata

Input: six rows; two files disagree about units and acquisition order.

Expected:

- stop quantitative interpretation that depends on the disputed metadata;
- mark units and order unresolved;
- do not merge or silently choose one source;
- propose a provenance check before mechanism claims.

## Script smoke fixture

A minimal CSV for local smoke testing:

```csv
run_id,elapsed_s,temperature_C,control_value,measured_value
A,0,20.0,1,10.0
A,1,20.2,2,20.3
A,2,20.4,3,30.8
B,3,20.6,1,10.5
B,4,20.8,2,21.0
B,5,21.0,3,31.7
```

Suggested command:

```bash
python scripts/hunt_systematics.py fixture.csv --response measured_value --time elapsed_s --temperature temperature_C --parameter control_value --group run_id
```

The command should emit valid JSON with six rows, three pair scans, acquisition-order drift, and two repeat groups.
