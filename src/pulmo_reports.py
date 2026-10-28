"""Reports and images bound to a single cached prediction, not a fresh inference."""
import copy
import hashlib
import io
import json
import zipfile

from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse

from pulmo_cases import ApiError, get_case
from pulmo_explain import explanation_status, render_png

router = APIRouter()


def explanation_bundle(case, run, index, opacity=.55):
    """Capture one immutable prediction reference before rendering any files."""
    snapshot = {**case, 'prediction': bound_prediction(case, run)}
    report = case_report(snapshot, run, index, opacity,
                         overlay=snapshot['prediction']['cam'] is not None)
    files = {'original.png': prediction_image(snapshot, index, run, False, opacity, True)}
    if snapshot['prediction']['cam'] is not None:
        files['overlay.png'] = prediction_image(snapshot, index, run, True, opacity, True)
    report['files'] = {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                       for name, data in files.items()}
    files['report.json'] = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    # If another prediction replaced this run while rendering, do not publish a stale export.
    bound_prediction(case, run)
    return archive.getvalue()


def bound_prediction(case, run):
    prediction = case.get('prediction')
    if not run or not prediction or prediction['id'] != run:
        raise ApiError(409, 'stale_explanation', 'Prediction expired. Run inference again.')
    return prediction


def validate_view(case, index, opacity):
    if not 0 <= index < len(case['stack']):
        raise ApiError(400, 'invalid_slice', 'Select an available sampled position.')
    if not 0 <= opacity <= 1:
        raise ApiError(400, 'invalid_opacity', 'Opacity must be between 0 and 1.')


def prediction_image(case, index, run='', overlay=False, opacity=.55, require_run=False):
    validate_view(case, index, opacity)
    prediction = bound_prediction(case, run) if overlay or require_run else None
    cam = None
    if overlay:
        if prediction['cam'] is None:
            raise ApiError(409, 'explanation_missing', 'This prediction has no Grad-CAM. Enable explanation and rerun.')
        cam = prediction['cam'][index]
    try:
        return render_png(case['stack'][index, 1], cam, opacity)
    except ValueError as exc:
        raise ApiError(400, 'invalid_explanation', str(exc)) from None


def case_report(case, run, index, opacity=.55, overlay=True):
    validate_view(case, index, opacity)
    prediction = bound_prediction(case, run)
    result = copy.deepcopy(prediction['result'])
    quality = case.get('quality') or {}
    return dict(
        schema_version=1, run_id=run, prediction=result,
        explanation=dict(method='Grad-CAM', target='predicted class logit',
                         layer='bb.layer4', normalization='case maximum',
                         status=explanation_status(prediction['cam']),
                         sampled_position=index+1, sampled_positions=len(case['stack']),
                         opacity=opacity, overlay=overlay,
                         coordinate_space='cropped 2.5D model input; not original CT slice numbering'),
        quality=quality,
        provenance=result.get('provenance', {'status': 'not supplied; checkpoint/result matching not verified'}),
        limitations=['Research use only; not a clinical diagnosis.',
                     'Attention is not lesion segmentation or severity assessment.',
                     'Probabilities are uncalibrated model scores.'],
    )


@router.get('/api/cases/{token}/explanation/report')
def download_report(token: str, run: str, index: int = 7, opacity: float = .55, overlay: bool = True):
    report = case_report(get_case(token), run, index, opacity, overlay)
    return JSONResponse(report, headers={
        'Content-Disposition': 'attachment; filename="pulmo-explanation.json"',
        'Cache-Control': 'no-store',
    })


@router.get('/api/cases/{token}/explanation/image')
def download_image(token: str, run: str, index: int = 7, opacity: float = .55, overlay: bool = True):
    data = prediction_image(get_case(token), index, run, overlay, opacity, require_run=True)
    return Response(data, media_type='image/png', headers={
        'Content-Disposition': 'attachment; filename="pulmo-explanation.png"',
        'Cache-Control': 'no-store',
    })


@router.get('/api/cases/{token}/explanation/bundle')
def download_bundle(token: str, run: str, index: int = 7, opacity: float = .55):
    data = explanation_bundle(get_case(token), run, index, opacity)
    return Response(data, media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="pulmo-explanation.zip"',
        'Cache-Control': 'no-store',
    })
