#!/usr/bin/env python3
"""Validate a manifest for ai-generated-test-auditor.

This helper is intentionally conservative and dependency-free.
It does not execute tests or mutations. It verifies that an audit packet
contains enough structured information for a reliable human/agent review.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_ROOT_FIELDS = ("target", "implementationFiles", "testCases", "mutationSamples")
REQUIRED_TEST_FIELDS = ("id", "kind", "oracle", "summary")
REQUIRED_MUTATION_FIELDS = ("id", "targetFile", "kind", "expectedFailingTests", "why")
ALLOWED_TEST_KINDS = {
    "happy-path",
    "boundary",
    "error-path",
    "side-effect",
    "regression",
    "state-transition",
}
ALLOWED_ORACLES = {
    "independent",
    "derived",
    "mirrored",
    "weak-signal",
}


def error(message: str) -> None:
    print(f"ERROR: {message}")



def warn(message: str) -> None:
    print(f"WARN: {message}")



def info(message: str) -> None:
    print(f"OK: {message}")



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
    if "implementationFiles" in data and not isinstance(data["implementationFiles"], list):
        problems.append("root field 'implementationFiles' must be a list")
    if "testCases" in data and not isinstance(data["testCases"], list):
        problems.append("root field 'testCases' must be a list")
    if "mutationSamples" in data and not isinstance(data["mutationSamples"], list):
        problems.append("root field 'mutationSamples' must be a list")
    return problems



def validate_implementation_files(items: list[Any]) -> tuple[list[str], set[str]]:
    problems: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, str) or not item.strip():
            problems.append(f"implementationFiles[{index}] must be a non-empty string")
            continue
        if item in seen:
            problems.append(f"duplicate implementation file: {item}")
            continue
        seen.add(item)
    return problems, seen



def validate_test_cases(items: list[Any]) -> tuple[list[str], dict[str, dict[str, Any]], set[str]]:
    problems: list[str] = []
    test_map: dict[str, dict[str, Any]] = {}
    kinds_seen: set[str] = set()

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"testCases[{index}] must be an object")
            continue
        for field in REQUIRED_TEST_FIELDS:
            if field not in item:
                problems.append(f"testCases[{index}] missing field: {field}")
        test_id = item.get("id")
        if not isinstance(test_id, str) or not test_id.strip():
            problems.append(f"testCases[{index}].id must be a non-empty string")
            continue
        if test_id in test_map:
            problems.append(f"duplicate test case id: {test_id}")
            continue

        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in ALLOWED_TEST_KINDS:
            problems.append(
                f"test case '{test_id}' has invalid kind '{kind}'. Allowed: {', '.join(sorted(ALLOWED_TEST_KINDS))}"
            )
        else:
            kinds_seen.add(kind)

        oracle = item.get("oracle")
        if not isinstance(oracle, str) or oracle not in ALLOWED_ORACLES:
            problems.append(
                f"test case '{test_id}' has invalid oracle '{oracle}'. Allowed: {', '.join(sorted(ALLOWED_ORACLES))}"
            )

        summary = item.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            problems.append(f"test case '{test_id}' field 'summary' must be a non-empty string")

        test_map[test_id] = item

    return problems, test_map, kinds_seen



def validate_mutations(
    items: list[Any], implementation_files: set[str], test_ids: set[str]
) -> tuple[list[str], set[str]]:
    problems: list[str] = []
    mutation_ids: set[str] = set()
    referenced_tests: set[str] = set()

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"mutationSamples[{index}] must be an object")
            continue
        for field in REQUIRED_MUTATION_FIELDS:
            if field not in item:
                problems.append(f"mutationSamples[{index}] missing field: {field}")

        mutation_id = item.get("id")
        if not isinstance(mutation_id, str) or not mutation_id.strip():
            problems.append(f"mutationSamples[{index}].id must be a non-empty string")
        elif mutation_id in mutation_ids:
            problems.append(f"duplicate mutation sample id: {mutation_id}")
        else:
            mutation_ids.add(mutation_id)

        target_file = item.get("targetFile")
        if not isinstance(target_file, str) or not target_file.strip():
            problems.append(f"mutation sample '{mutation_id or index}' has invalid targetFile")
        elif target_file not in implementation_files:
            problems.append(
                f"mutation sample '{mutation_id or index}' references undeclared implementation file: {target_file}"
            )

        kind = item.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            problems.append(f"mutation sample '{mutation_id or index}' has invalid kind")

        expected = item.get("expectedFailingTests")
        if not isinstance(expected, list) or not expected:
            problems.append(
                f"mutation sample '{mutation_id or index}' must declare a non-empty expectedFailingTests list"
            )
        else:
            for test_id in expected:
                if not isinstance(test_id, str) or not test_id.strip():
                    problems.append(
                        f"mutation sample '{mutation_id or index}' contains an invalid expected test id"
                    )
                    continue
                if test_id not in test_ids:
                    problems.append(
                        f"mutation sample '{mutation_id or index}' references unknown test case id: {test_id}"
                    )
                else:
                    referenced_tests.add(test_id)

        why = item.get("why")
        if not isinstance(why, str) or not why.strip():
            problems.append(f"mutation sample '{mutation_id or index}' field 'why' must be a non-empty string")

    return problems, referenced_tests



def coverage_warnings(kinds_seen: set[str], test_map: dict[str, dict[str, Any]], referenced_tests: set[str]) -> list[str]:
    warnings: list[str] = []
    for required_kind in ("happy-path", "boundary", "error-path"):
        if required_kind not in kinds_seen:
            warnings.append(f"audit packet has no test case tagged '{required_kind}'")

    if "side-effect" not in kinds_seen and "state-transition" not in kinds_seen:
        warnings.append("audit packet has no side-effect or state-transition coverage")

    mirrored_tests = [test_id for test_id, item in test_map.items() if item.get("oracle") == "mirrored"]
    if mirrored_tests:
        warnings.append(
            "tests using mirrored oracles need especially careful review: " + ", ".join(sorted(mirrored_tests))
        )

    if not referenced_tests:
        warnings.append("no mutation sample is mapped to a named test case")

    return warnings



def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python check_test_audit_manifest.py path/to/test-audit-manifest.json")
        return 2

    path = Path(argv[1])
    data = load_json(path)

    problems = validate_root(data)
    if problems:
        for problem in problems:
            error(problem)
        return 1

    impl_problems, implementation_files = validate_implementation_files(data["implementationFiles"])
    test_problems, test_map, kinds_seen = validate_test_cases(data["testCases"])
    mutation_problems, referenced_tests = validate_mutations(
        data["mutationSamples"], implementation_files, set(test_map.keys())
    )

    all_problems = impl_problems + test_problems + mutation_problems
    for problem in all_problems:
        error(problem)

    warnings = coverage_warnings(kinds_seen, test_map, referenced_tests)
    for item in warnings:
        warn(item)

    if all_problems:
        return 1

    info(f"validated audit manifest for target: {data['target']}")
    info(
        f"implementation files: {len(implementation_files)} | test cases: {len(test_map)} | mutation samples: {len(data['mutationSamples'])}"
    )
    if warnings:
        warn("audit packet is usable but has review gaps; see warnings above")
        return 0

    info("audit packet structure looks complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
