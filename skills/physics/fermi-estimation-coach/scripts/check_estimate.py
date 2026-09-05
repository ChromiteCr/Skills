#!/usr/bin/env python3
"""Validate a structured Fermi-estimate worksheet using only the standard library."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROLES = {"dominant", "secondary", "negligible"}
EVIDENCE = {"measured", "sourced", "derived", "assumed"}
METHODS = {"sum", "max", "product"}


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def close(actual: float, expected: float, tolerance: float) -> bool:
    scale = max(abs(actual), abs(expected), 1e-300)
    return abs(actual - expected) <= tolerance * scale


def validate_range(obj: Any, path: str, errors: list[str]) -> tuple[float, float, float] | None:
    if not isinstance(obj, dict):
        errors.append(f"{path}: expected an object")
        return None
    values: list[float] = []
    for key in ("low", "central", "high"):
        value = obj.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}.{key}: expected a number")
            return None
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            errors.append(f"{path}.{key}: expected a finite positive number")
            return None
        values.append(number)
    low, central, high = values
    if not low <= central <= high:
        errors.append(f"{path}: expected low <= central <= high")
    return low, central, high


def require_text(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    if not is_text(obj.get(key)):
        errors.append(f"{path}.{key}: expected a non-empty string")


def compare_range(actual: tuple[float, float, float] | None,
                  expected: tuple[float, float, float], path: str,
                  tolerance: float, errors: list[str]) -> None:
    if actual is None:
        return
    for label, got, want in zip(("low", "central", "high"), actual, expected):
        if not close(got, want, tolerance):
            errors.append(f"{path}.{label}: {got:g} does not match calculated {want:g} "
                          f"within {tolerance:.1%}")


def check_document(data: Any, tolerance: float) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root: expected a JSON object"]

    target = data.get("target")
    if not isinstance(target, dict):
        errors.append("target: expected an object")
        target_unit = None
    else:
        require_text(target, "name", "target", errors)
        require_text(target, "unit", "target", errors)
        target_unit = target.get("unit")

    mechanisms = data.get("mechanisms")
    if not isinstance(mechanisms, list) or not mechanisms:
        errors.append("mechanisms: expected a non-empty array")
        mechanisms = []

    mechanism_ids: set[str] = set()
    mechanism_ranges: dict[str, tuple[float, float, float]] = {}
    mechanism_roles: dict[str, str] = {}

    for index, mechanism in enumerate(mechanisms):
        path = f"mechanisms[{index}]"
        if not isinstance(mechanism, dict):
            errors.append(f"{path}: expected an object")
            continue
        mechanism_id = mechanism.get("id")
        if not is_text(mechanism_id):
            errors.append(f"{path}.id: expected a non-empty string")
            mechanism_id = f"<invalid-{index}>"
        elif mechanism_id in mechanism_ids:
            errors.append(f"{path}.id: duplicate mechanism ID {mechanism_id!r}")
        mechanism_ids.add(mechanism_id)

        role = mechanism.get("role")
        if role not in ROLES:
            errors.append(f"{path}.role: expected one of {sorted(ROLES)}")
        else:
            mechanism_roles[mechanism_id] = role
        require_text(mechanism, "provenance", path, errors)

        factors = mechanism.get("factors")
        if not isinstance(factors, list) or not factors:
            errors.append(f"{path}.factors: expected a non-empty array")
            factors = []
        factor_ranges: dict[str, tuple[float, float, float]] = {}
        factor_ids: set[str] = set()
        for factor_index, factor in enumerate(factors):
            factor_path = f"{path}.factors[{factor_index}]"
            if not isinstance(factor, dict):
                errors.append(f"{factor_path}: expected an object")
                continue
            factor_id = factor.get("id")
            if not is_text(factor_id):
                errors.append(f"{factor_path}.id: expected a non-empty string")
                continue
            if factor_id in factor_ids:
                errors.append(f"{factor_path}.id: duplicate factor ID {factor_id!r}")
            factor_ids.add(factor_id)
            require_text(factor, "name", factor_path, errors)
            require_text(factor, "unit", factor_path, errors)
            require_text(factor, "basis", factor_path, errors)
            if factor.get("evidence_status") not in EVIDENCE:
                errors.append(f"{factor_path}.evidence_status: expected one of {sorted(EVIDENCE)}")
            factor_range = validate_range(factor, factor_path, errors)
            if factor_range:
                factor_ranges[factor_id] = factor_range

        calculation = mechanism.get("calculation")
        calculated: tuple[float, float, float] | None = None
        if not isinstance(calculation, dict):
            errors.append(f"{path}.calculation: expected an object")
        else:
            coefficient = calculation.get("coefficient", 1)
            if (isinstance(coefficient, bool) or not isinstance(coefficient, (int, float))
                    or not math.isfinite(float(coefficient)) or coefficient <= 0):
                errors.append(f"{path}.calculation.coefficient: expected a finite positive number")
            else:
                multiply = calculation.get("multiply")
                divide = calculation.get("divide")
                if not isinstance(multiply, list) or not multiply:
                    errors.append(f"{path}.calculation.multiply: expected a non-empty array")
                    multiply = []
                if not isinstance(divide, list):
                    errors.append(f"{path}.calculation.divide: expected an array")
                    divide = []
                listed = multiply + divide
                invalid_ids = [item for item in listed if not is_text(item)]
                valid_ids = [item for item in listed if is_text(item)]
                if invalid_ids:
                    errors.append(f"{path}.calculation: all factor IDs must be non-empty strings")
                if len(valid_ids) != len(set(valid_ids)):
                    errors.append(f"{path}.calculation: factor IDs must not repeat")
                unknown = [item for item in valid_ids if item not in factor_ranges]
                if unknown:
                    errors.append(f"{path}.calculation: unknown or invalid factor IDs {unknown}")
                unused = factor_ids - set(valid_ids)
                if unused:
                    errors.append(f"{path}.calculation: unused factor IDs {sorted(unused)}")
                if not invalid_ids and not unknown and multiply:
                    c = float(coefficient)
                    low = central = high = c
                    for factor_id in multiply:
                        f_low, f_central, f_high = factor_ranges[factor_id]
                        low *= f_low
                        central *= f_central
                        high *= f_high
                    for factor_id in divide:
                        f_low, f_central, f_high = factor_ranges[factor_id]
                        low /= f_high
                        central /= f_central
                        high /= f_low
                    calculated = (low, central, high)

        estimate = mechanism.get("estimate")
        estimate_range = validate_range(estimate, f"{path}.estimate", errors)
        if isinstance(estimate, dict):
            require_text(estimate, "unit", f"{path}.estimate", errors)
            if target_unit and estimate.get("unit") != target_unit:
                errors.append(f"{path}.estimate.unit: must equal target unit {target_unit!r}")
        if calculated:
            compare_range(estimate_range, calculated, f"{path}.estimate", tolerance, errors)
        if estimate_range:
            mechanism_ranges[mechanism_id] = estimate_range

        reference = mechanism.get("reference_range")
        if reference is not None:
            reference_path = f"{path}.reference_range"
            if not isinstance(reference, dict):
                errors.append(f"{reference_path}: expected an object")
            else:
                low = reference.get("low")
                high = reference.get("high")
                valid = True
                for key, value in (("low", low), ("high", high)):
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(float(value)) or value <= 0):
                        errors.append(f"{reference_path}.{key}: expected a finite positive number")
                        valid = False
                require_text(reference, "unit", reference_path, errors)
                if isinstance(estimate, dict) and reference.get("unit") != estimate.get("unit"):
                    errors.append(f"{reference_path}.unit: must equal mechanism estimate unit")
                if valid and low > high:
                    errors.append(f"{reference_path}: expected low <= high")
                if valid and estimate_range and (estimate_range[2] < low or estimate_range[0] > high):
                    errors.append(f"{reference_path}: estimate range does not overlap reference range")

    synthesis = data.get("synthesis")
    if not isinstance(synthesis, dict):
        errors.append("synthesis: expected an object")
        return errors
    method = synthesis.get("method")
    if method not in METHODS:
        errors.append(f"synthesis.method: expected one of {sorted(METHODS)}")
    included = synthesis.get("included_mechanism_ids")
    if not isinstance(included, list) or not included:
        errors.append("synthesis.included_mechanism_ids: expected a non-empty array")
        included = []
    invalid_included = [item for item in included if not is_text(item)]
    valid_included = [item for item in included if is_text(item)]
    if invalid_included:
        errors.append("synthesis.included_mechanism_ids: all IDs must be non-empty strings")
    if len(valid_included) != len(set(valid_included)):
        errors.append("synthesis.included_mechanism_ids: IDs must not repeat")
    unknown = [item for item in valid_included if item not in mechanism_ranges]
    if unknown:
        errors.append(f"synthesis.included_mechanism_ids: unknown or invalid IDs {unknown}")
    required = {mid for mid, role in mechanism_roles.items() if role != "negligible"}
    omitted = required - set(valid_included)
    if omitted:
        errors.append(f"synthesis: omitted non-negligible mechanisms {sorted(omitted)}")
    require_text(synthesis, "decision", "synthesis", errors)

    synthesis_estimate = synthesis.get("estimate")
    synthesis_range = validate_range(synthesis_estimate, "synthesis.estimate", errors)
    if isinstance(synthesis_estimate, dict):
        require_text(synthesis_estimate, "unit", "synthesis.estimate", errors)
        if target_unit and synthesis_estimate.get("unit") != target_unit:
            errors.append(f"synthesis.estimate.unit: must equal target unit {target_unit!r}")

    if method in METHODS and valid_included and not invalid_included and not unknown:
        ranges = [mechanism_ranges[item] for item in valid_included]
        if method == "sum":
            expected = tuple(sum(values) for values in zip(*ranges))
        elif method == "max":
            expected = tuple(max(values) for values in zip(*ranges))
        else:
            expected_list = [1.0, 1.0, 1.0]
            for values in ranges:
                expected_list = [a * b for a, b in zip(expected_list, values)]
            expected = tuple(expected_list)
        compare_range(synthesis_range, expected, "synthesis.estimate", tolerance, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", type=Path, help="JSON worksheet to validate")
    parser.add_argument("--tolerance", type=float, default=0.05,
                        help="relative arithmetic tolerance (default: 0.05)")
    args = parser.parse_args()
    if not 0 <= args.tolerance < 1:
        parser.error("--tolerance must be at least 0 and less than 1")
    try:
        data = json.loads(args.worksheet.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read worksheet: {exc}", file=sys.stderr)
        return 2
    errors = check_document(data, args.tolerance)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAIL: {len(errors)} issue(s)")
        return 1
    print("PASS: estimate worksheet is structurally and arithmetically consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
