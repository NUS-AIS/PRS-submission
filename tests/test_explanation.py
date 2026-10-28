"""D's CPU tests use deterministic small networks; no downloaded weights required."""
import io
import hashlib
import json
import zipfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from torch import nn
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from pulmo_explain import capture_features, explain_forward, gradcam, render_png, explanation_status
from pulmo_reports import bound_prediction, case_report
from pulmo_server import app
from pulmo_cases import ApiError, remember, get_case


class SmallNet(nn.Module):
    def __init__(self, fusion=False):
        super().__init__()
        self.bb = nn.Module()
        self.bb.layer4 = nn.Conv2d(3, 4, 1)
        self.head = nn.Linear(4 + int(fusion), 3)
        self.fusion = fusion

    def forward(self, x, c):
        f = self.bb.layer4(x.flatten(0, 1)).mean((2, 3)).view(1, 2, 4).mean(1)
        if self.fusion:
            f = torch.cat([f, c], 1)
        return self.head(f)


class GradCamTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)

    def test_ct_and_fusion_logits_unchanged_and_hooks_removed(self):
        for fusion in (False, True):
            model = SmallNet(fusion).eval()
            x, c = torch.rand(1, 2, 3, 8, 8), torch.ones(1, 1)
            plain, absent = explain_forward(model, x, c, 'cpu', False)
            for _ in range(3):
                logits, maps = explain_forward(model, x, c, 'cpu', True)
                torch.testing.assert_close(plain, logits)
                self.assertEqual(maps.shape, (2, 8, 8))
                self.assertTrue(np.isfinite(maps).all())
                self.assertEqual(len(model.bb.layer4._forward_hooks), 0)
            self.assertIsNone(absent)

    def test_hook_removed_on_error(self):
        layer = nn.Identity()
        with self.assertRaises(RuntimeError):
            with capture_features(layer):
                raise RuntimeError('simulated forward failure')
        self.assertEqual(len(layer._forward_hooks), 0)

    def test_diagnostics_measure_explanation_only(self):
        model = SmallNet().eval()
        diagnostic = {}
        logits, maps = explain_forward(model, torch.rand(1, 2, 3, 8, 8),
                                      torch.ones(1, 1), 'cpu', True, diagnostic)
        self.assertGreaterEqual(diagnostic['gradcam_ms'], 0)
        self.assertEqual(diagnostic['target_class_index'], logits.argmax(1).item())
        self.assertEqual(diagnostic['sampled_positions'], 2)
        self.assertEqual(diagnostic['zero_signal_positions'],
                         np.flatnonzero(~maps.any(axis=(1, 2))).tolist())

    def test_zero_signal_is_explicit(self):
        model = SmallNet().eval()
        with torch.no_grad():
            model.head.weight.zero_()
        _, maps = explain_forward(model, torch.ones(1, 2, 3, 8, 8), torch.ones(1, 1), 'cpu', True)
        self.assertEqual(explanation_status(maps), 'zero_signal')
        self.assertEqual(explanation_status(None), 'not_requested')

    def test_nonfinite_logits_rejected(self):
        with self.assertRaises(ValueError):
            gradcam(torch.full((1, 3), float('nan')), torch.ones(2, 4, 8, 8))

    def test_render_opacity_zero_preserves_input(self):
        gray = np.arange(64, dtype=np.uint8).reshape(8, 8)
        image = np.array(Image.open(io.BytesIO(render_png(gray, np.ones((8, 8)), 0))))
        np.testing.assert_array_equal(image[:, :, 0], gray)
        for value in (-1, 2, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                render_png(gray, None, value)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.token = remember(np.zeros((16, 3, 224, 224), dtype=np.uint8), 'fixture', source='test')['token']
        self.case = get_case(self.token)
        self.case['prediction'] = dict(id='run-one', cam=np.ones((16, 224, 224), dtype=np.float32),
            result=dict(predicted_class='Other fungal infection', probabilities=[.1, .8, .1],
                        model='fixture', inputs={'used': False}))
        self.prefix = f'/api/cases/{self.token}'

    def test_report_matches_snapshot_and_is_independent(self):
        response = self.client.get(self.prefix+'/explanation/report?run=run-one&index=3&opacity=0.2')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['prediction'], self.case['prediction']['result'])
        self.assertEqual(data['explanation']['sampled_position'], 4)
        self.assertEqual(data['explanation']['opacity'], .2)
        self.assertIn('attachment', response.headers['content-disposition'])
        copy = case_report(self.case, 'run-one', 3)
        copy['prediction']['inputs']['used'] = True
        self.assertFalse(self.case['prediction']['result']['inputs']['used'])

    def test_png_and_viewer_do_not_run_inference(self):
        with patch('pulmo_prediction.infer', side_effect=AssertionError('must not infer')):
            for opacity in (0, .4, 1):
                response = self.client.get(self.prefix+f'/explanation/image?run=run-one&opacity={opacity}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Image.open(io.BytesIO(response.content)).size, (224, 224))
                self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_stale_run_rejected_for_both_downloads_and_overlay(self):
        for path in ('explanation/report', 'explanation/image', 'slices/7?overlay=true&'):
            separator = '' if '?' in path else '?'
            response = self.client.get(self.prefix+'/'+path+separator+'run=old')
            self.assertEqual(response.status_code, 409)
        with self.assertRaises(ApiError):
            bound_prediction(self.case, '')

    def test_invalid_view_parameters(self):
        for query in ('index=-1', 'index=16', 'opacity=-.1', 'opacity=1.1', 'opacity=nan'):
            response = self.client.get(self.prefix+'/explanation/report?run=run-one&'+query)
            self.assertEqual(response.status_code, 400, query)

    def test_no_cam_can_export_original_but_not_overlay(self):
        self.case['prediction']['cam'] = None
        response = self.client.get(self.prefix+'/explanation/image?run=run-one')
        self.assertEqual(response.status_code, 409)
        response = self.client.get(self.prefix+'/explanation/image?run=run-one&overlay=false')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(case_report(self.case, 'run-one', 0)['explanation']['status'], 'not_requested')

    def test_replaced_prediction_invalidates_old_report(self):
        self.case['prediction'] = {**self.case['prediction'], 'id': 'run-two'}
        self.assertEqual(self.client.get(self.prefix+'/explanation/report?run=run-one').status_code, 409)

    def test_bundle_files_match_report_hashes(self):
        response = self.client.get(self.prefix+'/explanation/bundle?run=run-one&index=2')
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(set(archive.namelist()), {'report.json', 'original.png', 'overlay.png'})
            report = json.loads(archive.read('report.json'))
            self.assertEqual(report['run_id'], 'run-one')
            self.assertEqual(report['explanation']['sampled_position'], 3)
            for name, meta in report['files'].items():
                data = archive.read(name)
                self.assertEqual(hashlib.sha256(data).hexdigest(), meta['sha256'])
                self.assertEqual(len(data), meta['bytes'])

    def test_bundle_without_cam_does_not_fabricate_overlay(self):
        self.case['prediction']['cam'] = None
        response = self.client.get(self.prefix+'/explanation/bundle?run=run-one')
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertNotIn('overlay.png', archive.namelist())
        self.assertEqual(self.client.get(self.prefix+'/explanation/bundle?run=old').status_code, 409)


if __name__ == '__main__':
    unittest.main()
