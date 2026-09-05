#!/usr/bin/env python3
"""Descriptive scan for systematic-error signatures in CSV data.

Uses only the Python standard library. Results are clues for investigation, not
proof of a physical cause.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable


def finite_float(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def paired(rows: list[dict[str, str]], x_name: str, y_name: str) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        x = finite_float(row.get(x_name, ""))
        y = finite_float(row.get(y_name, ""))
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
    return xs, ys


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = fmean(xs), fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denominator = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return sum(a * b for a, b in zip(dx, dy)) / denominator if denominator else None


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float] | None:
    if len(xs) < 2:
        return None
    mx, my = fmean(xs), fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if not sxx:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    sse = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    return {"slope": slope, "intercept": intercept, "sse": sse}


def solve_3x3(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) < 1e-15:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[column])]
    return [augmented[i][3] for i in range(3)]


def quadratic_fit(xs: list[float], ys: list[float]) -> dict[str, float] | None:
    if len(xs) < 4:
        return None
    sums = [sum(x ** power for x in xs) for power in range(5)]
    matrix = [[sums[i + j] for j in range(3)] for i in range(3)]
    vector = [sum((x ** power) * y for x, y in zip(xs, ys)) for power in range(3)]
    coefficients = solve_3x3(matrix, vector)
    if coefficients is None:
        return None
    a0, a1, a2 = coefficients
    sse = sum((y - (a0 + a1 * x + a2 * x * x)) ** 2 for x, y in zip(xs, ys))
    return {"constant": a0, "linear": a1, "quadratic": a2, "sse": sse}


def scan_pair(rows: list[dict[str, str]], predictor: str, response: str) -> dict[str, object]:
    xs, ys = paired(rows, predictor, response)
    linear = linear_fit(xs, ys)
    quadratic = quadratic_fit(xs, ys)
    result: dict[str, object] = {
        "predictor": predictor,
        "response": response,
        "n": len(xs),
        "pearson_r": correlation(xs, ys),
        "linear_fit": linear,
        "quadratic_fit": quadratic,
    }
    if linear and quadratic and linear["sse"] > 0:
        result["quadratic_sse_reduction_fraction"] = (linear["sse"] - quadratic["sse"]) / linear["sse"]
    else:
        result["quadratic_sse_reduction_fraction"] = None
    return result


def segment_drift(rows: list[dict[str, str]], response: str) -> dict[str, object]:
    values = [finite_float(row.get(response, "")) for row in rows]
    numeric = [value for value in values if value is not None]
    width = max(1, len(numeric) // 5) if numeric else 0
    if len(numeric) < 4:
        return {"n": len(numeric), "segment_width": width, "first_mean": None, "last_mean": None, "difference": None}
    first = fmean(numeric[:width])
    last = fmean(numeric[-width:])
    return {"n": len(numeric), "segment_width": width, "first_mean": first, "last_mean": last, "difference": last - first}


def repeat_scan(rows: list[dict[str, str]], group: str, response: str) -> dict[str, object]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        label = row.get(group, "").strip()
        value = finite_float(row.get(response, ""))
        if label and value is not None:
            buckets.setdefault(label, []).append(value)
    summaries = {
        label: {"n": len(values), "mean": fmean(values), "population_sd": pstdev(values) if len(values) > 1 else 0.0}
        for label, values in sorted(buckets.items())
    }
    means = [entry["mean"] for entry in summaries.values()]
    return {
        "group_count": len(summaries),
        "between_group_mean_range": max(means) - min(means) if len(means) >= 2 else None,
        "groups": summaries,
    }


def require_columns(fieldnames: Iterable[str] | None, required: Iterable[str]) -> None:
    available = set(fieldnames or [])
    missing = [name for name in required if name not in available]
    if missing:
        raise ValueError(f"missing CSV column(s): {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--response", required=True)
    parser.add_argument("--time")
    parser.add_argument("--temperature")
    parser.add_argument("--parameter", action="append", default=[])
    parser.add_argument("--group")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with args.csv_file.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        predictors = [name for name in [args.time, args.temperature, *args.parameter] if name]
        require_columns(reader.fieldnames, [args.response, *predictors, *([args.group] if args.group else [])])
        rows = list(reader)

    report: dict[str, object] = {
        "source": str(args.csv_file),
        "row_count": len(rows),
        "response": args.response,
        "warning": "Descriptive signatures are not proof of a physical cause.",
        "pair_scans": [scan_pair(rows, predictor, args.response) for predictor in predictors],
        "acquisition_order_drift": segment_drift(rows, args.response),
    }
    if args.group:
        report["repeat_scan"] = repeat_scan(rows, args.group, args.response)

    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
