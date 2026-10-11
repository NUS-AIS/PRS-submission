"""Local research UI. Run with uvicorn pulmo_server:app --app-dir src."""
from collections import OrderedDict
import io
import json
from pathlib import Path
import tempfile
import threading
import uuid

import nibabel as nib
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from common import ROOT, NUMERIC, BINARY, CATEGORICAL
from ct_preprocess import process
from pulmo_runtime import catalog, clinical_setup, infer, LABELS

app = FastAPI(title='Pulmo AI Research Workspace')
WEB = ROOT / 'web'
app.mount('/static', StaticFiles(directory=WEB), name='static')
CASES = OrderedDict()
CASE_LOCK = threading.Lock()
PREPROCESS_LOCK = threading.Lock()
UPLOAD_LIMIT = 200 * 1024 * 1024


def remember(stack, name, **metadata):
    token = uuid.uuid4().hex
    with CASE_LOCK:
        while len(CASES) >= 8:
            CASES.popitem(last=False)
        CASES[token] = dict(stack=stack, name=name, **metadata)
    return dict(token=token, name=name, slices=16, **metadata)


def get_case(token):
    with CASE_LOCK:
        if token not in CASES:
            raise HTTPException(404, 'Case expired. Upload or load it again.')
        return CASES[token]


@app.get('/')
def home():
    return FileResponse(WEB / 'index.html')


@app.get('/api/overview')
def overview():
    df, _ = clinical_setup()
    rows = catalog()
    return dict(models=rows, labels=LABELS, split=df.split.value_counts().to_dict(),
                groups=int(df.group.nunique()), numeric=NUMERIC, binary=BINARY,
                demos=[dict(id=int(i), label=f'Validation case {i:03d}') for i in df.index[df.split == 'val'] if (ROOT/'data'/'processed'/f'Case{i:03d}.npy').exists()])


@app.post('/api/demo/{case_id}')
def demo(case_id: int):
    df, _ = clinical_setup()
    if case_id not in df.index or df.loc[case_id, 'split'] != 'val':
        raise HTTPException(404, 'Only validation cases are available in the demo.')
    path = ROOT/'data'/'processed'/f'Case{case_id:03d}.npy'
    if not path.exists():
        raise HTTPException(404, 'Demo data is not installed.')
    row = df.loc[case_id]
    clinical = {k: (None if isinstance(row[k], (float, np.floating)) and np.isnan(row[k]) else row[k].item() if isinstance(row[k], np.generic) else row[k]) for k in NUMERIC+BINARY+CATEGORICAL}
    return remember(np.load(path, allow_pickle=False), f'Case {case_id:03d}', clinical=clinical, source='Validation demo')


def prepare_upload(path, filename):
    # Only one full 3D volume is expanded in memory at a time.
    with PREPROCESS_LOCK:
        return _prepare_upload(path, filename)


def _prepare_upload(path, filename):
    image = nib.load(path)
    if len(image.shape) != 3 or min(image.shape) < 3 or np.prod(image.shape, dtype=np.int64) > 64_000_000:
        raise ValueError('Use a 3D CT volume with at least 3 voxels per axis and at most 64 million voxels.')
    if not np.isfinite(image.affine).all() or abs(np.linalg.det(image.affine[:3, :3])) < 1e-10:
        raise ValueError('The NIfTI spatial orientation is invalid.')
    data = image.get_fdata(dtype=np.float32)
    if not np.isfinite(data).all() or np.ptp(data) == 0:
        raise ValueError('The volume contains invalid values or has no intensity variation.')
    if float(data.min()) > -200 or float(data.max()) < 0:
        raise ValueError('Expected CT intensities in Hounsfield units. Normalized images are not supported.')
    shape = list(image.shape)
    del data, image
    stack = process(Path(path))
    return remember(stack, filename, source='Uploaded CT', original_shape=shape)


@app.post('/api/upload')
async def upload(request: Request, filename: str):
    filename = Path(filename.replace('\\', '/')).name
    if not filename.lower().endswith(('.nii', '.nii.gz')):
        raise HTTPException(400, 'Upload a .nii or .nii.gz CT volume.')
    suffix = '.nii.gz' if filename.lower().endswith('.gz') else '.nii'
    with tempfile.TemporaryDirectory(prefix='pulmo-') as tmp:
        path = Path(tmp)/('scan'+suffix)
        total = 0
        with path.open('wb') as f:
            async for chunk in request.stream():
                total += len(chunk)
                if total > UPLOAD_LIMIT:
                    raise HTTPException(413, 'Upload limit is 200 MB.')
                f.write(chunk)
        try:
            return await run_in_threadpool(prepare_upload, str(path), filename)
        except (ValueError, OSError, EOFError, nib.filebasedimages.ImageFileError) as exc:
            raise HTTPException(400, f'Unable to read CT: {exc}') from exc


class Prediction(BaseModel):
    token: str
    model: str
    clinical: dict = Field(default_factory=dict)
    explain: bool = True


@app.post('/api/predict')
def predict(body: Prediction):
    case = get_case(body.token)
    try:
        result, cam = infer(case['stack'], body.model, body.clinical, body.explain)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, 'Inference failed. If GPU memory is full, stop training and retry.') from exc
    result.update(case=case['name'], source=case['source'], clinical=body.clinical if body.model.startswith('fusion') else {},
                  severity='Not assessed', disclaimer='Research use only. Not a clinical diagnosis.')
    run_id = uuid.uuid4().hex
    # Bind images to this exact inference so changing inputs cannot show a stale explanation.
    case['prediction'] = dict(id=run_id, cam=cam, result=result)
    return dict(**result, run_id=run_id, has_overlay=cam is not None)


@app.get('/api/cases/{token}/slices/{index}')
def slice_image(token: str, index: int, run: str = '', overlay: bool = False):
    case = get_case(token)
    if not 0 <= index < 16:
        raise HTTPException(400, 'Slice index must be between 0 and 15.')
    gray = case['stack'][index, 1]
    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(float)
    if overlay:
        prediction = case.get('prediction')
        if not prediction or prediction['id'] != run or prediction['cam'] is None:
            raise HTTPException(409, 'Run inference for this case before displaying an overlay.')
        cam = prediction['cam'][index]
        alpha = .55*cam[:, :, None]
        heat = np.stack([np.ones_like(cam)*255, 210*(1-cam), np.zeros_like(cam)], axis=2)
        rgb = rgb*(1-alpha)+heat*alpha
    buf = io.BytesIO()
    Image.fromarray(rgb.clip(0,255).astype('uint8')).save(buf, format='PNG')
    return Response(buf.getvalue(), media_type='image/png', headers={'Cache-Control':'no-store'})
