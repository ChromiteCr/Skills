#!/usr/bin/env python3
"""Executable regression tests for the modeling LaTeX static checker."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "skills/modeling/latex-paper-formatter/scripts/check_latex.py"
SKILL_DIR = CHECKER.parents[1]
FIXTURES = ROOT / "tests/fixtures/latex-paper-check"
REQUIRED_INVALID_CODES = {
    "duplicate-label",
    "missing-figure",
    "undefined-citation",
    "undefined-reference",
    "unresolved-placeholder",
}


def run_checker(
    path: Path, root: Path | None = ROOT, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CHECKER), "--json"]
    if root is not None:
        command += ["--root", str(root)]
    command.append(str(path))
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def parse_report(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    if not result.stdout:
        raise AssertionError(f"checker produced no JSON; stderr={result.stderr!r}")
    return json.loads(result.stdout)


def finding_codes(report: dict[str, object]) -> set[str]:
    findings = report["findings"]
    assert isinstance(findings, list)
    return {item["code"] for item in findings}


def main() -> int:
    valid = run_checker(FIXTURES / "valid.tex")
    valid_report = parse_report(valid)
    assert valid.returncode == 0, valid_report
    assert valid_report["summary"]["errors"] == 0, valid_report
    assert valid_report["summary"]["warnings"] == 0, valid_report

    invalid = run_checker(FIXTURES / "invalid.tex")
    invalid_report = parse_report(invalid)
    assert invalid.returncode == 1, invalid_report
    missing_codes = REQUIRED_INVALID_CODES - finding_codes(invalid_report)
    assert not missing_codes, f"missing invalid fixture findings: {sorted(missing_codes)}"
    manual_numbers = {
        item["message"]
        for item in invalid_report["findings"]
        if item["code"] == "manual-number-reference"
    }
    for written in ("Figure 2", "公式 (3)", "式（5）"):
        assert any(written in message for message in manual_numbers), invalid_report

    biblatex = run_checker(FIXTURES / "biblatex-invalid.tex")
    biblatex_report = parse_report(biblatex)
    biblatex_codes = finding_codes(biblatex_report)
    assert biblatex.returncode == 1, biblatex_report
    assert "undefined-citation" in biblatex_codes, biblatex_report
    assert "missing-bibliography" not in biblatex_codes, biblatex_report
    citation_messages = {
        item["message"]
        for item in biblatex_report["findings"]
        if item["code"] == "undefined-citation"
    }
    assert any("missing2026" in message for message in citation_messages), biblatex_report
    assert not any("smith2025" in message for message in citation_messages), biblatex_report

    # Multi-file paper, checked the way SKILL.md says: from the skill directory,
    # without --root. Nested \input, a dotted file name, \graphicspath from the
    # root preamble and \bibliography inside a sub-file all resolve from the
    # root file's directory, as TeX resolves them.
    multifile = run_checker(FIXTURES / "multifile-valid/main.tex", root=None, cwd=SKILL_DIR)
    multifile_report = parse_report(multifile)
    assert multifile.returncode == 0, multifile_report
    assert multifile_report["summary"]["sources"] == 5, multifile_report
    assert multifile_report["summary"]["errors"] == 0, multifile_report
    assert multifile_report["summary"]["warnings"] == 0, multifile_report

    # A path written relative to the sub-file, a figure whose case differs from
    # the disk (reported on case-insensitive macOS too) and Chinese manual numbers.
    broken = run_checker(
        FIXTURES / "multifile-invalid/main.tex", root=FIXTURES / "multifile-invalid"
    )
    broken_report = parse_report(broken)
    assert broken.returncode == 1, broken_report
    broken_counts = Counter(
        item["code"] for item in broken_report["findings"] if item["severity"] != "info"
    )
    assert broken_counts == {
        "subfile-relative-path": 1,
        "path-case-mismatch": 1,
        "manual-number-reference": 2,
    }, broken_report

    with tempfile.TemporaryDirectory() as temp_directory:
        temp_root = Path(temp_directory)
        project = temp_root / "project"
        project.mkdir()
        (temp_root / "outside.tex").write_text("outside", encoding="utf-8")
        escaped = project / "escaped.tex"
        escaped.write_text("\\input{../outside}\n", encoding="utf-8")
        escaped_report = parse_report(run_checker(escaped, project))
        assert "path-outside-root" in finding_codes(escaped_report), escaped_report

        unreadable = project / "unreadable.tex"
        unreadable.write_bytes(b"\\documentclass{article}\n\xff")
        unreadable_report = parse_report(run_checker(unreadable, project))
        assert "unreadable-tex-source" in finding_codes(unreadable_report), unreadable_report

    selftest = subprocess.run(
        [sys.executable, str(CHECKER), "--selftest"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert selftest.returncode == 0, selftest.stdout + selftest.stderr
    assert "passed" in selftest.stdout, selftest.stdout

    usage = subprocess.run(
        [sys.executable, str(CHECKER), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert usage.returncode == 0 and "usage:" in usage.stdout, usage.stdout + usage.stderr

    print(
        "OK: LaTeX checker fixtures, TeX path semantics, path case, Chinese manual numbers, "
        "citation parsing, path containment, read errors, --selftest and --help."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
