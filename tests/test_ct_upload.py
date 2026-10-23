"""CT upload chain: validation, quality metadata, case cache and upload -> CT-only -> slice.

Run from the repository root: python -m unittest tests.test_ct_upload

All volumes are synthetic phantoms generated here; no real CT is read or committed. The logic tests need
only the baseline requirements. The HTTP tests also need fastapi and httpx (fastapi.testclient). The
workflow test runs real inference code on a randomly initialised CT-only network, so it does not need
trained weights; with local runs/ct_aug-basic_seed0.pt it also runs once with the trained model.
"""
import asyncio
import gzip
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import ct_preprocess  # noqa: E402
import pulmo_upload  # noqa: E402
from pulmo_cases import ApiError, CaseStore  # noqa: E402

HAS_HTTP = all(importlib.util.find_spec(m) for m in ('fastapi', 'httpx'))
TRAINED_CT = ROOT/'runs'/'ct_aug-basic_seed0.pt'


def phantom(shape=(64, 64, 24), lungs=True):
    """Chest-like HU volume: soft-tissue ellipse in air with two low-density lung ellipsoids."""
    x, y, z = np.indices(shape)
    v = np.full(shape, -1000, dtype=np.int16)
    v[((x-32)/27)**2+((y-32)/23)**2 < 1] = 40
    if lungs:
        for cx in (21, 43):
            v[((x-cx)/8)**2+((y-32)/15)**2+((z-shape[2]//2)/min(10, shape[2]*.42))**2 < 1] = -750
    return v


def nifti_bytes(data, affine=np.diag([1, 1, 3, 1]), suffix='.nii'):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/('v'+suffix)
        nib.save(nib.Nifti1Image(data, affine), path)
        return path.read_bytes()


def singular_affine_bytes():
    """A phantom whose sform has a zero row. nibabel refuses to write it, so patch the header bytes."""
    raw = bytearray(nifti_bytes(phantom()))
    raw[252:256] = np.array([0, 1], '<i2').tobytes()  # qform_code=0, sform_code=1
    raw[312:328] = np.zeros(4, '<f4').tobytes()       # srow_z = 0
    return bytes(raw)


async def _chunks(data, size=1 << 16):
    for i in range(0, len(data), size):
        yield data[i:i+size]


def upload(data, filename, store=None):
    """Run the real upload service on bytes, with a private case store."""
    store = store or CaseStore()
    with mock.patch.object(pulmo_upload, 'remember', store.remember):
        return asyncio.run(pulmo_upload.receive_upload(_chunks(data), filename)), store


def leftover_temp_dirs():
    return set(Path(tempfile.gettempdir()).glob('pulmo-*'))


class UploadValidationTest(unittest.TestCase):
    def setUp(self):
        self.temp_before = leftover_temp_dirs()

    def tearDown(self):
        self.assertEqual(leftover_temp_dirs() - self.temp_before, set(), 'upload temp directory leaked')

    def assertRejected(self, data, filename, code, status=400):
        with self.assertRaises(ApiError) as ctx:
            upload(data, filename)
        err = ctx.exception
        self.assertEqual((err.status, err.code), (status, code), err.detail)
        self.assertIsInstance(err.detail, str)
        self.assertNotIn('pulmo-', err.detail)  # no server temp paths in user-facing messages
        return err

    def test_valid_compressed_and_uncompressed_give_same_stack(self):
        gz = nifti_bytes(phantom(), suffix='.nii.gz')
        case_gz, store_gz = upload(gz, 'scan.nii.gz')
        case_nii, store_nii = upload(gzip.decompress(gz), 'scan.nii')
        a, b = store_gz.get(case_gz['token'])['stack'], store_nii.get(case_nii['token'])['stack']
        self.assertEqual((a.shape, a.dtype), ((16, 3, 224, 224), np.uint8))
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(case_gz['name'], 'scan.nii.gz')
        self.assertEqual(case_gz['source'], 'Uploaded CT')

    def test_stack_matches_offline_preprocessing(self):
        data = nifti_bytes(phantom(), suffix='.nii.gz')
        case, store = upload(data, 'scan.nii.gz')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'scan.nii.gz'
            path.write_bytes(data)
            offline = ct_preprocess.process(path)
        self.assertTrue(np.array_equal(store.get(case['token'])['stack'], offline))

    def test_quality_metadata(self):
        case, store = upload(nifti_bytes(phantom()), 'scan.nii')
        q = case['quality']
        self.assertEqual(q['original_shape'], [64, 64, 24])
        self.assertEqual(q['original_spacing_mm'], [1, 1, 3])
        self.assertEqual(q['orientation'], 'RAS')
        self.assertEqual(q['intensity_range_hu'], [-1000, 40])
        self.assertEqual(q['pipeline'], ct_preprocess.PIPELINE_VERSION)
        self.assertEqual((q['samples'], q['output_shape']), (16, [16, 3, 224, 224]))
        self.assertEqual(len(q['sampled_slices']), 16)
        self.assertEqual(q['original_slices'], q['sampled_slices'])
        self.assertTrue(q['lung_mask_found'])
        self.assertEqual(q['warnings'], [])
        self.assertIn('does not confirm the imaging modality', q['hu_check'])
        # Only the model input stays cached, never the full volume or the debug mask.
        self.assertEqual(set(store.get(case['token'])), {'stack', 'name', 'source', 'original_shape', 'quality'})

    def test_flipped_axial_axis_maps_back_to_file_slices(self):
        q = upload(nifti_bytes(phantom(), np.diag([1, 1, -3, 1])), 'flip.nii')[0]['quality']
        self.assertEqual(q['orientation'], 'RAI')
        self.assertEqual(q['original_slices'], [23 - z for z in q['sampled_slices']])

    def test_quality_warnings(self):
        thick = upload(nifti_bytes(phantom((64, 64, 10)), np.diag([1, 1, 8, 1])), 'thick.nii')[0]['quality']
        self.assertEqual({w['code'] for w in thick['warnings']}, {'few_axial_slices', 'thick_slices'})
        empty = upload(nifti_bytes(phantom(lungs=False)), 'nolung.nii')[0]['quality']
        self.assertIn('lung_mask_empty', [w['code'] for w in empty['warnings']])
        self.assertFalse(empty['lung_mask_found'])

    def test_file_type_and_empty_upload(self):
        err = self.assertRejected(b'x', 'scan.dcm', 'unsupported_file_type')
        self.assertEqual(err.field_errors, {'filename': 'scan.dcm'})
        self.assertRejected(b'x', 'C:\\Users\\me\\scan.nii.zip', 'unsupported_file_type')
        self.assertRejected(b'', 'scan.nii', 'empty_upload')

    def test_corrupt_files(self):
        self.assertRejected(b'not a nifti volume', 'scan.nii', 'unreadable_file')
        gz = nifti_bytes(phantom(), suffix='.nii.gz')
        self.assertRejected(gz[:len(gz)//2], 'scan.nii.gz', 'unreadable_file')

    def test_shape_checks(self):
        err = self.assertRejected(nifti_bytes(np.zeros((8, 8, 8, 2), np.int16)), 'v4.nii', 'not_3d')
        self.assertEqual(err.field_errors, {'shape': [8, 8, 8, 2]})
        self.assertRejected(nifti_bytes(phantom((64, 64, 2))), 'thin.nii', 'volume_too_small')
        with mock.patch.object(pulmo_upload, 'MAX_VOXELS', 1000):
            self.assertRejected(nifti_bytes(phantom()), 'big.nii', 'volume_too_large')

    def test_intensity_checks(self):
        self.assertRejected(nifti_bytes(np.full((8, 8, 8), -500, np.int16)), 'c.nii', 'constant_volume')
        for bad in (np.nan, np.inf):
            data = phantom().astype(np.float32)
            data[0, 0, 0] = bad
            self.assertRejected(nifti_bytes(data), 'nan.nii', 'non_finite_values')
        normalized = np.random.default_rng(0).random((16, 16, 16), dtype=np.float32)
        self.assertRejected(nifti_bytes(normalized), 'norm.nii', 'intensity_not_hu')

    def test_invalid_affine(self):
        err = self.assertRejected(singular_affine_bytes(), 'a.nii', 'invalid_affine')
        self.assertIn('affine', err.field_errors)

    def test_size_limit(self):
        with mock.patch.object(pulmo_upload, 'UPLOAD_LIMIT', 1000):
            self.assertRejected(b'\0'*2000, 'big.nii', 'upload_too_large', status=413)


class CaseStoreTest(unittest.TestCase):
    def test_eviction_drops_oldest(self):
        store = CaseStore(limit=3)
        tokens = [store.remember(np.zeros(1), f'c{i}')['token'] for i in range(4)]
        self.assertEqual(len(store), 3)
        with self.assertRaises(ApiError) as ctx:
            store.get(tokens[0])
        self.assertEqual((ctx.exception.status, ctx.exception.code), (404, 'case_expired'))
        for token in tokens[1:]:
            self.assertEqual(store.get(token)['name'], f'c{tokens.index(token)}')

    def test_error_body(self):
        self.assertEqual(ApiError(400, 'x', 'msg').body(), dict(detail='msg', code='x'))
        self.assertEqual(ApiError(400, 'x', 'msg', dict(f=1)).body(), dict(detail='msg', code='x', field_errors=dict(f=1)))


@unittest.skipUnless(HAS_HTTP, 'fastapi and httpx are needed for the HTTP tests')
class UploadWorkflowTest(unittest.TestCase):
    """POST /api/upload -> POST /api/predict (CT only) -> GET slice PNGs, through the real app."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import pulmo_cases
        import pulmo_runtime
        import pulmo_server
        cls.runtime, cls.cases = pulmo_runtime, pulmo_cases
        cls.client = TestClient(pulmo_server.app, raise_server_exceptions=False)
        cls.data = nifti_bytes(phantom(), suffix='.nii.gz')

    def setUp(self):
        self.runtime.load_model.cache_clear()
        self.addCleanup(self.runtime.load_model.cache_clear)

    def post_upload(self, data, filename):
        return self.client.post('/api/upload', params=dict(filename=filename), content=data)

    def run_ct_only(self, model):
        r = self.post_upload(self.data, 'phantom.nii.gz')
        self.assertEqual(r.status_code, 200, r.text)
        token = r.json()['token']
        r = self.client.post('/api/predict', json=dict(token=token, model=model, clinical=dict(Age='ignored')))
        self.assertEqual(r.status_code, 200, r.text)
        result = r.json()
        self.assertEqual(result['clinical'], {})  # CT-only never uses clinical inputs
        self.assertEqual(result['source'], 'Uploaded CT')
        self.assertEqual(len(result['probabilities']), 3)
        self.assertAlmostEqual(sum(result['probabilities']), 1, places=4)
        self.assertTrue(result['has_overlay'])
        for index in (0, 15):
            plain = self.client.get(f'/api/cases/{token}/slices/{index}')
            overlay = self.client.get(f'/api/cases/{token}/slices/{index}',
                                      params=dict(run=result['run_id'], overlay='true'))
            for img in (plain, overlay):
                self.assertEqual((img.status_code, img.headers['content-type']), (200, 'image/png'))
                self.assertTrue(img.content.startswith(b'\x89PNG'))
        stale = self.client.get(f'/api/cases/{token}/slices/0', params=dict(run='old', overlay='true'))
        self.assertEqual(stale.status_code, 409)
        return result

    def test_structured_error_response(self):
        r = self.post_upload(nifti_bytes(np.zeros((8, 8, 8, 2), np.int16)), 'v4.nii')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), dict(detail=r.json()['detail'], code='not_3d', field_errors=dict(shape=[8, 8, 8, 2])))
        r = self.client.get('/api/cases/missing/slices/0')
        self.assertEqual((r.status_code, r.json()['code']), (404, 'case_expired'))

    def test_upload_eviction_over_http(self):
        tokens = [self.post_upload(self.data, 'phantom.nii.gz').json()['token']
                  for _ in range(self.cases.MAX_CASES + 1)]
        self.assertEqual(self.client.get(f'/api/cases/{tokens[0]}/slices/0').status_code, 404)
        self.assertEqual(self.client.get(f'/api/cases/{tokens[-1]}/slices/0').status_code, 200)

    def test_upload_ct_only_slices_with_untrained_network(self):
        import torch
        tag = 'ct_aug-basic_seed0'
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'runs').mkdir()
            torch.manual_seed(0)
            net = self.runtime.Net(False, self.runtime.clinical_width())
            torch.save(net.state_dict(), Path(tmp)/'runs'/f'{tag}.pt')
            # Point only the checkpoint lookup at the random weights; results/ stays the committed one.
            with mock.patch.object(self.runtime, 'ROOT', Path(tmp)):
                result = self.run_ct_only(tag)
        self.assertEqual(result['model'], tag)

    @unittest.skipUnless(TRAINED_CT.is_file(), 'trained weights runs/ct_aug-basic_seed0.pt not present')
    def test_upload_ct_only_slices_with_trained_model(self):
        self.run_ct_only('ct_aug-basic_seed0')


if __name__ == '__main__':
    unittest.main()
