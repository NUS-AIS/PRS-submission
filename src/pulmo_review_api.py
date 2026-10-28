"""Run-bound review endpoints and bounded offline archive checking."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from pulmo_attention import summary_csv
from pulmo_cases import ApiError, get_case
from pulmo_review import build_review_archive, review_snapshot
from pulmo_review_verify import MAX_ARCHIVE_BYTES, VerificationError, inspect_archive


router = APIRouter()
NO_CACHE = {'Cache-Control': 'no-store'}


@router.get('/api/cases/{token}/explanation/summary')
def review_summary(token: str, run: str, threshold: float = .5, positions: str = ''):
    report, _, _ = review_snapshot(get_case(token), run, threshold, positions)
    return JSONResponse(report, headers=NO_CACHE)


@router.get('/api/cases/{token}/explanation/statistics')
def review_statistics(token: str, run: str, threshold: float = .5, positions: str = ''):
    report, _, _ = review_snapshot(get_case(token), run, threshold, positions)
    return Response(summary_csv(report['attention']), media_type='text/csv', headers={
        **NO_CACHE, 'Content-Disposition': 'attachment; filename="pulmo-statistics.csv"',
    })


@router.get('/api/cases/{token}/explanation/review')
def review_package(token: str, run: str, threshold: float = .5, positions: str = '',
                   opacity: float = .55, include_clinical: bool = False):
    data = build_review_archive(get_case(token), run, threshold, positions, opacity, include_clinical)
    return Response(data, media_type='application/zip', headers={
        **NO_CACHE, 'Content-Disposition': 'attachment; filename="pulmo-review.zip"',
    })


@router.post('/api/explanation/verify')
async def verify_package(request: Request):
    # Stream raw ZIP bytes to enforce a cap even without Content-Length.
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_ARCHIVE_BYTES:
            raise ApiError(413, 'archive_size', 'Review archive exceeds the 64 MB limit.')
        payload.extend(chunk)
    try:
        result = await run_in_threadpool(inspect_archive, bytes(payload))
    except VerificationError as exc:
        raise ApiError(400, exc.code, str(exc)) from None
    return JSONResponse(result, headers=NO_CACHE)
