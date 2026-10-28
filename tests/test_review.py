"""Review mathematics, privacy, export integrity and HTTP error contracts."""
import copy
import csv
import hashlib
import io
import json
import stat
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from pulmo_attention import attention_summary, selected_positions, summary_csv, validate_stack
from pulmo_cases import ApiError, get_case, remember
from pulmo_review import build_review_archive, contact_sheet, pixel_fingerprint, review_snapshot
from pulmo_review_compare import compare_reports
from pulmo_review_verify import VerificationError, inspect_archive, safe_name, strict_json
from pulmo_server import app


def fixture():
    stack = np.arange(2 * 3 * 8 * 8, dtype=np.uint8).reshape(2, 3, 8, 8)
    cam = np.zeros((2, 8, 8), dtype=np.float32)
    cam[0, 2, 3] = 1
    cam[1] = .25
    return {
        'name': 'private-patient-name',
        'stack': stack,
        'source': 'private-filename.nii',
        'prediction': {
            'id': 'fixture-run',
            'cam': cam,
            'result': {
                'model': 'fixture-model',
                'predicted_class': 'Other fungal',
                'probabilities': [.1, .7, .2],
                'case': 'private-patient-name',
                'source': 'private-filename.nii',
                'clinical': {'Age': 45},
                'inputs': {'used': True},
                'unrecognized_future_field': 'private-value',
            },
        },
    }


