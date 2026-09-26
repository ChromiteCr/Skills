#!/usr/bin/env python3
"""Validate a structured Fermi-estimate worksheet using only the standard library.

Usage:
    python3 check_estimate.py estimate.json [--tolerance 0.05]
    python3 check_estimate.py --selftest

Exit status: 0 the worksheet passes; 1 validation errors (listed on stdout);
2 the file cannot be read or the arguments are wrong.

The worksheet format is described in ../references/estimate-schema.md. Unknown
keys are errors, because a misspelt optional key would otherwise switch its check
off silently. For a `product` synthesis the included mechanism units are
multiplied and must equal the target unit; SI coherent derived units (N, J, W,
Pa, Hz, C, V, F, ohm, S, Wb, T, H) are expanded to base units, and any other
symbol (kW, h, yr, people) is kept as its own unit, so convert first.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROLES = {"dominant", "secondary", "negligible"}
EVIDENCE = {"measured", "sourced", "derived", "assumed"}
METHODS = {"sum", "max", "product"}

ALLOWED_KEYS = {
    "root": {"target", "mechanisms", "synthesis"},
    "target": {"name", "unit"},
    "mechanism": {"id", "role", "provenance", "factors", "calculation", "estimate", "reference_range"},
    "factor": {"id", "name", "unit", "low", "central", "high", "evidence_status", "basis"},
    "calculation": {"coefficient", "multiply", "divide"},
    "estimate": {"low", "central", "high", "unit"},
    "reference_range": {"low", "high", "unit"},
    "synthesis": {"method", "included_mechanism_ids", "estimate", "decision"},
}

SI_BASE = ("kg", "m", "s", "A", "K", "mol", "cd")
SI_DERIVED = {
    "Hz": {"s": -1},
    "N": {"kg": 1, "m": 1, "s": -2},
    "Pa": {"kg": 1, "m": -1, "s": -2},
    "J": {"kg": 1, "m": 2, "s": -2},
    "W": {"kg": 1, "m": 2, "s": -3},
    "C": {"A": 1, "s": 1},
    "V": {"kg": 1, "m": 2, "s": -3, "A": -1},
    "F": {"kg": -1, "m": -2, "s": 4, "A": 2},
    "ohm": {"kg": 1, "m": 2, "s": -3, "A": -2},
    "\u03a9": {"kg": 1, "m": 2, "s": -3, "A": -2},
    "S": {"kg": -1, "m": -2, "s": 3, "A": 2},
    "Wb": {"kg": 1, "m": 2, "s": -2, "A": -1},
    "T": {"kg": 1, "s": -2, "A": -1},
    "H": {"kg": 1, "m": 2, "s": -2, "A": -2},
}
SUPERSCRIPT_DIGITS = str.maketrans("\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207b\u207a",
                                   "0123456789-+")
UNIT_TOKEN = re.compile(r"(?P<name>[^\W\d][\w\u00b0%']*|\u00b0\w+|%)(?:(?:\^|\*\*)(?P<exp>[+-]?\d+))?")


class UnitError(ValueError):
    """A unit string that the product composition cannot read."""


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_one_of(value: Any, allowed: set[str]) -> bool:
    """Membership test that cannot raise on lists or objects."""
    return isinstance(value, str) and value in allowed


def positive_number(value: Any) -> float | None:
    """Return a finite positive float, or None (bools, huge integers and NaN are rejected)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and number > 0 else None


def check_keys(obj: dict[str, Any], kind: str, path: str, errors: list[str]) -> None:
    unknown = sorted(set(obj) - ALLOWED_KEYS[kind])
    if unknown:
        errors.append(f"{path}: unknown key(s) {unknown}; allowed: {sorted(ALLOWED_KEYS[kind])}")


