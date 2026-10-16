#!/usr/bin/env python3
"""Read-only PR test orchestration; NOT an authority to approve or merge a PR.

Git checkout: --base BASE compares BASE...HEAD, including both sides of renames.
Exported tree: --root TREE --files-json FILE does not need .git. FILE is a JSON
list of repo-relative paths, or {"files": [...]}; entries may instead be
{"path": "...", "status": "A|M|D|T"}. GitHub filename/status/previous_filename
records are also accepted. Supply the COMPLETE change set, including deletions.
--skill NAME (repeatable) selects tests without a diff; it never certifies scope.
--branch auto/... enables a defense-in-depth file scope check. A trusted
controller must independently verify scope, semantic test weakening, approvals,
and checks for the exact reviewed head/merge SHA using policy outside this tree.

No dependencies are needed by this runner itself. requirements-ci.txt pins the
imports exercised by the skill tests. Local mode uses the SAME gate as CI mode;
there is no platform/skip bypass. Bento's complete regression suite requires
macOS 14+, Swift/Apple Vision, Chrome and its fonts; the older shared photo I/O
selftests require Apple's Display P3 ICC profile. Missing coverage fails closed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
CINEGRADE = "skills/photography/photo-cinematic-grade"
METADATA = {
    "README.md", "CHANGELOG.md", "SKILL_INDEX.md", "VERSIONING.md", "LICENSE",
    "AUDIT-AND-IDEAS.md", "CONTRIBUTING.md", ".gitignore",
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
}
AUTO_METADATA = {
    "README.md", "CHANGELOG.md", "SKILL_INDEX.md",
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
}
STATUSES = {"A": "A", "M": "M", "D": "D", "T": "T", "added": "A",
            "modified": "M", "removed": "D", "changed": "T"}
# Avoid treating a test named "HEIC skipped with a warning" as skipped coverage.
INCOMPLETE = re.compile(
    r"(?im)^\s*(?:OK|FAILED)\s*\([^\n)]*(?:skipped|expected failures)=[1-9]"
    r"|^.*\.\.\. skipped [\"']|\b(?:ICC tests|P3 checks) skipped\b"
    r"|^Ran 0 tests\b|\b0/0 (?:self-tests |tests )?passed\b"
)


class CIError(ValueError):
    """Invalid inputs or incomplete required coverage."""


@dataclass(frozen=True)
class Change:
    path: str
    status: str = "M"


@dataclass(frozen=True)
class Check:
    name: str
    argv: tuple[str, ...]
    cwd: Path
    timeout: int = 600
    blocked: str = ""


def safe_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise CIError(f"invalid repository-relative path: {value!r}")
    path = PurePosixPath(value)
    if (path.is_absolute() or any(p in {"", ".", ".."} for p in value.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise CIError(f"invalid repository-relative path: {value!r}")
    return value


def unique_changes(changes: Sequence[Change]) -> list[Change]:
    result: dict[str, Change] = {}
    for change in changes:
        safe_path(change.path)
        if change.status not in {"A", "M", "D", "T"}:
            raise CIError(f"unsupported change status: {change.status!r}")
        if change.path in result and result[change.path] != change:
            raise CIError(f"conflicting change records: {change.path}")
        result[change.path] = change
    return sorted(result.values(), key=lambda change: change.path)


def load_changes(path: Path, root: Path) -> list[Change]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("files")
    if not isinstance(data, list):
        raise CIError("--files-json must contain a list, or an object with a files list")
    changes = []
    for entry in data:
        if isinstance(entry, str):
            name = safe_path(entry)
            changes.append(Change(name, "M" if (root / name).exists() else "D"))
            continue
        if not isinstance(entry, dict):
            raise CIError("file records must be strings or objects")
        name = safe_path(entry.get("path", entry.get("filename")))
        status = entry.get("status", "M")
        if not isinstance(status, str):
            raise CIError(f"unsupported change status: {status!r}")
        if status in {"renamed", "R"}:
            changes.extend([Change(safe_path(entry.get("previous_filename")), "D"), Change(name, "A")])
        elif isinstance(status, str) and status in STATUSES:
            changes.append(Change(name, STATUSES[status]))
        else:
            raise CIError(f"unsupported change status: {status!r}")
    return unique_changes(changes)


def git_changes(root: Path, base: str) -> list[Change]:
    """Resolve the revision first so untrusted text cannot become a git option."""
    revision = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", base + "^{commit}"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise CIError("git did not resolve --base to a commit")
    raw = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
         "--name-status", "-z", revision + "...HEAD", "--"],
        cwd=root, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    fields = raw.split("\0")
    if fields[-1] != "" or len(fields[:-1]) % 2:
        raise CIError("malformed git name-status output")
    return unique_changes([Change(fields[i + 1], fields[i]) for i in range(0, len(fields) - 1, 2)])


def business_test_owner(root: Path, name: str) -> Path | None:
    """Map only controller-supported test paths to one existing skill."""
    parts = PurePosixPath(name).parts
    if len(parts) < 2 or parts[0] != "tests":
        return None
    matches = []
    for skill, directory in skill_dirs(root).items():
        exact = "test_" + skill.replace("-", "_") + ".py"
        if ((len(parts) == 2 and parts[1] == exact)
                or (len(parts) >= 3 and parts[1] == skill)):
            matches.append(directory)
    if len(matches) > 1:
        raise CIError("ambiguous business test owner: " + name)
    return matches[0] if matches else None


def scope_errors(root: Path, changes: Sequence[Change], branch: str) -> list[str]:
    """Conservative auto/* allowlist, not semantic review or merge permission."""
    if not branch.startswith("auto/"):
        return []  # Maintenance can test policy files, but gains no merge authorization.
    errors = []
    for change in changes:
        name = safe_path(change.path)
        path = PurePosixPath(name)
        lower = name.lower()
        parts = {part.lower() for part in path.parts}
        allowed = (name in AUTO_METADATA or name.startswith(("skills/", "tests/cases/", "tests/fixtures/"))
                   or business_test_owner(root, name) is not None)
        sensitive = (
            parts & {".git", ".github", ".ssh", ".aws", ".openclaw", ".claude", ".config", "control", "credentials", "skills-dev-control"}
            or path.name.lower() in {
                "audit-and-ideas.md", "contributing.md", "agents.md", "claude.md",
                ".netrc", ".npmrc", ".pypirc", ".gitconfig", ".gitmodules", ".gitattributes",
                "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "authorized_keys", "kubeconfig",
            }
            or any(part.startswith(".env") for part in parts)
            or re.search(r"(?:^|[/_.-])(?:credentials?|secrets?|tokens?)(?:[/_.-]|$)", lower)
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
        )
        if not allowed or sensitive:
            errors.append(f"auto branch cannot change protected/control path: {name}")
        # Built-in selftests live in production scripts; conservatively require
        # maintenance review for script deletion instead of guessing from a name.
        is_test = (name.startswith("tests/") or "scripts" in path.parts
                   or path.name.startswith(("test_", "test-")) or path.stem in {"test", "tests", "selftest"}
                   or path.name.endswith(("_test.py", ".test.js", ".spec.js")))
        if change.status == "D" and is_test:
            errors.append(f"auto branch cannot remove/rename existing tests or fixtures: {name}")
        target = root / name
        if change.status == "T" or any(p.is_symlink() for p in [target, *target.parents] if p != root.parent):
            errors.append(f"auto branch cannot introduce type changes/symlinks: {name}")
    return errors


def skill_dirs(root: Path) -> dict[str, Path]:
    result = {}
    for path in sorted((root / "skills").glob("*/*/SKILL.md")):
        if path.parent.name in result:
            raise CIError(f"duplicate skill name: {path.parent.name}")
        result[path.parent.name] = path.parent
    if not result:
        raise CIError("no skills found; refusing an empty test scope")
    return result


