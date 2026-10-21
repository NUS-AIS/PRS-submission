"""CT upload service: stream to a temporary file, validate the NIfTI volume, preprocess, cache."""
from pathlib import Path
import tempfile
import threading

import nibabel as nib
import numpy as np
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from ct_preprocess import process
from pulmo_cases import remember

UPLOAD_LIMIT = 200 * 1024 * 1024
MAX_VOXELS = 64_000_000
PREPROCESS_LOCK = threading.Lock()


def prepare_upload(path, filename):
    # Only one full 3D volume is expanded in memory at a time.
    with PREPROCESS_LOCK:
        return _prepare_upload(path, filename)


def _prepare_upload(path, filename):
    image = nib.load(path)
    if len(image.shape) != 3 or min(image.shape) < 3 or np.prod(image.shape, dtype=np.int64) > MAX_VOXELS:
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


async def receive_upload(chunks, filename):
    """Write the request body to disk under the size limit, then preprocess it off the event loop."""
    filename = Path(filename.replace('\\', '/')).name
    if not filename.lower().endswith(('.nii', '.nii.gz')):
        raise HTTPException(400, 'Upload a .nii or .nii.gz CT volume.')
    suffix = '.nii.gz' if filename.lower().endswith('.gz') else '.nii'
    with tempfile.TemporaryDirectory(prefix='pulmo-') as tmp:
        path = Path(tmp)/('scan'+suffix)
        total = 0
        with path.open('wb') as f:
            async for chunk in chunks:
                total += len(chunk)
                if total > UPLOAD_LIMIT:
                    raise HTTPException(413, 'Upload limit is 200 MB.')
                f.write(chunk)
        try:
            return await run_in_threadpool(prepare_upload, str(path), filename)
        except (ValueError, OSError, EOFError, nib.filebasedimages.ImageFileError) as exc:
            raise HTTPException(400, f'Unable to read CT: {exc}') from exc
