#!/usr/bin/env python3
"""Deterministic numerical-stability measurements for CSV data."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Iterable


def fail(message: str) -> "NoReturn":
    raise ValueError(message)


def read_columns(path: Path, names: Iterable[str]) -> dict[str, list[float]]:
    required = list(names)
    values = {name: [] for name in required}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            fail("CSV has no header row")
        missing = [name for name in required if name not in reader.fieldnames]
        if missing:
            fail("missing CSV columns: " + ", ".join(missing))
        for row_number, row in enumerate(reader, start=2):
            for name in required:
                try:
                    value = float(row[name])
                except (TypeError, ValueError):
                    fail(f"row {row_number}, column {name!r} is not numeric")
                if not math.isfinite(value):
                    fail(f"row {row_number}, column {name!r} is not finite")
                values[name].append(value)
    if not values[required[0]]:
        fail("CSV has no data rows")
    return values


def ensure_strictly_increasing(values: list[float], label: str) -> None:
    if any(b <= a for a, b in zip(values, values[1:])):
        fail(f"{label} must be strictly increasing")


def linear_detrend(values: list[float]) -> list[float]:
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values)) / denominator
    return [y - (y_mean + slope * (i - x_mean)) for i, y in enumerate(values)]


def spectrum_metrics(times: list[float], signal: list[float]) -> dict[str, object]:
    n = len(times)
    if n < 8:
        return {"available": False, "reason": "at least 8 samples required"}
    dts = [b - a for a, b in zip(times, times[1:])]
    mean_dt = sum(dts) / len(dts)
    max_relative_deviation = max(abs(dt - mean_dt) for dt in dts) / mean_dt
    if max_relative_deviation > 1e-6:
        return {
            "available": False,
            "reason": "samples are not uniformly spaced; plain DFT not applied",
            "max_relative_dt_deviation": max_relative_deviation,
        }

    residual = linear_detrend(signal)
    powers: list[tuple[int, float]] = []
    for k in range(1, n // 2 + 1):
        real = 0.0
        imag = 0.0
        for j, value in enumerate(residual):
            angle = 2 * math.pi * k * j / n
            real += value * math.cos(angle)
            imag -= value * math.sin(angle)
        powers.append((k, real * real + imag * imag))

    total_power = sum(power for _, power in powers)
    nyquist = 1 / (2 * mean_dt)
    if total_power <= 0:
        return {
            "available": True,
            "nyquist_frequency": nyquist,
            "dominant_frequency": None,
            "dominant_fraction_of_nyquist": None,
            "upper_quarter_power_fraction": 0.0,
        }

    dominant_k, _ = max(powers, key=lambda item: item[1])
    dominant_frequency = dominant_k / (n * mean_dt)
    upper_quarter_power = sum(
        power for k, power in powers if (k / (n * mean_dt)) >= 0.75 * nyquist
    )
    return {
        "available": True,
        "nyquist_frequency": nyquist,
        "dominant_frequency": dominant_frequency,
        "dominant_fraction_of_nyquist": dominant_frequency / nyquist,
        "upper_quarter_power_fraction": upper_quarter_power / total_power,
        "note": "compare frequencies across refined runs before identifying a ghost mode",
    }


def trajectory(args: argparse.Namespace) -> dict[str, object]:
    names = [args.time_col, args.invariant_col]
    if args.signal_col:
        names.append(args.signal_col)
    data = read_columns(args.input, names)
    times = data[args.time_col]
    invariant = data[args.invariant_col]
    ensure_strictly_increasing(times, args.time_col)

    baseline = invariant[0]
    scale = args.scale if args.scale is not None else abs(baseline)
    if not math.isfinite(scale) or scale <= 0:
        fail("normalization scale must be positive; provide --scale for a zero initial invariant")
    signed = [(value - baseline) / scale for value in invariant]
    absolute = [abs(value - baseline) for value in invariant]
    relative = [abs(value) for value in signed]
    max_index = max(range(len(relative)), key=relative.__getitem__)

    crossing = None
    if args.tolerance is not None:
        if args.tolerance < 0:
            fail("tolerance must be non-negative")
        crossing = next(
            (
                {"index": i, "time": times[i], "relative_drift": relative[i]}
                for i in range(len(relative))
                if relative[i] > args.tolerance
            ),
            None,
        )

    result: dict[str, object] = {
        "mode": "trajectory",
        "samples": len(times),
        "time_range": [times[0], times[-1]],
        "baseline_invariant": baseline,
        "normalization_scale": scale,
        "endpoint_signed_relative_drift": signed[-1],
        "max_absolute_drift": max(absolute),
        "max_relative_drift": relative[max_index],
        "max_drift_time": times[max_index],
        "tolerance": args.tolerance,
        "first_tolerance_crossing": crossing,
    }
    if args.signal_col:
        result["spectrum"] = spectrum_metrics(times, data[args.signal_col])
    return result


def regression_slope(xs: list[float], ys: list[float]) -> float:
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        fail("step values must not all be identical")
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator


def convergence(args: argparse.Namespace) -> dict[str, object]:
    data = read_columns(args.input, [args.step_col, args.error_col])
    pairs = sorted(
        zip(data[args.step_col], data[args.error_col]), reverse=True
    )
    if len(pairs) < 3:
        fail("at least three refinement rows are required")
    if any(step <= 0 or error <= 0 for step, error in pairs):
        fail("step and error values must be positive")
    if len({step for step, _ in pairs}) != len(pairs):
        fail("step values must be unique")

    pairwise = []
    for (coarse_h, coarse_e), (fine_h, fine_e) in zip(pairs, pairs[1:]):
        order = math.log(coarse_e / fine_e) / math.log(coarse_h / fine_h)
        pairwise.append(
            {
                "coarse_step": coarse_h,
                "fine_step": fine_h,
                "coarse_error": coarse_e,
                "fine_error": fine_e,
                "observed_order": order,
            }
        )
    overall = regression_slope(
        [math.log(step) for step, _ in pairs],
        [math.log(error) for _, error in pairs],
    )
    monotone = all(fine_e < coarse_e for (_, coarse_e), (_, fine_e) in zip(pairs, pairs[1:]))
    return {
        "mode": "convergence",
        "points": len(pairs),
        "coarse_to_fine": [{"step": h, "error": e} for h, e in pairs],
        "errors_decrease_monotonically": monotone,
        "pairwise_observed_orders": pairwise,
        "overall_log_log_slope": overall,
        "note": "a slope measures convergence behavior; it does not prove model validity",
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)

    trajectory_parser = subparsers.add_parser("trajectory", help="measure invariant drift and spectral indicators")
    trajectory_parser.add_argument("input", type=Path)
    trajectory_parser.add_argument("--time-col", default="time")
    trajectory_parser.add_argument("--invariant-col", default="energy")
    trajectory_parser.add_argument("--signal-col")
    trajectory_parser.add_argument("--scale", type=float)
    trajectory_parser.add_argument("--tolerance", type=float)
    trajectory_parser.set_defaults(function=trajectory)

    convergence_parser = subparsers.add_parser("convergence", help="estimate observed refinement order")
    convergence_parser.add_argument("input", type=Path)
    convergence_parser.add_argument("--step-col", default="step")
    convergence_parser.add_argument("--error-col", default="error")
    convergence_parser.set_defaults(function=convergence)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = args.function(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
