#!/usr/bin/env python3
"""Validate a manifest for ai-generated-test-auditor.

This helper is intentionally conservative and dependency-free.
It does not execute tests or mutations. It verifies that an audit packet
contains enough structured information for a reliable human/agent review.

Usage:
    python3 check_test_audit_manifest.py path/to/test-audit-manifest.json
    python3 check_test_audit_manifest.py --selftest

`kind` and `oracle` accept the canonical values below and the wording SKILL.md
uses (for example "mirrored logic" -> mirrored, "weak signal" -> weak-signal,
"happy path" -> happy-path, "error / invalid input" -> error-path).

Exit codes: 0 = manifest valid (warnings may remain); 1 = manifest has
problems; 2 = the file cannot be read as JSON (missing, a directory, not
UTF-8, invalid JSON) or the arguments are wrong.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
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
# SKILL.md Step 2 and Step 3 wording, normalised (lower case, runs of other characters -> "-")
ORACLE_ALIASES = {
    "independent-oracle": "independent",
    "derived-oracle": "derived",
    "mirrored-logic": "mirrored",
    "mirrored-oracle": "mirrored",
    "weak": "weak-signal",
    "weak-signal-oracle": "weak-signal",
}
KIND_ALIASES = {
    "happy": "happy-path",
    "boundary-case": "boundary",
    "boundary-cases": "boundary",
    "boundary-value": "boundary",
    "boundary-values": "boundary",
    "error": "error-path",
    "error-case": "error-path",
    "error-cases": "error-path",
    "invalid-input": "error-path",
    "error-invalid-input": "error-path",
    "error-invalid-input-cases": "error-path",
    "failure-path": "error-path",
    "side-effects": "side-effect",
    "stateful": "side-effect",
    "stateful-or-side-effect": "side-effect",
    "stateful-or-side-effect-cases": "side-effect",
    "regression-hook": "regression",
    "regression-hooks": "regression",
}


class InputError(Exception):
    """The manifest file cannot be read as JSON (exit code 2)."""


def normalise(value: Any, allowed: set[str], aliases: dict[str, str]) -> str | None:
    """Canonical enum value for `value`, or None when it is not recognised."""
    if not isinstance(value, str):
        return None
    key = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if key in allowed:
        return key
    return aliases.get(key)


def error(message: str) -> None:
    print(f"ERROR: {message}")



def warn(message: str) -> None:
    print(f"WARN: {message}")



def info(message: str) -> None:
    print(f"OK: {message}")



def load_json(path: Path) -> Any:
    if path.is_dir():
        raise InputError(f"{path} is a directory; pass the manifest JSON file")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError(f"file not found: {path}") from None
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text; save the manifest as UTF-8 JSON") from None
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from None


def unknown_keys(item: dict[str, Any], known: tuple[str, ...], where: str) -> list[str]:
    return [
        f"{where} has unknown key '{key}' (ignored); known keys: {', '.join(known)}"
        for key in item
        if key not in known
    ]


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



def validate_test_cases(
    items: list[Any],
) -> tuple[list[str], dict[str, dict[str, Any]], set[str], list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    test_map: dict[str, dict[str, Any]] = {}
    kinds_seen: set[str] = set()

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"testCases[{index}] must be an object")
            continue
        for field in REQUIRED_TEST_FIELDS:
            if field not in item:
                problems.append(f"testCases[{index}] missing field: {field}")
        warnings.extend(unknown_keys(item, REQUIRED_TEST_FIELDS, f"testCases[{index}]"))
        test_id = item.get("id")
        if not isinstance(test_id, str) or not test_id.strip():
            problems.append(f"testCases[{index}].id must be a non-empty string")
            continue
        if test_id in test_map:
            problems.append(f"duplicate test case id: {test_id}")
            continue

        kind = item.get("kind")
        canonical_kind = normalise(kind, ALLOWED_TEST_KINDS, KIND_ALIASES)
        if canonical_kind is None:
            problems.append(
                f"test case '{test_id}' has invalid kind '{kind}'. Allowed: {', '.join(sorted(ALLOWED_TEST_KINDS))} "
                "(SKILL.md wording such as 'happy path' or 'error / invalid input' is accepted too)"
            )
        else:
            kinds_seen.add(canonical_kind)
            if canonical_kind != kind:
                notes.append(f"test case '{test_id}': kind '{kind}' read as '{canonical_kind}'")

        oracle = item.get("oracle")
        canonical_oracle = normalise(oracle, ALLOWED_ORACLES, ORACLE_ALIASES)
        if canonical_oracle is None:
            problems.append(
                f"test case '{test_id}' has invalid oracle '{oracle}'. Allowed: {', '.join(sorted(ALLOWED_ORACLES))} "
                "(SKILL.md wording such as 'mirrored logic' or 'weak signal' is accepted too)"
            )
        elif canonical_oracle != oracle:
            notes.append(f"test case '{test_id}': oracle '{oracle}' read as '{canonical_oracle}'")

        summary = item.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            problems.append(f"test case '{test_id}' field 'summary' must be a non-empty string")

        test_map[test_id] = {**item, "kind": canonical_kind or kind, "oracle": canonical_oracle or oracle}

    return problems, test_map, kinds_seen, warnings, notes



def validate_mutations(
    items: list[Any], implementation_files: set[str], test_ids: set[str]
) -> tuple[list[str], set[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    mutation_ids: set[str] = set()
    referenced_tests: set[str] = set()

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"mutationSamples[{index}] must be an object")
            continue
        for field in REQUIRED_MUTATION_FIELDS:
            if field not in item:
                problems.append(f"mutationSamples[{index}] missing field: {field}")
        warnings.extend(unknown_keys(item, REQUIRED_MUTATION_FIELDS, f"mutationSamples[{index}]"))

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

    return problems, referenced_tests, warnings



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



def check(path: Path) -> int:
    data = load_json(path)

    problems = validate_root(data)
    if problems:
        for problem in problems:
            error(problem)
        return 1
    root_warnings = unknown_keys(data, REQUIRED_ROOT_FIELDS, "manifest root")

    impl_problems, implementation_files = validate_implementation_files(data["implementationFiles"])
    test_problems, test_map, kinds_seen, test_warnings, notes = validate_test_cases(data["testCases"])
    mutation_problems, referenced_tests, mutation_warnings = validate_mutations(
        data["mutationSamples"], implementation_files, set(test_map.keys())
    )

    all_problems = impl_problems + test_problems + mutation_problems
    for problem in all_problems:
        error(problem)

    for note in notes:
        info(note)
    warnings = root_warnings + test_warnings + mutation_warnings
    warnings += coverage_warnings(kinds_seen, test_map, referenced_tests)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_test_audit_manifest.py",
        description="Check that an ai-generated-test-auditor audit packet (manifest JSON) is structurally "
        "complete. It does not run tests or mutations.",
        epilog="Exit codes: 0 valid (warnings may remain), 1 manifest problems, 2 unreadable file or bad arguments.",
    )
    parser.add_argument("manifest", nargs="?", help="path to the test-audit manifest JSON")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.manifest:
        parser.print_usage(sys.stderr)
        print("ERROR: pass the manifest JSON file (or --selftest)", file=sys.stderr)
        return 2
    try:
        return check(Path(args.manifest))
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


SKILL_EXAMPLE = {
    "target": "Validate AI-generated tests for create_user",
    "implementationFiles": ["src/user_service.py"],
    "testCases": [
        {"id": "accepts_valid_name", "kind": "happy-path", "oracle": "independent",
         "summary": "Creates a user when name and email are valid"},
        {"id": "rejects_blank_name", "kind": "error-path", "oracle": "independent",
         "summary": "Raises ValueError for blank name"},
    ],
    "mutationSamples": [
        {"id": "skip_blank_name_validation", "targetFile": "src/user_service.py", "kind": "remove-validation",
         "expectedFailingTests": ["rejects_blank_name"],
         "why": "A real guard should be observable through the public API"},
    ],
}


def selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def run(payload: Any, raw: bytes | None = None, as_dir: bool = False) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            if not as_dir:
                target = Path(tmp) / "manifest.json"
                target.write_bytes(raw if raw is not None else json.dumps(payload).encode("utf-8"))
            sink = io.StringIO()
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                code = main([str(target)])
            return code, sink.getvalue()

    def expect(name: str, cond: bool, detail: str) -> None:
        results.append((name, bool(cond), detail))

    code, out = run(SKILL_EXAMPLE)
    expect("SKILL.md example manifest is valid (exit 0, coverage warnings only)",
           code == 0 and "ERROR" not in out and "no test case tagged 'boundary'" in out, out)
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    if skill_md.is_file():
        block = re.search(r"```json\n(.*?)```", skill_md.read_text(encoding="utf-8"), re.S)
        code, out = run(None, raw=block.group(1).encode("utf-8")) if block else (None, "no json block")
        expect("the example manifest printed in SKILL.md itself is valid (exit 0)", code == 0, out)

    vocab = json.loads(json.dumps(SKILL_EXAMPLE))
    vocab["testCases"] = [
        {"id": "gold", "kind": "happy path", "oracle": "mirrored logic", "summary": "copies the branch"},
        {"id": "no_crash", "kind": "error / invalid input", "oracle": "weak signal", "summary": "only checks no raise"},
        {"id": "edge", "kind": "Boundary cases", "oracle": "Independent oracle", "summary": "threshold 100"},
    ]
    vocab["mutationSamples"][0]["expectedFailingTests"] = ["gold"]
    code, out = run(vocab)
    expect("SKILL.md wording 'mirrored logic', 'weak signal', 'happy path' accepted (exit 0)",
           code == 0 and "read as 'mirrored'" in out and "read as 'weak-signal'" in out
           and "mirrored oracles need especially careful review: gold" in out, out)

    bad = json.loads(json.dumps(SKILL_EXAMPLE))
    bad["testCases"][0]["oracle"] = "copied"
    code, out = run(bad)
    expect("unknown oracle value is an error that lists the allowed values (exit 1)",
           code == 1 and "invalid oracle 'copied'" in out and "weak-signal" in out, out)

    ghost = json.loads(json.dumps(SKILL_EXAMPLE))
    ghost["mutationSamples"][0]["expectedFailingTests"] = ["rejects_negative_price"]
    code, out = run(ghost)
    expect("mutation naming a test that is not in the packet is an error (exit 1)",
           code == 1 and "unknown test case id: rejects_negative_price" in out, out)

    extra = json.loads(json.dumps(SKILL_EXAMPLE))
    extra["testCases"][0]["oracel"] = "independent"
    code, out = run(extra)
    expect("unknown key is reported, not silently ignored", code == 0 and "unknown key 'oracel'" in out, out)

    code, out = run(None, as_dir=True)
    expect("directory argument: clear error, exit 2, no traceback",
           code == 2 and "is a directory" in out and "Traceback" not in out, out)
    code, out = run(None, raw=b"\xff\xfe{not utf8")
    expect("non-UTF-8 file: clear error, exit 2", code == 2 and "not UTF-8" in out, out)
    code, out = run(None, raw=b'{"target": ')
    expect("invalid JSON: clear error, exit 2", code == 2 and "invalid JSON" in out, out)
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        missing = main([os.path.join(tempfile.gettempdir(), "no-such-manifest-4f1c.json")])
    expect("missing file: exit 2", missing == 2 and "file not found" in sink.getvalue(), sink.getvalue())

    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--help"], capture_output=True, text=True)
    expect("--help prints usage and exits 0", proc.returncode == 0 and "usage:" in proc.stdout, proc.stdout + proc.stderr)

    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else "\n      " + detail.replace("\n", "\n      ")))
    print(f"selftest: {len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
