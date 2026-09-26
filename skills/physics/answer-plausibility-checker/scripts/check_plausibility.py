#!/usr/bin/env python3
"""Mechanical plausibility checks for one normalized physical result.

All compared values must already use the same unit. Standard library only.

Uncertainties are standard uncertainties (coverage factor k=1). Compatibility
with the reference is judged by z = |value - reference| / sqrt(u^2 + u_ref^2):
the check passes when z <= max_z (default 2). Unknown fields are input errors
(exit 2), so a misspelled key cannot silently switch a check off.

Exit codes: 0 no check failed, 1 at least one check failed, 2 invalid input.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import sys
from pathlib import Path
from typing import Any

TOP_LEVEL_FIELDS = (
    "value",
    "quantity",
    "unit",
    "conditions",
    "source",
    "notes",
    "bounds",
    "expected_range",
    "max_order_gap",
    "reference",
    "uncertainty",
    "reference_uncertainty",
    "max_z",
    "conservation",
)
TEXT_FIELDS = ("quantity", "unit", "conditions", "source", "notes")
NESTED_FIELDS = {
    "bounds": ("min", "max"),
    "expected_range": ("min", "max", "source", "checked"),
    "reference": ("value", "unit", "source", "checked"),
    "conservation": ("left", "right", "relative_tolerance"),
}
NESTED_TEXT_FIELDS = ("unit", "source", "checked")
MISPLACED_HINTS = {
    ("reference", "uncertainty"): "put the reference's standard uncertainty in top-level 'reference_uncertainty'",
}


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def result(name: str, status: str, detail: str) -> dict[str, Any]:
    return {"check": name, "status": status, "detail": detail}


def reject_unknown_fields(data: dict[str, Any]) -> None:
    problems: list[str] = []
    for key in data:
        if key not in TOP_LEVEL_FIELDS:
            hint = difflib.get_close_matches(str(key), TOP_LEVEL_FIELDS, n=1)
            suggestion = f" (did you mean '{hint[0]}'?)" if hint else ""
            problems.append(f"unknown field '{key}'{suggestion}")
    for field in TEXT_FIELDS:
        if field in data and not isinstance(data[field], str):
            problems.append(f"{field} must be a string")
    for parent, allowed in NESTED_FIELDS.items():
        block = data.get(parent)
        if not isinstance(block, dict):
            continue
        for key in block:
            if key in allowed:
                continue
            hint = MISPLACED_HINTS.get((parent, key))
            if hint is None:
                close = difflib.get_close_matches(str(key), allowed, n=1)
                hint = f"did you mean '{close[0]}'?" if close else f"allowed: {', '.join(allowed)}"
            problems.append(f"unknown field '{parent}.{key}' ({hint})")
        for key in NESTED_TEXT_FIELDS:
            if key in block and not isinstance(block[key], str):
                problems.append(f"{parent}.{key} must be a string")
    if problems:
        raise ValueError("; ".join(problems))


def inspect(data: dict[str, Any]) -> list[dict[str, Any]]:
    reject_unknown_fields(data)
    value = finite_number(data.get("value"), "value")
    checks: list[dict[str, Any]] = [result("finite_value", "pass", f"value={value:g}")]

    bounds = data.get("bounds")
    if bounds is not None:
        if not isinstance(bounds, dict) or not ({"min", "max"} & bounds.keys()):
            raise ValueError("bounds must contain min and/or max")
        low = finite_number(bounds["min"], "bounds.min") if "min" in bounds else None
        high = finite_number(bounds["max"], "bounds.max") if "max" in bounds else None
        if low is not None and high is not None and low > high:
            raise ValueError("bounds.min must not exceed bounds.max")
        passed = (low is None or value >= low) and (high is None or value <= high)
        checks.append(result("bounds", "pass" if passed else "fail", f"value={value:g}, min={low}, max={high}"))

    expected = data.get("expected_range")
    if expected is not None:
        if not isinstance(expected, dict) or "min" not in expected or "max" not in expected:
            raise ValueError("expected_range requires min and max")
        low = finite_number(expected["min"], "expected_range.min")
        high = finite_number(expected["max"], "expected_range.max")
        if low > high:
            raise ValueError("expected_range.min must not exceed expected_range.max")
        passed = low <= value <= high
        checks.append(result("expected_range", "pass" if passed else "fail", f"value={value:g}, range=[{low:g}, {high:g}]"))

    if "max_order_gap" in data and "reference" not in data:
        raise ValueError("max_order_gap only applies to the order-of-magnitude check, which needs reference.value")
    reference = data.get("reference")
    ref_value: float | None = None
    if reference is not None:
        if not isinstance(reference, dict) or "value" not in reference:
            raise ValueError("reference requires value")
        ref_value = finite_number(reference["value"], "reference.value")
        threshold = finite_number(data.get("max_order_gap", 1.0), "max_order_gap")
        if threshold < 0:
            raise ValueError("max_order_gap must be nonnegative")
        if value == 0 or ref_value == 0:
            detail = "order gap undefined because candidate or reference is zero"
            checks.append(result("order_of_magnitude", "not_run", detail))
        elif value * ref_value < 0:
            checks.append(result("order_of_magnitude", "fail", "candidate and reference have opposite signs"))
        else:
            ratio = abs(value / ref_value)
            gap = abs(math.log10(ratio))
            passed = gap <= threshold
            checks.append(result("order_of_magnitude", "pass" if passed else "fail", f"ratio={ratio:.6g}, order_gap={gap:.6g}, threshold={threshold:g}"))

    if "max_z" in data and "uncertainty" not in data and "reference_uncertainty" not in data:
        raise ValueError("max_z only applies to the uncertainty check, which needs uncertainty and reference_uncertainty")
    if "uncertainty" in data or "reference_uncertainty" in data:
        if ref_value is None or "uncertainty" not in data or "reference_uncertainty" not in data:
            raise ValueError("uncertainty compatibility requires reference.value, uncertainty, and reference_uncertainty")
        unc = finite_number(data["uncertainty"], "uncertainty")
        ref_unc = finite_number(data["reference_uncertainty"], "reference_uncertainty")
        if unc < 0 or ref_unc < 0:
            raise ValueError("uncertainties must be nonnegative")
        max_z = finite_number(data.get("max_z", 2.0), "max_z")
        if max_z <= 0:
            raise ValueError("max_z must be positive")
        difference = abs(value - ref_value)
        combined = math.hypot(unc, ref_unc)
        if combined == 0:
            checks.append(result(
                "uncertainty_compatibility",
                "not_run",
                f"both uncertainties are zero, so z is undefined (|value-reference|={difference:g}); give standard uncertainties",
            ))
        else:
            z = difference / combined
            status = "pass" if z <= max_z else "fail"
            item = result(
                "uncertainty_compatibility",
                status,
                f"z={z:.4g} (|value-reference|={difference:g}, combined standard uncertainty={combined:.6g}), "
                f"max_z={max_z:g}; uncertainties read as standard uncertainties (k=1)",
            )
            item["z"] = z
            checks.append(item)

    balance = data.get("conservation")
    if balance is not None:
        if not isinstance(balance, dict) or "left" not in balance or "right" not in balance:
            raise ValueError("conservation requires left and right arrays")
        if not isinstance(balance["left"], list) or not isinstance(balance["right"], list):
            raise ValueError("conservation.left and conservation.right must be arrays")
        left = sum(finite_number(v, f"conservation.left[{i}]") for i, v in enumerate(balance["left"]))
        right = sum(finite_number(v, f"conservation.right[{i}]") for i, v in enumerate(balance["right"]))
        tolerance = finite_number(balance.get("relative_tolerance", 1e-6), "conservation.relative_tolerance")
        if tolerance < 0:
            raise ValueError("conservation.relative_tolerance must be nonnegative")
        scale = max(abs(left), abs(right), 1e-30)
        relative_residual = abs(left - right) / scale
        passed = relative_residual <= tolerance
        checks.append(result("conservation_balance", "pass" if passed else "fail", f"left={left:g}, right={right:g}, relative_residual={relative_residual:.6g}, tolerance={tolerance:g}"))

    return checks


def run_selftest() -> int:
    outcomes: list[tuple[str, bool, str]] = []

    def status_of(checks: list[dict[str, Any]], name: str) -> str | None:
        return next((c["status"] for c in checks if c["check"] == name), None)

    def expect_status(name: str, data: dict[str, Any], check: str, status: str, detail_part: str = "") -> None:
        try:
            checks = inspect(data)
        except ValueError as exc:
            outcomes.append((name, False, f"unexpected input error: {exc}"))
            return
        got = status_of(checks, check)
        detail = next((c["detail"] for c in checks if c["check"] == check), "")
        ok = got == status and detail_part in detail
        outcomes.append((name, ok, f"{check} status={got}; detail={detail!r}"))

    def expect_error(name: str, data: dict[str, Any], message_part: str) -> None:
        try:
            inspect(data)
        except ValueError as exc:
            outcomes.append((name, message_part in str(exc), f"error={exc}"))
            return
        outcomes.append((name, False, "no input error raised"))

    documented = {
        "quantity": "launch speed",
        "value": 11200,
        "unit": "m/s",
        "bounds": {"min": 0},
        "expected_range": {"min": 1.0e4, "max": 1.3e4, "source": "source URL", "checked": "YYYY-MM-DD"},
        "reference": {"value": 11186, "unit": "m/s", "source": "source URL", "checked": "YYYY-MM-DD"},
        "max_order_gap": 1,
        "uncertainty": 50,
        "reference_uncertainty": 20,
        "max_z": 2,
        "conservation": {"left": [100.0, 5.0], "right": [103.0, 2.0], "relative_tolerance": 0.001},
    }
    try:
        doc_checks = inspect(documented)
        doc_ok = all(c["status"] == "pass" for c in doc_checks) and len(doc_checks) == 6
        outcomes.append(("documented example: six checks pass", doc_ok, str([(c["check"], c["status"]) for c in doc_checks])))
    except ValueError as exc:
        outcomes.append(("documented example: six checks pass", False, f"error={exc}"))

    # Audit regression: a 1.56-sigma difference used to fail because the +-u intervals do not overlap.
    g_case = {
        "value": 9.780,
        "uncertainty": 0.010,
        "reference": {"value": 9.802},
        "reference_uncertainty": 0.010,
    }
    expect_status("1.56 sigma difference is compatible at max_z=2", g_case, "uncertainty_compatibility", "pass", "z=1.556")
    expect_status("same difference fails at max_z=1.5", dict(g_case, max_z=1.5), "uncertainty_compatibility", "fail", "z=1.556")
    expect_status(
        "3.5 sigma difference fails at default max_z",
        dict(g_case, value=9.753),
        "uncertainty_compatibility",
        "fail",
        "z=3.465",
    )
    expect_status(
        "zero combined uncertainty is not_run",
        dict(g_case, uncertainty=0, reference_uncertainty=0),
        "uncertainty_compatibility",
        "not_run",
    )

    # Audit regression: a misspelled key used to be ignored and the run reported only PASS.
    expect_error("misspelled expected-range is an input error", {"value": 100, "expected-range": {"min": 1, "max": 2}}, "did you mean 'expected_range'")
    expect_status("expected_range out of range fails", {"value": 100, "expected_range": {"min": 1, "max": 2}}, "expected_range", "fail")
    expect_status("order gap 2 fails at default max_order_gap=1", {"value": 100, "reference": {"value": 1}}, "order_of_magnitude", "fail")
    expect_status("order gap 2 passes at max_order_gap=2.5", {"value": 100, "reference": {"value": 1}, "max_order_gap": 2.5}, "order_of_magnitude", "pass")
    expect_error("reference.uncertainty is an input error with a hint", dict(g_case, reference={"value": 9.802, "uncertainty": 0.01}), "reference_uncertainty")
    expect_error("unknown bounds key is an input error", {"value": 1, "bounds": {"min": 0, "maximum": 5}}, "bounds.maximum")
    expect_error("uncertainty without a reference is an input error", {"value": 1, "uncertainty": 0.1}, "requires reference.value")
    expect_error("max_z without uncertainties is an input error", {"value": 1, "reference": {"value": 1}, "max_z": 2}, "max_z only applies")

    failed = 0
    for name, ok, detail in outcomes:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  [{detail}]"))
        failed += 0 if ok else 1
    print(f"selftest: {len(outcomes) - failed}/{len(outcomes)} passed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, nargs="?", help="JSON input record")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()
    if args.input is None:
        parser.error("an input JSON file is required (or use --selftest)")

    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("input root must be an object")
        checks = inspect(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
    else:
        for check in checks:
            print(f"{check['status'].upper():7} {check['check']}: {check['detail']}")

    return 1 if any(check["status"] == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
