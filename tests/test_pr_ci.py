#!/usr/bin/env python3
"""Standard-library regression tests for CI selection, scope and fail-closed gate."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_ci_under_test", ROOT / "scripts/pr_automation/ci.py")
ci = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ci
SPEC.loader.exec_module(ci)


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pr-ci-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.put("scripts/validate.sh", "#!/bin/sh\nexit 0\n")
        self.put("tests/test_pr_ci.py", "# fixture: never executed\n")
        self.alpha = self.skill("physics", "alpha")
        self.beta = self.skill("physics", "beta")
        self.gamma = self.skill("writing", "gamma")
        self.cine = self.skill("photography", "photo-cinematic-grade")
        self.put(ci.CINEGRADE + "/scripts/test_cinegrade.py", "# full suite fixture\n")

    def put(self, name, text=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def skill(self, category, name):
        return self.put(f"skills/{category}/{name}/SKILL.md", "fixture\n").parent

    def manifest(self, data):
        return self.put("files.json", json.dumps(data))


class ManifestTests(TreeCase):
    def test_export_strings_infer_missing_deletions_without_git(self):
        path = self.manifest(["skills/physics/alpha/SKILL.md", "tests/cases/old.md"])
        self.assertEqual(ci.load_changes(path, self.root), [
            ci.Change("skills/physics/alpha/SKILL.md"), ci.Change("tests/cases/old.md", "D")])
        self.assertFalse((self.root / ".git").exists())

    def test_status_records_and_github_rename_include_old_path(self):
        path = self.manifest({"files": [
            {"path": "README.md", "status": "M"},
            {"filename": "tests/cases/new.md", "status": "renamed", "previous_filename": "tests/cases/old.md"},
        ]})
        self.assertEqual(ci.load_changes(path, self.root), [
            ci.Change("README.md"), ci.Change("tests/cases/new.md", "A"), ci.Change("tests/cases/old.md", "D")])

    def test_duplicate_conflict_is_rejected(self):
        with self.assertRaisesRegex(ci.CIError, "conflicting"):
            ci.unique_changes([ci.Change("a", "M"), ci.Change("a", "D")])
        self.assertEqual(ci.unique_changes([ci.Change("a"), ci.Change("a")]), [ci.Change("a")])

    def test_unsafe_paths_rejected(self):
        for name in ["", "/tmp/a", "../a", "skills/../a", "./a", "a//b", "a/", "a\\b", "a\nb", "a\0b", None]:
            with self.subTest(name=name), self.assertRaises(ci.CIError):
                ci.safe_path(name)
        self.assertEqual(ci.safe_path("skills/example/with space.md"), "skills/example/with space.md")

    def test_invalid_manifests_are_rejected(self):
        for data in [None, {}, {"files": {}}, [1], [{"status": "M"}], [{"path": "a", "status": "?"}],
                     [{"path": "a", "status": "renamed"}], [{"path": "a", "status": []}], [{"path": "a", "status": {}}]]:
            with self.subTest(data=data), self.assertRaises(ci.CIError):
                ci.load_changes(self.manifest(data), self.root)

    def test_git_uses_merge_base_diff_and_handles_space_and_deletion(self):
        sha = "a" * 40
        with mock.patch.object(ci.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, sha + "\n", ""),
            subprocess.CompletedProcess([], 0, b"M\0skills/physics/alpha/a b.py\0D\0tests/cases/old.md\0", b""),
        ]) as run:
            changes = ci.git_changes(self.root, "origin/main")
        self.assertEqual(changes[-1], ci.Change("tests/cases/old.md", "D"))
        self.assertIn("--end-of-options", run.call_args_list[0].args[0])
        command = run.call_args_list[1].args[0]
        self.assertIn(sha + "...HEAD", command)
        self.assertIn("--no-renames", command)
        self.assertIn("--no-ext-diff", command)
        self.assertIn("--no-textconv", command)

    def test_bad_git_revision_or_diff_cannot_be_an_empty_pass(self):
        for data in ["not-a-sha", ""]:
            with mock.patch.object(ci.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, data)), self.assertRaises(ci.CIError):
                ci.git_changes(self.root, "--evil")
        with mock.patch.object(ci.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, "a" * 40), subprocess.CompletedProcess([], 0, b"M\0odd")
        ]), self.assertRaises(ci.CIError):
            ci.git_changes(self.root, "main")


class ScopeTests(TreeCase):
    def test_auto_allows_skill_and_release_metadata(self):
        changes = [ci.Change("skills/physics/alpha/SKILL.md"), ci.Change("README.md"),
                   ci.Change("tests/cases/alpha.md", "A")]
        self.assertEqual(ci.scope_errors(self.root, changes, "auto/alpha"), [])

    def test_auto_denies_control_and_credentials_even_nested(self):
        paths = ["AUDIT-AND-IDEAS.md", "CONTRIBUTING.md", ".github/workflows/ci.yml",
                 "scripts/pr_automation/ci.py", "scripts/validate.sh", "tests/test_pr_ci.py",
                 ".git/config", "control/state.json", ".env", "skills/physics/alpha/credentials.json",
                 "skills/physics/alpha/private.key", "skills/physics/alpha/.github/a",
                 "skills/physics/alpha/AGENTS.md", "skills/physics/alpha/secrets/token.json",
                 "skills/physics/alpha/.netrc", "skills/physics/alpha/.npmrc",
                 "skills/physics/alpha/id_ed25519", "skills/physics/alpha/.gitattributes"]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(ci.scope_errors(self.root, [ci.Change(path)], "auto/alpha"))

    def test_existing_test_deletion_or_rename_source_fails(self):
        for path in ["tests/cases/alpha.md", "tests/fixtures/alpha/image.png", "skills/physics/alpha/scripts/test_alpha.py",
                     "skills/physics/alpha/scripts/check.py", "skills/physics/alpha/test.py"]:
            with self.subTest(path=path):
                errors = ci.scope_errors(self.root, [ci.Change(path, "D")], "auto/alpha")
                self.assertTrue(any("remove/rename" in error for error in errors))

    def test_symlink_and_type_change_fail(self):
        target = self.put("skills/physics/alpha/target.py")
        alias = target.with_name("alias.py")
        alias.symlink_to(target)
        for change in [ci.Change(str(alias.relative_to(self.root)), "A"), ci.Change("skills/physics/alpha/target.py", "T")]:
            self.assertTrue(ci.scope_errors(self.root, [change], "auto/alpha"))

    def test_maintenance_can_test_protected_files_without_merge_authorization(self):
        self.assertEqual(ci.scope_errors(self.root, [ci.Change(".github/workflows/skills-ci.yml")], "maintenance/bootstrap"), [])


class SelectionTests(TreeCase):
    def test_skill_metadata_selects_skill(self):
        self.assertEqual(ci.affected_dirs(self.root, [ci.Change("skills/physics/alpha/SKILL.md")], []), {self.alpha})

    def test_metadata_only_still_has_two_mandatory_checks(self):
        selected = ci.affected_dirs(self.root, [ci.Change("README.md")], [])
        self.assertEqual(selected, set())
        checks = ci.build_checks(self.root, selected)
        self.assertEqual(len(checks), 2)
        self.assertEqual(checks[0].argv, ("./scripts/validate.sh",))
        self.assertIn("test_pr*.py", checks[1].argv)
        self.assertEqual(ci.affected_dirs(self.root, [ci.Change("tests/test_prctl.py")], []), set())

    def test_case_and_fixture_select_owner(self):
        for path in ["tests/cases/alpha.md", "tests/fixtures/alpha/input.json"]:
            self.assertEqual(ci.affected_dirs(self.root, [ci.Change(path)], []), {self.alpha})

    def test_unknown_fixture_expands_instead_of_zero_tests(self):
        selected = ci.affected_dirs(self.root, [ci.Change("tests/fixtures/unknown/input.json")], [])
        self.assertTrue({self.alpha, self.gamma, self.cine}.issubset(selected))

    def test_shared_category_edits_expand_category_and_shared_selftests(self):
        shared = self.put("skills/physics/_shared/scripts/helper.py", "# --selftest\n").parent.parent
        selected = ci.affected_dirs(self.root, [ci.Change("skills/physics/_shared/contract.md")], [])
        self.assertEqual(selected, {self.alpha, self.beta, shared})
        own = ci.affected_dirs(self.root, [ci.Change("skills/physics/alpha/SKILL.md")], [])
        self.assertIn(shared, own)
        self.assertIn(shared, ci.affected_dirs(self.root, [], ["alpha"]))
        self.assertIn(shared, ci.affected_dirs(self.root, [ci.Change("tests/cases/alpha.md")], []))

    def test_shared_copy_edit_expands_even_if_copies_diverge(self):
        self.put("skills/physics/alpha/scripts/image_io.py", "one")
        self.put("skills/writing/gamma/scripts/image_io.py", "two")
        selected = ci.affected_dirs(self.root, [ci.Change("skills/physics/alpha/scripts/image_io.py")], [])
        self.assertEqual(selected, {self.alpha, self.gamma})

    def test_requirements_and_global_runner_expand_full_scope(self):
        for path in ["scripts/pr_automation/requirements-ci.txt", "requirements.txt", "pyproject.toml", "scripts/run-selftests.sh"]:
            selected = ci.affected_dirs(self.root, [ci.Change(path)], [])
            self.assertTrue({self.alpha, self.beta, self.gamma, self.cine}.issubset(selected))

    def test_controller_business_test_paths_map_to_exact_owner(self):
        for name in ['tests/test_alpha.py', 'tests/alpha/test_regression.py']:
            self.put(name, '# SYNTHETIC test path\n')
            change = ci.Change(name, 'A')
            self.assertEqual(ci.scope_errors(self.root, [change], 'auto/alpha'), [])
            self.assertEqual(ci.affected_dirs(self.root, [change], []), {self.alpha})
        self.assertTrue(ci.scope_errors(self.root, [ci.Change('tests/test_unowned.py', 'A')], 'auto/alpha'))
        self.assertTrue(ci.scope_errors(self.root, [ci.Change('tests/test_pr_ci.py', 'M')], 'auto/alpha'))
        self.assertTrue(ci.scope_errors(self.root, [ci.Change('tests/test_alpha.py', 'D')], 'auto/alpha'))

    def test_business_tests_are_executed_and_failures_are_not_skipped(self):
        # SYNTHETIC acceptance fixture, not real project observations.
        self.put('tests/test_alpha.py', 'import unittest\nclass Synthetic(unittest.TestCase):\n def test_bad(self): self.assertEqual(1, 2)\n')
        self.put('tests/alpha/test_more.py', 'import unittest\nclass Synthetic(unittest.TestCase):\n def test_ok(self): self.assertEqual(2, 2)\n')
        checks = ci.build_checks(self.root, {self.alpha})
        business = [check for check in checks if check.name.startswith('business tests')]
        self.assertEqual(len(business), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            results = [ci.run_check(check, dict(os.environ, PYTHONDONTWRITEBYTECODE='1')) for check in business]
        self.assertEqual(results, [False, True])

    def test_skill_option_never_narrows_diff_selection(self):
        selected = ci.affected_dirs(self.root, [ci.Change("skills/physics/alpha/SKILL.md")], ["gamma"])
        self.assertEqual(selected, {self.alpha, self.gamma})
        with self.assertRaisesRegex(ci.CIError, "unknown"):
            ci.affected_dirs(self.root, [], ["missing"])

    def test_selftests_deduplicated_by_bytes_but_full_cinegrade_always_added(self):
        self.put("skills/physics/alpha/scripts/helper.py", "# --selftest\n")
        self.put("skills/physics/beta/scripts/helper.py", "# --selftest\n")
        checks = ci.build_checks(self.root, {self.alpha, self.beta, self.cine})
        self.assertEqual(sum("--selftest" in check.argv for check in checks), 1)
        self.assertEqual(checks[-1].name, "full test_cinegrade.py (all groups)")
        self.assertEqual(len(checks[-1].argv), 3)  # No reduced group selector.

    def test_every_photography_change_requires_full_cinegrade(self):
        photo = self.skill("photography", "photo-caption-writer")
        self.assertEqual(ci.build_checks(self.root, {photo})[-1].name, "full test_cinegrade.py (all groups)")
        (self.cine / "scripts/test_cinegrade.py").unlink()
        with self.assertRaisesRegex(ci.CIError, "complete"):
            ci.build_checks(self.root, {photo})

    def test_bento_linux_is_explicitly_blocked_not_green_skip(self):
        bento = self.skill("coding-helper", "bento-infographic")
        self.put("skills/coding-helper/bento-infographic/scripts/bento.py", "# --selftest\n")
        with mock.patch.object(ci.sys, "platform", "linux"):
            checks = ci.build_checks(self.root, {bento})
        self.assertIn("macOS 14+", checks[-1].blocked)

    def test_missing_mandatory_test_file_fails(self):
        (self.root / "tests/test_pr_ci.py").unlink()
        with self.assertRaisesRegex(ci.CIError, "mandatory"):
            ci.build_checks(self.root, set())


class ExecutionTests(TreeCase):
    def run_script(self, code):
        check = ci.Check("fixture subprocess", (sys.executable, "-B", "-c", code), self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            return ci.run_check(check, dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_real_subprocess_exit_status_is_honored(self):
        self.assertTrue(self.run_script("print('2/2 passed')"))
        self.assertFalse(self.run_script("raise SystemExit(7)"))

    def test_skips_empty_and_expected_failures_are_not_success(self):
        for output in ["Ran 0 tests in 0.000s\nOK", "OK (skipped=1)", "OK (expected failures=1)",
                       "test_example ... skipped 'needs macOS'", "PASS: ICC tests skipped (no Display P3 profile on this system)",
                       "PASS: P3 checks skipped (no Display P3 profile on this system)", "0/0 self-tests passed"]:
            with self.subTest(output=output):
                self.assertFalse(self.run_script("print(" + repr(output) + ")"))
        self.assertTrue(self.run_script("print('PASS: HEIC skipped with a warning and the sips command')"))

    def test_timeout_oserror_and_platform_block_fail(self):
        check = ci.Check("fixture", ("unused",), self.root)
        for error in [FileNotFoundError("missing"), subprocess.TimeoutExpired("unused", 1)]:
            with mock.patch.object(ci.subprocess, "run", side_effect=error), contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(ci.run_check(check, {}))
        with mock.patch.object(ci.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(ci.run_check(ci.Check("platform", ("unused",), self.root, blocked="needs macOS"), {}))
            run.assert_not_called()

    def test_export_cli_runs_global_checks_without_git(self):
        files = self.manifest(["skills/physics/alpha/SKILL.md"])
        with mock.patch.object(ci, "run_check", return_value=True) as run, mock.patch.object(ci, "git_changes") as git, contextlib.redirect_stdout(io.StringIO()):
            result = ci.main(["--root", str(self.root), "--files-json", str(files), "--mode", "local", "--branch", "auto/alpha"])
        self.assertEqual(result, 0)
        git.assert_not_called()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[1]["PYTHONDONTWRITEBYTECODE"], "1")

    def test_empty_manifest_unknown_skill_and_scope_violation_fail(self):
        for args in [["--files-json", str(self.manifest([]))],
                     ["--files-json", str(self.manifest([])), "--skill", "alpha"], ["--skill", "not-a-skill"]]:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ci.main(["--root", str(self.root), *args]), 1)
        files = self.manifest([{"path": "AUDIT-AND-IDEAS.md", "status": "M"}])
        with mock.patch.object(ci, "run_check") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ci.main(["--root", str(self.root), "--files-json", str(files), "--branch", "auto/alpha"]), 1)
        run.assert_not_called()

    def test_all_required_checks_run_and_any_failure_fails_both_modes(self):
        for mode in ["local", "ci"]:
            with mock.patch.object(ci, "run_check", side_effect=[False, True]) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ci.main(["--root", str(self.root), "--skill", "alpha", "--mode", mode]), 1)
                self.assertEqual(run.call_count, 2)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/skills-ci.yml").read_text()

    def test_readonly_event_and_pinned_action_contract(self):
        text = self.workflow
        self.assertRegex(text, r"pull_request:\s+branches: \[main\]")
        self.assertRegex(text, r"push:\s+branches: \[main\]")
        self.assertNotIn("pull_request_target:", text)
        self.assertNotRegex(text, r"\$\{\{[^\n}]*\bsecrets\s*[.\[]")
        self.assertNotIn("paths:", text)
        self.assertNotIn("paths-ignore:", text)
        self.assertIn("contents: read", text)
        self.assertNotRegex(text, r"(?m)^\s+\S+: write\s*$")
        self.assertIn("persist-credentials: false", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn('python-version: "3.12.10"', text)
        self.assertIn('runs-on: macos-15', text)
        self.assertIn('Display P3.icc', text)
        self.assertIn('hashlib.sha256(data).hexdigest() != expected', text)
        self.assertIn('0b58fb370093f9a9f4ff785d94405710b79de67c', text)
        actions = re.findall(r"uses: (\S+)", text)
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(re.fullmatch(r"actions/(?:checkout|setup-python)@[0-9a-f]{40}", action) for action in actions))

    def test_aggregate_runs_always_with_nonempty_fixed_dependencies(self):
        self.assertIn("name: Skills gate", self.workflow)
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("needs: [checks]", self.workflow)
        source = self.workflow.split("python3 - <<'PY'\n", 1)[1].rsplit("          PY", 1)[0]
        code = textwrap.dedent(source)
        cases = [({}, False), ({"checks": {"result": "success"}}, True)]
        cases += [({"checks": {"result": status}}, False) for status in ["failure", "skipped", "cancelled", None]]
        cases += [({"other": {"result": "success"}}, False), ({"checks": {}}, False),
                  ({"checks": {"result": "success"}, "unexpected": {"result": "success"}}, False)]
        for needs, success in cases:
            with self.subTest(needs=needs):
                result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,
                                        env=dict(os.environ, NEEDS_JSON=json.dumps(needs)))
                self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_dependencies_all_pinned_and_justified_packages_present(self):
        lines = (ROOT / "scripts/pr_automation/requirements-ci.txt").read_text().splitlines()
        requirements = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
        self.assertTrue(requirements)
        for requirement in requirements:
            self.assertRegex(requirement, r"^[A-Za-z0-9_-]+==[0-9]+(?:\.[0-9]+)+$")
        self.assertIn("Pillow==11.3.0", requirements)
        self.assertIn("numpy==2.2.6", requirements)
        self.assertIn("opencv-python-headless==4.12.0.88", requirements)


if __name__ == "__main__":
    unittest.main(verbosity=2)
