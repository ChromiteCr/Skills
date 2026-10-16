"""TOKEN-LESS SYNTHETIC tests. Only temporary local repositories; GitHub is mocked.
No live repository/config/guard is modified and no external API is contacted.
"""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/pr_automation/prctl.py'
spec = importlib.util.spec_from_file_location('synthetic_prctl', MODULE)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class LocalStorageBoundaryTests(unittest.TestCase):
    """SYNTHETIC local paths only; no cloud directory is created or accessed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='SYNTHETIC-local-only-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()

    def test_known_cloud_paths_refused_before_any_write(self):
        for part in ('OneDrive', 'OneDrive-Example', 'CloudStorage',
                     'Mobile Documents', 'Dropbox', 'Google Drive', 'iCloud Drive'):
            root = self.home / part / 'repo'
            with self.subTest(part=part), self.assertRaisesRegex(
                    p.Refused, 'cloud_synced_path_forbidden'):
                p.Controller(root)
            self.assertFalse((self.home / part).exists())

    def test_private_directory_cannot_create_cloud_path(self):
        target = self.home / 'OneDrive-SYNTHETIC'
        with self.assertRaisesRegex(p.Refused, 'cloud_synced_path_forbidden'):
            p.private_dir(target)
        self.assertFalse(target.exists())

    def test_symlink_destination_refused_even_if_target_is_local(self):
        target = self.home / 'real'
        target.mkdir()
        alias = self.home / 'alias'
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(p.Refused, 'symlink_local_path'):
            p.local_path(alias / 'repo')
        self.assertFalse((target / 'repo').exists())

    def test_relative_and_traversing_paths_refused(self):
        for path in ('relative/repo', self.home / '..' / 'other'):
            with self.assertRaisesRegex(p.Refused, 'absolute_local_path_required'):
                p.local_path(path)

    def test_local_absolute_directory_accepted(self):
        target = self.home / 'approved-local'
        self.assertEqual(p.private_dir(target), target)
        self.assertTrue(target.is_dir())

    def test_source_checkout_does_not_default_to_a_live_repository(self):
        with patch.object(p, '__file__', str(self.home / 'program' / 'prctl.py')):
            with self.assertRaisesRegex(p.Refused, 'local_runtime_not_installed'):
                p.Controller()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_private_runtime_config_selects_local_root(self):
        program = self.home / 'program'
        program.mkdir(mode=0o700)
        target = self.home / 'local-control-repo'
        p.atomic(program / 'runtime-config.json', {'schema': 1, 'root': str(target)})
        with patch.object(p, '__file__', str(program / 'prctl.py')):
            self.assertEqual(p.runtime_root(), target)
        self.assertFalse(target.exists())

    def test_private_runtime_config_rejects_hardlinks_and_public_permissions(self):
        config = self.home / 'runtime-config.json'
        p.atomic(config, {'schema': 1, 'root': str(self.home / 'SYNTHETIC-root')})
        with patch.object(p, '__file__', str(self.home / 'prctl.py')):
            config.chmod(0o644)
            with self.assertRaisesRegex(p.Refused, 'unsafe_private_file'):
                p.runtime_root()
            config.chmod(0o600)
            alias = self.home / 'SYNTHETIC-hardlink.json'
            os.link(config, alias)
            with self.assertRaisesRegex(p.Refused, 'unsafe_private_file'):
                p.runtime_root()


class TestRegistrationPolicyTests(unittest.TestCase):
    BASE = ('import unittest\n'
            'class Existing(unittest.TestCase):\n'
            '    def test_assertion(self):\n'
            '        self.assertEqual(2 + 2, 4)\n'
            'def run_tests(group="all"):\n'
            '    suite = unittest.TestSuite()\n'
            '    if group != "io":\n'
            '        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Existing))\n'
            '    result = unittest.TextTestRunner().run(suite)\n'
            '    return 0 if result.wasSuccessful() else 1\n')
    PAIR = ('        from test_extra import ExtraTests\n'
            '        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ExtraTests))\n')

    def added(self, addition=None):
        return self.BASE.replace('    result =', (self.PAIR if addition is None else addition) + '    result =')

    def test_current_cinegrade_style_two_line_registration(self):
        self.assertTrue(p.additive_test_registration(self.BASE, self.added()))
        # The top-level import variant also preserves all original AST nodes.
        new = 'from test_extra import ExtraTests\n' + self.added(self.PAIR.split('\n', 1)[1])
        self.assertTrue(p.additive_test_registration(self.BASE, new))

    def test_assertion_modification_deletion_and_fixture_body_edits_rejected(self):
        for old, new in [('2 + 2, 4', '2 + 2, 5'),
                         ('        self.assertEqual(2 + 2, 4)\n', ''),
                         ('        self.assertEqual', '        self.skipTest("skip")\n        self.assertEqual')]:
            with self.subTest(old=old):
                self.assertFalse(p.additive_test_registration(self.BASE, self.added().replace(old, new)))
        # Even a purely additive weakening of an old body is not a registration.
        changed = self.added().replace('        self.assertEqual', '        return\n        self.assertEqual')
        self.assertFalse(p.additive_test_registration(self.BASE, changed))

    def test_unsafe_imports_skips_runner_patching_and_shadowing_rejected(self):
        additions = [
            self.PAIR.replace('test_extra', 'os'),
            self.PAIR.replace('ExtraTests', 'Existing'),
            self.PAIR.replace('ExtraTests', 'unittest'),
            self.PAIR.replace('ExtraTests', 'ExtraTests as Existing'),
            self.PAIR.replace('test_extra', 'test_skip'),
            self.PAIR + '        unittest.TextTestRunner.run = lambda self, suite: None\n',
            self.PAIR + '        Existing = ExtraTests\n',
            self.PAIR + '        Existing.__unittest_skip__ = True\n',
            self.PAIR + '        Existing = unittest.expectedFailure(Existing)\n',
            self.PAIR + '        pytest.mark.xfail(Existing)\n',
        ]
        for addition in additions:
            with self.subTest(addition=addition):
                self.assertFalse(p.additive_test_registration(self.BASE, self.added(addition)))

    def test_redefinitions_arbitrary_append_and_duplicate_names_rejected(self):
        for addition in ['\ndef run_tests():\n    pass\n',
                         '\nclass Existing:\n    pass\n',
                         '\ndef test_new():\n    assert True\n']:
            self.assertFalse(p.additive_test_registration(self.BASE, self.added() + addition))
        duplicate = self.BASE.replace('    def test_assertion(self):',
                                     '    def test_assertion(self): pass\n    def test_assertion(self):')
        self.assertFalse(p.additive_test_registration(duplicate, duplicate.replace('    result =', self.PAIR + '    result =')))

    def test_fixture_registration_deletion_and_type_changes_always_require_review(self):
        c = p.Controller.__new__(p.Controller)
        for status, path in [('M', 'tests/fixtures/example/test_fixture.py'),
                             ('D', 'tests/test_example.py'), ('T', 'tests/test_example.py')]:
            with self.subTest(status=status, path=path), patch.object(c, 'paths', return_value=[status, path]), patch.object(c, 'git') as git:
                self.assertIsNotNone(c.review_required({'integration_base': 'SYNTHETIC'}, Path('/SYNTHETIC')))
                git.assert_not_called()


class FakeGitHub:
    def __init__(self):
        self.pr = None
        self.calls = []
        self.ambiguous_create = False
        self.fail_query = False
        self.controller = None
        self.protection = {
            'required_status_checks': {'strict': True, 'checks': [{'context': p.GATE_NAME, 'app_id': p.GATE_APP_ID}]},
            'required_pull_request_reviews': {'required_approving_review_count': 0, 'bypass_pull_request_allowances': {}},
            'enforce_admins': {'enabled': True}, 'allow_force_pushes': {'enabled': False},
            'allow_deletions': {'enabled': False}}
        self.rules, self.rulesets = [], {}

    def __call__(self, *args, check=True):
        self.calls.append(args)
        code, out = 0, ''
        if args[:2] == ('api', 'user'):
            out = p.NAME
        elif args[0] == 'api':
            if args[1].endswith('/branches/main/protection'):
                code, out = (0, json.dumps(self.protection)) if self.protection is not None else (1, '{}')
            elif args[1].endswith('/rules/branches/main'):
                out = json.dumps(self.rules)
            elif '/rulesets/' in args[1]:
                out = json.dumps(self.rulesets[int(args[1].rsplit('/', 1)[1])])
            else:
                raise AssertionError('Unexpected synthetic policy API: ' + repr(args))
        elif args[:2] == ('pr', 'list'):
            if self.fail_query:
                raise p.Refused('SYNTHETIC query unavailable')
            if self.pr:
                item, repo = self.controller.item()
                self.pr['headRefOid'] = self.controller.remote_sha(repo, item['branch'])
            out = json.dumps([self.pr] if self.pr else [])
        elif args[:2] == ('pr', 'create'):
            item, repo = self.controller.item()
            self.pr = dict(number=1, state='OPEN', isDraft=True,
                           body=args[args.index('--body') + 1], headRefName=item['branch'],
                           headRefOid=self.controller.remote_sha(repo, item['branch']), baseRefName='main',
                           mergeCommit=None, mergeStateStatus='CLEAN', statusCheckRollup=[], autoMergeRequest=None,
                           url='https://example.invalid/SYNTHETIC/1')
            code = 1 if self.ambiguous_create else 0
        elif args[:2] == ('pr', 'ready'):
            self.pr['isDraft'] = '--undo' in args
        elif args[:2] == ('pr', 'merge'):
            assert '--admin' not in args
            if '--disable-auto' in args:
                self.pr['autoMergeRequest'] = None
            else:
                assert '--auto' in args and '--match-head-commit' in args
                self.pr['autoMergeRequest'] = {'enabledAt': 'SYNTHETIC'}
        else:
            raise AssertionError('Unexpected synthetic API: ' + repr(args))
        return {'stdout': out, 'stderr': 'SYNTHETIC ambiguous response' if code else '',
                'returncode': code, 'exit_code': code, 'receipt': 'SYNTHETIC_API'}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        clean_environment = patch.dict(os.environ)
        clean_environment.start()
        self.addCleanup(clean_environment.stop)
        os.environ.pop('SKILLS_GUARD_FD', None)  # Synthetic tests never borrow a real owner's lease FD.
        self.tmp = tempfile.TemporaryDirectory(prefix='SYNTHETIC-prctl-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        config = self.home / 'synthetic.gitconfig'
        config.write_text('[user]\n name = ' + p.NAME + '\n email = ' + p.EMAIL + '\n[init]\n defaultBranch = main\n')
        original_env = p.environment

        def synthetic_env():
            env = original_env()
            env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(config))
            return env
        self.env_patch = patch.object(p, 'environment', synthetic_env)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.source, self.remote, self.live = [self.home / x for x in ('source', 'remote.git', 'live')]
        self.source.mkdir()
        self.git(self.source, 'init', '-b', 'main')
        self.put(self.source, 'skills/demo/example/SKILL.md', '# SYNTHETIC skill\n')
        self.put(self.source, 'skills/demo/example/scripts/work.py', 'print("SYNTHETIC")\n')
        self.put(self.source, 'skills/demo/example/legacy.md', 'SYNTHETIC obsolete documentation\n')
        self.put(self.source, 'skills/demo/example/obsolete.md', 'SYNTHETIC obsolete documentation\n')
        self.put(self.source, 'tests/cases/example.md', 'SYNTHETIC baseline test case\n')
        self.put(self.source, 'AUDIT-AND-IDEAS.md', 'SYNTHETIC exact audit snapshot\n')
        self.put(self.source, 'README.md', 'SYNTHETIC baseline\n')
        self.git(self.source, 'add', '.')  # Fixture creation ONLY; controller must never blanket-add.
        self.git(self.source, 'commit', '-m', 'SYNTHETIC baseline')
        self.git(self.home, 'clone', '--bare', str(self.source), str(self.remote))
        self.git(self.source, 'remote', 'add', 'origin', str(self.remote))
        self.git(self.home, 'clone', str(self.remote), str(self.live))
        (self.live / '.git/skills-dev-control').mkdir(mode=0o700)
        self.api = FakeGitHub()
        self.c = self.new_controller()
        # Trusted CI stand-in verifies a git-free export + complete manifest; failure can be injected.
        self.tool = self.home / 'synthetic-tools'
        self.tool.mkdir()
        self.ci = self.tool / 'ci.py'
        self.ci.write_text('import argparse, pathlib, json, sys\n'
                           'p=argparse.ArgumentParser(); p.add_argument("--files-json"); p.add_argument("--mode"); p.add_argument("--root"); p.add_argument("--branch"); a=p.parse_args()\n'
                           'assert pathlib.Path.cwd() == pathlib.Path(a.root)\n'
                           'assert a.mode == "local" and not pathlib.Path(".git").exists()\n'
                           'assert a.branch == "auto/synthetic-one"\n'
                           'manifest=pathlib.Path(a.files_json); assert manifest.is_absolute()\n'
                           'assert json.loads(manifest.read_text())\n'
                           'print("SYNTHETIC exact snapshot checked")\n')
        self.file_patch = patch.object(p, '__file__', str(self.tool / 'prctl.py'))
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)

    def git(self, cwd, *args):
        return subprocess.check_output(['git', *args], cwd=cwd, env=p.environment(), stderr=subprocess.PIPE).decode().strip()

    @staticmethod
    def put(repo, path, content):
        path = repo / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def new_controller(self):
        c = p.Controller(self.live, str(self.remote))
        c.gh = self.api
        self.api.controller = c
        return c

    def create(self):
        result = self.c.create(argparse.Namespace(id='synthetic-one', skill='example',
                            title='SYNTHETIC improve example', acceptance='SYNTHETIC tests pass'))
        return Path(result['clone'])

    def edit(self, repo):
        self.put(repo, 'skills/demo/example/SKILL.md', '# SYNTHETIC changed skill\n')
        self.put(repo, 'tests/test_example.py', 'import unittest\nclass Synthetic(unittest.TestCase):\n def test_real(self): self.assertEqual(2+2,4)\n')

    def advance_main(self, path='README.md', text='SYNTHETIC upstream\n'):
        self.put(self.source, path, text)
        self.git(self.source, 'add', '--', path)
        self.git(self.source, 'commit', '-m', 'SYNTHETIC upstream change')
        self.git(self.source, 'push', 'origin', 'main')
        return self.git(self.source, 'rev-parse', 'HEAD')

    def merge_pr_on_main(self):
        """SYNTHETIC GitHub response backed by a real temporary remote squash."""
        self.git(self.source, 'fetch', 'origin', self.api.pr['headRefName'])
        self.git(self.source, 'merge', '--squash', 'FETCH_HEAD')
        self.git(self.source, 'commit', '-m', 'SYNTHETIC server squash merge')
        self.git(self.source, 'push', 'origin', 'main')
        oid = self.git(self.source, 'rev-parse', 'HEAD')
        self.api.pr.update(state='MERGED', mergeCommit={'oid': oid})
        return oid

    def test_prepare_ignores_dirty_live_main_and_reads_exact_remote_audit(self):
        self.put(self.live, 'README.md', 'SYNTHETIC human edit KEEP')
        self.put(self.live, 'personal.txt', 'SYNTHETIC private human work KEEP')
        head = self.git(self.live, 'rev-parse', 'HEAD')
        new = self.advance_main('AUDIT-AND-IDEAS.md', 'SYNTHETIC latest audit\n')
        result = self.c.prepare()
        self.assertEqual(result['base'], new)
        self.assertEqual(p.load(result['audit_snapshot'])['text'], 'SYNTHETIC latest audit\n')
        self.assertEqual(self.git(self.live, 'rev-parse', 'HEAD'), head)
        self.assertEqual((self.live / 'README.md').read_text(), 'SYNTHETIC human edit KEEP')

    def test_dirty_owned_workspace_resumes_and_plan_is_stable(self):
        repo = self.create()
        self.edit(repo)
        first = self.c.item()[0]['plan_hash']
        self.c = self.new_controller()
        result = self.c.prepare()
        self.assertTrue(result['dirty'])
        self.assertEqual(result['plan_hash'], first)
        self.assertEqual(self.create(), repo)
        with self.assertRaisesRegex(p.Refused, 'another_plan_active'):
            self.c.create(argparse.Namespace(id='other', title='other', skill='example', acceptance='different'))

    def test_new_test_in_exact_snapshot_and_idempotent_finish(self):
        repo = self.create()
        self.edit(repo)
        self.ci.write_text(self.ci.read_text() + 'assert pathlib.Path("tests/test_example.py").is_file()\n')
        first = self.c.finish()
        self.assertEqual(first['status'], 'auto_merge_enabled')
        head = self.git(repo, 'rev-parse', 'HEAD')
        self.assertIn('tests/test_example.py', self.git(repo, 'show', '--name-only', '--format=', 'HEAD'))
        self.c = self.new_controller()
        second = self.c.finish()
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), head)
        self.assertEqual(second['counters']['commits'], 1)
        self.assertEqual(second['counters']['finish_attempts'], 2)
        self.assertEqual(second['counters']['validations'], 1)
        self.assertEqual(len(self.c.item()[0]['additional_test_receipts']), 1)
        self.assertEqual(sum(x[:2] == ('pr', 'create') for x in self.api.calls), 1)
        self.assertTrue((repo / '.git').is_dir())
        self.assertFalse((repo / '.git/objects/info/alternates').exists())

    def test_append_commit_and_counters_survive_new_turn(self):
        repo = self.create()
        self.edit(repo)
        self.c.finish()
        old = self.git(repo, 'rev-parse', 'HEAD')
        self.put(repo, 'skills/demo/example/SKILL.md', '# SYNTHETIC second change\n')
        self.c = self.new_controller()
        result = self.c.finish()
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD^'), old)
        self.assertEqual(result['counters']['commits'], 2)
        self.assertEqual(result['counters']['pr_create_attempts'], 1)
        self.assertEqual(result['counters']['validations'], 2)

    def test_ambiguous_pr_create_queries_then_reuses(self):
        repo = self.create()
        self.edit(repo)
        self.api.ambiguous_create = True
        self.assertEqual(self.c.finish()['status'], 'auto_merge_enabled')
        self.c.finish()
        self.assertEqual(sum(x[:2] == ('pr', 'create') for x in self.api.calls), 1)

    def test_ambiguous_push_reconciles_remote_before_retry(self):
        repo = self.create()
        self.edit(repo)
        original = self.c.git
        count = []

        def ambiguous(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args[0] == 'push':
                count.append(1)
                result.update(returncode=1, exit_code=1)
            return result
        self.c.git = ambiguous
        self.c.finish()
        self.c.finish()
        self.assertEqual(len(count), 1)

    def test_unknown_remote_advance_is_preserved_not_force_pushed(self):
        repo = self.create()
        self.edit(repo)
        self.c.finish()
        remote_copy = self.home / 'SYNTHETIC-other-writer'
        self.git(self.home, 'clone', str(self.remote), str(remote_copy))
        self.git(remote_copy, 'checkout', 'auto/synthetic-one')
        self.put(remote_copy, 'skills/demo/example/foreign.md', 'SYNTHETIC unknown advance KEEP')
        self.git(remote_copy, 'add', '--', 'skills/demo/example/foreign.md')
        self.git(remote_copy, 'commit', '-m', 'SYNTHETIC unknown writer')
        self.git(remote_copy, 'push', 'origin', 'auto/synthetic-one')
        remote_head = self.git(remote_copy, 'rev-parse', 'HEAD')
        self.put(repo, 'skills/demo/example/SKILL.md', 'SYNTHETIC owned later work KEEP')
        with self.assertRaisesRegex(p.Refused, 'remote_divergence_preserved'):
            self.c.finish()
        self.assertEqual(self.c.remote_sha(repo, 'auto/synthetic-one'), remote_head)
        self.assertEqual((repo / 'skills/demo/example/SKILL.md').read_text(), 'SYNTHETIC owned later work KEEP')

    def test_query_failure_blocks_retry_mutations(self):
        repo = self.create()
        self.edit(repo)
        self.api.fail_query = True
        with self.assertRaisesRegex(p.Refused, 'query unavailable'):
            self.c.finish()
        self.assertEqual(self.git(repo, 'rev-list', '--count', 'HEAD'), '1')
        self.assertFalse(any(x[:2] == ('pr', 'create') for x in self.api.calls))

    def test_true_test_failure_retains_edits_without_commit_or_push(self):
        repo = self.create()
        self.edit(repo)
        self.ci.write_text('import sys; print("SYNTHETIC failure"); sys.exit(19)\n')
        with self.assertRaisesRegex(p.Refused, 'local_checks_failed'):
            self.c.finish()
        self.assertEqual(self.git(repo, 'rev-list', '--count', 'HEAD'), '1')
        receipts = [p.load(x) for x in self.c.receipts.glob('validation-*.json')]
        self.assertEqual(receipts[-1]['exit_code'], 19)
        self.assertTrue((repo / 'tests/test_example.py').exists())
        self.assertFalse(self.api.pr)

    def test_new_business_unittest_failure_and_skip_fail_closed(self):
        repo = self.create()
        self.edit(repo)
        for body, code in [('self.fail("SYNTHETIC failing acceptance test")', 1),
                           ('self.skipTest("SYNTHETIC missing coverage")', 73)]:
            self.put(repo, 'tests/test_example.py',
                     'import unittest\nclass Synthetic(unittest.TestCase):\n def test_acceptance(self): ' + body + '\n')
            with self.assertRaisesRegex(p.Refused, 'targeted_tests_failed_or_incomplete') as caught:
                self.c.finish()
            self.assertEqual(caught.exception.code, code)
            self.assertIsNone(self.api.pr)
            self.assertEqual(self.git(repo, 'rev-list', '--count', 'HEAD'), '1')

    def test_persistent_failure_budget_caps_initial_plus_two_repairs(self):
        repo = self.create()
        self.edit(repo)
        self.c.finish()  # Existing PR and clone must survive budget exhaustion.
        pr = self.api.pr['number']
        head = self.git(repo, 'rev-parse', 'HEAD')
        self.put(repo, 'skills/demo/example/SKILL.md', 'SYNTHETIC repair work KEEP\n')
        self.ci.write_text('import sys; sys.exit(19)\n')
        for count in range(1, 4):
            self.c = self.new_controller()  # New process/run cannot reset the streak.
            with self.assertRaisesRegex(p.Refused, 'local_checks_failed') as caught:
                self.c.finish()
            self.assertEqual(self.c.item()[0]['validation_failure_streak'], count)
            self.assertEqual(self.c.item()[0]['validation_failures'], {'local_checks': count})
        self.assertIn('repair_budget_exhausted', caught.exception.reason)
        self.c = self.new_controller()
        count = self.c.item()[0]['counters']['validations']
        with self.assertRaisesRegex(p.Refused, 'repair_budget_exhausted'):
            self.c.finish()
        with self.assertRaisesRegex(p.Refused, 'repair_budget_exhausted'):
            self.c.run(argparse.Namespace(foreground=True, command=[sys.executable, '-c', 'pass']))
        self.assertEqual(self.c.item()[0]['counters']['validations'], count)
        self.assertEqual(self.api.pr['number'], pr)
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), head)
        self.assertEqual((repo / 'skills/demo/example/SKILL.md').read_text(), 'SYNTHETIC repair work KEEP\n')

    def test_full_snapshot_recovery_clears_only_current_validation_streak(self):
        repo = self.create()
        self.edit(repo)
        good_ci = self.ci.read_text()
        self.ci.write_text('import sys; sys.exit(1)\n')
        with self.assertRaisesRegex(p.Refused, 'local_checks_failed'):
            self.c.finish()
        self.ci.write_text(good_ci)
        self.put(repo, 'tests/test_example.py',
                 'import unittest\nclass Synthetic(unittest.TestCase):\n def test_real(self): self.fail("failure")\n')
        self.c = self.new_controller()
        with self.assertRaisesRegex(p.Refused, 'targeted_tests_failed'):
            self.c.finish()
        item = self.c.item()[0]
        self.assertEqual(item['validation_failure_streak'], 2)
        self.assertEqual(item['validation_failures'], {'local_checks': 1, 'targeted_tests': 1})
        self.edit(repo)
        self.c = self.new_controller()
        self.c.finish()
        item = self.new_controller().item()[0]
        self.assertEqual(item['validation_failure_streak'], 0)
        self.assertEqual(item['validation_failures'], {})
        self.assertEqual(item['counters']['local_checks_failures'], 1)
        self.assertEqual(item['counters']['targeted_tests_failures'], 1)

    def test_transport_and_launch_interruptions_do_not_consume_repair_budget(self):
        repo = self.create()
        self.edit(repo)
        self.api.fail_query = True
        with self.assertRaisesRegex(p.Refused, 'query unavailable'):
            self.c.finish()
        self.api.fail_query = False
        invoke = self.c.invoke
        for code in (124, 127):
            def interrupted(*args, **kwargs):
                if kwargs.get('kind') == 'validation':
                    return dict(exit_code=code, returncode=code, stdout='', stderr='',
                                timed_out=code == 124, launch_failed=code == 127,
                                stdout_truncated=False, stderr_truncated=False, receipt='SYNTHETIC-interruption')
                return invoke(*args, **kwargs)
            with patch.object(self.c, 'invoke', interrupted), self.assertRaisesRegex(p.Refused, 'validation_interrupted'):
                self.c.finish()
        self.assertEqual(self.new_controller().item()[0].get('validation_failure_streak', 0), 0)
        # An actual validator choosing 127 is a failure, not inability to launch.
        self.ci.write_text('import sys; sys.exit(127)\n')
        with self.assertRaisesRegex(p.Refused, 'local_checks_failed'):
            self.c.finish()
        self.assertEqual(self.new_controller().item()[0]['validation_failure_streak'], 1)

    def test_zero_exit_truncated_local_validation_fails_closed(self):
        repo = self.create()
        self.edit(repo)
        for stream in ('stdout', 'stderr'):
            self.c = self.new_controller()
            invoke = self.c.invoke
            def truncated(*args, **kwargs):
                result = invoke(*args, **kwargs)
                if kwargs.get('kind') == 'validation':
                    result[stream + '_truncated'] = True
                return result
            with patch.object(self.c, 'invoke', truncated), self.assertRaisesRegex(p.Refused, 'local_checks_failed_or_truncated'):
                self.c.finish()
        self.assertEqual(self.new_controller().item()[0]['validation_failure_streak'], 2)
        self.assertIsNone(self.api.pr)

    def test_existing_registration_pair_can_use_gates_but_fixtures_stay_draft(self):
        path = 'skills/demo/example/scripts/test_cinegrade.py'
        self.advance_main(path, TestRegistrationPolicyTests.BASE)
        repo = self.create()
        self.edit(repo)
        baseline = TestRegistrationPolicyTests()
        self.put(repo, path, baseline.added())
        self.put(repo, 'skills/demo/example/scripts/test_extra.py',
                 'import unittest\nclass ExtraTests(unittest.TestCase):\n def test_extra(self): self.assertTrue(True)\n')
        self.assertEqual(self.c.finish()['status'], 'auto_merge_enabled')
        self.put(repo, 'tests/cases/example.md', 'SYNTHETIC baseline test case\nSYNTHETIC appended evidence\n')
        self.assertEqual(self.c.finish()['status'], 'review_required')

    def test_unsafe_paths_and_symlinks_are_rejected_before_staging(self):
        repo = self.create()
        item = self.c.item()[0]
        for name in ('../bad', '/tmp/bad', 'skills/demo/example/../bad', '.github/a.yml',
                     'scripts/pr_automation/prctl.py', 'AUDIT-AND-IDEAS.md',
                     'skills/demo/example/.env', 'skills/demo/example/AGENTS.md',
                     'skills/demo/example/client.key', 'tests/test_other.py'):
            with self.subTest(path=name), self.assertRaises(p.Refused):
                self.c.allowed(item, repo, name)
        target = repo / 'skills/demo/example/link'
        target.symlink_to(self.home)
        with self.assertRaisesRegex(p.Refused, 'symlink'):
            self.c.finish()
        self.assertEqual(self.git(repo, 'diff', '--cached', '--name-only'), '')

    def test_cached_out_of_scope_cannot_hide_behind_restored_worktree(self):
        repo = self.create()
        self.edit(repo)
        original = (repo / 'AUDIT-AND-IDEAS.md').read_text()
        self.put(repo, 'AUDIT-AND-IDEAS.md', 'SYNTHETIC forbidden staged change')
        self.git(repo, 'add', '--', 'AUDIT-AND-IDEAS.md')
        self.put(repo, 'AUDIT-AND-IDEAS.md', original)
        with self.assertRaisesRegex(p.Refused, 'private_or_control_path'):
            self.c.finish()
        self.assertIn('AUDIT-AND-IDEAS.md', self.git(repo, 'diff', '--cached', '--name-only'))
        self.assertIsNone(self.api.pr)

    def test_unsafe_id_unknown_directory_and_plan_tamper(self):
        for name in ('../x', 'x/y', '-x', 'Mixed', 'x..y'):
            with self.assertRaises(p.Refused):
                p.label(name)
        unknown = self.c.data / 'items/synthetic-one'
        unknown.mkdir(mode=0o700)
        (unknown / 'KEEP').write_text('SYNTHETIC unknown data')
        with self.assertRaisesRegex(p.Refused, 'unknown_item_directory'):
            self.create()
        self.assertTrue((unknown / 'KEEP').exists())

    def test_plan_tamper_and_hook_config_and_stale_owner(self):
        repo = self.create()
        item = self.c.item()[0]
        item['title'] += ' altered'
        with self.assertRaisesRegex(p.Refused, 'plan_hash_changed'):
            self.c.prepare()
        item['title'] = 'SYNTHETIC improve example'
        self.git(repo, 'config', 'core.hooksPath', 'SYNTHETIC-hook-path')
        with self.assertRaisesRegex(p.Refused, 'hooks_filters'):
            self.c.prepare()
        self.git(repo, 'config', '--unset', 'core.hooksPath')
        hook = repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 0\n')
        hook.chmod(0o700)
        with self.assertRaisesRegex(p.Refused, 'active_hooks'):
            self.c.prepare()
        hook.unlink()  # Inside this synthetic temporary fixture only.
        owner = self.c.data / 'items/synthetic-one/owner.json'
        p.atomic(owner, {'id': 'synthetic-one', 'nonce': 'SYNTHETIC stale owner'})
        with self.assertRaisesRegex(p.Refused, 'ownership_mismatch'):
            self.c.prepare()

    def test_clean_base_advance_nonrewriting_merge(self):
        repo = self.create()
        self.edit(repo)
        self.c.checkpoint()
        head = self.git(repo, 'rev-parse', 'HEAD')
        original_base = self.c.item()[0]['base']
        main = self.advance_main()
        result = self.c.reconcile()
        self.assertEqual(result['status'], 'resumable')
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD^1'), head)
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD^2'), main)
        self.assertEqual(self.c.item()[0]['base'], original_base)
        self.assertEqual(self.c.item()[0]['integration_base'], main)
        self.ci.write_text(self.ci.read_text() +
                          'assert "README.md" not in {c["path"] for c in json.loads(manifest.read_text())}\n')
        self.c.finish()
        self.assertEqual(self.c.item()[0]['counters']['base_updates'], 1)
        item = self.c.item()[0]
        self.assertEqual(item['validated_integration_base'], main)
        snapshots = [p.load(f) for f in (self.c.data / 'snapshots').glob('*/snapshot.json')]
        self.assertTrue(any(s['integration_base'] == main and s['base'] == original_base for s in snapshots))

    def test_validation_cache_includes_integration_base(self):
        repo = self.create()
        self.edit(repo)
        self.c.checkpoint()
        item = self.c.item()[0]
        tree = item['validated_tree']
        item['validated_integration_base'] = '0' * 40  # SYNTHETIC stale cache provenance.
        self.c.save()
        self.c.checkpoint()
        self.assertEqual(item['validated_tree'], tree)
        self.assertEqual(item['validated_integration_base'], item['integration_base'])
        self.assertEqual(item['counters']['validations'], 2)

    def test_exact_add_preserves_unstaged_and_staged_deletions(self):
        repo = self.create()
        self.edit(repo)
        self.c.checkpoint()
        path = 'skills/demo/example/legacy.md'
        (repo / path).unlink()
        with patch.object(self.c, 'git', wraps=self.c.git) as calls:
            self.c.checkpoint()
        adds = [call.args[1:] for call in calls.call_args_list if 'add' in call.args[1:]]
        self.assertEqual(adds, [('--literal-pathspecs', 'add', '--', path)])
        self.assertIn('D\t' + path, self.git(repo, 'show', '--name-status', '--format=', 'HEAD'))
        path = 'skills/demo/example/obsolete.md'
        self.git(repo, 'rm', '--', path)  # SYNTHETIC pre-staged deletion must not be restaged.
        with patch.object(self.c, 'git', wraps=self.c.git) as calls:
            self.c.checkpoint()
        self.assertFalse(any('add' in call.args[1:] for call in calls.call_args_list))
        self.assertIn('D\t' + path, self.git(repo, 'show', '--name-status', '--format=', 'HEAD'))

    def test_dirty_advanced_base_has_checkpoint_recovery_path(self):
        repo = self.create()
        self.edit(repo)
        before = self.git(repo, 'rev-parse', 'HEAD')
        self.advance_main()
        self.assertEqual(self.c.finish()['status'], 'needs_update')
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), before)
        self.c.checkpoint()
        self.assertIsNone(self.api.pr)
        self.c = self.new_controller()
        self.assertEqual(self.c.finish()['status'], 'auto_merge_enabled')

    def test_merge_conflict_preserves_owned_commit_and_files(self):
        repo = self.create()
        self.edit(repo)
        self.c.checkpoint()
        head = self.git(repo, 'rev-parse', 'HEAD')
        self.advance_main('skills/demo/example/SKILL.md', '# SYNTHETIC incompatible upstream\n')
        with self.assertRaisesRegex(p.Refused, 'merge_conflict_preserved'):
            self.c.reconcile()
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), head)
        self.assertEqual((repo / 'skills/demo/example/SKILL.md').read_text(), '# SYNTHETIC changed skill\n')

    def test_exact_app_gate_no_bypass_classic_protection(self):
        original = json.loads(json.dumps(self.api.protection))
        self.c.verify_server_gate()
        mutations = [
            lambda d: d['required_status_checks']['checks'][0].update(app_id=-1),
            lambda d: d['required_status_checks']['checks'][0].update(context='SYNTHETIC spoofed name'),
            lambda d: d['required_status_checks'].update(strict=False),
            lambda d: d['enforce_admins'].update(enabled=False),
            lambda d: d['allow_force_pushes'].update(enabled=True),
            lambda d: d['allow_deletions'].update(enabled=True),
            lambda d: d['required_pull_request_reviews'].update(bypass_pull_request_allowances={'users': ['SYNTHETIC-bypass']}),
            lambda d: d.pop('required_pull_request_reviews'),
        ]
        for change in mutations:
            self.api.protection = json.loads(json.dumps(original))
            change(self.api.protection)
            with self.assertRaisesRegex(p.Refused, 'server_gate_not_enforced'):
                self.c.verify_server_gate()
        self.api.protection = None
        with self.assertRaises(p.Refused):
            self.c.verify_server_gate()

    def test_active_ruleset_gate_requires_app_and_zero_bypass(self):
        self.api.protection = None
        self.api.rules = [dict(type=t, ruleset_id=1) for t in ('pull_request', 'non_fast_forward', 'deletion')]
        self.api.rules.append({'type': 'required_status_checks', 'ruleset_id': 1, 'parameters': {
            'strict_required_status_checks_policy': True,
            'required_status_checks': [{'context': p.GATE_NAME, 'integration_id': p.GATE_APP_ID}]}})
        self.api.rulesets[1] = {'target': 'branch', 'enforcement': 'active', 'bypass_actors': []}
        self.c.verify_server_gate()
        self.api.rulesets[1]['bypass_actors'] = [{'actor_type': 'RepositoryRole', 'actor_id': 5}]
        with self.assertRaises(p.Refused):
            self.c.verify_server_gate()
        self.api.rulesets[1]['bypass_actors'] = []
        self.api.rulesets[1]['enforcement'] = 'evaluate'
        with self.assertRaises(p.Refused):
            self.c.verify_server_gate()
        self.api.rulesets[1]['enforcement'] = 'active'
        self.api.rules[-1]['parameters']['required_status_checks'][0]['integration_id'] = None
        with self.assertRaises(p.Refused):
            self.c.verify_server_gate()

    def test_missing_server_gate_stays_draft_then_recovers_without_duplicate(self):
        repo = self.create()
        self.edit(repo)
        good = self.api.protection
        self.api.protection = None
        with self.assertRaisesRegex(p.Refused, 'server_gate_not_enforced'):
            self.c.finish()
        self.assertEqual(self.c.item()[0]['phase'], 'server_gate_unverified')
        self.assertTrue(self.api.pr['isDraft'])
        self.assertFalse(any(c[:2] in (('pr', 'ready'), ('pr', 'merge')) for c in self.api.calls))
        self.api.protection = good
        self.assertEqual(self.c.finish()['status'], 'auto_merge_enabled')
        self.assertEqual(self.c.item()[0]['counters']['commits'], 1)
        self.assertEqual(sum(c[:2] == ('pr', 'create') for c in self.api.calls), 1)

    def test_export_is_byte_exact_and_validation_cannot_mutate_it(self):
        repo = self.create()
        self.edit(repo)
        self.ci.write_text(self.ci.read_text() + 'pathlib.Path("skills/demo/example/SKILL.md").write_text("SYNTHETIC mutation")\n')
        with self.assertRaisesRegex(p.Refused, 'export_content_changed'):
            self.c.finish()
        self.assertEqual((repo / 'skills/demo/example/SKILL.md').read_text(), '# SYNTHETIC changed skill\n')
        self.assertIsNone(self.api.pr)

    def test_existing_test_change_stays_draft(self):
        repo = self.create()
        self.edit(repo)
        self.put(repo, 'tests/cases/example.md', 'SYNTHETIC altered existing test\n')
        result = self.c.finish()
        self.assertEqual(result['status'], 'review_required')
        self.assertTrue(self.api.pr['isDraft'])
        self.assertFalse(any(x[:2] == ('pr', 'merge') for x in self.api.calls))

    def test_append_test_evidence_change_disables_auto_and_restores_draft(self):
        repo = self.create()
        self.edit(repo)
        self.c.finish()
        self.put(repo, 'tests/cases/example.md', 'SYNTHETIC evidence needing review')
        result = self.c.finish()
        self.assertEqual(result['status'], 'review_required')
        self.assertTrue(self.api.pr['isDraft'])
        self.assertIsNone(self.api.pr['autoMergeRequest'])
        self.assertEqual(result['counters']['disable_auto_attempts'], 1)
        self.assertEqual(result['counters']['draft_attempts'], 1)

    def test_failed_checks_then_merged_reconciliation_preserves_dirty_clone(self):
        repo = self.create()
        self.edit(repo)
        self.c.finish()
        self.api.pr['statusCheckRollup'] = [{'conclusion': 'FAILURE'}]
        self.assertEqual(self.c.reconcile()['status'], 'checks_failed')
        self.put(repo, 'skills/demo/example/SKILL.md', 'SYNTHETIC work after PR KEEP')
        self.put(repo, 'SYNTHETIC-untracked.txt', 'SYNTHETIC untracked KEEP')
        before = self.git(repo, 'rev-parse', 'HEAD')
        index = self.git(repo, 'write-tree')
        merge = self.merge_pr_on_main()
        tip = self.advance_main()
        self.assertNotEqual(merge, tip)  # Ancestor proof, not equality with current main.
        self.assertEqual(self.c.reconcile()['status'], 'merged')
        self.assertIsNone(self.c.state['active'])
        self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), before)
        self.assertEqual(self.git(repo, 'write-tree'), index)
        self.assertEqual(self.git(repo, 'rev-parse', 'origin/main'), tip)
        self.assertEqual((repo / 'SYNTHETIC-untracked.txt').read_text(), 'SYNTHETIC untracked KEEP')
        self.assertEqual((repo / 'skills/demo/example/SKILL.md').read_text(), 'SYNTHETIC work after PR KEEP')
        queries = [c for c in self.api.calls if c[:2] == ('pr', 'list')]
        self.assertTrue(all('mergeCommit' in c[c.index('--json') + 1].split(',') for c in queries))

    def test_merged_without_proven_main_ancestry_keeps_active_and_dirty(self):
        repo = self.create()
        self.edit(repo)
        self.c.finish()
        before = self.git(repo, 'rev-parse', 'HEAD')
        self.put(repo, 'skills/demo/example/SKILL.md', 'SYNTHETIC dirty KEEP')
        for merge in (None, {}, {'oid': 'SYNTHETIC-invalid'}, {'oid': 'f' * 40}, {'oid': before}):
            self.api.pr.update(state='MERGED', mergeCommit=merge)
            with self.subTest(merge=merge), self.assertRaisesRegex(p.Refused, 'merged_commit_'):
                self.c.finish()
            self.assertEqual(self.c.state['active'], 'synthetic-one')
            self.assertNotEqual(self.c.item()[0]['phase'], 'merged')
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), before)
            self.assertEqual((repo / 'skills/demo/example/SKILL.md').read_text(), 'SYNTHETIC dirty KEEP')

    def test_foreground_front_door_real_exit_and_fd_forwarding(self):
        repo = self.create()
        for command in (['sh', '-c', 'true'], ['env', 'sh'], ['python3', '&'], ['git', 'push', 'origin', 'main']):
            with self.assertRaises(p.Refused):
                p.command_allowed(command)
        fd = os.open(self.home / 'SYNTHETIC-fd', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with patch.dict(os.environ, {'SKILLS_GUARD_FD': str(fd)}):
                result = self.c.run(argparse.Namespace(foreground=True, command=[sys.executable, '-c',
                    'import os,sys; os.fstat(int(os.environ["SKILLS_GUARD_FD"])); print("SYNTHETIC"); sys.exit(23)']))
        finally:
            os.close(fd)
        self.assertEqual(result['exit_code'], 23)
        self.assertEqual(p.load(result['receipt'])['exit_code'], 23)

    def test_work_output_capture_is_bounded_with_true_exit(self):
        result = self.c.invoke([sys.executable, '-c',
                               'import sys; sys.stdout.write("x"*1100000); sys.exit(31)'],
                               check=False, kind='work')
        saved = p.load(result['receipt'])
        self.assertEqual(saved['exit_code'], 31)
        self.assertEqual(saved['stdout_bytes'], 1100000)
        self.assertEqual(len(saved['stdout']), 1024 * 1024)
        self.assertTrue(saved['stdout_truncated'])

    def test_timeout_and_explicit_finite_guard_bound(self):
        result = self.c.invoke([sys.executable, '-c', 'import time; time.sleep(2)'], timeout=0.05, check=False)
        self.assertEqual(result['exit_code'], 124)
        self.assertTrue(p.load(result['receipt'])['timed_out'])
        with patch.object(p, 'Controller') as constructor:
            self.assertEqual(p.main(['status', '--run-id', 'synthetic', '--timeout', '0']), 73)
            constructor.assert_not_called()

    def test_guard_full_receipt_truncation_and_stale_lease_exit(self):
        devctl = self.c.control / 'devctl.py'
        report = {'ok': False, 'status': 'command_finished', 'exit_code': 23, 'outer_exit_code': 0,
                  'stdout': 'SYNTHETIC-' * 200000, 'stderr': 'SYNTHETIC error', 'stdout_truncated': True,
                  'stderr_truncated': False, 'writer_finished': False,
                  'stdout_bytes_observed': 9999999, 'child_exit_code': 23, 'outputs_complete': False}
        devctl.write_text('import json\nprint(json.dumps(' + repr(report) + '))\n')
        payload, receipt, code = self.c.guard(['run'])
        self.assertEqual(code, 23)
        self.assertEqual(p.load(receipt)['stdout'], report['stdout'])
        self.assertTrue(p.load(receipt)['stdout_truncated'])
        self.assertEqual(stat.S_IMODE(Path(receipt).stat().st_mode), 0o600)
        runpath = self.c.data / 'runs/turn-one.json'
        p.atomic(runpath, {'owner': 'SYNTHETIC-private-owner-file', 'ended': False})
        devctl.write_text('import json\nprint(json.dumps({"status":"refused","reason":"stale_owner", "exit_code":77}))\n')
        args = argparse.Namespace(action='start', run_id='turn-one', timeout=600)
        result = self.c.dispatch(args, ['start', '--run-id', 'turn-one'])
        self.assertEqual(result['exit_code'], 77)
        self.assertNotIn('owner', json.dumps({k: v for k, v in result.items() if k != 'reason'}))
        self.assertTrue(Path(result['receipt']).exists())

    def test_start_persists_full_receipt_before_summary_and_same_run_checks_guard(self):
        devctl = self.c.control / 'devctl.py'
        devctl.write_text('import json,sys\n'
                          'print(json.dumps({"ok":True,"exit_code":0,"outer_exit_code":0,"status":"acquired",'
                          '"owner_file":"SYNTHETIC-owner-path","stdout":"", "run":"turn-one"}))\n')
        args = argparse.Namespace(action='start', run_id='turn-one', timeout=600)
        result = self.c.dispatch(args, ['start', '--run-id', 'turn-one'])
        self.assertEqual(result['status'], 'started')
        self.assertNotIn('owner_file', result)
        self.assertEqual(p.load(result['receipt'])['owner_file'], 'SYNTHETIC-owner-path')
        self.assertEqual(p.load(self.c.data / 'runs/turn-one.json')['begin_receipt'], result['receipt'])
        report = self.synthetic_guard_report({'status': 'already_started', 'exit_code': 0})
        devctl.write_text('import json\nprint(json.dumps(' + repr(report) + '))\n')
        with patch.object(self.c, 'guard', wraps=self.c.guard) as guard:
            self.assertEqual(self.c.dispatch(args, ['start', '--run-id', 'turn-one'])['exit_code'], 0)
            self.assertEqual(guard.call_args.args[0][0], 'run')

    def test_begin_receipt_recovers_missing_run_index_only_after_owner_check(self):
        receipt = self.c.receipt('devctl-result', {'status': 'acquired', 'run': 'recover-turn',
                                                'owner_file': 'SYNTHETIC-owner', 'exit_code': 0})
        args = argparse.Namespace(action='start', run_id='recover-turn', timeout=44)
        report = self.synthetic_guard_report({'status': 'already_started', 'exit_code': 0})
        with patch.object(self.c, 'guard', return_value=(report, receipt, 0)) as guard:
            result = self.c.dispatch(args, ['start', '--run-id', 'recover-turn'])
            self.assertEqual(result['status'], 'recovered_start')
            self.assertEqual(guard.call_args.args[0][0], 'run')
            self.assertIn('44', guard.call_args.args[0])
        self.assertTrue((self.c.data / 'runs/recover-turn.json').exists())

    @staticmethod
    def synthetic_guard_report(inner):
        return {'status': 'command_finished', 'exit_code': 0, 'writer_finished': True,
                'outputs_complete': True, 'stdout_truncated': False, 'stderr_truncated': False,
                'stdout': json.dumps(inner), 'stderr': 'SYNTHETIC guard stderr'}

    def test_nominal_guard_success_requires_complete_writer_and_streams(self):
        devctl = self.c.control / 'devctl.py'
        for key, value in [('writer_finished', False), ('writer_finished', None),
                           ('outputs_complete', False), ('outputs_complete', None),
                           ('stdout_truncated', True), ('stderr_truncated', True)]:
            report = self.synthetic_guard_report({'status': 'idle', 'exit_code': 0})
            if value is None:
                report.pop(key)
            else:
                report[key] = value
            devctl.write_text('import json\nprint(json.dumps(' + repr(report) + '))\n')
            with self.subTest(key=key, value=value):
                payload, receipt, code = self.c.guard(['run'])
                self.assertEqual(payload, report)
                self.assertEqual(code, 73)
                self.assertEqual({k: v for k, v in p.load(receipt).items()
                                  if k not in ('kind', 'credential_redaction')}, report)
        # Non-run guard actions do not execute a writer and need no writer fields.
        devctl.write_text('import json\nprint(json.dumps({"status":"SYNTHETIC","exit_code":0}))\n')
        for action in ('begin', 'end', 'status'):
            self.assertEqual(self.c.guard([action])[2], 0)

    def test_dispatch_requires_worker_dict_and_explicit_actual_exit(self):
        runpath = self.c.data / 'runs/synthetic-turn.json'
        p.atomic(runpath, {'owner': 'SYNTHETIC-owner', 'ended': False})
        args = argparse.Namespace(action='status', run_id='synthetic-turn', timeout=44)
        devctl = self.c.control / 'devctl.py'
        for stdout, expected in [('', 73), ('SYNTHETIC malformed', 73), ('[]', 73), ('null', 73),
                                 ('{}', 73), ('{"exit_code":false}', 73),
                                 ('{"exit_code":"0"}', 73), ('{"exit_code":29}', 29),
                                 ('{"status":"idle","exit_code":0}', 0)]:
            report = self.synthetic_guard_report({})
            report['stdout'] = stdout
            devctl.write_text('import json\nprint(json.dumps(' + repr(report) + '))\n')
            with self.subTest(stdout=stdout):
                result = self.c.dispatch(args, ['status', '--run-id', 'synthetic-turn'])
                self.assertEqual(result['exit_code'], expected)
                self.assertEqual(p.load(result['receipt'])['stdout'], stdout)

    def test_recovered_start_does_not_index_malformed_worker_success(self):
        receipt = self.c.receipt('devctl-result', {'status': 'acquired', 'run': 'recover-turn',
                                                'owner_file': 'SYNTHETIC-owner', 'exit_code': 0})
        args = argparse.Namespace(action='start', run_id='recover-turn', timeout=44)
        report = self.synthetic_guard_report([])
        with patch.object(self.c, 'guard', return_value=(report, receipt, 0)):
            result = self.c.dispatch(args, ['start', '--run-id', 'recover-turn'])
        self.assertEqual(result['exit_code'], 73)
        self.assertFalse((self.c.data / 'runs/recover-turn.json').exists())

    def test_guard_preserves_invalid_exit_receipt_and_transport_truncation(self):
        report = self.synthetic_guard_report({'status': 'idle', 'exit_code': 0})
        for stream in ('stdout', 'stderr'):
            transport = {'stdout': json.dumps(report), 'stderr': '', 'exit_code': 0,
                         'stdout_truncated': False, 'stderr_truncated': False,
                         'receipt': 'SYNTHETIC-transport'}
            transport[stream + '_truncated'] = True
            with patch.object(self.c, 'invoke', return_value=transport):
                payload, receipt, code = self.c.guard(['run'])
            self.assertEqual(code, 73)
            self.assertEqual(payload, report)
            self.assertEqual(p.load(receipt)['stdout'], report['stdout'])
        report.pop('exit_code')
        devctl = self.c.control / 'devctl.py'
        devctl.write_text('import json\nprint(json.dumps(' + repr(report) + '))\n')
        with self.assertRaisesRegex(p.Refused, 'invalid_guard_receipt; receipt='):
            self.c.guard(['run'])
        saved = [p.load(f) for f in self.c.receipts.glob('devctl-result-*.json')]
        self.assertTrue(any('exit_code' not in r and r['stdout'] == report['stdout'] for r in saved))

    def test_worker_main_emits_explicit_success_exit(self):
        guard_dir = self.c.control / 'lease-guard'
        guard_dir.mkdir(mode=0o700)
        fd = os.open(guard_dir / 'mutex.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with patch.object(p, 'Controller', return_value=self.c), \
                    patch.object(p, 'inherited_fd', return_value=(fd,)), \
                    patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
                code = p.main(['_worker', 'status', '--run-id', 'synthetic-turn'])
                inner = json.loads(output.getvalue())
        finally:
            os.close(fd)
        self.assertEqual(code, 0)
        self.assertEqual(inner['exit_code'], 0)
        self.assertEqual(inner['status'], 'idle')

    def test_no_credentials_in_environment_or_receipts_and_no_stdin_override(self):
        with patch.dict(os.environ, {'GH_TOKEN': 'ghp_SYNTHETICSECRET', 'GITHUB_TOKEN': 'SYNTHETIC',
                                     'GIT_DIR': '/SYNTHETIC/wrong', 'OTHER_API_KEY': 'SYNTHETIC-sensitive'}):
            env = p.environment()
            self.assertNotIn('GH_TOKEN', env)
            self.assertNotIn('GITHUB_TOKEN', env)
            self.assertNotIn('GIT_DIR', env)
            self.assertNotIn('OTHER_API_KEY', env)
            self.assertEqual(env['GH_CONFIG_DIR'], p.GH_CONFIG)
        path = self.c.receipt('synthetic', {'stdout': 'ghp_SYNTHETICSECRET\nOTHER_API_KEY=SYNTHETIC-sensitive',
                                            'token': 'SYNTHETIC owner', 'api_key': 'SYNTHETIC-key'})
        text = Path(path).read_text()
        self.assertNotIn('ghp_SYNTHETICSECRET', text)
        self.assertNotIn('SYNTHETIC owner', text)
        self.assertNotIn('SYNTHETIC-sensitive', text)
        self.assertNotIn('SYNTHETIC-key', text)
        with patch.object(p.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'', b'')) as run:
            self.c.invoke([sys.executable, '-c', 'pass'])
            self.assertIsNone(run.call_args.kwargs['input'])
            self.assertNotIn('stdin', run.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
