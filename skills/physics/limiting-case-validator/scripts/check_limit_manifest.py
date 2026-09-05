#!/usr/bin/env python3
"""Validate a limiting-case audit manifest.

This helper is intentionally conservative and dependency-free.
It checks whether a planned limiting-case review is structurally complete
before a human or agent spends time on the physics.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ALLOWED_APPROACHES = {
    "0",
    "+0",
    "-0",
    "inf",
    "+inf",
    "-inf",
    "small",
    "large",
    "equal-scale",
    "threshold",
    "special-value",
    "turn-off",
    "symmetry",
}

REQUIRED_ROOT_FIELDS = ("target", "variables", "cases")
REQUIRED_VARIABLE_FIELDS = ("name",)
REQUIRED_CASE_FIELDS = ("id", "variable", "approach", "expected", "why")


def error(msg: str) -> None:
    print(f"ERROR: {msg}")


def warn(msg: str) -> None:
    print(f"WARN: {msg}")


def info(msg: str) -> None:
    print(f"OK: {msg}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")


def validate_root(data: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["manifest root must be a JSON object"]
    for field in REQUIRED_ROOT_FIELDS:
        if field not in data:
            problems.append(f"missing root field: {field}")
    if "variables" in data and not isinstance(data["variables"], list):
        problems.append("root field 'variables' must be a list")
    if "cases" in data and not isinstance(data["cases"], list):
        problems.append("root field 'cases' must be a list")
    return problems


def validate_variables(variables: list[Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    problems: list[str] = []
    seen: dict[str, dict[str, Any]] = {}

    for index, variable in enumerate(variables, start=1):
        if not isinstance(variable, dict):
            problems.append(f"variables[{index}] must be an object")
            continue
        for field in REQUIRED_VARIABLE_FIELDS:
            if field not in variable:
                problems.append(f"variables[{index}] missing field: {field}")
        name = variable.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"variables[{index}].name must be a non-empty string")
            continue
        if name in seen:
            problems.append(f"duplicate variable name: {name}")
            continue
        baseline = variable.get("baselineLimits", [])
        if baseline is None:
            baseline = []
        if not isinstance(baseline, list) or not all(isinstance(item, str) for item in baseline):
            problems.append(f"variable '{name}' has invalid baselineLimits; expected list of strings")
        seen[name] = variable

    return problems, seen


def validate_cases(cases: list[Any], variable_names: set[str]) -> tuple[list[str], set[str]]:
    problems: list[str] = []
    case_ids: set[str] = set()
    referenced_variables: set[str] = set()

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            problems.append(f"cases[{index}] must be an object")
            continue
        for field in REQUIRED_CASE_FIELDS:
            if field not in case:
                problems.append(f"cases[{index}] missing field: {field}")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            problems.append(f"cases[{index}].id must be a non-empty string")
        elif case_id in case_ids:
            problems.append(f"duplicate case id: {case_id}")
        else:
            case_ids.add(case_id)

        variable = case.get("variable")
        if not isinstance(variable, str) or not variable.strip():
            problems.append(f"cases[{index}].variable must be a non-empty string")
        elif variable not in variable_names:
            problems.append(f"case '{case_id or index}' references undeclared variable: {variable}")
        else:
            referenced_variables.add(variable)

        approach = case.get("approach")
        if not isinstance(approach, str) or not approach.strip():
            problems.append(f"case '{case_id or index}' has invalid approach")
        elif approach not in ALLOWED_APPROACHES:
            problems.append(
                f"case '{case_id or index}' uses unsupported approach '{approach}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_APPROACHES))}"
            )

        for field in ("expected", "why"):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"case '{case_id or index}' field '{field}' must be a non-empty string")

    return problems, referenced_variables


def baseline_warnings(variables: dict[str, dict[str, Any]], cases: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    covered = {(case.get("variable"), case.get("approach")) for case in cases if isinstance(case, dict)}

    for name, variable in variables.items():
        baseline = variable.get("baselineLimits", []) or []
        for item in baseline:
            if (name, item) not in covered:
                warnings.append(
                    f"variable '{name}' declares baseline limit '{item}' but no matching case was provided"
                )

    return warnings


def reference_warnings(variables: dict[str, dict[str, Any]], referenced_variables: set[str]) -> list[str]:
    warnings: list[str] = []
    for name in variables:
        if name not in referenced_variables:
            warnings.append(f"declared variable '{name}' is never tested by any case")
    return warnings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python check_limit_manifest.py path/to/limit-manifest.json")
        return 2

    path = Path(argv[1])
    data = load_json(path)

    problems = validate_root(data)
    if problems:
        for problem in problems:
            error(problem)
        return 1

    variables = data["variables"]
    cases = data["cases"]

    var_problems, variable_map = validate_variables(variables)
    case_problems, referenced_variables = validate_cases(cases, set(variable_map.keys()))

    all_problems = var_problems + case_problems
    for problem in all_problems:
        error(problem)

    warnings = baseline_warnings(variable_map, cases)
    warnings.extend(reference_warnings(variable_map, referenced_variables))
    for item in warnings:
        warn(item)

    if all_problems:
        return 1

    info(f"validated manifest for target: {data['target']}")
    info(f"variables: {len(variable_map)} | cases: {len(cases)}")
    if warnings:
        warn("manifest is usable but incomplete; review warnings above")
        return 0

    info("manifest structure looks complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
