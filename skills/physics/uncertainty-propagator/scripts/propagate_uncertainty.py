#!/usr/bin/env python3
"""Propagate correlated standard uncertainties through symbolic models.

Input and output are JSON. Numerical inputs must use a coherent unit system.
Dependencies: sympy, numpy.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp


class InputError(ValueError):
    """Raised when the input specification is incomplete or inconsistent."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON input specification")
    parser.add_argument("--samples", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--indent", type=int, default=2)
    return parser.parse_args()


def require_finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise InputError(f"{label} must be a finite number")
    return result


def load_spec(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise InputError("top-level JSON value must be an object")
    return data


def parse_variables(spec: dict[str, Any]) -> tuple[list[str], np.ndarray, np.ndarray]:
    raw = spec.get("variables")
    if not isinstance(raw, dict) or not raw:
        raise InputError("variables must be a non-empty object")

    names = list(raw)
    if len(set(names)) != len(names):
        raise InputError("variable names must be unique")
    for name in names:
        if not isinstance(name, str) or not name.isidentifier():
            raise InputError(f"invalid variable name: {name!r}")

    means: list[float] = []
    stds: list[float] = []
    for name in names:
        item = raw[name]
        if not isinstance(item, dict):
            raise InputError(f"variables.{name} must be an object")
        means.append(require_finite(item.get("value"), f"variables.{name}.value"))
        std = require_finite(
            item.get("std_uncertainty"), f"variables.{name}.std_uncertainty"
        )
        if std < 0:
            raise InputError(f"variables.{name}.std_uncertainty cannot be negative")
        stds.append(std)
    return names, np.asarray(means, dtype=float), np.asarray(stds, dtype=float)


def build_covariance(
    spec: dict[str, Any], names: list[str], stds: np.ndarray
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    index = {name: i for i, name in enumerate(names)}
    covariance = np.diag(stds**2)
    seen: set[tuple[int, int]] = set()
    normalized: list[dict[str, Any]] = []

    correlations = spec.get("correlations", [])
    if not isinstance(correlations, list):
        raise InputError("correlations must be an array")
    for position, item in enumerate(correlations):
        if not isinstance(item, dict):
            raise InputError(f"correlations[{position}] must be an object")
        a, b = item.get("a"), item.get("b")
        if a not in index or b not in index:
            raise InputError(f"correlations[{position}] names an unknown variable")
        if a == b: raise InputError(f"correlations[{position}] must name two distinct variables")
        i, j = sorted((index[a], index[b]))
        if (i, j) in seen:
            raise InputError(f"duplicate correlation pair: {a}, {b}")
        seen.add((i, j))
        rho = require_finite(item.get("rho"), f"correlations[{position}].rho")
        if not -1.0 <= rho <= 1.0:
            raise InputError(f"correlations[{position}].rho must be within [-1, 1]")
        value = rho * stds[i] * stds[j]
        covariance[i, j] = covariance[j, i] = value
        normalized.append({"a": names[i], "b": names[j], "rho": rho})

    eigenvalues = np.linalg.eigvalsh(covariance)
    tolerance = max(1.0, float(np.max(np.diag(covariance)))) * 1e-12
    if float(np.min(eigenvalues)) < -tolerance:
        raise InputError(
            "input covariance is not positive semidefinite; correlations are inconsistent"
        )
    return covariance, normalized


def parse_outputs(
    spec: dict[str, Any], names: list[str]
) -> tuple[list[str], list[sp.Expr], list[sp.Symbol]]:
    raw = spec.get("outputs")
    if not isinstance(raw, dict) or not raw:
        raise InputError("outputs must be a non-empty object")

    symbols = list(sp.symbols(" ".join(names), real=True, seq=True))
    locals_map = dict(zip(names, symbols))
    allowed_symbols = set(symbols)
    output_names: list[str] = []
    expressions: list[sp.Expr] = []

    for output_name, source in raw.items():
        if not isinstance(output_name, str) or not output_name.isidentifier():
            raise InputError(f"invalid output name: {output_name!r}")
        if not isinstance(source, str) or not source.strip():
            raise InputError(f"outputs.{output_name} must be a non-empty expression string")
        try:
            expression = sp.sympify(source, locals=locals_map)
        except (sp.SympifyError, TypeError, SyntaxError) as exc:
            raise InputError(f"cannot parse outputs.{output_name}: {exc}") from exc
        unknown = expression.free_symbols - allowed_symbols
        if unknown:
            raise InputError(
                f"outputs.{output_name} contains unknown symbols: "
                + ", ".join(sorted(str(symbol) for symbol in unknown))
            )
        output_names.append(output_name)
        expressions.append(expression)
    return output_names, expressions, symbols


def safe_condition_number(jacobian: np.ndarray) -> float | str | None:
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    if singular_values.size < 2:
        return None
    largest = float(np.max(singular_values))
    smallest = float(np.min(singular_values))
    tolerance = largest * np.finfo(float).eps * max(jacobian.shape)
    if smallest <= tolerance:
        return "infinite"
    return largest / smallest


def scaled_jacobian(
    jacobian: np.ndarray,
    means: np.ndarray,
    stds: np.ndarray,
    output_values: np.ndarray,
    output_stds: np.ndarray,
) -> tuple[np.ndarray, list[float], list[float]]:
    """Scale Jacobian with central magnitudes, then uncertainty magnitudes as fallback."""
    input_scales = np.where(np.abs(means) > 0, np.abs(means), stds)
    input_scales = np.where(input_scales > 0, input_scales, 1.0)
    output_scales = np.where(np.abs(output_values) > 0, np.abs(output_values), output_stds)
    output_scales = np.where(output_scales > 0, output_scales, 1.0)
    scaled = (jacobian * input_scales[np.newaxis, :]) / output_scales[:, np.newaxis]
    return scaled, input_scales.tolist(), output_scales.tolist()


def scalar_budget(
    names: list[str],
    means: np.ndarray,
    stds: np.ndarray,
    output_value: float,
    row: np.ndarray,
    covariance: np.ndarray,
) -> dict[str, Any]:
    diagonal = row**2 * stds**2
    total = float(row @ covariance @ row.T)
    correlation = total - float(np.sum(diagonal))
    entries = []
    for i, name in enumerate(names):
        elasticity = None
        if output_value != 0.0:
            elasticity = float((means[i] / output_value) * row[i])
        entries.append(
            {
                "variable": name,
                "sensitivity": float(row[i]),
                "elasticity": elasticity,
                "diagonal_variance_contribution": float(diagonal[i]),
            }
        )
    return {
        "entries": entries,
        "diagonal_variance_sum": float(np.sum(diagonal)),
        "correlation_variance_contribution": correlation,
        "total_variance": total,
    }


def monte_carlo(
    functions: list[Any],
    means: np.ndarray,
    covariance: np.ndarray,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    if samples < 2:
        raise InputError("--samples must be at least 2")
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(
        means, covariance, size=samples, check_valid="raise", method="eigh"
    )
    columns = []
    valid = np.ones(samples, dtype=bool)
    for function in functions:
        with np.errstate(all="ignore"):
            values = np.asarray(function(*draws.T), dtype=float)
        if values.ndim == 0:
            values = np.full(samples, float(values))
        values = np.broadcast_to(values, (samples,))
        valid &= np.isfinite(values)
        columns.append(values)

    matrix = np.column_stack(columns)
    valid_matrix = matrix[valid]
    if len(valid_matrix) < 2:
        raise InputError("fewer than two finite Monte Carlo output draws")
    quantiles = np.quantile(valid_matrix, [0.025, 0.5, 0.975], axis=0)
    centered = valid_matrix - np.mean(valid_matrix, axis=0)
    standard = np.std(valid_matrix, axis=0, ddof=1)
    skewness = np.full(len(functions), np.nan)
    nonzero = standard > 0
    skewness[nonzero] = np.mean(centered[:, nonzero] ** 3, axis=0) / standard[nonzero] ** 3
    return {
        "requested_samples": samples,
        "valid_samples": int(np.sum(valid)),
        "invalid_samples": int(samples - np.sum(valid)),
        "mean": np.mean(valid_matrix, axis=0).tolist(),
        "std_uncertainty": standard.tolist(),
        "quantiles": {
            "0.025": quantiles[0].tolist(),
            "0.5": quantiles[1].tolist(),
            "0.975": quantiles[2].tolist(),
        },
        "skewness": [None if not math.isfinite(float(x)) else float(x) for x in skewness],
        "seed": seed,
    }


def calculate(spec: dict[str, Any], samples: int, seed: int) -> dict[str, Any]:
    names, means, stds = parse_variables(spec)
    covariance, correlations = build_covariance(spec, names, stds)
    output_names, expressions, symbols = parse_outputs(spec, names)

    substitutions = dict(zip(symbols, means))
    values = np.asarray([float(expr.evalf(subs=substitutions)) for expr in expressions])
    if not np.all(np.isfinite(values)):
        raise InputError("one or more outputs are not finite at the central values")

    symbolic_jacobian = sp.Matrix(expressions).jacobian(symbols)
    jacobian = np.asarray(symbolic_jacobian.evalf(subs=substitutions), dtype=float)
    if not np.all(np.isfinite(jacobian)):
        raise InputError("Jacobian is not finite at the central values")
    output_covariance = jacobian @ covariance @ jacobian.T
    variances = np.diag(output_covariance)
    tolerance = max(1.0, float(np.max(np.abs(variances)))) * 1e-12
    if float(np.min(variances)) < -tolerance:
        raise InputError("propagated covariance has a negative variance")
    standard = np.sqrt(np.maximum(variances, 0.0))
    dimensionless_jacobian, input_scales, output_scales = scaled_jacobian(
        jacobian, means, stds, values, standard
    )

    functions = [sp.lambdify(symbols, expr, modules="numpy") for expr in expressions]
    simulation = monte_carlo(functions, means, covariance, samples, seed)
    mc_standard = np.asarray(simulation["std_uncertainty"], dtype=float)
    comparison = []
    for i, name in enumerate(output_names):
        denominator = standard[i]
        relative_difference = None
        if denominator > 0:
            relative_difference = float(abs(mc_standard[i] - denominator) / denominator)
        comparison.append(
            {
                "output": name,
                "linear_std_uncertainty": float(standard[i]),
                "monte_carlo_std_uncertainty": float(mc_standard[i]),
                "relative_difference": relative_difference,
                "diagnostic_flag_over_10_percent": (
                    relative_difference is not None and relative_difference > 0.10
                ),
            }
        )

    result: dict[str, Any] = {
        "variables": names,
        "correlations": correlations,
        "input_covariance": covariance.tolist(),
        "outputs": output_names,
        "expressions": {name: str(expr) for name, expr in zip(output_names, expressions)},
        "central_values": dict(zip(output_names, values.tolist())),
        "symbolic_jacobian": [
            [str(symbolic_jacobian[i, j]) for j in range(len(names))]
            for i in range(len(output_names))
        ],
        "numeric_jacobian": jacobian.tolist(),
        "output_covariance": output_covariance.tolist(),
        "linear_std_uncertainty": dict(zip(output_names, standard.tolist())),
        "jacobian_conditioning": {
            "dimensionless_jacobian": dimensionless_jacobian.tolist(),
            "input_scales": input_scales,
            "output_scales": output_scales,
            "condition_number": safe_condition_number(dimensionless_jacobian),
            "scale_rule": "absolute central value; standard uncertainty fallback; then 1",
        },
        "monte_carlo": simulation,
        "method_comparison": comparison,
        "warnings": [
            "Numerical inputs must already use coherent units.",
            "Monte Carlo sampling assumes a joint normal input distribution.",
            "Jacobian conditioning depends on the documented scaling convention.",
            "Propagation does not include unknown bias or model inadequacy.",
        ],
    }
    if len(output_names) == 1:
        result["sensitivity_budget"] = scalar_budget(
            names, means, stds, float(values[0]), jacobian[0], covariance
        )
    return result


def main() -> int:
    args = parse_args()
    try:
        report = calculate(load_spec(args.input), args.samples, args.seed)
    except (InputError, ValueError, TypeError, np.linalg.LinAlgError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=args.indent, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
