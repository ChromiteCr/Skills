#!/usr/bin/env python3
"""Propagate correlated standard uncertainties through symbolic models.

Input and output are JSON. Numerical inputs must use a coherent unit system.
Dependencies: sympy, numpy.

Every name in an output expression is a plain symbol and must be declared
under "variables". The only built-in constant is pi (write exp(1) for Euler's
number), and only the functions in ALLOWED_FUNCTIONS may be called. SymPy's
reserved names (E, I, S, N, Q, O, gamma, ...) are never given their SymPy
meaning, and Python reserved words (lambda, if, ...) are rejected by name.
Unknown JSON fields are input errors. Exit codes: 0 report, 2 input error;
--selftest exits 0 when all regression cases pass and 1 otherwise.
"""

from __future__ import annotations

import argparse
import difflib
import io
import json
import keyword
import math
import tokenize
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import auto_number, auto_symbol, convert_xor, parse_expr

TOP_LEVEL_FIELDS = ("variables", "correlations", "outputs")
VARIABLE_FIELDS = ("value", "std_uncertainty", "unit")
CORRELATION_FIELDS = ("a", "b", "rho")
ALLOWED_CONSTANTS: dict[str, Any] = {"pi": sp.pi}
ALLOWED_FUNCTIONS: dict[str, Any] = {
    "sqrt": sp.sqrt,
    "cbrt": sp.cbrt,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "atan2": sp.atan2,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "asinh": sp.asinh,
    "acosh": sp.acosh,
    "atanh": sp.atanh,
    "abs": sp.Abs,
    "Abs": sp.Abs,
    "erf": sp.erf,
    "erfc": sp.erfc,
}
PARSER_GLOBALS: dict[str, Any] = {
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Rational": sp.Rational,
    "Symbol": sp.Symbol,
    "Function": sp.Function,
}


