"""Local integration checks; requires installed baseline data and checkpoints."""
import sys
from pathlib import Path
import tempfile
import unittest
import nibabel as nib
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fastapi.testclient import TestClient
from pulmo_server import app
from pulmo_runtime import infer, clinical_setup
from common import ROOT, NUMERIC, BINARY, CATEGORICAL


class Integration(unittest.TestCase):
    def test_checkpoint_parity(self):
        df, _ = clinical_setup()
        for mode in ('ct', 'fusion'):
            tag = f'{mode}_aug-basic_seed0'
            saved = pd.read_csv(ROOT/'results'/f'{tag}_test_probs.csv', index_col=0)
            case = int(saved.index[0])
            values = df.loc[case, NUMERIC+BINARY+CATEGORICAL].to_dict()
            result, cam = infer(np.load(ROOT/'data'/'processed'/f'Case{case:03d}.npy'), tag, values)
            np.testing.assert_allclose(result['probabilities'], saved.iloc[0][['p0','p1','p2']], atol=.003, rtol=0)
            self.assertEqual(cam.shape, (16,224,224))
            self.assertTrue(np.isfinite(cam).all())

    def test_upload_and_prediction(self):
        with TestClient(app) as client, tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(client.post('/api/upload?filename=bad.nii', content=b'invalid').status_code, 400)
            # Synthetic HU phantom tests file processing only; it is not clinical evidence.
            x,y,z = np.indices((64,64,24))
            volume = np.full((64,64,24), -1000, dtype=np.int16)
            volume[((x-32)/27)**2+((y-32)/23)**2<1] = 40
            for cx in (21,43):
                volume[((x-cx)/8)**2+((y-32)/15)**2+((z-12)/10)**2<1] = -750
            path=Path(tmp)/'phantom.nii.gz'
            nib.save(nib.Nifti1Image(volume, np.diag([1,1,3,1])),path)
            uploaded=client.post('/api/upload?filename=phantom.nii.gz', content=path.read_bytes())
            self.assertEqual(uploaded.status_code,200,uploaded.text)
            token=uploaded.json()['token']
            body=dict(token=token,model='ct_aug-basic_seed0',explain=True)
            response=client.post('/api/predict',json=body)
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            self.assertAlmostEqual(sum(result['probabilities']),1,places=5)
            image=client.get(f'/api/cases/{token}/slices/7?overlay=true&run='+result['run_id'])
            self.assertEqual(image.headers['content-type'],'image/png')
            self.assertTrue(image.content.startswith(b'\x89PNG'))
            self.assertEqual(client.get(f'/api/cases/{token}/slices/7?overlay=true&run=stale').status_code,409)
            body['model']='fusion_aug-basic_seed0'
            self.assertEqual(client.post('/api/predict',json=body).status_code,400)

if __name__ == '__main__':
    unittest.main(verbosity=2)