def parse_unit(text: str) -> dict[str, int]:
    """Read 'W m^-2 K^-1', 'm/s^2', 'W/(m^2 K)', 's⁻¹' or '1' into base-unit exponents."""
    raw = text.strip()
    for run in re.findall(r"[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207a\u207b]+", raw):
        raw = raw.replace(run, "^" + run.translate(SUPERSCRIPT_DIGITS), 1)
    raw = unicodedata.normalize("NFKC", raw).replace("**", "^")
    for separator in ("\u00b7", "\u22c5", "*", "\u00d7"):
        raw = raw.replace(separator, " ")
    parts = raw.split("/")
    if len(parts) > 2:
        raise UnitError("use at most one '/'")
    exponents: dict[str, int] = {}
    for position, part in enumerate(parts):
        part = part.strip()
        if position == 1 and part.startswith("(") and part.endswith(")"):
            part = part[1:-1].strip()
        if "(" in part or ")" in part:
            raise UnitError("parentheses are only allowed around the whole denominator")
        tokens = part.split()
        if not tokens:
            raise UnitError("empty numerator or denominator")
        if tokens == ["1"]:
            continue
        sign = -1 if position == 1 else 1
        for token in tokens:
            match = UNIT_TOKEN.fullmatch(token)
            if not match:
                raise UnitError(f"cannot read {token!r}; write symbols with integer exponents, "
                                "for example 'W m^-2 K^-1'")
            name, power = match.group("name"), sign * int(match.group("exp") or 1)
            for base, base_power in SI_DERIVED.get(name, {name: 1}).items():
                exponents[base] = exponents.get(base, 0) + power * base_power
    return {name: power for name, power in exponents.items() if power}


def format_unit(exponents: dict[str, int]) -> str:
    if not exponents:
        return "1"
    order = [name for name in SI_BASE if name in exponents] + sorted(set(exponents) - set(SI_BASE))
    return " ".join(name if exponents[name] == 1 else f"{name}^{exponents[name]}" for name in order)


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
        number = positive_number(value)
        if number is None:
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
    check_keys(data, "root", "root", errors)

    target = data.get("target")
    if not isinstance(target, dict):
        errors.append("target: expected an object")
        target_unit = None
    else:
        check_keys(target, "target", "target", errors)
        require_text(target, "name", "target", errors)
        require_text(target, "unit", "target", errors)
        target_unit = target.get("unit") if is_text(target.get("unit")) else None

    mechanisms = data.get("mechanisms")
    if not isinstance(mechanisms, list) or not mechanisms:
        errors.append("mechanisms: expected a non-empty array")
        mechanisms = []

    mechanism_ids: set[str] = set()
    mechanism_ranges: dict[str, tuple[float, float, float]] = {}
    mechanism_roles: dict[str, str] = {}
    mechanism_units: dict[str, Any] = {}

    for index, mechanism in enumerate(mechanisms):
        path = f"mechanisms[{index}]"
        if not isinstance(mechanism, dict):
            errors.append(f"{path}: expected an object")
            continue
        check_keys(mechanism, "mechanism", path, errors)
        mechanism_id = mechanism.get("id")
        if not is_text(mechanism_id):
            errors.append(f"{path}.id: expected a non-empty string")
            mechanism_id = f"<invalid-{index}>"
        elif mechanism_id in mechanism_ids:
            errors.append(f"{path}.id: duplicate mechanism ID {mechanism_id!r}")
        mechanism_ids.add(mechanism_id)

        role = mechanism.get("role")
        if not is_one_of(role, ROLES):
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
            check_keys(factor, "factor", factor_path, errors)
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
            if not is_one_of(factor.get("evidence_status"), EVIDENCE):
                errors.append(f"{factor_path}.evidence_status: expected one of {sorted(EVIDENCE)}")
            factor_range = validate_range(factor, factor_path, errors)
            if factor_range:
                factor_ranges[factor_id] = factor_range

        calculation = mechanism.get("calculation")
        calculated: tuple[float, float, float] | None = None
        if not isinstance(calculation, dict):
            errors.append(f"{path}.calculation: expected an object")
        else:
            check_keys(calculation, "calculation", f"{path}.calculation", errors)
            coefficient = calculation.get("coefficient", 1)
            if positive_number(coefficient) is None:
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
            check_keys(estimate, "estimate", f"{path}.estimate", errors)
            require_text(estimate, "unit", f"{path}.estimate", errors)
            mechanism_units[mechanism_id] = estimate.get("unit")
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
                check_keys(reference, "reference_range", reference_path, errors)
                low = positive_number(reference.get("low"))
                high = positive_number(reference.get("high"))
                valid = True
                for key, value in (("low", low), ("high", high)):
                    if value is None:
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
    method = synthesis.get("method") if isinstance(synthesis, dict) else None
    method = method if is_one_of(method, METHODS) else None

    # Units: sum and max add like quantities, so every mechanism estimate must carry the
    # target unit exactly; a product multiplies the included units, and only that
    # combined unit has to equal the target unit (checked below).
    if target_unit and method != "product":
        for index, mechanism in enumerate(mechanisms):
            if isinstance(mechanism, dict) and isinstance(mechanism.get("estimate"), dict):
                if mechanism["estimate"].get("unit") != target_unit:
                    errors.append(f"mechanisms[{index}].estimate.unit: must equal target unit {target_unit!r}")

    if not isinstance(synthesis, dict):
        errors.append("synthesis: expected an object")
        return errors
    check_keys(synthesis, "synthesis", "synthesis", errors)
    if method is None:
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

    if target_unit and method == "product" and valid_included and not invalid_included and not unknown:
        try:
            combined: dict[str, int] = {}
            for mechanism_id in valid_included:
                unit = mechanism_units.get(mechanism_id)
                if not is_text(unit):
                    raise UnitError(f"mechanism {mechanism_id!r} has no estimate unit")
                try:
                    for name, power in parse_unit(unit).items():
                        combined[name] = combined.get(name, 0) + power
                except UnitError as exc:
                    raise UnitError(f"mechanism {mechanism_id!r} unit {unit!r}: {exc}") from None
            combined = {name: power for name, power in combined.items() if power}
            try:
                wanted = parse_unit(target_unit)
            except UnitError as exc:
                raise UnitError(f"target unit {target_unit!r}: {exc}") from None
            if combined != wanted:
                errors.append(f"synthesis: product of included mechanism units is {format_unit(combined)!r} "
                              f"but target unit {target_unit!r} is {format_unit(wanted)!r}")
        except UnitError as exc:
            errors.append(f"synthesis: cannot compose units for product: {exc}")

    synthesis_estimate = synthesis.get("estimate")
    synthesis_range = validate_range(synthesis_estimate, "synthesis.estimate", errors)
    if isinstance(synthesis_estimate, dict):
        check_keys(synthesis_estimate, "estimate", "synthesis.estimate", errors)
        require_text(synthesis_estimate, "unit", "synthesis.estimate", errors)
        if target_unit and synthesis_estimate.get("unit") != target_unit:
            errors.append(f"synthesis.estimate.unit: must equal target unit {target_unit!r}")

    if method is not None and valid_included and not invalid_included and not unknown:
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


