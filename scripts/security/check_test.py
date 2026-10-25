import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('security_check', Path(__file__).with_name('check.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class SecurityRunnerTests(unittest.TestCase):
    def test_download_rejects_tampered_content(self):
        with patch.object(checker.urllib.request, 'urlopen', return_value=io.BytesIO(b'tampered')):
            with self.assertRaisesRegex(RuntimeError, 'Checksum mismatch'):
                checker.download('https://example.invalid/tool', '0' * 64)

    def test_secret_reports_redact_values_and_scan_all_history(self):
        with patch.object(checker, 'binary', return_value='gitleaks'), patch.object(checker, 'run') as run:
            checker.secrets()
        args = run.call_args.args
        self.assertIn('--redact=100', args)
        self.assertIn('--log-opts=--all', args)

    def test_image_scan_keeps_complete_report_before_applying_gate(self):
        with patch.object(checker, 'binary', return_value='trivy'), patch.object(checker, 'run') as run, \
                patch.object(checker, 'verify_image_platform') as verify:
            checker.image('example.invalid/image@sha256:' + 'a' * 64, 'linux/arm64')
        self.assertEqual(verify.call_args.args[1], 'linux/arm64')
        report, sbom, gate = [call.args for call in run.call_args_list]
        self.assertIn('--platform=linux/arm64', report)
        self.assertNotIn('--ignore-unfixed', report)
        self.assertNotIn('--severity=HIGH,CRITICAL', report)
        self.assertIn('--format=cyclonedx', sbom)
        self.assertIn('--ignore-unfixed', gate)
        self.assertIn('--exit-code=1', gate)

    def test_wrong_architecture_or_missing_metadata_cannot_pass_image_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'image.json'
            for metadata in [{}, {'ImageConfig': {'os': 'linux', 'architecture': 'amd64'}}]:
                report.write_text(json.dumps({'Metadata': metadata}))
                with self.assertRaisesRegex(RuntimeError, 'platform mismatch'):
                    checker.verify_image_platform(report, 'linux/arm64')
            report.write_text(json.dumps({'Metadata': {'ImageConfig': {'os': 'linux', 'architecture': 'arm64'}}}))
            checker.verify_image_platform(report, 'linux/arm64')

    def test_scanner_failure_propagates(self):
        with patch.object(checker, 'binary', return_value='gitleaks'), patch.object(
            checker, 'run', side_effect=subprocess.CalledProcessError(2, 'gitleaks')
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                checker.secrets()

    def test_empty_configuration_coverage_is_not_a_pass(self):
        with patch.object(checker, 'LOCK', {'config_paths': []}):
            with self.assertRaisesRegex(RuntimeError, 'No configuration checks'):
                checker.config()

    def test_configuration_failures_do_not_skip_remaining_targets(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(checker, 'REPORTS', Path(temporary)), \
                patch.object(checker, 'LOCK', {'config_paths': ['first', 'second']}), \
                patch.object(checker, 'binary', return_value='trivy'), \
                patch.object(checker, 'run', side_effect=[subprocess.CalledProcessError(1, 'trivy'), None]) as run:
            with self.assertRaises(SystemExit) as error:
                checker.config()
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(run.call_count, 2)
            coverage = json.loads((Path(temporary) / 'config-coverage.json').read_text())
            self.assertEqual(coverage['trivyTargets'], ['first', 'second'])


if __name__ == '__main__':
    unittest.main()
