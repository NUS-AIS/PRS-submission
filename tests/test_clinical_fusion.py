"""Clinical input chain: validation, training-median imputation, input summaries and fusion prediction.

Run from the repository root: python -m unittest tests.test_clinical_fusion

The validation and statistics tests need only the committed clinical table and split. The HTTP tests also
need fastapi and httpx; they run the real /api/predict on randomly initialised CT-only and fusion networks,
so they do not need trained weights. With local runs/ and data/processed/ one more test uses a trained
fusion model on a validation case.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from common import NUMERIC, BINARY, SPLIT_CSV  # noqa: E402
from pulmo_clinical import (ClinicalError, FIELDS, clinical_schema, clinical_setup, clinical_summary,  # noqa: E402
                            clinical_vector, clinical_width, training_reference, validate_clinical)

HAS_HTTP = all(importlib.util.find_spec(m) for m in ('fastapi', 'httpx'))
TRAINED_FUSION = ROOT/'runs'/'fusion_aug-basic_seed0.pt'
VALID = {'Age': 63, 'Lymphocyte Count': 1.2, 'D-Dimer': 420, **{k: 0 for k in BINARY}, 'Gender': 'F'}


def errors(**changes):
    """Field errors for VALID with some values changed ({} when the input is accepted)."""
    try:
        validate_clinical({**VALID, **changes})
    except ClinicalError as exc:
        return exc.field_errors
    return {}


class ClinicalValidationTest(unittest.TestCase):
    def test_valid_input(self):
        self.assertEqual(validate_clinical(VALID), VALID)
        self.assertEqual(validate_clinical({**VALID, 'Age': '63', 'Diabetes': np.int64(1)})['Age'], 63.0)

    def test_age_bounds(self):
        for ok in (0, 120, 45.5):
            self.assertEqual(errors(Age=ok), {})
        for bad in (-1, 120.5, 200):
            self.assertEqual(list(errors(Age=bad)), ['Age'])

    def test_negative_and_non_finite_numbers(self):
        for name in NUMERIC:
            for bad in (-0.01, float('inf'), float('-inf'), 'inf'):
                self.assertIn('non-negative number', errors(**{name: bad})[name])

    def test_wrong_types(self):
        for bad in ('abc', [1], {'v': 1}, True):
            self.assertIn('must be a number', errors(**{'D-Dimer': bad})['D-Dimer'])
        for bad in (2, -1, 0.5, '1', True):
            self.assertIn('0 (no) or 1 (yes)', errors(Diabetes=bad)['Diabetes'])
        with self.assertRaises(ClinicalError) as ctx:
            validate_clinical(['Age', 63])
        self.assertEqual(list(ctx.exception.field_errors), ['clinical'])

    def test_blank_numbers_are_missing_not_zero(self):
        for blank in (None, '', '  ', float('nan')):
            self.assertTrue(np.isnan(validate_clinical({**VALID, 'Age': blank})['Age']))

    def test_missing_binary_is_rejected_never_filled(self):
        for blank in (None, '', float('nan')):
            self.assertIn('Please specify AIDS', errors(AIDS=blank)['AIDS'])
        values = dict(VALID)
        del values['AIDS']
        with self.assertRaises(ClinicalError):
            clinical_vector(values)

    def test_sex_uses_training_coding(self):
        for bad in ('m', 'Male', 'X', None, 0):
            self.assertIn('M/F', errors(Gender=bad)['Gender'])
        m, f = clinical_vector({**VALID, 'Gender': 'M'}), clinical_vector(VALID)
        self.assertEqual(np.flatnonzero(m != f).tolist(), [10, 11])  # only the one-hot sex columns differ

    def test_all_errors_reported_together(self):
        found = errors(Age=-1, Diabetes=None, Gender='X', **{'D-Dimer': 'abc'})
        self.assertEqual(set(found), {'Age', 'Diabetes', 'Gender', 'D-Dimer'})
        with self.assertRaises(ValueError):  # ClinicalError stays a ValueError for older callers
            clinical_vector({**VALID, 'Age': -1})


class TrainingStatisticsTest(unittest.TestCase):
    def test_medians_and_scaling_use_training_rows_only(self):
        df, pre = clinical_setup()
        train = df[df.split == 'train']
        ref = training_reference()
        self.assertEqual(ref['train_rows'], len(train))
        self.assertEqual(ref['medians'], {k: float(train[k].median()) for k in NUMERIC})
        self.assertNotEqual(ref['medians']['Age'], float(df['Age'].median()))  # all rows would give 64
        scaler = pre.named_transformers_['num'].named_steps['standardscaler']
        imputed = train[NUMERIC].fillna(train[NUMERIC].median())
        np.testing.assert_allclose(scaler.mean_, imputed.mean().to_numpy())

    def test_vector_matches_fitted_transformer(self):
        df, pre = clinical_setup()
        rows = df[FIELDS].iloc[[0]]
        values = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in rows.iloc[0].items()}
        np.testing.assert_array_equal(clinical_vector(values), pre.transform(rows).astype(np.float32))
        self.assertEqual(clinical_vector(VALID).shape, (1, clinical_width()))

    def test_split_hash_ignores_line_endings(self):
        import hashlib
        lf = SPLIT_CSV.read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(training_reference()['split_sha256'], hashlib.sha256(lf).hexdigest()[:12])


class ClinicalSummaryTest(unittest.TestCase):
    def test_blank_number_reports_training_median(self):
        summary = clinical_summary({**VALID, 'D-Dimer': None})
        dd = next(f for f in summary['fields'] if f['field'] == 'D-Dimer')
        self.assertEqual((dd['submitted'], dd['used'], dd['source']), (None, 420.0, 'training median'))
        self.assertEqual(summary['imputed'], ['D-Dimer'])
        self.assertIn('not stated', dd['unit'])

    def test_summary_is_what_the_model_receives(self):
        values = {**VALID, 'Age': None, 'Lymphocyte Count': None}
        used = {f['field']: f['used'] for f in clinical_summary(values)['fields']}
        np.testing.assert_array_equal(clinical_vector(values), clinical_vector(used))

    def test_complete_input_and_unknown_fields(self):
        summary = clinical_summary({**VALID, 'Weight': 70})
        self.assertEqual((summary['used'], summary['imputed'], summary['ignored_fields']), (True, [], ['Weight']))
        self.assertTrue(all(f['source'] == 'user input' for f in summary['fields']))
        self.assertEqual(summary['preprocessing']['train_rows'], training_reference()['train_rows'])

    def test_schema_matches_rules(self):
        fields = {f['field']: f for f in clinical_schema()['fields']}
        self.assertEqual(list(fields), FIELDS)
        self.assertEqual({k for k, f in fields.items() if f['required']}, set(BINARY) | {'Gender'})
        self.assertEqual((fields['Age']['max'], fields['Age']['median']), (120, 63.0))


@unittest.skipUnless(HAS_HTTP, 'fastapi and httpx are needed for the HTTP tests')
class FusionPredictionApiTest(unittest.TestCase):
    """POST /api/predict through the real app, on random CT-only and fusion networks."""

    @classmethod
    def setUpClass(cls):
        import torch
        from fastapi.testclient import TestClient
        import pulmo_cases, pulmo_runtime, pulmo_server
        cls.runtime, cls.cases = pulmo_runtime, pulmo_cases
        cls.client = TestClient(pulmo_server.app, raise_server_exceptions=False)
        cls.tmp = tempfile.TemporaryDirectory()
        (Path(cls.tmp.name)/'runs').mkdir()
        for mode in ('ct', 'fusion'):
            torch.manual_seed(0)
            net = pulmo_runtime.Net(mode == 'fusion', clinical_width())
            torch.save(net.state_dict(), Path(cls.tmp.name)/'runs'/f'{mode}_aug-basic_seed0.pt')
        cls.stack = np.random.default_rng(0).integers(0, 256, (16, 3, 224, 224), dtype=np.uint8)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        # Only checkpoint lookup moves to the random weights; results/ stays the committed one.
        patch = mock.patch.object(self.runtime, 'ROOT', Path(self.tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.runtime.load_model.cache_clear()
        self.addCleanup(self.runtime.load_model.cache_clear)
        self.token = self.cases.remember(self.stack, 'synthetic', source='Test')['token']

    def predict(self, model, clinical, explain=False):
        return self.client.post('/api/predict', json=dict(token=self.token, model=model, clinical=clinical, explain=explain))

    def test_fusion_response_keeps_old_keys_and_adds_inputs(self):
        r = self.predict('fusion_aug-basic_seed0', {**VALID, 'D-Dimer': None}, explain=True)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue({'probabilities', 'predicted_class', 'run_id', 'has_overlay', 'clinical'} <= set(body))
        self.assertEqual((body['inputs']['used'], body['inputs']['imputed']), (True, ['D-Dimer']))
        expected, _ = self.runtime.infer(self.stack, 'fusion_aug-basic_seed0', {**VALID, 'D-Dimer': None}, True)
        np.testing.assert_allclose(body['probabilities'], expected['probabilities'], atol=1e-5)

    def test_invalid_clinical_gives_field_errors(self):
        r = self.predict('fusion_aug-basic_seed0', {**VALID, 'Age': -5, 'Gender': None, 'AIDS': None})
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertEqual((body['code'], set(body['field_errors'])), ('invalid_clinical', {'Age', 'Gender', 'AIDS'}))
        self.assertIsInstance(body['detail'], str)

    def test_ct_only_ignores_clinical_inputs(self):
        a = self.predict('ct_aug-basic_seed0', {'Age': 'not a number'}).json()
        b = self.predict('ct_aug-basic_seed0', VALID).json()
        self.assertEqual((a['inputs']['used'], a['clinical']), (False, {}))
        np.testing.assert_allclose(a['probabilities'], b['probabilities'], atol=1e-6)

    def test_unknown_model(self):
        r = self.predict('fusion_aug-basic_seed9', VALID)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'model_unavailable'))

    def test_changed_input_makes_old_explanation_stale(self):
        first = self.predict('fusion_aug-basic_seed0', VALID, explain=True).json()
        second = self.predict('fusion_aug-basic_seed0', {**VALID, 'Age': 30}, explain=True).json()
        self.assertNotEqual(first['run_id'], second['run_id'])
        slice_ = lambda run: self.client.get(f'/api/cases/{self.token}/slices/0', params=dict(overlay='true', run=run))
        self.assertEqual(slice_(first['run_id']).status_code, 409)
        self.assertEqual(slice_(second['run_id']).status_code, 200)
        # A rejected request does not create a run or replace the last valid one.
        self.assertEqual(self.predict('fusion_aug-basic_seed0', {**VALID, 'Age': -1}).status_code, 400)
        self.assertEqual(slice_(second['run_id']).status_code, 200)

    def test_clinical_rules_endpoint(self):
        r = self.client.get('/api/clinical')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), clinical_schema())


@unittest.skipUnless(HAS_HTTP and TRAINED_FUSION.is_file() and (ROOT/'data'/'processed').is_dir(),
                     'trained fusion weights and data/processed/ not present')
class TrainedFusionTest(unittest.TestCase):
    def test_validation_case_summary_matches_dataset(self):
        from fastapi.testclient import TestClient
        import pulmo_server
        client = TestClient(pulmo_server.app)
        df, _ = clinical_setup()
        case_id = int(next(i for i in df.index[df.split == 'val'] if df.loc[i, NUMERIC].isna().any()))
        demo = client.post(f'/api/demo/{case_id}').json()
        r = client.post('/api/predict', json=dict(token=demo['token'], model='fusion_aug-basic_seed0',
                                                  clinical=demo['clinical'], explain=False))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['inputs']['imputed'], [k for k in NUMERIC if np.isnan(df.loc[case_id, k])])


if __name__ == '__main__':
    unittest.main()
