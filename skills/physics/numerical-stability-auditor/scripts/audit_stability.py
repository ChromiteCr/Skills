#!/usr/bin/env python3
"""Deterministic numerical-stability measurements for CSV data.

Uniform sampling for the spectral check is judged against the printed precision
of the time column: times written with d decimals may each be off by half a unit
in the last place, so intervals may differ from their mean by about 10^-d.

The convergence subcommand accepts two or more rows. Two rows are what three
runs give in self-convergence (two successive differences); the output then
carries a warning because a single order estimate cannot show whether the order
is stable. Put each successive difference |u(h_i) - u(h_(i+1))| on the row of
the coarser step h_i, and use a common refinement ratio.

Exit codes: 0 JSON written; 2 input error. --selftest exits 0 when all regression
cases pass and 1 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, NoReturn


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def read_columns(
    path: Path, names: Iterable[str], keep_text: Iterable[str] = ()
) -> tuple[dict[str, list[float]], dict[str, list[str]]]:
    required = list(names)
    values: dict[str, list[float]] = {name: [] for name in required}
    texts: dict[str, list[str]] = {name: [] for name in keep_text}
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
                if name in texts:
                    texts[name].append(row[name].strip())
    if not values[required[0]]:
        fail("CSV has no data rows")
    return values, texts


def print_resolution(texts: list[str]) -> float | None:
    """Finest unit in the last printed place, e.g. '0.0333' -> 1e-4, '3.3e-02' -> 1e-3."""
    exponents = []
    for text in texts:
        try:
            exponent = Decimal(text).as_tuple().exponent
        except InvalidOperation:
            return None
        if isinstance(exponent, int):
            exponents.append(exponent)
    return 10.0 ** min(exponents) if exponents else None


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


def spectrum_metrics(
    times: list[float], signal: list[float], time_resolution: float | None = None
) -> dict[str, object]:
    n = len(times)
    if n < 8:
        return {"available": False, "reason": "at least 8 samples required"}
    dts = [b - a for a, b in zip(times, times[1:])]
    mean_dt = sum(dts) / len(dts)
    max_relative_deviation = max(abs(dt - mean_dt) for dt in dts) / mean_dt
    # Each printed time is within half a unit of its last place, so an interval can differ
    # from the mean interval by up to one unit (plus the small error of the mean itself).
    rounding_allowance = 0.0
    if time_resolution is not None:
        rounding_allowance = time_resolution * (1.0 + 1.0 / (n - 1)) / mean_dt
    tolerance = max(1e-6, rounding_allowance * (1.0 + 1e-9))
    spacing = {
        "max_relative_dt_deviation": max_relative_deviation,
        "time_print_resolution": time_resolution,
        "relative_uniformity_tolerance": tolerance,
    }
    if max_relative_deviation > tolerance:
        return {
            "available": False,
            "reason": "samples are not uniformly spaced beyond the printed precision of the time column; plain DFT not applied",
            **spacing,
        }
    if rounding_allowance > 1e-2:
        spacing["warning"] = (
            "time values are printed so coarsely that rounding alone allows intervals to differ by more than 1% of dt; "
            "uniform sampling is assumed, not verified"
        )

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
            **spacing,
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
        **spacing,
    }


def trajectory(args: argparse.Namespace) -> dict[str, object]:
    names = [args.time_col, args.invariant_col]
    if args.signal_col:
        names.append(args.signal_col)
    data, texts = read_columns(args.input, names, keep_text=[args.time_col])
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
        result["spectrum"] = spectrum_metrics(
            times, data[args.signal_col], print_resolution(texts[args.time_col])
        )
    return result


def regression_slope(xs: list[float], ys: list[float]) -> float:
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        fail("step values must not all be identical")
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator


def convergence(args: argparse.Namespace) -> dict[str, object]:
    data, _ = read_columns(args.input, [args.step_col, args.error_col])
    pairs = sorted(
        zip(data[args.step_col], data[args.error_col]), reverse=True
    )
    if len(pairs) < 2:
        fail(
            "at least two refinement rows are required: errors against a reference at three or more "
            "resolutions, or two successive differences from three runs"
        )
    if any(step <= 0 or error <= 0 for step, error in pairs):
        fail("step and error values must be positive")
    if len({step for step, _ in pairs}) != len(pairs):
        fail("step values must be unique")

    warnings: list[str] = []
    if len(pairs) == 2:
        warnings.append(
            "only two rows, so one observed order and no check that it is stable. Three runs in "
            "self-convergence give exactly two successive differences; with errors against a reference, "
            "two rows are only two resolutions and cannot support an order claim. Add a finer run before "
            "calling the order established"
        )
    ratios = [coarse_h / fine_h for (coarse_h, _), (fine_h, _) in zip(pairs, pairs[1:])]
    if len(ratios) > 1 and max(ratios) > min(ratios) * 1.01:
        warnings.append(
            "refinement ratios differ ("
            + ", ".join(f"{ratio:.4g}" for ratio in ratios)
            + "); if the error column holds successive differences, the pairwise orders are biased "
            "unless the ratio is common"
        )

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
        "refinement_ratios": ratios,
        "warnings": warnings,
        "note": "a slope measures convergence behavior; it does not prove model validity",
    }


def run_selftest() -> int:
    outcomes: list[tuple[str, bool, str]] = []

    def check(name: str, func) -> None:  # type: ignore[no-untyped-def]
        try:
            ok, detail = func()
        except Exception as exc:  # noqa: BLE001 - a crash is a failed case
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        outcomes.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)

        def write(name: str, text: str) -> Path:
            path = root / name
            path.write_text(text, encoding="utf-8")
            return path

        def run_convergence(path: Path) -> dict[str, object]:
            return convergence(argparse.Namespace(input=path, step_col="step", error_col="error"))

        def run_trajectory(path: Path) -> dict[str, object]:
            return trajectory(
                argparse.Namespace(
                    input=path, time_col="time", invariant_col="energy", signal_col="signal", scale=None, tolerance=None
                )
            )

        def exact(h: float) -> float:
            return 1.0 + h * h  # u(h) with true order 2

        def differences(steps: list[float]) -> str:
            rows = [f"{a!r},{abs(exact(a) - exact(b))!r}" for a, b in zip(steps, steps[1:])]
            return "step,error\n" + "\n".join(rows) + "\n"

        documented = write("documented.csv", "step,error\n0.04,0.0016\n0.02,0.0004\n0.01,0.0001\n")

        def documented_case() -> tuple[bool, str]:
            result = run_convergence(documented)
            orders = [item["observed_order"] for item in result["pairwise_observed_orders"]]  # type: ignore[index,union-attr]
            ok = all(abs(o - 2.0) < 1e-9 for o in orders) and abs(result["overall_log_log_slope"] - 2.0) < 1e-9  # type: ignore[operator]
            return ok and not result["warnings"], json.dumps(result)[:300]

        check("documented error table: orders 2, no warning", documented_case)

        # Audit regression: three runs give two successive differences and used to be rejected.
        three_runs = write("three_runs.csv", differences([0.04, 0.02, 0.01]))

        def three_run_case() -> tuple[bool, str]:
            result = run_convergence(three_runs)
            order = result["pairwise_observed_orders"][0]["observed_order"]  # type: ignore[index]
            ok = result["points"] == 2 and abs(order - 2.0) < 1e-6 and any("only two rows" in w for w in result["warnings"])  # type: ignore[union-attr]
            return ok, json.dumps(result)[:300]

        check("three runs (two differences, coarser-step pairing) accepted with a warning", three_run_case)

        uneven = write("uneven.csv", differences([0.1, 0.05, 0.02, 0.01]))

        def uneven_case() -> tuple[bool, str]:
            result = run_convergence(uneven)
            orders = [round(item["observed_order"], 4) for item in result["pairwise_observed_orders"]]  # type: ignore[index,union-attr]
            ok = orders == [1.8365, 2.1237] and any("ratios differ" in w for w in result["warnings"])  # type: ignore[union-attr]
            return ok, f"orders={orders}, warnings={result['warnings']}"

        check("unequal refinement ratios are flagged for successive differences", uneven_case)

        single = write("single.csv", "step,error\n0.01,0.0001\n")

        def single_case() -> tuple[bool, str]:
            try:
                run_convergence(single)
            except ValueError as exc:
                return "at least two refinement rows" in str(exc), str(exc)
            return False, "no error raised"

        check("a single row is still an input error", single_case)

        def signal_rows(time_text) -> str:  # type: ignore[no-untyped-def]
            rows = []
            for i in range(64):
                t = i / 30
                value = math.sin(2 * math.pi * t) + 0.3 * (-1) ** i
                rows.append(f"{time_text(i, t)},10.0,{value!r}")
            return "time,energy,signal\n" + "\n".join(rows) + "\n"

        exact_times = run_trajectory(write("exact.csv", signal_rows(lambda i, t: repr(t))))["spectrum"]
        # Audit regression: a time column rounded to 4 decimals used to skip the spectral check.
        rounded = write("rounded.csv", signal_rows(lambda i, t: repr(round(t, 4))))

        def rounded_case() -> tuple[bool, str]:
            spectrum = run_trajectory(rounded)["spectrum"]
            ok = (
                spectrum["available"] is True  # type: ignore[index]
                and exact_times["available"] is True  # type: ignore[index]
                and abs(spectrum["upper_quarter_power_fraction"] - exact_times["upper_quarter_power_fraction"]) < 0.02  # type: ignore[index,operator]
                and spectrum["time_print_resolution"] == 1e-4  # type: ignore[index]
            )
            return ok, json.dumps(spectrum)[:300]

        check("time column rounded to 4 decimals still gets the spectral check", rounded_case)

        adaptive = write(
            "adaptive.csv",
            signal_rows(lambda i, t: f"{sum(1 / 30 * (1 + 0.05 * math.sin(k)) for k in range(i)):.6f}"),
        )

        def adaptive_case() -> tuple[bool, str]:
            spectrum = run_trajectory(adaptive)["spectrum"]
            return spectrum["available"] is False, json.dumps(spectrum)[:300]  # type: ignore[index]

        check("genuinely nonuniform (5% adaptive) steps are still rejected", adaptive_case)

        # A 0.25 s grid printed with one decimal: rounding alone moves intervals by up to 40% of dt.
        coarse = write("coarse.csv", signal_rows(lambda i, t: f"{0.25 * i:.1f}"))

        def coarse_case() -> tuple[bool, str]:
            spectrum = run_trajectory(coarse)["spectrum"]
            ok = spectrum["available"] is False or "warning" in spectrum  # type: ignore[operator]
            return ok, json.dumps(spectrum)[:300]

        check("times printed coarser than 1% of dt are never silently accepted", coarse_case)

    import subprocess

    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--help"], capture_output=True, text=True)
    outcomes.append(("--help prints usage and exits 0", proc.returncode == 0 and "usage:" in proc.stdout, f"exit={proc.returncode}"))

    failed = 0
    for name, ok, detail in outcomes:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  [{detail}]"))
        failed += 0 if ok else 1
    print(f"selftest: {len(outcomes) - failed}/{len(outcomes)} passed")
    return 0 if failed == 0 else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    subparsers = root.add_subparsers(dest="command")

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
    root = parser()
    args = root.parse_args()
    if args.selftest:
        return run_selftest()
    if args.command is None:
        root.error("choose a subcommand: trajectory or convergence (or use --selftest)")
    try:
        result = args.function(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
