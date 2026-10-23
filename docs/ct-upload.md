# CT upload and quality metadata

How the research UI accepts a CT volume, what it checks, what it returns, and how the
upload → CT-only prediction → slice browsing path is tested.

Code: `src/pulmo_upload.py` (validation and processing), `src/pulmo_cases.py` (case cache and
`ApiError`), `src/ct_preprocess.py` (model input, `summarize()`), `web/modules/ct-viewer.js` (page).

## Accepted input

| Check | Limit | Error `code` | HTTP |
|---|---|---|---|
| File name ends in `.nii` or `.nii.gz` (case-insensitive) | — | `unsupported_file_type` | 400 |
| Request body is not empty | — | `empty_upload` | 400 |
| Upload size | 200 MB (`UPLOAD_LIMIT`) | `upload_too_large` | 413 |
| nibabel can read the header and voxel data | — | `unreadable_file` | 400 |
| Exactly three dimensions | 4D series are rejected, not split | `not_3d` | 400 |
| Every axis has at least 3 voxels | — | `volume_too_small` | 400 |
| Voxel count | 64,000,000 (`MAX_VOXELS`) | `volume_too_large` | 400 |
| Affine is finite and its 3×3 part is not singular | — | `invalid_affine` | 400 |
| All voxel values are finite | no NaN / ±inf | `non_finite_values` | 400 |
| Intensities are not constant | — | `constant_volume` | 400 |
| Range reaches below −200 and above 0 | Hounsfield units expected | `intensity_not_hu` | 400 |
| `ct_preprocess.process` succeeds | — | `preprocessing_failed` | 400 |

DICOM folders, normalized (0–1) images and segmentation masks are not supported; convert DICOM to
NIfTI first and keep the values in HU.

The HU range check is an input plausibility check only. It catches normalized or non-intensity
images; it does **not** confirm that the file is a CT scan or a chest scan.

## Error response

Every rejection uses the same JSON body. `detail` is always a displayable string (the page shows it
as is); `field_errors` is present only when a specific field is at fault.

```json
{
  "detail": "Unable to read CT: expected a 3D volume, got 4 dimensions [8, 8, 8, 2].",
  "code": "not_3d",
  "field_errors": {"shape": [8, 8, 8, 2]}
}
```

A token that is no longer cached returns `404 {"code": "case_expired", ...}`. Messages never contain
the server's temporary file path.

## Upload response

`POST /api/upload?filename=<name>` with the raw file as the request body.

| Field | Meaning |
|---|---|
| `token`, `name`, `slices`, `source`, `original_shape` | Case handle, as before (`slices` = 16, `source` = `Uploaded CT`) |
| `quality.original_shape`, `original_spacing_mm`, `orientation` | Header values in the file's own voxel order; orientation as axis codes, e.g. `RAS`, `LPS` |
| `quality.intensity_range_hu` | Minimum and maximum voxel value |
| `quality.pipeline`, `window_hu` | `ct_preprocess.PIPELINE_VERSION` and the lung window (−1350..150 HU) |
| `quality.ras_shape`, `ras_spacing_mm` | Shape and spacing after reorienting to RAS |
| `quality.lung_mask_found`, `crop` | Whether the lung mask was found; square crop box `x0, y0, side` in RAS voxels |
| `quality.samples`, `sampled_slices` | 16 axial centres used for the model, as RAS slice indices |
| `quality.original_slices` | The same 16 positions as slice indices of the uploaded file's axial axis |
| `quality.output_shape` | `[16, 3, 224, 224]`, uint8 |
| `quality.warnings` | List of `{code, detail}`; the case is still usable |
| `quality.hu_check` | The plausibility note above |

Validation demo cases return `quality: null`, because only their preprocessed stacks are shipped.

Warnings:

- `lung_mask_empty` — no lung region found; crop and slice sampling fell back to the full volume.
- `few_axial_slices` — the lung covers fewer than 16 axial slices, so some samples repeat.
- `thick_slices` — axial spacing above 5 mm; the three channels of each sample are far apart.

## Memory and cache

The upload is streamed to a temporary directory that is deleted on success and on every error.
One volume is expanded at a time (`PREPROCESS_LOCK`). After preprocessing only the
`(16, 3, 224, 224)` uint8 stack and the small metadata above are kept; the full volume, mask and
debug arrays are released. The cache holds the 8 most recent cases (`MAX_CASES`) and evicts the
oldest first; an evicted token returns `case_expired`, and the page asks the user to load it again.

Preprocessing is unchanged by the upload service: an uploaded file produces exactly the same stack as
running `ct_preprocess.process` on it offline (covered by a test).

## Page behaviour

`web/modules/ct-viewer.js` shows Upload → Preprocess → Ready stages (no fake percentage), offers a
retry only for network or server (5xx) failures, opens the quality panel automatically when there are
warnings, labels each slice with its source slice index, shows the server message if a slice image
fails to load, and supports ←/→, PgUp/PgDn (±4), Home/End for browsing. It must be included after
`app.js` in `web/index.html`:

```html
<link rel="stylesheet" href="/static/styles/ct-viewer.css">
<script src="/static/modules/ct-viewer.js"></script>
```

## Tests

```bash
python -m unittest tests.test_ct_upload -v
```

All volumes are synthetic phantoms generated in the test (a soft-tissue ellipse with two lung
ellipsoids); no real CT is read or committed.

| Group | Needs | Covers |
|---|---|---|
| `UploadValidationTest` | baseline requirements | `.nii` and `.nii.gz` give the same stack; stack equals offline preprocessing; quality fields; flipped axial axis; warnings; every error code above; no temp directory left behind |
| `CaseStoreTest` | baseline requirements | eviction order, `case_expired`, error body shape |
| `UploadWorkflowTest` | `fastapi`, `httpx` | HTTP error bodies; eviction over HTTP; upload → CT-only predict → plain and overlay slice PNGs; stale overlay `run` rejected with 409 |

The workflow test runs the real inference code on a randomly initialised CT-only network saved to a
temporary `runs/`, so it checks the wiring (shapes, clinical input ignored, Grad-CAM overlay binding)
without trained weights; its probabilities are meaningless. If `runs/ct_aug-basic_seed0.pt` exists
locally, the same path also runs once with the trained model. `httpx` is required by
`fastapi.testclient` but is not in `requirements-ui.txt`; install it to run this group, otherwise it
is skipped.
