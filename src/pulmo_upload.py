"""CT upload service: stream to a temporary file, validate the NIfTI volume, preprocess, cache.

Every rejection is an ApiError with a stable `code` and the offending field. The HU range test is an
input plausibility check only: it rejects normalized images but does not confirm the modality is CT.
"""
from pathlib import Path
import tempfile
import threading

import nibabel as nib
import numpy as np
from starlette.concurrency import run_in_threadpool

from ct_preprocess import K, process, summarize
from pulmo_cases import ApiError, remember

UPLOAD_LIMIT = 200 * 1024 * 1024
MAX_VOXELS = 64_000_000
HU_AIR_BELOW, HU_TISSUE_ABOVE = -200, 0  # a chest CT in HU reaches below -200 (air) and above 0 (tissue)
THICK_SLICE_MM = 5.0
PREPROCESS_LOCK = threading.Lock()
READ_ERRORS = (ValueError, OSError, EOFError, nib.filebasedimages.ImageFileError)


def rejected(code, detail, status=400, **field_errors):
    return ApiError(status, code, f'Unable to read CT: {detail}', field_errors or None)


def inspect_volume(path):
    """Validate the raw NIfTI and return header-level metadata (original voxel order)."""
    try:
        # No memmap: on Windows a mapped temp file cannot be deleted while an error traceback holds it.
        image = nib.load(path, mmap=False)
        shape = [int(n) for n in image.shape]
    except READ_ERRORS:
        raise rejected('unreadable_file', 'the file is not a readable NIfTI volume.') from None
    if len(shape) != 3:
        raise rejected('not_3d', f'expected a 3D volume, got {len(shape)} dimensions {shape}.', shape=shape)
    if min(shape) < 3:
        raise rejected('volume_too_small', f'every axis needs at least 3 voxels, got {shape}.', shape=shape)
    if np.prod(shape, dtype=np.int64) > MAX_VOXELS:
        raise rejected('volume_too_large', f'{shape} exceeds {MAX_VOXELS:,} voxels.', shape=shape)
    affine = image.affine
    if not np.isfinite(affine).all() or abs(np.linalg.det(affine[:3, :3])) < 1e-10:
        raise rejected('invalid_affine', 'the NIfTI spatial orientation is invalid.', affine='singular or non-finite')
    try:
        data = image.get_fdata(dtype=np.float32)
    except READ_ERRORS:
        raise rejected('unreadable_file', 'the voxel data is truncated or corrupt.') from None
    if not np.isfinite(data).all():
        raise rejected('non_finite_values', 'the volume contains NaN or infinite values.', intensity='non-finite')
    lo, hi = float(data.min()), float(data.max())
    if lo == hi:
        raise rejected('constant_volume', 'the volume has no intensity variation.', intensity=f'constant {lo:g}')
    if lo > HU_AIR_BELOW or hi < HU_TISSUE_ABOVE:
        raise rejected('intensity_not_hu',
                       f'intensities span {lo:g} to {hi:g}; Hounsfield units should reach below {HU_AIR_BELOW} '
                       f'and above {HU_TISSUE_ABOVE}. Normalized images are not supported.',
                       intensity=[round(lo, 1), round(hi, 1)])
    ornt = nib.io_orientation(affine)
    axial = int(np.flatnonzero(ornt[:, 0] == 2)[0])  # original axis that becomes RAS superior
    return dict(original_shape=shape,
                original_spacing_mm=[round(float(z), 4) for z in image.header.get_zooms()[:3]],
                orientation=''.join(nib.aff2axcodes(affine)),
                intensity_range_hu=[round(lo, 1), round(hi, 1)],
                axial_axis=axial, axial_flipped=bool(ornt[axial, 1] < 0))


def quality_warnings(summary):
    warnings = []
    if not summary['lung_mask_found']:
        warnings.append(dict(code='lung_mask_empty', detail='No lung region was found; cropping and slice sampling '
                                                            'fell back to the full volume.'))
    span = summary['sampled_slices'][-1] - summary['sampled_slices'][0] + 1
    if span < K:
        warnings.append(dict(code='few_axial_slices', detail=f'The sampled lung range covers {span} axial slices, '
                                                             f'fewer than the {K} samples, so some samples repeat.'))
    dz = summary['ras_spacing_mm'][2]
    if dz > THICK_SLICE_MM:
        warnings.append(dict(code='thick_slices', detail=f'Axial spacing is {dz:g} mm; the 3 channels of each '
                                                         f'sample are {dz:g} mm apart.'))
    return warnings


def build_quality(meta, summary):
    """Merge header metadata with the preprocessing summary. sampled_slices index the RAS volume;
    original_slices are the same positions in the uploaded file's own axial axis."""
    n = meta['original_shape'][meta['axial_axis']]
    original = [n - 1 - z if meta['axial_flipped'] else z for z in summary['sampled_slices']]
    return dict(**meta, **summary, samples=K, original_slices=original, warnings=quality_warnings(summary),
                hu_check='Intensity range is plausible for Hounsfield units. This is an input plausibility '
                         'check and does not confirm the imaging modality.')


def prepare_upload(path, filename):
    # Only one full 3D volume is expanded in memory at a time.
    with PREPROCESS_LOCK:
        return _prepare_upload(path, filename)


def _prepare_upload(path, filename):
    meta = inspect_volume(path)
    failure = None
    try:
        stack, debug = process(Path(path), return_debug=True)
        summary = summarize(debug)
        del debug  # the full volume and mask are not kept in the case cache
    except (ValueError, IndexError, OSError, EOFError) as exc:
        failure = str(exc)  # raise outside the except block so its frames (and any memmap) are released
    if failure is not None:
        raise ApiError(400, 'preprocessing_failed', f'Unable to preprocess CT: {failure}')
    return remember(stack, filename, source='Uploaded CT', original_shape=meta['original_shape'],
                    quality=build_quality(meta, summary))


async def receive_upload(chunks, filename):
    """Write the request body to disk under the size limit, then preprocess it off the event loop."""
    filename = Path(filename.replace('\\', '/')).name
    if not filename.lower().endswith(('.nii', '.nii.gz')):
        raise ApiError(400, 'unsupported_file_type', 'Upload a .nii or .nii.gz CT volume.', dict(filename=filename))
    suffix = '.nii.gz' if filename.lower().endswith('.gz') else '.nii'
    with tempfile.TemporaryDirectory(prefix='pulmo-') as tmp:
        path = Path(tmp)/('scan'+suffix)
        total = 0
        with path.open('wb') as f:
            async for chunk in chunks:
                total += len(chunk)
                if total > UPLOAD_LIMIT:
                    raise ApiError(413, 'upload_too_large', 'Upload limit is 200 MB.', dict(size=f'> {UPLOAD_LIMIT} bytes'))
                f.write(chunk)
        if total == 0:
            raise ApiError(400, 'empty_upload', 'The uploaded file is empty.', dict(size=0))
        return await run_in_threadpool(prepare_upload, str(path), filename)