def affected_dirs(root: Path, changes: Sequence[Change], wanted: Sequence[str]) -> set[Path]:
    skills = skill_dirs(root)
    all_dirs = set(skills.values()) | {p.parent.parent for p in (root / "skills").glob("*/_shared/scripts/*.py")}
    selected: set[Path] = set()
    for name in wanted:
        if name not in skills:
            raise CIError(f"unknown --skill: {name}")
        selected.add(skills[name])
    for change in changes:
        name = change.path
        parts = PurePosixPath(name).parts
        basename = parts[-1]
        if ("requirements" in basename.lower() or basename in {"pyproject.toml", "uv.lock", "poetry.lock"}
                or (name.startswith("scripts/") and not name.startswith("scripts/pr_automation/"))
                or name.startswith("templates/")):
            selected.update(all_dirs)
        elif len(parts) >= 3 and parts[0] == "skills":
            owner = root.joinpath(*parts[:3])
            if parts[2] == "_shared":
                selected.update(p for p in all_dirs if p.parent.name == parts[1])
            elif owner in all_dirs:
                selected.add(owner)
                shared = root / "skills" / parts[1] / "_shared"
                if shared in all_dirs:
                    selected.add(shared)
            else:
                selected.update(all_dirs)  # Deleted/unrecognised owner: conservative coverage.
            # Shared code copies can differ in a bad PR; match the filename, not digest.
            if len(parts) >= 5 and parts[3] == "scripts" and basename.endswith(".py"):
                selected.update(p.parent.parent for p in (root / "skills").glob(f"*/*/scripts/{basename}"))
        elif name.startswith(("tests/cases/", "tests/fixtures/")):
            owner_name = Path(parts[2]).stem if parts[1] == "cases" else parts[2]
            owner_name = {"latex-paper-check": "latex-paper-formatter"}.get(owner_name, owner_name)
            if owner_name in skills:
                selected.add(skills[owner_name])
            else:
                selected.update(all_dirs)
        elif business_test_owner(root, name) is not None:
            selected.add(business_test_owner(root, name))
        elif name == "tests/test_latex_checker.py":
            selected.add(skills["latex-paper-formatter"])
        elif (name in METADATA or name.startswith((".github/", "scripts/pr_automation/", "tests/test_pr"))):
            pass  # Mandatory global validation and automation unit tests still run.
        else:
            selected.update(all_dirs)
    # Explicit --skill and fixture-only selections also exercise category helpers.
    for directory in tuple(selected):
        shared = directory.parent / "_shared"
        if shared in all_dirs:
            selected.add(shared)
    return selected