class InputError(ValueError):
    """Raised when the input specification is incomplete or inconsistent."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", type=Path, nargs="?", help="JSON input specification")
    parser.add_argument("--samples", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--indent", type=int, default=2)
    parser.add_argument(
        "--selftest", action="store_true", help="run the built-in regression cases and exit"
    )
    args = parser.parse_args()
    if not args.selftest and args.input is None:
        parser.error("an input JSON file is required (or use --selftest)")
    return args


def reject_unknown_fields(obj: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
    for key in obj:
        if key in allowed:
            continue
        close = difflib.get_close_matches(str(key), allowed, n=1)
        hint = f"did you mean '{close[0]}'?" if close else f"allowed: {', '.join(allowed)}"
        raise InputError(f"{where} has unknown field {key!r} ({hint})")


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
    reject_unknown_fields(spec, TOP_LEVEL_FIELDS, "input")
    raw = spec.get("variables")
    if not isinstance(raw, dict) or not raw:
        raise InputError("variables must be a non-empty object")

    names = list(raw)
    if len(set(names)) != len(names):
        raise InputError("variable names must be unique")
    for name in names:
        if not isinstance(name, str) or not name.isidentifier():
            raise InputError(f"invalid variable name: {name!r}")
        if keyword.iskeyword(name):
            raise InputError(
                f"variable name {name!r} is a Python reserved word and cannot appear in an "
                "expression; rename it (for example 'lam' for lambda)"
            )

    means: list[float] = []
    stds: list[float] = []
    for name in names:
        item = raw[name]
        if not isinstance(item, dict):
            raise InputError(f"variables.{name} must be an object")
        reject_unknown_fields(item, VARIABLE_FIELDS, f"variables.{name}")
        if "unit" in item and not isinstance(item["unit"], str):
            raise InputError(f"variables.{name}.unit must be a string (a label only)")
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
        reject_unknown_fields(item, CORRELATION_FIELDS, f"correlations[{position}]")
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


def check_expression_names(source: str, output_name: str, declared: set[str]) -> None:
    """Reject every name that is not a declared variable, pi, or a called allowed function."""
    try:
        tokens = [
            token
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type
            not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT)
        ]
    except (tokenize.TokenError, SyntaxError) as exc:
        raise InputError(f"cannot parse outputs.{output_name}: {exc}") from exc

    undeclared: list[str] = []
    for position, token in enumerate(tokens):
        if token.type != tokenize.NAME:
            continue
        name = token.string
        called = position + 1 < len(tokens) and tokens[position + 1].string == "("
        if keyword.iskeyword(name):
            raise InputError(
                f"outputs.{output_name} uses the Python reserved word {name!r}; "
                "rename that variable (for example 'lam' for lambda)"
            )
        if name in declared:
            if called:
                raise InputError(
                    f"outputs.{output_name}: {name!r} is a declared variable and cannot be called as a function"
                )
        elif name in ALLOWED_FUNCTIONS:
            if not called:
                raise InputError(
                    f"outputs.{output_name}: {name!r} is a function and must be called, "
                    f"or declare {name!r} under variables"
                )
        elif name in ALLOWED_CONSTANTS:
            if called:
                raise InputError(f"outputs.{output_name}: constant {name!r} cannot be called")
        elif name not in undeclared:
            undeclared.append(name)
    if undeclared:
        raise InputError(
            f"outputs.{output_name} uses undeclared symbols: {', '.join(undeclared)}. "
            "Every name is a plain symbol and must be declared under variables; the only built-in "
            "constant is pi (write exp(1) for Euler's number). Allowed functions: "
            + ", ".join(sorted(ALLOWED_FUNCTIONS))
        )


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
        check_expression_names(source, output_name, set(names))
        # Declared variables come last so they shadow pi and the function names.
        namespace = {**ALLOWED_FUNCTIONS, **ALLOWED_CONSTANTS, **locals_map}
        try:
            expression = parse_expr(
                source,
                local_dict=namespace,
                global_dict=dict(PARSER_GLOBALS),
                transformations=(auto_symbol, auto_number, convert_xor),
            )
        except (sp.SympifyError, TypeError, SyntaxError, ValueError, tokenize.TokenError) as exc:
            raise InputError(f"cannot parse outputs.{output_name}: {exc}") from exc
        if not isinstance(expression, sp.Expr):
            raise InputError(f"outputs.{output_name} is not a numeric expression")
        unknown = expression.free_symbols - allowed_symbols
        undefined = expression.atoms(AppliedUndef)
        if unknown or undefined:
            raise InputError(
                f"outputs.{output_name} contains unknown symbols or functions: "
                + ", ".join(sorted(str(item) for item in unknown | undefined))
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
    central: list[float] = []
    for output_name, expr in zip(output_names, expressions):
        evaluated = expr.evalf(subs=substitutions)
        if not evaluated.is_real:
            raise InputError(
                f"outputs.{output_name} is not a real number at the central values ({evaluated}); "
                "check the domain, for example sqrt or log of a negative input"
            )
        central.append(float(evaluated))
    values = np.asarray(central)
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


def run_selftest() -> int:
    outcomes: list[tuple[str, bool, str]] = []

    def expect_error(name: str, spec: dict[str, Any], message_part: str) -> None:
        try:
            calculate(spec, 2000, 1)
        except InputError as exc:
            outcomes.append((name, message_part in str(exc), f"error={exc}"))
            return
        except Exception as exc:  # noqa: BLE001 - an unreadable crash is itself a failure
            outcomes.append((name, False, f"unexpected {type(exc).__name__}: {exc}"))
            return
        outcomes.append((name, False, "no input error raised"))

    def expect_value(name: str, spec: dict[str, Any], check: Any) -> None:
        try:
            report = calculate(spec, 20_000, 20260904)
        except Exception as exc:  # noqa: BLE001
            outcomes.append((name, False, f"unexpected {type(exc).__name__}: {exc}"))
            return
        outcomes.append((name, bool(check(report)), f"central={report['central_values']}, u={report['linear_std_uncertainty']}"))

    def one(x: float = 2.0, u: float = 0.1) -> dict[str, float]:
        return {"value": x, "std_uncertainty": u}

    pendulum = {
        "variables": {
            "L": {"value": 0.994, "std_uncertainty": 0.002},
            "T": {"value": 2.006, "std_uncertainty": 0.004},
        },
        "correlations": [{"a": "L", "b": "T", "rho": 0.25}],
        "outputs": {"g": "4*pi**2*L/T**2"},
    }

    def pendulum_ok(report: dict[str, Any]) -> bool:
        elasticity = {e["variable"]: e["elasticity"] for e in report["sensitivity_budget"]["entries"]}
        return (
            abs(report["central_values"]["g"] - 9.751788278914825) < 1e-9
            and abs(report["linear_std_uncertainty"]["g"] - 0.03893487075947634) < 1e-12
            and abs(elasticity["T"] + 2.0) < 1e-9
            and abs(elasticity["L"] - 1.0) < 1e-9
        )

    expect_value("documented pendulum example is unchanged (signed elasticity -2 for T)", pendulum, pendulum_ok)

    # Audit regressions: SymPy reserved names used to take their SymPy meaning or crash unreadably.
    expect_error("undeclared E is rejected, not Euler's number", {"variables": {"x": one()}, "outputs": {"y": "E*x"}}, "undeclared symbols: E")
    expect_error("undeclared I is rejected, not the imaginary unit", {"variables": {"R": one()}, "outputs": {"y": "I*R"}}, "undeclared symbols: I")
    expect_error("undeclared S is rejected with a readable message", {"variables": {"x": one()}, "outputs": {"y": "S*x"}}, "undeclared symbols: S")
    expect_error("undeclared gamma used as a name is rejected", {"variables": {"x": one()}, "outputs": {"y": "gamma*x"}}, "undeclared symbols: gamma")
    expect_error("unknown function is rejected", {"variables": {"x": one()}, "outputs": {"y": "foo(x)"}}, "undeclared symbols: foo")
    expect_error(
        "variable named lambda is rejected by name",
        {"variables": {"lambda": one(5e-7, 1e-9), "d": one(1e-3, 1e-5)}, "outputs": {"theta": "lambda/d"}},
        "reserved word",
    )
    expect_value(
        "declared E is a plain symbol (Young's modulus)",
        {"variables": {"E": one(2.0e11, 1.0e9), "strain": one(1.0e-3, 1.0e-5)}, "outputs": {"stress": "E*strain"}},
        lambda r: abs(r["central_values"]["stress"] - 2.0e8) < 1e-3,
    )
    expect_value(
        "declared lam with sqrt and exp(1) works",
        {"variables": {"lam": one(4.0, 0.1)}, "outputs": {"y": "sqrt(lam)*exp(1)"}},
        lambda r: abs(r["central_values"]["y"] - 2.0 * math.e) < 1e-12,
    )
    expect_value(
        "caret power is still accepted",
        {"variables": {"x": one()}, "outputs": {"y": "x^2"}},
        lambda r: abs(r["central_values"]["y"] - 4.0) < 1e-12,
    )
    expect_error("misspelled correlations key is rejected", {"variables": {"x": one(), "y": one(1.0)}, "correlation": [], "outputs": {"z": "x-y"}}, "did you mean 'correlations'")
    expect_error("unknown variable field is rejected", {"variables": {"x": {"value": 1.0, "uncertainty": 0.1}}, "outputs": {"y": "x"}}, "variables.x has unknown field")
    expect_error("complex central value is reported clearly", {"variables": {"x": one(-4.0)}, "outputs": {"y": "sqrt(x)"}}, "not a real number")
    expect_value(
        "correlated difference uses the covariance term",
        {
            "variables": {"x": one(), "y": one(1.0)},
            "correlations": [{"a": "x", "b": "y", "rho": 0.9}],
            "outputs": {"z": "x-y"},
        },
        lambda r: abs(r["linear_std_uncertainty"]["z"] - math.sqrt(0.002)) < 1e-12,
    )

    failed = 0
    for name, ok, detail in outcomes:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  [{detail}]"))
        failed += 0 if ok else 1
    print(f"selftest: {len(outcomes) - failed}/{len(outcomes)} passed")
    return 0 if failed == 0 else 1


def main() -> int:
    args = parse_args()
    if args.selftest:
        return run_selftest()
    try:
        report = calculate(load_spec(args.input), args.samples, args.seed)
    except (InputError, ValueError, TypeError, np.linalg.LinAlgError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=args.indent, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