SCHEMA_EXAMPLE: dict[str, Any] = {
    "target": {"name": "heat loss", "unit": "W"},
    "mechanisms": [{
        "id": "convection", "role": "dominant", "provenance": "prior mechanism analysis",
        "factors": [
            {"id": "h", "name": "heat-transfer coefficient", "unit": "W m^-2 K^-1", "low": 5, "central": 10,
             "high": 20, "evidence_status": "sourced", "basis": "source and access date"},
            {"id": "area", "name": "exposed area", "unit": "m^2", "low": 1.8, "central": 2.0, "high": 2.2,
             "evidence_status": "measured", "basis": "dimensions supplied by user"},
            {"id": "delta_t", "name": "temperature difference", "unit": "K", "low": 8, "central": 10,
             "high": 12, "evidence_status": "measured", "basis": "sensor readings"},
        ],
        "calculation": {"coefficient": 1, "multiply": ["h", "area", "delta_t"], "divide": []},
        "estimate": {"low": 72, "central": 200, "high": 528, "unit": "W"},
        "reference_range": {"low": 50, "high": 1000, "unit": "W"},
    }],
    "synthesis": {
        "method": "sum", "included_mechanism_ids": ["convection"],
        "estimate": {"low": 72, "central": 200, "high": 528, "unit": "W"},
        "decision": "Order 10^2 W; measurement needed if the threshold is below 500 W.",
    },
}


def _product_sheet(rate_unit: str, energy_unit: str) -> dict[str, Any]:
    """Two dominant mechanisms multiplied into a power: events per time times energy per event."""
    def mechanism(mechanism_id: str, unit: str, values: tuple[int, int, int]) -> dict[str, Any]:
        low, central, high = values
        return {"id": mechanism_id, "role": "dominant", "provenance": "user",
                "factors": [{"id": "x", "name": mechanism_id, "unit": unit, "low": low, "central": central,
                             "high": high, "evidence_status": "assumed", "basis": "stated guess"}],
                "calculation": {"multiply": ["x"], "divide": []},
                "estimate": {"low": low, "central": central, "high": high, "unit": unit}}
    return {"target": {"name": "mean power", "unit": "W"},
            "mechanisms": [mechanism("rate", rate_unit, (1, 2, 4)), mechanism("energy", energy_unit, (10, 20, 40))],
            "synthesis": {"method": "product", "included_mechanism_ids": ["rate", "energy"],
                          "estimate": {"low": 10, "central": 40, "high": 160, "unit": "W"},
                          "decision": "tens of watts"}}