def build_checks(root: Path, selected: set[Path]) -> list[Check]:
    python = sys.executable
    if not (root / "scripts/validate.sh").is_file() or not (root / "tests/test_pr_ci.py").is_file():
        raise CIError("mandatory global validator or PR CI unit test file is missing")
    checks = [
        Check("global structure + LaTeX regressions", ("./scripts/validate.sh",), root),
        Check("PR automation unit tests", (python, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_pr*.py", "-v"), root),
    ]
    seen = set()
    for directory in sorted(selected):
        for script in sorted((directory / "scripts").glob("*.py")):
            if script.name.startswith("test_") or "--selftest" not in script.read_text(encoding="utf-8"):
                continue
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            if digest in seen:
                continue  # Identical shared bytes tested once, as in run-selftests.sh.
            seen.add(digest)
            blocked = ""
            if directory.name == "bento-infographic" and sys.platform != "darwin":
                blocked = "full bento tests require macOS 14+, Swift/Apple Vision, Chrome and SF Pro/PingFang/Inter fonts; Linux cannot certify this change"
            checks.append(Check(str(script.relative_to(root)) + " --selftest",
                                (python, "-B", str(script), "--selftest"), script.parent, blocked=blocked))
    for directory in sorted(selected):
        skill = directory.name
        named = "test_" + skill.replace("-", "_") + ".py"
        if (root / "tests" / named).is_file():
            checks.append(Check(f"business tests {named}", (
                sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
                "-p", named, "-v"), root))
        owned = root / "tests" / skill
        if owned.is_dir() and any(owned.rglob("test*.py")):
            checks.append(Check(f"business tests tests/{skill}", (
                sys.executable, "-B", "-m", "unittest", "discover", "-s", f"tests/{skill}",
                "-p", "test*.py", "-v"), root))
    if any(p.parent.name == "photography" for p in selected):
        test = root / CINEGRADE / "scripts/test_cinegrade.py"
        if not test.is_file():
            raise CIError("photography change requires the complete test_cinegrade.py suite")
        checks.append(Check("full test_cinegrade.py (all groups)", (python, "-B", str(test)), test.parent))
    return checks


def run_check(check: Check, env: dict[str, str]) -> bool:
    print(f"RUN: {check.name}", flush=True)
    if check.blocked:
        print(f"FAIL: required platform unavailable: {check.blocked}", flush=True)
        return False
    try:
        proc = subprocess.run(check.argv, cwd=check.cwd, env=env, capture_output=True,
                              text=True, errors="replace", timeout=check.timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {check.name}: {exc}", flush=True)
        return False
    output = proc.stdout + proc.stderr
    if output:
        print(output, end="" if output.endswith("\n") else "\n", flush=True)
    incomplete = INCOMPLETE.search(output)
    passed = proc.returncode == 0 and not incomplete
    print(f"{'PASS' if passed else 'FAIL'}: {check.name} (exit {proc.returncode})", flush=True)
    if incomplete:
        print("FAIL: required tests were skipped/empty/expected-failing; install the required platform/dependencies, do not treat this as final acceptance", flush=True)
    return passed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--base", help="git base revision; compare BASE...HEAD")
    source.add_argument("--files-json", type=Path, help="complete changed-file manifest for a git-free snapshot")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository/export root")
    parser.add_argument("--skill", action="append", default=[], help="additional skill to test, repeatable; never narrows diff-derived coverage")
    parser.add_argument("--mode", choices=("local", "ci"), default="local", help="same fail-closed checks in both modes")
    parser.add_argument("--branch", default=os.environ.get("GITHUB_HEAD_REF", ""), help="head branch; auto/* enables file scope restrictions")
    args = parser.parse_args(argv)
    if not (args.base or args.files_json or args.skill):
        parser.error("provide --base, --files-json, or --skill")
    try:
        root = args.root.resolve(strict=True)
        changes = git_changes(root, args.base) if args.base else load_changes(args.files_json, root) if args.files_json else []
        if (args.base or args.files_json) and not changes:
            raise CIError("empty changed-file set; refusing an empty diff gate")
        errors = scope_errors(root, changes, args.branch)
        if errors:
            raise CIError("\n".join(errors))
        selected = affected_dirs(root, changes, args.skill)
        checks = build_checks(root, selected)
        if not checks:
            raise CIError("empty required check set")
        print(f"Mode: {args.mode}; {len(changes)} changed paths; {len(selected)} affected skill/shared directories", flush=True)
        if not args.base and not args.files_json:
            print("Targeted tests only: --skill does NOT certify the changed-file scope or authorize a merge.", flush=True)
        if not selected:
            print("Metadata-only change: global structural checks and automation unit tests remain mandatory.", flush=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        # validate.sh invokes python3; keep it on this interpreter's environment.
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        results = [run_check(check, env) for check in checks]
        print(f"Required checks: {sum(results)}/{len(results)} passed; skipped coverage is a failure.", flush=True)
        return 0 if results and all(results) else 1
    except (CIError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
