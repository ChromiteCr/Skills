#!/usr/bin/env python3
"""First-pass, dependency-free diagnostics for fitted numeric data.

Input and output are JSON. This helper does not fit a model and does not decide
whether observations should be excluded.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def numeric_vector(value: Any, name: str, length: int | None = None) -> list[float]:
    if not isinstance(value, list) or not value:
        fail(f"{name} must be a non-empty array")
    result: list[float] = []
    for i, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            fail(f"{name}[{i}] must be numeric")
        number = float(item)
        if not math.isfinite(number):
            fail(f"{name}[{i}] must be finite")
        result.append(number)
    if length is not None and len(result) != length:
        fail(f"{name} must contain {length} values")
    return result


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def pearson(a: list[float], b: list[float]) -> float | None:
    ma, mb = mean(a), mean(b)
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    denom = math.sqrt(sum(x * x for x in da) * sum(x * x for x in db))
    if denom == 0:
        return None
    return sum(x * y for x, y in zip(da, db)) / denom


def sign_runs(values: list[float]) -> dict[str, int]:
    signs = [1 if x > 0 else -1 for x in values if x != 0]
    runs = 0 if not signs else 1 + sum(a != b for a, b in zip(signs, signs[1:]))
    return {"positive": signs.count(1), "negative": signs.count(-1), "runs": runs}


def invert(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    augmented = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            fail("design_matrix is rank-deficient; leverage is undefined")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        augmented[col] = [x / scale for x in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [x - factor * y for x, y in zip(augmented[row], augmented[col])]
    return [row[n:] for row in augmented]


def mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(x * y for x, y in zip(row, vector)) for row in matrix]


def influence(design: Any, residuals: list[float]) -> dict[str, Any]:
    n = len(residuals)
    if not isinstance(design, list) or len(design) != n or not design:
        fail(f"design_matrix must contain {n} rows")
    rows = [numeric_vector(row, f"design_matrix[{i}]") for i, row in enumerate(design)]
    p = len(rows[0])
    if p == 0 or any(len(row) != p for row in rows):
        fail("design_matrix must be rectangular and non-empty")
    if n <= p: fail("design_matrix requires more rows than columns")
    xtx = [[sum(row[i] * row[j] for row in rows) for j in range(p)] for i in range(p)]
    inv = invert(xtx)
    leverage = [sum(x * y for x, y in zip(row, mat_vec(inv, row))) for row in rows]
    mse = sum(r * r for r in residuals) / (n - p)
    if mse == 0:
        cooks = [0.0 for _ in residuals]
    else:
        cooks = [
            (r * r / (p * mse)) * (h / ((1.0 - h) ** 2)) if h < 1.0 - 1e-12 else None
            for r, h in zip(residuals, leverage)
        ]
    return {
        "assumption": "ordinary least-squares linear-model approximation",
        "design_columns": p,
        "leverage": leverage,
        "cooks_distance": cooks,
        "review_heuristics": {"leverage_gt": 2.0 * p / n, "cooks_distance_gt": 4.0 / n},
    }


def audit(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        fail("input must be a JSON object")
    observed = numeric_vector(data.get("observed"), "observed")
    n = len(observed)
    predicted = numeric_vector(data.get("predicted"), "predicted", n)
    k = data.get("parameter_count")
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        fail("parameter_count must be a nonnegative integer")
    if n <= k: fail("number of observations must exceed parameter_count")

    residuals = [y - yhat for y, yhat in zip(observed, predicted)]
    rss = sum(r * r for r in residuals)
    result: dict[str, Any] = {
        "convention": "residual = observed - predicted",
        "n": n,
        "parameter_count": k,
        "degrees_of_freedom": n - k,
        "residuals": residuals,
        "summary": {
            "bias": mean(residuals),
            "rmse": math.sqrt(rss / n),
            "rss": rss,
            "minimum": min(residuals),
            "maximum": max(residuals),
            "sign_runs": sign_runs(residuals),
        },
        "warnings": [],
    }

    if rss > 0:
        result["gaussian_common_variance_scores"] = {
            "assumption": "independent Gaussian residuals with common unknown variance",
            "aic_without_shared_constant": n * math.log(rss / n) + 2 * k,
            "bic_without_shared_constant": n * math.log(rss / n) + k * math.log(n),
        }
    else:
        result["warnings"].append("RSS is zero; fallback AIC/BIC are singular and were omitted")

    if "sigma" in data:
        sigma = numeric_vector(data["sigma"], "sigma", n)
        if any(x <= 0 for x in sigma):
            fail("all sigma values must be positive")
        normalized = [r / s for r, s in zip(residuals, sigma)]
        chi2 = sum(z * z for z in normalized)
        result["uncertainty_diagnostics"] = {
            "normalized_residuals": normalized,
            "chi_square": chi2,
            "reduced_chi_square": chi2 / (n - k),
            "caveat": "interpret only if sigma values are justified standard uncertainties and error dependence is handled",
        }
    else:
        result["warnings"].append("sigma absent; calibrated chi-square diagnostics were not computed")

    variables = data.get("variables", {})
    if not isinstance(variables, dict):
        fail("variables must be an object mapping names to numeric arrays")
    scans: dict[str, Any] = {}
    for name, values in variables.items():
        vector = numeric_vector(values, f"variables.{name}", n)
        scans[str(name)] = {
            "residual_pearson_r": pearson(vector, residuals),
            "absolute_residual_pearson_r": pearson(vector, [abs(r) for r in residuals]),
        }
    if scans:
        result["variable_scans"] = scans

    result["prediction_scans"] = {
        "residual_pearson_r": pearson(predicted, residuals),
        "absolute_residual_pearson_r": pearson(predicted, [abs(r) for r in residuals]),
    }

    if "design_matrix" in data:
        result["influence"] = influence(data["design_matrix"], residuals)
    else:
        result["warnings"].append("design_matrix absent; leverage and influence were not computed")

    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: audit_fit.py INPUT.json", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(json.dumps(audit(data), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