def repack(data, change, rehash=False):
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        files = {name: source.read(name) for name in source.namelist()}
    change(files)
    if rehash:
        manifest = json.loads(files['manifest.json'])
        manifest['files'] = {name: {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                             for name, value in files.items() if name != 'manifest.json'}
        files['manifest.json'] = json.dumps(manifest).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as dest:
        for name, value in files.items():
            dest.writestr(name, value)
    return output.getvalue()


class AttentionMathTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture()
        self.stack = self.case['stack']
        self.cam = self.case['prediction']['cam']

    def test_point_mass_centroid_peak_box_and_entropy(self):
        summary = attention_summary(self.stack, self.cam)
        row = summary['rows'][0]
        self.assertEqual(row['centroid'], {'x': 3, 'y': 2})
        self.assertEqual(row['peak'], {'x': 3, 'y': 2})
        self.assertEqual(row['threshold_box'], {'x_min': 3, 'x_max': 3, 'y_min': 2, 'y_max': 2})
        self.assertEqual(row['entropy'], 0)
        self.assertEqual(row['positive_fraction'], 1 / 64)
        self.assertEqual(row['above_threshold_fraction'], 1 / 64)
        self.assertEqual(row['image_half_mass'], {'left': 1, 'right': 0, 'upper': 1, 'lower': 0})

    def test_uniform_map_has_maximum_entropy_and_centered_centroid(self):
        row = attention_summary(self.stack, self.cam)['rows'][1]
        self.assertEqual(row['entropy'], 1)
        self.assertEqual(row['centroid'], {'x': 3.5, 'y': 3.5})
        self.assertIsNone(row['threshold_box'])
        self.assertEqual(row['positive_fraction'], 1)
        self.assertEqual(row['above_threshold_fraction'], 0)

    def test_case_mass_ranking_and_subset_denominator(self):
        full = attention_summary(self.stack, self.cam)
        self.assertEqual(full['ranked_positions'], [2, 1])
        self.assertAlmostEqual(sum(row['selected_mass_fraction'] for row in full['rows']), 1)
        subset = attention_summary(self.stack, self.cam, positions='1')
        self.assertEqual(subset['rows'][0]['selected_mass_fraction'], 1)

    def test_threshold_zero_does_not_count_zero_signal_pixels(self):
        row = attention_summary(self.stack, self.cam, threshold=0)['rows'][0]
        self.assertEqual(row['above_threshold_fraction'], 1 / 64)

    def test_threshold_is_inclusive(self):
        row = attention_summary(self.stack, self.cam, threshold=.25)['rows'][1]
        self.assertEqual(row['above_threshold_fraction'], 1)

    def test_tiny_positive_signal_is_not_rounded_to_absent(self):
        result = attention_summary(self.stack, self.cam * 1e-12)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['ranked_positions'], [2, 1])
        self.assertGreater(result['rows'][0]['selected_mass_fraction'], 0)

    def test_missing_cam_is_not_zero_signal(self):
        missing = attention_summary(self.stack, None)
        zero = attention_summary(self.stack, self.cam * 0)
        self.assertEqual(missing['status'], 'not_requested')
        self.assertEqual(zero['status'], 'zero_signal')
        self.assertIsNone(missing['rows'][0]['mean'])
        self.assertEqual(zero['rows'][0]['mean'], 0)
        self.assertIsNone(zero['rows'][0]['entropy'])
        self.assertEqual(zero['ranked_positions'], [])

    def test_constant_inputs_reported(self):
        result = attention_summary(self.stack * 0, self.cam)
        self.assertEqual(result['constant_input_positions'], [1, 2])

    def test_invalid_maps_fail_instead_of_silently_clipping(self):
        for value in (float('nan'), float('inf'), -1, 2):
            maps = self.cam.copy()
            maps[0, 0, 0] = value
            with self.subTest(value=value), self.assertRaises(ApiError):
                attention_summary(self.stack, maps)

    def test_invalid_stack_shapes_and_dtypes(self):
        for stack in (self.stack[:, :2], self.stack.astype(float), self.stack[0], self.stack[:0]):
            with self.subTest(shape=stack.shape), self.assertRaises(ApiError):
                validate_stack(stack, None)
        with self.assertRaises(ApiError):
            validate_stack(self.stack, self.cam[:, :3])

    def test_invalid_thresholds(self):
        for value in (None, '', True, -.1, 1.1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ApiError):
                attention_summary(self.stack, self.cam, threshold=value)

    def test_selection_sorted_and_one_based(self):
        self.assertEqual(selected_positions('2,1', 2), [0, 1])
        self.assertEqual(selected_positions('', 2), [0, 1])
        self.assertEqual(selected_positions([2], 2), [1])

    def test_selection_rejects_duplicate_range_and_type_errors(self):
        for positions in ('1,1', '0', '3', '1.2', '1,', [True], [1.0], [], ['1']):
            with self.subTest(positions=positions), self.assertRaises(ApiError):
                selected_positions(positions, 2)

    def test_csv_has_correct_values_and_empty_missing_metrics(self):
        data = summary_csv(attention_summary(self.stack, None)).decode()
        rows = list(csv.DictReader(io.StringIO(data)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['position'], '1')
        self.assertEqual(rows[0]['centroid_x'], '')
        self.assertEqual(rows[0]['mean'], '')
        self.assertEqual(rows[0]['status'], 'not_requested')


class ReviewExportTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture()

    def test_archive_roundtrip_and_each_png_decodable(self):
        data = build_review_archive(self.case, 'fixture-run')
        result = inspect_archive(data)
        self.assertTrue(result['valid'])
        self.assertEqual(result['file_count'], 9)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                if name.endswith('.png'):
                    with Image.open(io.BytesIO(archive.read(name))) as image:
                        image.verify()
            self.assertIn('index.html', archive.namelist())

    def test_default_export_omits_identifiers_and_clinical_data(self):
        report, _, _ = review_snapshot(self.case, 'fixture-run')
        serialized = json.dumps(report)
        self.assertNotIn('private-', serialized)
        self.assertNotIn('clinical', report['prediction'])
        self.assertNotIn('inputs', report['prediction'])
        self.assertFalse(report['privacy']['clinical_inputs_included'])

    def test_clinical_export_is_explicit_and_does_not_mutate_result(self):
        report, _, _ = review_snapshot(self.case, 'fixture-run', include_clinical=True)
        self.assertEqual(report['prediction']['clinical'], {'Age': 45})
        report['prediction']['clinical']['Age'] = 100
        self.assertEqual(self.case['prediction']['result']['clinical']['Age'], 45)

    def test_no_cam_export_omits_overlays(self):
        self.case['prediction']['cam'] = None
        data = build_review_archive(self.case, 'fixture-run')
        result = inspect_archive(data)
        self.assertEqual(result['file_count'], 7)
        self.assertEqual(result['report']['attention']['status'], 'not_requested')

    def test_subset_contains_only_selected_images(self):
        data = build_review_archive(self.case, 'fixture-run', positions='2')
        result = inspect_archive(data)
        self.assertEqual(result['report']['attention']['selected_positions'], [2])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertNotIn('images/position-001-original.png', archive.namelist())

    def test_html_escapes_model_metadata_and_contains_no_script(self):
        self.case['prediction']['result']['model'] = '<script>alert(1)</script>'
        data = build_review_archive(self.case, 'fixture-run')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            page = archive.read('index.html').decode()
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Content-Security-Policy', page)
        self.assertNotIn('https://', page)

    def test_fingerprint_depends_on_pixels_and_shape(self):
        stack = self.case['stack']
        first = pixel_fingerprint(stack)
        changed = stack.copy()
        changed[0, 0, 0, 0] ^= 1
        self.assertNotEqual(first, pixel_fingerprint(changed))
        self.assertNotEqual(first, pixel_fingerprint(stack.reshape(2, 3, 4, 16)))
        self.assertEqual(first, pixel_fingerprint(stack.copy()))

    def test_stale_run_rejected_before_export(self):
        with self.assertRaises(ApiError) as error:
            build_review_archive(self.case, 'old')
        self.assertEqual(error.exception.code, 'stale_explanation')

    def test_run_replaced_during_export_is_rejected(self):
        from pulmo_review import render_png
        def replace(*args, **kwargs):
            data = render_png(*args, **kwargs)
            self.case['prediction'] = {**self.case['prediction'], 'id': 'new'}
            return data
        with patch('pulmo_review.render_png', side_effect=replace):
            with self.assertRaises(ApiError) as error:
                build_review_archive(self.case, 'fixture-run')
        self.assertEqual(error.exception.code, 'stale_explanation')

    def test_export_limit_enforced(self):
        with patch('pulmo_review.MAX_EXPORT_BYTES', 10):
            with self.assertRaises(ApiError) as error:
                build_review_archive(self.case, 'fixture-run')
        self.assertEqual(error.exception.status, 413)

    def test_invalid_contact_sheet_layout(self):
        with self.assertRaises(ApiError):
            contact_sheet([])


class ArchiveVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = build_review_archive(fixture(), 'fixture-run')

    def assert_rejected(self, data, code):
        with self.assertRaises(VerificationError) as error:
            inspect_archive(data)
        self.assertEqual(error.exception.code, code)

    def test_modified_bytes_rejected(self):
        def change(files):
            files['statistics.csv'] = b'X' + files['statistics.csv'][1:]
        self.assert_rejected(repack(self.archive, change), 'hash_mismatch')

    def test_modified_size_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.update({'statistics.csv': b'x'})), 'size_mismatch')

    def test_extra_file_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.update({'extra.txt': b'x'})), 'manifest_members')

    def test_missing_file_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.pop('statistics.csv')), 'manifest_members')

    def test_unsafe_path_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.update({'../outside.txt': b'x'})), 'unsafe_path')

    def test_missing_manifest_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.pop('manifest.json')), 'missing_manifest')

    def test_corrupt_zip_rejected(self):
        self.assert_rejected(b'not a zip', 'invalid_zip')

    def test_duplicate_zip_member_rejected(self):
        buffer = io.BytesIO()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('a', b'a')
                archive.writestr('a', b'b')
        self.assert_rejected(buffer.getvalue(), 'duplicate_member')

    def test_symlink_rejected(self):
        buffer = io.BytesIO()
        entry = zipfile.ZipInfo('link')
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(entry, b'/target')
        self.assert_rejected(buffer.getvalue(), 'unsupported_member')

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(VerificationError) as error:
            strict_json(b'{"a":1,"a":2}', 'fixture')
        self.assertEqual(error.exception.code, 'duplicate_json_key')

    def test_nonfinite_json_rejected(self):
        for value in (b'NaN', b'Infinity', b'-Infinity', b'1e999'):
            with self.subTest(value=value), self.assertRaises(VerificationError):
                strict_json(b'{"a":' + value + b'}', 'fixture')

    def test_oversized_archive_rejected_before_open(self):
        with patch('pulmo_review_verify.MAX_ARCHIVE_BYTES', 1):
            self.assert_rejected(self.archive, 'archive_size')

    def test_expanded_size_and_member_count_limits(self):
        with patch('pulmo_review_verify.MAX_EXPANDED_BYTES', 1):
            self.assert_rejected(self.archive, 'expanded_size')
        with patch('pulmo_review_verify.MAX_ENTRIES', 1):
            self.assert_rejected(self.archive, 'entry_limit')

    def test_manifest_wrong_version_rejected(self):
        def change(files):
            manifest = json.loads(files['manifest.json'])
            manifest['schema_version'] = 99
            files['manifest.json'] = json.dumps(manifest).encode()
        self.assert_rejected(repack(self.archive, change), 'unsupported_format')

    def test_manifest_invalid_digest_rejected(self):
        def change(files):
            manifest = json.loads(files['manifest.json'])
            manifest['files']['report.json']['sha256'] = 'not-a-hash'
            files['manifest.json'] = json.dumps(manifest).encode()
        self.assert_rejected(repack(self.archive, change), 'invalid_manifest_hash')

    def test_rehashed_out_of_range_metric_rejected(self):
        def change(files):
            report = json.loads(files['report.json'])
            report['attention']['rows'][0]['entropy'] = 2
            files['report.json'] = json.dumps(report).encode()
        self.assert_rejected(repack(self.archive, change, True), 'invalid_statistics')

    def test_rehashed_duplicate_position_rejected(self):
        def change(files):
            report = json.loads(files['report.json'])
            report['attention']['selected_positions'] = [1, 1]
            files['report.json'] = json.dumps(report).encode()
        self.assert_rejected(repack(self.archive, change, True), 'invalid_positions')

    def test_rehashed_missing_required_file_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.pop('index.html'), True), 'missing_required_file')

    def test_json_top_level_and_utf8_are_checked(self):
        for payload in (b'[]', b'null', b'"text"', b'\xff'):
            with self.subTest(payload=payload), self.assertRaises(VerificationError):
                strict_json(payload, 'fixture')

    def test_invalid_report_with_recomputed_hash_still_rejected(self):
        def change(files):
            report = json.loads(files['report.json'])
            report['prediction']['probabilities'] = [1, 1, 1]
            files['report.json'] = json.dumps(report).encode()
        self.assert_rejected(repack(self.archive, change, rehash=True), 'invalid_scores')

    def test_report_run_mismatch_rejected(self):
        def change(files):
            report = json.loads(files['report.json'])
            report['run_id'] = 'different'
            files['report.json'] = json.dumps(report).encode()
        self.assert_rejected(repack(self.archive, change, rehash=True), 'run_mismatch')

    def test_rehashed_missing_overlay_still_rejected(self):
        self.assert_rejected(repack(self.archive, lambda files: files.pop('images/position-001-overlay.png'), True), 'image_members')

    def test_safe_name_rejects_windows_and_traversal_paths(self):
        for name in ('/a', '../a', 'a/../b', 'a\\b', 'C:a', 'a//b', 'a\x00b', './a', ''):
            with self.subTest(name=name):
                self.assertFalse(safe_name(name))
        self.assertTrue(safe_name('images/position-001-original.png'))


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.left = review_snapshot(fixture(), 'fixture-run')[0]
        self.right = copy.deepcopy(self.left)
        self.right['run_id'] = 'second-run'

    def test_identical_reports_have_zero_deltas(self):
        result = compare_reports(self.left, self.right)
        self.assertTrue(result['same_input'])
        self.assertEqual(result['class_score_deltas'], [0, 0, 0])
        self.assertEqual(result['position_deltas'][0]['right_minus_left']['mean'], 0)

    def test_threshold_change_suppresses_fraction_difference(self):
        self.right['attention']['threshold'] = .8
        result = compare_reports(self.left, self.right)
        self.assertFalse(result['same_threshold'])
        self.assertIsNone(result['position_deltas'][0]['right_minus_left']['above_threshold_fraction'])

    def test_different_input_suppresses_attention_deltas(self):
        self.right['input_fingerprint'] = 'a' * 64
        result = compare_reports(self.left, self.right)
        self.assertFalse(result['same_input'])
        self.assertTrue(all(value is None for value in result['position_deltas'][0]['right_minus_left'].values()))

    def test_score_delta_direction_and_prediction_change(self):
        self.right['prediction']['probabilities'] = [.8, .1, .1]
        self.right['prediction']['predicted_class'] = 'Aspergillus'
        result = compare_reports(self.left, self.right)
        self.assertEqual(result['class_score_deltas'], [.7, -.6, -.1])
        self.assertTrue(result['prediction_changed'])

    def test_redacted_inputs_are_unknown_not_equal(self):
        self.assertIsNone(compare_reports(self.left, self.right)['clinical_equal'])

    def test_disjoint_selection_is_reported(self):
        self.left['attention']['rows'] = self.left['attention']['rows'][:1]
        self.right['attention']['rows'] = self.right['attention']['rows'][1:]
        result = compare_reports(self.left, self.right)
        self.assertEqual(result['common_positions'], [])
        self.assertEqual(result['left_only_positions'], [1])
        self.assertEqual(result['right_only_positions'], [2])


class ReviewHttpTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        sample = fixture()
        self.token = remember(sample['stack'], sample['name'], source='fixture')['token']
        self.case = get_case(self.token)
        self.case['prediction'] = sample['prediction']
        self.prefix = f'/api/cases/{self.token}/explanation'

    def test_summary_and_csv_are_run_bound_and_no_store(self):
        for endpoint in ('summary', 'statistics'):
            response = self.client.get(f'{self.prefix}/{endpoint}?run=fixture-run&positions=1')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            stale = self.client.get(f'{self.prefix}/{endpoint}?run=old')
            self.assertEqual(stale.status_code, 409)

    def test_review_download_and_verify_http_roundtrip(self):
        response = self.client.get(f'{self.prefix}/review?run=fixture-run')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/zip')
        verified = self.client.post('/api/explanation/verify', content=response.content)
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()['valid'])

    def test_error_codes_for_invalid_options(self):
        for query in ('threshold=nan', 'threshold=2', 'positions=0', 'positions=1,1', 'opacity=nan'):
            response = self.client.get(f'{self.prefix}/review?run=fixture-run&{query}')
            self.assertEqual(response.status_code, 400, query)
            self.assertIn('code', response.json())

    def test_bad_archive_returns_structured_error(self):
        response = self.client.post('/api/explanation/verify', content=b'bad')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_zip')

    def test_review_does_not_run_inference(self):
        with patch('pulmo_prediction.infer', side_effect=AssertionError('must not infer')):
            response = self.client.get(f'{self.prefix}/review?run=fixture-run')
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