def _changed(edit) -> dict[str, Any]:
    document = copy.deepcopy(SCHEMA_EXAMPLE)
    edit(document)
    return document


def _selftest_cases() -> list[tuple[str, Any, str | None]]:
    """(label, worksheet, None if it must pass or a substring the errors must contain)."""
    first = lambda d: d["mechanisms"][0]  # noqa: E731 - short accessor for the cases below
    factor = lambda d: d["mechanisms"][0]["factors"][0]  # noqa: E731
    return [
        ("schema example passes", copy.deepcopy(SCHEMA_EXAMPLE), None),
        ("product s^-1 x J = W passes", _product_sheet("s^-1", "J"), None),
        ("product with superscripts s⁻¹ x J = W passes", _product_sheet("s⁻¹", "J"), None),
        ("product 1 x W = W passes", _product_sheet("1", "W"), None),
        ("product mislabelled W x W = W fails", _product_sheet("W", "W"), "product of included mechanism units"),
        ("product with unreadable unit fails", _product_sheet("W/(m^2", "J"), "cannot compose units"),
        ("sum still needs the exact target unit",
         _changed(lambda d: first(d)["estimate"].update(unit="kW")), "must equal target unit"),
        ("method given as a list", _changed(lambda d: d["synthesis"].update(method=["sum"])), "synthesis.method"),
        ("role given as an object", _changed(lambda d: first(d).update(role={"x": 1})), ".role"),
        ("evidence_status given as a list",
         _changed(lambda d: factor(d).update(evidence_status=["sourced"])), "evidence_status"),
        ("factor id given as a list", _changed(lambda d: factor(d).update(id=["h"])), ".id"),
        ("included id given as an object",
         _changed(lambda d: d["synthesis"].update(included_mechanism_ids=[{"id": "convection"}])),
         "included_mechanism_ids"),
        ("zero value", _changed(lambda d: factor(d).update(low=0)), "finite positive"),
        ("infinite value", _changed(lambda d: factor(d).update(high=float("inf"))), "finite positive"),
        ("integer too large for a float", _changed(lambda d: factor(d).update(high=10 ** 400)), "finite positive"),
        ("reversed range", _changed(lambda d: factor(d).update(low=30)), "low <= central <= high"),
        ("omitted non-negligible mechanism (Case 5)",
         _changed(lambda d: d["synthesis"].update(included_mechanism_ids=[])), "omitted non-negligible"),
        ("synthesis central changed to 20 (Case 5)",
         _changed(lambda d: d["synthesis"]["estimate"].update(central=20)), "does not match calculated"),
        ("misspelt optional key",
         _changed(lambda d: first(d).update(refrence_range=first(d).pop("reference_range"))), "unknown key"),
    ]


def selftest() -> int:
    cases = _selftest_cases()
    failures = 0
    for label, document, expected in cases:
        errors = check_document(document, 0.05)
        if expected is None:
            ok = not errors
            detail = "" if ok else f": unexpected errors {errors}"
        else:
            ok = any(expected in error for error in errors)
            detail = "" if ok else f": expected an error containing {expected!r}, got {errors}"
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}{detail}")
    print(f"selftest: {len(cases) - failures}/{len(cases)} passed")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("worksheet", type=Path, nargs="?", help="JSON worksheet to validate")
    parser.add_argument("--tolerance", type=float, default=0.05,
                        help="relative arithmetic tolerance (default: 0.05)")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.worksheet is None:
        parser.error("a worksheet path is required (or use --selftest)")
    if not 0 <= args.tolerance < 1:
        parser.error("--tolerance must be at least 0 and less than 1")
    try:
        data = json.loads(args.worksheet.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        print(f"ERROR: cannot read worksheet: {exc}", file=sys.stderr)
        return 2
    try:
        errors = check_document(data, args.tolerance)
    except Exception as exc:  # a crash must never be read as a validation verdict
        print(f"ERROR: checker failed on this worksheet: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAIL: {len(errors)} issue(s)")
        return 1
    print("PASS: estimate worksheet is structurally and arithmetically consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
