"""TOKEN-LESS SYNTHETIC software regression tests, NOT production observations.

All receipts, error details, paths and controller state below are invented fixtures.
No real Controller is initialized, no subprocess or API is run, and no production
repository, state, lock or owner is read or written. Any filesystem paths live in
TemporaryDirectory; guard transport and receipt persistence are mocked. Run with
PYTHONDONTWRITEBYTECODE=1 (or python -B) to avoid source-tree bytecode writes.
"""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/pr_automation/prctl.py'
spec = importlib.util.spec_from_file_location('synthetic_pr_worker_result', MODULE)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class WorkerResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='SYNTHETIC-worker-result-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.receipt = str(self.home / 'SYNTHETIC-guard-receipt.json')
        # Deliberately bypass __init__: never discover runtime config or real state.
        self.c = p.Controller.__new__(p.Controller)
        self.c.root = self.home / 'SYNTHETIC-root'
        self.c.control = self.home / 'SYNTHETIC-control'
        self.c.receipt = Mock(return_value=self.receipt)
        self.c.invoke = Mock(side_effect=AssertionError('unexpected subprocess'))
        self.subprocess = patch.object(
            p.subprocess, 'run', side_effect=AssertionError('no real subprocess allowed'))
        self.subprocess.start()
        self.addCleanup(self.subprocess.stop)

    @staticmethod
    def report(inner, **changes):
        """Invented complete guard evidence, including independent child outcome."""
        report = {
            'status': 'command_finished', 'exit_code': inner.get('exit_code', 0),
            'outer_exit_code': 0, 'child_exit_code': inner.get('exit_code', 0),
            'timed_out': False, 'signal': None, 'wrapper_signal': None,
            'writer_finished': True, 'outputs_complete': True,
            'stdout_truncated': False, 'stderr_truncated': False,
            'stdout': json.dumps(inner, ensure_ascii=False), 'stderr': '',
        }
        report.update(changes)
        return report

    def result(self, inner, code=None, **changes):
        report = self.report(inner, **changes)
        if code is None:
            code = report['exit_code']
        return p.Controller.worker_result(report, self.receipt, code)

    def guarded_result(self, report, transport_code=0, **transport_changes):
        transport = {
            'stdout': json.dumps(report), 'stderr': '', 'exit_code': transport_code,
            'stdout_truncated': False, 'stderr_truncated': False,
            'receipt': str(self.home / 'SYNTHETIC-transport.json'),
        }
        transport.update(transport_changes)
        self.c.invoke = Mock(return_value=transport)
        payload, receipt, code = self.c.guard(['run'])
        self.c.receipt.assert_called_with('devctl-result', report)
        return p.Controller.worker_result(payload, receipt, code)

    def assert_stopped(self, result, code=None, business_reason=None):
        self.assertEqual(result['status'], 'refused')
        self.assertIs(type(result['exit_code']), int)
        self.assertNotEqual(result['exit_code'], 0)
        self.assertEqual(result['receipt'], self.receipt)
        self.assertTrue(result.get('reason'))
        if code is not None:
            self.assertEqual(result['exit_code'], code)
        if business_reason is not None:
            self.assertNotEqual(result['reason'], business_reason)

    def test_complete_no_active_item_reason_survives_exit_73(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        self.assertEqual(self.result(inner), {**inner, 'receipt': self.receipt})

    def test_complete_business_reason_and_detail_survive_nonzero_exits(self):
        for code in (1, 23, 73):
            with self.subTest(code=code):
                reason = 'SYNTHETIC validation_failed; clone_and_pr_preserved; detail=中文\nsecond line'
                inner = {'status': 'refused', 'reason': reason, 'exit_code': code,
                         'phase': 'SYNTHETIC-validation', 'counters': {'failures': 2},
                         'receipt': str(self.home / 'SYNTHETIC-inner-receipt.json')}
                self.assertEqual(self.result(inner), {**inner, 'receipt': self.receipt})

    def test_complete_business_failure_survives_real_guard_adapter(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        # devctl uses report-only exit: business 73 is in JSON, transport is 0.
        self.assertEqual(self.guarded_result(self.report(inner), transport_code=0),
                         {**inner, 'receipt': self.receipt})

    def test_nonzero_transport_cannot_hide_behind_matching_business_exit(self):
        # SYNTHETIC collisions include SIGKILL/SIGTERM normalized by invoke(),
        # plus timeout and ordinary failure. Raw transport failure wins in all.
        for code, returncode in ((73, 73), (124, 124), (137, -9), (143, -15)):
            with self.subTest(code=code, returncode=returncode):
                inner = {'status': 'refused', 'reason': 'SYNTHETIC-business-failure', 'exit_code': code}
                result = self.guarded_result(self.report(inner), transport_code=code,
                                             returncode=returncode, timed_out=code == 124)
                self.assert_stopped(result, code, inner['reason'])
                self.assertEqual(result['reason'], 'guard_transport_failed')

    def test_success_path_and_nested_detail_unchanged(self):
        for status in ('idle', 'prepared', 'created', 'already_started', 'command_finished'):
            with self.subTest(status=status):
                inner = {'status': status, 'exit_code': 0, 'SYNTHETIC-detail': ['a', {'b': 2}]}
                self.assertEqual(self.result(inner), {**inner, 'receipt': self.receipt})

    def test_legacy_minimal_success_schema_remains_accepted(self):
        inner = {'status': 'idle', 'exit_code': 0}
        report = self.report(inner)
        for field in ('outer_exit_code', 'child_exit_code', 'timed_out', 'signal', 'wrapper_signal'):
            report.pop(field)
        self.assertEqual(p.Controller.worker_result(report, self.receipt, 0),
                         {**inner, 'receipt': self.receipt})

    def test_success_with_business_review_reason_is_not_refusal(self):
        inner = {'status': 'review_required', 'reason': 'SYNTHETIC existing assertion changed',
                 'exit_code': 0}
        self.assertEqual(self.result(inner), {**inner, 'receipt': self.receipt})

    def test_explicit_inner_exit_remains_authoritative_when_outer_is_zero(self):
        # Compatibility: existing tests accept explicit inner exits with outer zero.
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        self.assertEqual(self.result(inner, code=0, exit_code=0),
                         {**inner, 'receipt': self.receipt})

    def test_summary_does_not_mutate_full_guard_receipt(self):
        report = self.report({'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73})
        before = deepcopy(report)
        p.Controller.worker_result(report, self.receipt, 73)
        self.assertEqual(report, before)

    def test_real_guard_reason_overrides_business_reason(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        for reason, code in [('SYNTHETIC-stale-lease', 77), ('SYNTHETIC-timeout', 124),
                             ('SYNTHETIC-guard-refusal', 73)]:
            with self.subTest(reason=reason):
                result = self.result(inner, code=code, exit_code=code, reason=reason)
                self.assert_stopped(result, code, inner['reason'])
                self.assertEqual(result['reason'], reason)

    def test_real_guard_reason_with_unreadable_worker_still_wins(self):
        report = self.report({}, stdout='SYNTHETIC malformed', exit_code=77,
                             reason='SYNTHETIC-stale-lease', writer_finished=False)
        result = p.Controller.worker_result(report, self.receipt, 77)
        self.assert_stopped(result, 77)
        self.assertEqual(result['reason'], 'SYNTHETIC-stale-lease')

    def test_timeout_and_signal_exits_override_complete_business_failure(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        # Guard/transport exits differ from worker exit: never relabel as business failure.
        for code in (124, 137, 143, -9, -15):
            with self.subTest(code=code):
                result = self.result(inner, code=code, exit_code=code)
                self.assert_stopped(result, code, inner['reason'])

    def test_interrupt_markers_override_even_matching_business_exit(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        for field, value in [('timed_out', True), ('signal', 15), ('wrapper_signal', 15),
                             ('outer_exit_code', 73), ('child_exit_code', 23)]:
            with self.subTest(field=field):
                self.assert_stopped(self.result(inner, **{field: value}), 73, inner['reason'])

    def test_missing_child_outcome_or_timeout_attestation_fails_closed(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        for field in ('outer_exit_code', 'child_exit_code', 'timed_out'):
            with self.subTest(field=field):
                report = self.report(inner)
                report.pop(field)
                self.assert_stopped(p.Controller.worker_result(report, self.receipt, 73),
                                    73, inner['reason'])

    def test_guard_failure_cannot_look_like_worker_success(self):
        inner = {'status': 'idle', 'exit_code': 0}
        for code in (73, 124, 143):
            with self.subTest(code=code):
                self.assert_stopped(self.result(inner, code=code, exit_code=code), code)

    def test_incomplete_guard_fields_override_business_reason(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        for field, value in [('writer_finished', False), ('outputs_complete', False),
                             ('stdout_truncated', True), ('stderr_truncated', True)]:
            with self.subTest(field=field):
                result = self.guarded_result(self.report(inner, **{field: value}))
                self.assert_stopped(result, 73, inner['reason'])

    def test_missing_or_non_boolean_completion_fields_fail_closed(self):
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        for field in ('writer_finished', 'outputs_complete', 'stdout_truncated', 'stderr_truncated'):
            for value in (None, 0, 1, 'false', 'true'):
                with self.subTest(field=field, value=value):
                    report = self.report(inner)
                    if value is None:
                        report.pop(field)
                    else:
                        report[field] = value
                    self.assert_stopped(self.guarded_result(report), 73, inner['reason'])

    def test_writer_and_stream_incompleteness_refuse_nominal_success(self):
        inner = {'status': 'idle', 'exit_code': 0}
        for field, value in [('writer_finished', False), ('outputs_complete', False),
                             ('stdout_truncated', True), ('stderr_truncated', True)]:
            with self.subTest(field=field):
                self.assert_stopped(self.guarded_result(self.report(inner, **{field: value})), 73)

    def test_transport_truncation_refuses_nominal_success(self):
        inner = {'status': 'idle', 'exit_code': 0}
        for field in ('stdout_truncated', 'stderr_truncated'):
            with self.subTest(field=field):
                self.assert_stopped(self.guarded_result(self.report(inner), **{field: True}), 73)

    def test_transport_truncation_overrides_even_matching_business_exit_73(self):
        # Regression trap: code 73 alone cannot distinguish business refusal from
        # incomplete transport. Retaining a reason must not hide that uncertainty.
        inner = {'status': 'refused', 'reason': 'no_active_item', 'exit_code': 73}
        for field in ('stdout_truncated', 'stderr_truncated'):
            with self.subTest(field=field):
                self.assert_stopped(self.guarded_result(
                    self.report(inner), transport_code=73, **{field: True}),
                    73, inner['reason'])

    def test_nonzero_worker_without_business_reason_still_has_failure_reason(self):
        for reason in (None, ''):
            with self.subTest(reason=reason):
                inner = {'status': 'command_finished', 'exit_code': 23}
                if reason is not None:
                    inner['reason'] = reason
                self.assert_stopped(self.result(inner), 23)

    def test_malformed_json_and_non_object_worker_output_fail_closed(self):
        for stdout in ('', 'SYNTHETIC not JSON', '{', '[]', 'null', '1', 'true',
                       '"SYNTHETIC"', '{}\n{}'):
            with self.subTest(stdout=stdout):
                report = self.report({}, exit_code=0, stdout=stdout)
                self.assert_stopped(p.Controller.worker_result(report, self.receipt, 0), 73)

    def test_worker_exit_must_be_explicit_integer_not_bool(self):
        for exit_value in (None, False, True, '0', '73', 0.0, 73.0, [], {}):
            with self.subTest(exit_value=exit_value):
                inner = {'status': 'idle'}
                if exit_value is not None:
                    inner['exit_code'] = exit_value
                report = self.report(inner, exit_code=0)
                self.assert_stopped(p.Controller.worker_result(report, self.receipt, 0), 73)

    def test_invalid_worker_receipt_does_not_erase_nonzero_guard_exit(self):
        report = self.report({}, exit_code=143, stdout='SYNTHETIC invalid')
        self.assert_stopped(p.Controller.worker_result(report, self.receipt, 143), 143)

    def test_guard_exit_must_be_explicit_integer_before_worker_parsing(self):
        for exit_value in (None, False, True, '0', 0.0):
            with self.subTest(exit_value=exit_value):
                report = self.report({'status': 'idle', 'exit_code': 0})
                if exit_value is None:
                    report.pop('exit_code')
                else:
                    report['exit_code'] = exit_value
                with self.assertRaisesRegex(p.Refused, 'invalid_guard_receipt'):
                    self.guarded_result(report)


class NoActiveItemBoundaryTests(unittest.TestCase):
    def test_run_before_create_refuses_73_before_any_command_or_write(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-no-active-item-') as directory:
            home = Path(directory).resolve()
            c = p.Controller.__new__(p.Controller)
            c.state = {'active': None, 'items': {}}
            c.data = home / 'SYNTHETIC-state-not-created'
            c.invoke = Mock(side_effect=AssertionError('child must not run'))
            c.inspect = Mock(side_effect=AssertionError('no clone should be inspected'))
            c.bump = Mock(side_effect=AssertionError('no counters may change'))
            c.save = Mock(side_effect=AssertionError('no state may be written'))
            c.create = Mock(side_effect=AssertionError('run may not implicitly create an item'))
            before = deepcopy(c.state)
            with patch.object(p, 'private_dir', side_effect=AssertionError('no directory write')) as mkdir, \
                    patch.object(p, 'command_allowed', side_effect=AssertionError('too late')) as allowed, \
                    patch.object(p.subprocess, 'run', side_effect=AssertionError('no subprocess')) as child:
                for foreground, command in [(True, ['SYNTHETIC-never-executed']),
                                             (True, ['--', 'SYNTHETIC-never-executed']),
                                             (False, ['sh', '-c', 'SYNTHETIC-never-executed'])]:
                    with self.subTest(foreground=foreground, command=command):
                        with self.assertRaises(p.Refused) as caught:
                            c.run(argparse.Namespace(foreground=foreground, command=command))
                        self.assertEqual(caught.exception.reason, 'no_active_item')
                        self.assertEqual(caught.exception.code, 73)
                for operation in (c.invoke, c.inspect, c.bump, c.save, c.create, mkdir, allowed, child):
                    operation.assert_not_called()
            self.assertEqual(c.state, before)
            self.assertFalse(c.data.exists())
            self.assertEqual(list(home.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
