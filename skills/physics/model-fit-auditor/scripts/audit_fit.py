#!/usr/bin/env python3
"""First-pass, dependency-free diagnostics for fitted numeric data.

Input and output are JSON. This helper does not fit a model and does not decide
whether observations should be excluded.

Leverage and Cook's distance come from a Householder QR factorization with
column pivoting. When the design matrix has a constant (intercept) column, the
other columns are centered first, which leaves the column space and therefore
the leverages unchanged; every column is then scaled to unit norm. The rank is
decided with a relative tolerance, so SI-small regressors (1e-7 m) and large
offsets (Unix epoch seconds) give the same leverages as rescaled data. The
leverages must sum to the rank; if they do not, leverage is withheld.

Exit codes: 0 diagnostics written (read "warnings"); 2 input error.
--selftest exits 0 when all regression cases pass and 1 otherwise.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

ALLOWED_FIELDS = ("observed", "predicted", "parameter_count", "sigma", "variables", "design_matrix")
EPSILON = sys.float_info.epsilon
LEVERAGE_ERROR_LIMIT = 1e-3


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


def prepared_columns(rows: list[list[float]]) -> tuple[list[list[float]], bool, float]:
    """Center non-constant columns when an intercept column exists, then scale to unit norm.

    Both steps keep the column space, so the hat matrix and the leverages are unchanged.
    Also return how much a rounding error in the raw values is magnified relative to the
    prepared column (large when a big offset was removed, e.g. squared epoch seconds).
    """
    columns = [[row[j] for row in rows] for j in range(len(rows[0]))]
    has_intercept = any(col[0] != 0.0 and all(value == col[0] for value in col) for col in columns)
    n = len(rows)
    prepared: list[list[float]] = []
    magnification = 1.0
    for col in columns:
        largest = max(abs(value) for value in col)
        if has_intercept and not all(value == col[0] for value in col):
            center = math.fsum(col) / len(col)
            col = [value - center for value in col]
        norm = math.sqrt(math.fsum(value * value for value in col))
        if norm > 0:
            magnification = max(magnification, largest * math.sqrt(n) / norm)
            prepared.append([value / norm for value in col])
        else:
            prepared.append(col[:])
    return prepared, has_intercept, magnification


def orthonormal_basis(columns: list[list[float]]) -> tuple[list[list[float]], int, float | None]:
    """Householder QR with column pivoting; return Q's first `rank` columns, the rank, and |R11|/|Rrr|."""
    n, p = len(columns[0]), len(columns)
    work = [col[:] for col in columns]
    reflectors: list[list[float]] = []
    diagonal: list[float] = []
    for k in range(p):
        norms = [math.sqrt(math.fsum(value * value for value in work[j][k:])) for j in range(k, p)]
        best = k + max(range(len(norms)), key=norms.__getitem__)
        work[k], work[best] = work[best], work[k]
        x = work[k][k:]
        alpha = norms[best - k]
        if alpha == 0.0:
            diagonal.append(0.0)
            reflectors.append([0.0] * (n - k))
            continue
        alpha = -alpha if x[0] > 0 else alpha
        v = x[:]
        v[0] -= alpha
        v_norm = math.sqrt(math.fsum(value * value for value in v))
        v = [value / v_norm for value in v] if v_norm > 0 else [0.0] * len(v)
        reflectors.append(v)
        diagonal.append(abs(alpha))
        for j in range(k + 1, p):
            tail = work[j][k:]
            dot = math.fsum(a * b for a, b in zip(v, tail))
            work[j][k:] = [t - 2.0 * dot * a for a, t in zip(v, tail)]

    largest = diagonal[0] if diagonal else 0.0
    tolerance = max(n, p) * EPSILON * largest
    rank = 0
    for value in diagonal:
        if value <= tolerance:
            break
        rank += 1

    basis: list[list[float]] = []
    for j in range(rank):
        q = [0.0] * n
        q[j] = 1.0
        for k in range(rank - 1, -1, -1):
            v = reflectors[k]
            dot = math.fsum(a * b for a, b in zip(v, q[k:]))
            q[k:] = [t - 2.0 * dot * a for a, t in zip(v, q[k:])]
        basis.append(q)
    condition = largest / diagonal[rank - 1] if rank else None
    return basis, rank, condition


