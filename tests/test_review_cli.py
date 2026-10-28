"""Offline entry points and reproducible audit arithmetic."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from contribution_audit import category, collect, identity, markdown
from pulmo_review import build_review_archive
from review_report import main
from test_review import fixture


class OfflineCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.archive = self.root / 'report.zip'
        self.archive.write_bytes(build_review_archive(fixture(), 'fixture-run'))

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([str(arg) for arg in args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_verify_defaults_to_summary_not_clinical_report(self):
        code, stdout, stderr = self.run_cli('verify', self.archive)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, '')
        self.assertNotIn('report', json.loads(stdout))

    def test_include_report_flag_is_explicit(self):
        code, stdout, _ = self.run_cli('verify', self.archive, '--include-report')
        self.assertEqual(code, 0)
        self.assertIn('report', json.loads(stdout))

    def test_compare_verifies_both_inputs(self):
        code, stdout, _ = self.run_cli('compare', self.archive, self.archive)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout)['same_input'])
        invalid = self.root / 'invalid.zip'
        invalid.write_bytes(b'not zip')
        code, stdout, stderr = self.run_cli('compare', self.archive, invalid)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, '')
        self.assertEqual(json.loads(stderr)['code'], 'invalid_zip')

    def test_output_file_never_overwrites_existing_file(self):
        target = self.root / 'result.json'
        code, _, _ = self.run_cli('verify', self.archive, '--output', target)
        self.assertEqual(code, 0)
        saved = target.read_bytes()
        code, _, stderr = self.run_cli('verify', self.archive, '--output', target)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr)['code'], 'file_error')
        self.assertEqual(target.read_bytes(), saved)

    def test_missing_archive_returns_json_error(self):
        code, stdout, stderr = self.run_cli('verify', self.root / 'missing.zip')
        self.assertEqual(code, 2)
        self.assertEqual(stdout, '')
        self.assertEqual(json.loads(stderr)['code'], 'file_error')


class AuditTests(unittest.TestCase):
    def test_categories_keep_tables_out_of_source_counts(self):
        self.assertEqual(category('tests/test_review.py'), 'tests')
        self.assertEqual(category('src/train.py'), 'production')
        self.assertEqual(category('data/splits.csv'), 'other')
        self.assertEqual(category('docs/guide.md'), 'documentation')

    def test_identity_uses_email_not_display_name(self):
        self.assertEqual(identity('zhouqian2123@gmail.com'), ('A', 'ZhouJiasheng-Jason'))
        self.assertEqual(identity('unknown@example.com'), ('unmapped', 'unknown@example.com'))

    def test_mixed_history_totals_and_blame(self):
        email = '265002037+hanjingmu2004-coder@users.noreply.github.com'
        history = (f'COMMIT\t{email}\tFirst Name\tparent\n'
                   '10\t2\tsrc/a.py\n5\t0\ttests/test_a.py\n'
                   f'COMMIT\t{email}\tSecond Name\tparent\n'
                   '20\t0\tdocs/a.md\n-\t-\tfigures/image.png\n')
        def fake_git(root, *args):
            if args[0] == 'rev-parse':
                return 'a' * 40
            if args[0] == 'log':
                return history
            if args[0] == 'ls-tree':
                return 'src/a.py\0tests/test_a.py\0docs/a.md\0'
            if args[0] == 'blame':
                return f'author-mail <{email}>\n\tline one\n'
            raise AssertionError(args)
        with patch('contribution_audit.git', side_effect=fake_git):
            result = collect('.')
        row = result['members'][0]
        self.assertEqual(row['commits'], 2)
        self.assertEqual(row['added'], 35)
        self.assertEqual(row['deleted'], 2)
        self.assertEqual(row['code_added'], 15)
        self.assertEqual(row['current_code_lines'], 2)
        self.assertEqual(row['addition_share'], 1)
        self.assertEqual(row['names'], ['First Name', 'Second Name'])
        self.assertIn('35', markdown(result))


if __name__ == '__main__':
    unittest.main()
