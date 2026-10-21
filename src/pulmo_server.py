"""Local research UI. Run with uvicorn pulmo_server:app --app-dir src."""
import io
import json
import uuid

import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from common import ROOT, NUMERIC, BINARY, CATEGORICAL
from pulmo_cases import ApiError, get_case, remember
from pulmo_runtime import catalog, clinical_setup, infer, LABELS
from pulmo_upload import receive_upload

app = FastAPI(title='Pulmo AI Research Workspace')
WEB = ROOT / 'web'
app.mount('/static', StaticFiles(directory=WEB), name='static')


@app.exception_handler(ApiError)
def api_error(request: Request, exc: ApiError):
    return JSONResponse(exc.body(), status_code=exc.status)


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
        raise ApiError(404, 'demo_not_validation', 'Only validation cases are available in the demo.', dict(case_id=case_id))
    path = ROOT/'data'/'processed'/f'Case{case_id:03d}.npy'
    if not path.exists():
        raise ApiError(404, 'demo_not_installed', 'Demo data is not installed.', dict(case_id=case_id))
    row = df.loc[case_id]
    clinical = {k: (None if isinstance(row[k], (float, np.floating)) and np.isnan(row[k]) else row[k].item() if isinstance(row[k], np.generic) else row[k]) for k in NUMERIC+BINARY+CATEGORICAL}
    # Demo stacks were preprocessed offline; the source volume (and so its quality metadata) is not shipped.
    return remember(np.load(path, allow_pickle=False), f'Case {case_id:03d}', clinical=clinical, source='Validation demo',
                    quality=None)


@app.post('/api/upload')
async def upload(request: Request, filename: str):
    return await receive_upload(request.stream(), filename)


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