def influence(design: Any, residuals: list[float], warnings: list[str]) -> dict[str, Any]:
    n = len(residuals)
    if not isinstance(design, list) or len(design) != n or not design:
        fail(f"design_matrix must contain {n} rows")
    rows = [numeric_vector(row, f"design_matrix[{i}]") for i, row in enumerate(design)]
    p = len(rows[0])
    if p == 0 or any(len(row) != p for row in rows):
        fail("design_matrix must be rectangular and non-empty")
    if n <= p: fail("design_matrix requires more rows than columns")

    columns, centered, magnification = prepared_columns(rows)
    basis, rank, condition = orthonormal_basis(columns)
    method = "Householder QR with column pivoting on unit-norm columns" + (
        "; non-constant columns centered because an intercept column is present" if centered else ""
    )
    result: dict[str, Any] = {
        "assumption": "ordinary least-squares linear-model approximation",
        "method": method,
        "design_columns": p,
        "rank": rank,
        "condition_estimate": condition,
    }
    if rank == 0:
        warnings.append("design_matrix has no nonzero column; leverage and Cook's distance were not computed")
        return result
    if rank < p:
        warnings.append(
            f"design_matrix has numerical rank {rank} but {p} columns (collinear or duplicate columns); "
            f"leverage is the projection onto the {rank}-dimensional column space and Cook's distance uses {rank} parameters"
        )
    error_bound = (condition or 1.0) * EPSILON * magnification
    result["leverage_error_bound"] = error_bound
    if error_bound > LEVERAGE_ERROR_LIMIT:
        warnings.append(
            f"leverage and Cook's distance withheld: rounding error in the design matrix could change them by about "
            f"{error_bound:.2g} (condition estimate {condition:.3g} after centering and scaling). Large offsets in "
            "polynomial columns (for example squared epoch seconds) lose precision before this script sees them; "
            "subtract a reference value from the predictor before building the design matrix"
        )
        return result

    leverage = [math.fsum(q[i] * q[i] for q in basis) for i in range(n)]
    leverage_sum = math.fsum(leverage)
    result["leverage_sum"] = leverage_sum
    if abs(leverage_sum - rank) > 1e-9 * max(1, n):
        warnings.append(
            f"internal check failed: leverage sums to {leverage_sum:.12g}, not the rank {rank}; "
            "leverage and Cook's distance withheld"
        )
        return result

    mse = sum(r * r for r in residuals) / (n - rank)
    if mse == 0:
        cooks = [0.0 for _ in residuals]
    else:
        cooks = [
            (r * r / (rank * mse)) * (h / ((1.0 - h) ** 2)) if h < 1.0 - 1e-12 else None
            for r, h in zip(residuals, leverage)
        ]
    result["leverage"] = leverage
    result["cooks_distance"] = cooks
    result["review_heuristics"] = {"leverage_gt": 2.0 * rank / n, "cooks_distance_gt": 4.0 / n}
    return result


