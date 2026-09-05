#!/usr/bin/env python3
"""Mechanical plausibility checks for one normalized physical result.

All compared values must already use the same unit. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def result(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def inspect(data: dict[str, Any]) -> list[dict[str, str]]:
    value = finite_number(data.get("value"), "value")
    checks: list[dict[str, str]] = [result("finite_value", "pass", f"value={value:g}")]

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

    reference = data.get("reference")
    ref_value: float | None = None
    if reference is not None:
        if not isinstance(reference, dict) or "value" not in reference:
            raise ValueError("reference requires value")
        ref_value = finite_number(reference["value"], "reference.value")
        if value == 0 or ref_value == 0:
            detail = "order gap undefined because candidate or reference is zero"
            checks.append(result("order_of_magnitude", "not_run", detail))
        elif value * ref_value < 0:
            checks.append(result("order_of_magnitude", "fail", "candidate and reference have opposite signs"))
        else:
            ratio = abs(value / ref_value)
            gap = abs(math.log10(ratio))
            threshold = finite_number(data.get("max_order_gap", 1.0), "max_order_gap")
            if threshold < 0:
                raise ValueError("max_order_gap must be nonnegative")
            passed = gap <= threshold
            checks.append(result("order_of_magnitude", "pass" if passed else "fail", f"ratio={ratio:.6g}, order_gap={gap:.6g}, threshold={threshold:g}"))

    if "uncertainty" in data or "reference_uncertainty" in data:
        if ref_value is None or "uncertainty" not in data or "reference_uncertainty" not in data:
            raise ValueError("uncertainty overlap requires reference.value, uncertainty, and reference_uncertainty")
        unc = finite_number(data["uncertainty"], "uncertainty")
        ref_unc = finite_number(data["reference_uncertainty"], "reference_uncertainty")
        if unc < 0 or ref_unc < 0:
            raise ValueError("uncertainties must be nonnegative")
        overlap = max(value - unc, ref_value - ref_unc) <= min(value + unc, ref_value + ref_unc)
        checks.append(result("uncertainty_overlap", "pass" if overlap else "fail", f"candidate=[{value-unc:g}, {value+unc:g}], reference=[{ref_value-ref_unc:g}, {ref_value+ref_unc:g}]"))

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON input record")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("input root must be an object")
        checks = inspect(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
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
