"""Local research UI. Run with uvicorn pulmo_server:app --app-dir src."""
import json

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from common import ROOT, NUMERIC, BINARY, CATEGORICAL
from pulmo_cases import ApiError, get_case, remember
from pulmo_clinical import clinical_schema
from pulmo_prediction import predict_case
from pulmo_runtime import catalog, clinical_setup, LABELS
from pulmo_upload import receive_upload
from pulmo_reports import router as explanation_router, prediction_image

app = FastAPI(title='Pulmo AI Research Workspace')
app.include_router(explanation_router)
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


@app.get('/api/clinical')
def clinical_fields():
    return clinical_schema()


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
    return predict_case(get_case(body.token), body.model, body.clinical, body.explain)


@app.get('/api/cases/{token}/slices/{index}')
def slice_image(token: str, index: int, run: str = '', overlay: bool = False, opacity: float = .55):
    data = prediction_image(get_case(token), index, run, overlay, opacity)
    return Response(data, media_type='image/png', headers={'Cache-Control': 'no-store'})