def audit(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        fail("input must be a JSON object")
    for key in data:
        if key not in ALLOWED_FIELDS:
            close = difflib.get_close_matches(str(key), ALLOWED_FIELDS, n=1)
            hint = f"did you mean '{close[0]}'?" if close else f"allowed: {', '.join(ALLOWED_FIELDS)}"
            fail(f"unknown field {key!r} ({hint})")
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
        result["influence"] = influence(data["design_matrix"], residuals, result["warnings"])
    else:
        result["warnings"].append("design_matrix absent; leverage and influence were not computed")

    return result


def run_selftest() -> int:
    outcomes: list[tuple[str, bool, str]] = []

    def check(name: str, func) -> None:  # type: ignore[no-untyped-def]
        try:
            ok, detail = func()
        except Exception as exc:  # noqa: BLE001 - a crash is a failed case
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        outcomes.append((name, ok, detail))

    def straight_line_case(xs: list[float]) -> dict[str, Any]:
        n = len(xs)
        observed = [0.5 + 0.001 * i + (0.01 if i % 3 == 0 else -0.005) for i in range(n)]
        predicted = [0.5 + 0.001 * i for i in range(n)]
        return {"observed": observed, "predicted": predicted, "parameter_count": 2, "design_matrix": [[1.0, x] for x in xs]}

    def exact_first_leverage(n: int) -> float:
        # Equally spaced x with an intercept: h_1 = 1/n + (x_1 - mean)^2 / Sxx.
        center = (n - 1) / 2
        return 1.0 / n + center**2 / sum((i - center) ** 2 for i in range(n))

    def leverage_case(name: str, xs: list[float], expected_first: float) -> None:
        def run() -> tuple[bool, str]:
            report = audit(straight_line_case(xs))
            inf = report["influence"]
            lev = inf["leverage"]
            ok = abs(lev[0] - expected_first) < 1e-9 and abs(math.fsum(lev) - 2.0) < 1e-9 and inf["rank"] == 2
            return ok, f"leverage[0]={lev[0]}, sum={math.fsum(lev)}, expected {expected_first}"

        check(name, run)

    # Audit regressions: epoch-second regressors gave wrong leverages at n=8 and "rank-deficient" at n>=10.
    for n in (8, 12, 50):
        leverage_case(
            f"epoch-second regressor, n={n}: exact leverage and sum 2",
            [1758700000.0 + i for i in range(n)],
            exact_first_leverage(n),
        )

    # Audit regression: wavelengths in metres were reported as rank-deficient (exit 2).
    def si_small_case() -> tuple[bool, str]:
        metres = [(400 + 30 * i) * 1e-9 for i in range(11)]
        in_m = audit(straight_line_case(metres))["influence"]["leverage"]
        in_nm = audit(straight_line_case([x * 1e9 for x in metres]))["influence"]["leverage"]
        ok = all(abs(a - b) < 1e-12 for a, b in zip(in_m, in_nm)) and abs(in_m[0] - exact_first_leverage(11)) < 1e-9
        return ok, f"m={in_m[:2]}, nm={in_nm[:2]}"

    check("SI-small regressor in metres matches nanometres", si_small_case)

    def no_intercept_small_case() -> tuple[bool, str]:
        lam = [(400 + 30 * i) * 1e-9 for i in range(11)]
        report = audit({
            "observed": [float(i) for i in range(11)],
            "predicted": [float(i) + 0.1 * (-1) ** i for i in range(11)],
            "parameter_count": 2,
            "design_matrix": [[x, x * x] for x in lam],
        })
        inf = report["influence"]
        return inf["rank"] == 2 and abs(inf["leverage_sum"] - 2.0) < 1e-9, json.dumps(inf)[:200]

    check("no-intercept design with metres and metres squared has rank 2", no_intercept_small_case)

    def rounded_polynomial_case() -> tuple[bool, str]:
        # (epoch seconds)^2 is already rounded in the input, so the quadratic column carries no usable
        # information; the exact leverage of the intended design is 0.5467, the rounded one is far off.
        xs = [1758700000.0 + i for i in range(12)]
        report = audit({**straight_line_case(xs), "parameter_count": 3, "design_matrix": [[1.0, x, x * x] for x in xs]})
        inf = report["influence"]
        ok = "leverage" not in inf and any("withheld" in w for w in report["warnings"])
        return ok, json.dumps(inf)[:200]

    check("quadratic column in raw epoch seconds: leverage withheld, not silently wrong", rounded_polynomial_case)

    def cooks_formula_case() -> tuple[bool, str]:
        data = {
            "observed": [1.0, 2.2, 2.9, 4.1, 6.0],
            "predicted": [1.0, 2.0, 3.0, 4.0, 5.0],
            "parameter_count": 2,
            "design_matrix": [[1.0, float(i)] for i in range(5)],
        }
        inf = audit(data)["influence"]
        residuals = [0.0, 0.2, -0.1, 0.1, 1.0]
        leverage = [1 / 5 + (i - 2) ** 2 / 10 for i in range(5)]
        mse = sum(r * r for r in residuals) / 3
        expected = [(r * r / (2 * mse)) * h / (1 - h) ** 2 for r, h in zip(residuals, leverage)]
        ok = all(abs(a - b) < 1e-12 for a, b in zip(inf["cooks_distance"], expected))
        return ok, f"got {inf['cooks_distance']}, expected {expected}"

    check("Cook's distance matches the textbook formula", cooks_formula_case)

    def scores_case() -> tuple[bool, str]:
        data = {"observed": [1.0, 2.1, 2.9], "predicted": [1.1, 2.0, 3.0], "parameter_count": 2, "sigma": [0.1, 0.1, 0.2]}
        report = audit(data)
        rss = 0.01 + 0.01 + 0.01
        scores = report["gaussian_common_variance_scores"]
        chi = report["uncertainty_diagnostics"]
        ok = (
            abs(scores["aic_without_shared_constant"] - (3 * math.log(rss / 3) + 4)) < 1e-12
            and abs(scores["bic_without_shared_constant"] - (3 * math.log(rss / 3) + 2 * math.log(3))) < 1e-12
            and abs(chi["chi_square"] - 2.25) < 1e-12
            and abs(chi["reduced_chi_square"] - 2.25) < 1e-12
        )
        return ok, json.dumps({"scores": scores, "chi": chi["chi_square"]})

    check("documented minimal input: AIC, BIC and chi-square by formula", scores_case)

    def collinear_case() -> tuple[bool, str]:
        report = audit({
            "observed": [1.0, 2.0, 3.1, 3.9],
            "predicted": [1.0, 2.0, 3.0, 4.0],
            "parameter_count": 1,
            "design_matrix": [[float(i), 2.0 * i] for i in range(1, 5)],
        })
        inf = report["influence"]
        ok = inf["rank"] == 1 and abs(inf["leverage_sum"] - 1.0) < 1e-9 and any("numerical rank 1" in w for w in report["warnings"])
        return ok, json.dumps(inf)[:200]

    check("truly collinear columns: rank 1 with a warning, other diagnostics kept", collinear_case)

    def expect_error(name: str, data: dict[str, Any], message_part: str) -> None:
        def run() -> tuple[bool, str]:
            try:
                audit(data)
            except ValueError as exc:
                return message_part in str(exc), str(exc)
            return False, "no error raised"

        check(name, run)

    expect_error(
        "ragged design matrix is an input error",
        {"observed": [1.0, 2.0, 3.0], "predicted": [1.0, 2.0, 3.0], "parameter_count": 1, "design_matrix": [[1.0], [1.0, 2.0], [1.0]]},
        "rectangular",
    )
    expect_error(
        "misspelled sigma key is an input error",
        {"observed": [1.0, 2.0, 3.0], "predicted": [1.0, 2.0, 3.0], "parameter_count": 1, "sigmas": [0.1, 0.1, 0.1]},
        "did you mean 'sigma'",
    )

    def help_case() -> tuple[bool, str]:
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--help"], capture_output=True, text=True)
        return proc.returncode == 0 and "usage:" in proc.stdout, f"exit={proc.returncode}, stderr={proc.stderr[:120]!r}"

    check("--help prints usage and exits 0", help_case)

    failed = 0
    for name, ok, detail in outcomes:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  [{detail}]"))
        failed += 0 if ok else 1
    print(f"selftest: {len(outcomes) - failed}/{len(outcomes)} passed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, nargs="?", help="fit JSON: observed, predicted, parameter_count; optional sigma, variables, design_matrix")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = parser.parse_args()
    if args.selftest:
        return run_selftest()
    if args.input is None:
        parser.error("an input JSON file is required (or use --selftest)")
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        print(json.dumps(audit(data), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
