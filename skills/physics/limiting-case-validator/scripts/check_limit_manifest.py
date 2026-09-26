#!/usr/bin/env python3
"""Validate a limiting-case audit manifest.

This helper is intentionally conservative and dependency-free.
It checks whether a planned limiting-case review is structurally complete
before a human or agent spends time on the physics. It does not evaluate
any limit; it only checks that the plan names its variables, its limits,
and a physical expectation for each limit.

Usage:
    python3 check_limit_manifest.py path/to/limit-manifest.json
    python3 check_limit_manifest.py --selftest

Manifest (JSON object):
    target     required  non-empty string: the formula or claim under test
    variables  required  non-empty list of objects:
                 name            required  non-empty string, unique
                 baselineLimits  optional  list of approach words that must be tested
                 meaning, units, range, notes  optional free text
    cases      required  non-empty list of objects:
                 id        required  non-empty string, unique
                 variable  required  a declared variable name
                 approach  required  one of ALLOWED_APPROACHES
                 expected  required  physical expectation, written before the math
                 why       required  why this limit is physically relevant
                 notes     optional  free text
    notes      optional  free text

Unknown fields are errors, so a misspelled optional field (for example
"baseline_limits") cannot silently switch a check off.

Exit codes: 0 structurally valid (WARN lines may still list gaps),
1 structural errors or unreadable file, 2 usage error.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
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
OPTIONAL_ROOT_FIELDS = ("notes",)
REQUIRED_VARIABLE_FIELDS = ("name",)
OPTIONAL_VARIABLE_FIELDS = ("baselineLimits", "meaning", "units", "range", "notes")
REQUIRED_CASE_FIELDS = ("id", "variable", "approach", "expected", "why")
OPTIONAL_CASE_FIELDS = ("notes",)
FREE_TEXT_FIELDS = ("meaning", "units", "range", "notes")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: file not found: {path}")
    except IsADirectoryError:
        raise SystemExit(f"ERROR: expected a JSON file, got a directory: {path}")
    except UnicodeDecodeError:
        raise SystemExit(f"ERROR: file is not UTF-8 text: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")


def unknown_field_problems(obj: dict[str, Any], allowed: tuple[str, ...], where: str) -> list[str]:
    problems: list[str] = []
    for key in obj:
        if key in allowed:
            continue
        hint = difflib.get_close_matches(str(key), allowed, n=1)
        suggestion = f" (did you mean '{hint[0]}'?)" if hint else ""
        problems.append(
            f"{where} has unknown field '{key}'{suggestion}; allowed fields: {', '.join(allowed)}"
        )
    return problems


def free_text_problems(obj: dict[str, Any], where: str) -> list[str]:
    return [
        f"{where} field '{field}' must be a string"
        for field in FREE_TEXT_FIELDS
        if field in obj and not isinstance(obj[field], str)
    ]


def validate_root(data: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["manifest root must be a JSON object"]
    problems.extend(unknown_field_problems(data, REQUIRED_ROOT_FIELDS + OPTIONAL_ROOT_FIELDS, "manifest root"))
    problems.extend(free_text_problems(data, "manifest root"))
    for field in REQUIRED_ROOT_FIELDS:
        if field not in data:
            problems.append(f"missing root field: {field}")
    if "target" in data and (not isinstance(data["target"], str) or not data["target"].strip()):
        problems.append("root field 'target' must be a non-empty string (the formula or claim under test)")
    if "variables" in data:
        if not isinstance(data["variables"], list):
            problems.append("root field 'variables' must be a list")
        elif not data["variables"]:
            problems.append("root field 'variables' is empty: declare at least one control parameter")
    if "cases" in data:
        if not isinstance(data["cases"], list):
            problems.append("root field 'cases' must be a list")
        elif not data["cases"]:
            problems.append("root field 'cases' is empty: a manifest with no limiting cases tests nothing")
    return problems


def validate_variables(variables: list[Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    problems: list[str] = []
    seen: dict[str, dict[str, Any]] = {}

    for index, variable in enumerate(variables, start=1):
        if not isinstance(variable, dict):
            problems.append(f"variables[{index}] must be an object")
            continue
        where = f"variables[{index}]"
        problems.extend(
            unknown_field_problems(variable, REQUIRED_VARIABLE_FIELDS + OPTIONAL_VARIABLE_FIELDS, where)
        )
        problems.extend(free_text_problems(variable, where))
        for field in REQUIRED_VARIABLE_FIELDS:
            if field not in variable:
                problems.append(f"{where} missing field: {field}")
        name = variable.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{where}.name must be a non-empty string")
            continue
        if name in seen:
            problems.append(f"duplicate variable name: {name}")
            continue
        baseline = variable.get("baselineLimits", [])
        if baseline is None:
            baseline = []
        if not isinstance(baseline, list) or not all(isinstance(item, str) for item in baseline):
            problems.append(f"variable '{name}' has invalid baselineLimits; expected list of strings")
        else:
            for item in baseline:
                if item not in ALLOWED_APPROACHES:
                    problems.append(
                        f"variable '{name}' baselineLimits entry '{item}' is not an approach word. "
                        f"Allowed: {', '.join(sorted(ALLOWED_APPROACHES))}"
                    )
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
        problems.extend(
            unknown_field_problems(case, REQUIRED_CASE_FIELDS + OPTIONAL_CASE_FIELDS, f"cases[{index}]")
        )
        problems.extend(free_text_problems(case, f"cases[{index}]"))
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

        label = case_id if isinstance(case_id, str) and case_id.strip() else index
        variable = case.get("variable")
        if not isinstance(variable, str) or not variable.strip():
            problems.append(f"cases[{index}].variable must be a non-empty string")
        elif variable not in variable_names:
            problems.append(f"case '{label}' references undeclared variable: {variable}")
        else:
            referenced_variables.add(variable)

        approach = case.get("approach")
        if not isinstance(approach, str) or not approach.strip():
            problems.append(f"case '{label}' has invalid approach")
        elif approach not in ALLOWED_APPROACHES:
            problems.append(
                f"case '{label}' uses unsupported approach '{approach}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_APPROACHES))}"
            )

        for field in ("expected", "why"):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"case '{label}' field '{field}' must be a non-empty string")

    return problems, referenced_variables


def baseline_warnings(variables: dict[str, dict[str, Any]], cases: list[Any]) -> list[str]:
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


def check_manifest(data: Any) -> tuple[int, list[str]]:
    """Return (exit_code, output_lines) for an already parsed manifest."""
    lines: list[str] = []
    problems = validate_root(data)
    if problems:
        lines.extend(f"ERROR: {problem}" for problem in problems)
        return 1, lines

    variables = data["variables"]
    cases = data["cases"]

    var_problems, variable_map = validate_variables(variables)
    case_problems, referenced_variables = validate_cases(cases, set(variable_map.keys()))

    all_problems = var_problems + case_problems
    lines.extend(f"ERROR: {problem}" for problem in all_problems)

    warnings = baseline_warnings(variable_map, cases)
    warnings.extend(reference_warnings(variable_map, referenced_variables))
    lines.extend(f"WARN: {item}" for item in warnings)

    if all_problems:
        return 1, lines

    lines.append(f"OK: validated manifest for target: {data['target']}")
    lines.append(f"OK: variables: {len(variable_map)} | cases: {len(cases)}")
    if warnings:
        lines.append("WARN: manifest is usable but incomplete; review warnings above")
        return 0, lines

    lines.append("OK: manifest structure looks complete")
    return 0, lines


def _complete_manifest() -> dict[str, Any]:
    return {
        "target": "T = 2*pi*sqrt(L/g)*(1 + theta0)",
        "variables": [
            {"name": "theta0", "meaning": "launch amplitude", "units": "rad", "baselineLimits": ["+0"]},
            {"name": "g", "units": "m/s^2", "baselineLimits": ["+inf"]},
        ],
        "cases": [
            {
                "id": "L1",
                "variable": "theta0",
                "approach": "+0",
                "expected": "period returns to 2*pi*sqrt(L/g); first correction is even in theta0",
                "why": "small-angle textbook limit",
            },
            {
                "id": "L2",
                "variable": "g",
                "approach": "+inf",
                "expected": "restoring force dominates, period goes to 0",
                "why": "stiff-restoring limit",
            },
        ],
    }


def run_selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def expect(name: str, data: Any, code: int, must_contain: str = "", must_not_contain: str = "") -> None:
        got_code, lines = check_manifest(data)
        text = "\n".join(lines)
        ok = got_code == code
        if must_contain and must_contain not in text:
            ok = False
        if must_not_contain and must_not_contain in text:
            ok = False
        results.append((name, ok, f"exit={got_code}; output={text!r}"))

    expect("complete manifest passes", _complete_manifest(), 0, "manifest structure looks complete")

    # Audit regression: an empty manifest used to print "manifest structure looks complete" and exit 0.
    expect(
        "empty manifest is an error",
        {"target": "x", "variables": [], "cases": []},
        1,
        "root field 'cases' is empty",
        "looks complete",
    )

    uncovered = _complete_manifest()
    uncovered["cases"] = uncovered["cases"][:1]
    expect("uncovered baseline limit warns", uncovered, 0, "declares baseline limit '+inf'", "looks complete")

    typo = _complete_manifest()
    typo["variables"][0]["baseline_limits"] = typo["variables"][0].pop("baselineLimits")
    expect("misspelled optional field is an error", typo, 1, "did you mean 'baselineLimits'")

    bad_approach = _complete_manifest()
    bad_approach["cases"][0]["approach"] = "zero"
    expect("unsupported approach is an error", bad_approach, 1, "unsupported approach 'zero'")

    bad_baseline = _complete_manifest()
    bad_baseline["variables"][1]["baselineLimits"] = ["infinity"]
    expect("baseline entry must be an approach word", bad_baseline, 1, "'infinity' is not an approach word")

    blank_target = _complete_manifest()
    blank_target["target"] = "  "
    expect("blank target is an error", blank_target, 1, "'target' must be a non-empty string")

    undeclared = _complete_manifest()
    undeclared["cases"][1]["variable"] = "L"
    expect("case on undeclared variable is an error", undeclared, 1, "undeclared variable: L")

    try:
        load_json(Path("/nonexistent/limit-manifest.json"))
        results.append(("missing file is reported", False, "no SystemExit raised"))
    except SystemExit as exc:
        results.append(("missing file is reported", "file not found" in str(exc), str(exc)))

    # Audit regression: --help used to be read as a file name.
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--help"],
        capture_output=True,
        text=True,
    )
    results.append(
        (
            "--help prints usage and exits 0",
            proc.returncode == 0 and "usage:" in proc.stdout and "file not found" not in proc.stdout,
            f"exit={proc.returncode}",
        )
    )

    failed = 0
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  [{detail}]"))
        failed += 0 if ok else 1
    print(f"selftest: {len(results) - failed}/{len(results)} passed")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that a limiting-case manifest is structurally complete before the physics is done. "
            "Fields: target; variables[] (name, optional baselineLimits/meaning/units/range/notes); "
            "cases[] (id, variable, approach, expected, why, optional notes). "
            f"Approach words: {', '.join(sorted(ALLOWED_APPROACHES))}. "
            "Exit 0 = structurally valid (WARN lines may remain), 1 = errors, 2 = usage error."
        )
    )
    parser.add_argument("manifest", nargs="?", help="path to the limit-manifest JSON file")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if not args.manifest:
        parser.error("a manifest path is required (or use --selftest)")

    code, lines = check_manifest(load_json(Path(args.manifest)))
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
