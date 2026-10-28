# Full-case explanation review

Member D extends the cached Grad-CAM workflow with descriptive statistics, selected-position exports, integrity checks and offline comparisons. Model weights, preprocessing, data splits and prediction probabilities are unchanged.

## Browser workflow

1. Load a validation demo or upload a supported CT volume.
2. Select a model and run inference with Grad-CAM enabled.
3. Scroll to **Explanation Review** below the inference panels.
4. Leave **Positions to review** blank for all positions, or enter a comma-separated selection such as `1,4,8,16`.
5. Choose an attention display threshold between 0 and 1.
6. Click **Refresh attention statistics**.
7. Sort by sampled position or attention mass. Click a position number to open it in the existing viewer.
8. Export statistics as CSV, or export the full review ZIP.
9. Extract a trusted exported archive and open `index.html` for offline review and browser printing.
10. Select the original ZIP under **Verify a saved review** to check its manifest, file hashes and schema.

Changing review options cancels pending review requests. Changing the case, clinical inputs or prediction invalidates review results. Statistics, exports and opacity changes never invoke inference.

## What the numbers mean

| Field | Definition | Interpretation limit |
|---|---|---|
| Mean | Average case-normalized attention over the input image | Not a confidence score |
| Maximum | Maximum normalized attention in that position | Not evidence strength across patients |
| Sum / mass | Sum of attention values over all pixels | Depends on resolution and normalization |
| Positive fraction | Fraction of pixels with attention greater than zero | Not a disease-area estimate |
| Above-threshold fraction | Positive pixels at or above the chosen threshold, divided by total pixels | Threshold is a display choice |
| Selected mass fraction | Position mass divided by mass over the selected positions | Changes when the selection changes |
| Entropy | Entropy of normalized pixel mass divided by log(pixel count) | Describes spatial spread only |
| Centroid | Attention-weighted x/y mean in model-input pixels | Not an anatomical landmark |
| Peak | First maximum pixel in row-major order | Ties do not identify a unique location |
| Threshold box | Inclusive image-pixel bounds of positive above-threshold values | Not lesion segmentation |
| Image-half mass | Mass fractions in image left/right and upper/lower halves | Image halves are not patient anatomical sides |

Zero-signal heatmaps have zero mean/maximum but no centroid, entropy or threshold box. Heatmaps that were not requested have missing measurements, not invented zeros. Threshold zero still excludes pixels whose attention is exactly zero.

## Archive contents

| File | Purpose |
|---|---|
| `report.json` | Prediction, selected positions, statistics, method, privacy and limitations |
| `statistics.csv` | Flat numerical rows for independent analysis |
| `index.html` | Script-free, offline, printable report |
| `contact-sheet.png` | Labelled overview of the selected positions |
| `images/position-NNN-original.png` | Middle channel of each selected model input |
| `images/position-NNN-overlay.png` | Cached Grad-CAM overlay, omitted when not requested |
| `manifest.json` | File names, byte sizes, SHA256 digests and run identifier |

The manifest does not hash itself. Verification detects changed members, sizes or bytes; it is not a signature. Someone able to rewrite the archive and manifest can produce a new internally consistent archive.

## Data handling

- Case names and source filenames are omitted using an explicit export allowlist.
- Clinical inputs and their preprocessing summary are omitted unless the user checks the inclusion option.
- CT pixels and the model-input fingerprint remain sensitive research data. Omission of names does not make images anonymous.
- The input fingerprint includes stack dimensions, dtype and pixels. It identifies exact preprocessed inputs, not patients or original CT volumes.
- Nothing is saved to a server report database. The browser downloads the generated archive.
- The verifier reads ZIP members in memory and never extracts files or executes HTML.

## Offline commands

Run from the repository with its Python environment:

```sh
python src/review_report.py verify path/to/review.zip
python src/review_report.py verify path/to/review.zip --include-report
python src/review_report.py compare left.zip right.zip --output comparison.json
```

The CLI exits with code 0 on success and 2 on a verification or file error. Output files are created exclusively and never overwrite existing files. Comparison verifies both archives first. Deltas are right minus left.

Different model-input fingerprints suppress attention deltas. Different thresholds suppress above-threshold-fraction deltas. Omitted clinical inputs are reported as unknown, not equal. A prediction-class change also changes the Grad-CAM target. A difference in scores is not evidence that either model is more accurate.

## API

| Method and path | Parameters | Response |
|---|---|---|
| GET `/api/cases/{token}/explanation/summary` | `run`, `threshold`, `positions` | Review JSON without images |
| GET `/api/cases/{token}/explanation/statistics` | Same | CSV attachment |
| GET `/api/cases/{token}/explanation/review` | Same plus `opacity`, `include_clinical` | Full ZIP attachment |
| POST `/api/explanation/verify` | Raw ZIP body | Integrity result and parsed report |

Positions are one-based in review APIs, unlike the existing viewer's zero-based `index`. Duplicate, fractional and out-of-range selections are rejected. All responses use `Cache-Control: no-store`. Stale run identifiers return HTTP 409; invalid report options return 400; oversize exports or uploads return 413.

The archive verifier caps compressed and expanded data at 64 MiB, metadata at 2 MiB and membership at 270 files. Only stored/deflated ordinary ZIP files are supported. Unsafe paths, duplicate members, symlinks, encryption and unsupported schema versions are rejected.

## Validation

```sh
python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_explanation_request.cjs tests/test_review_state.cjs
node --check web/modules/review.js
```

Synthetic CPU fixtures verify point-mass and uniform-map mathematics, tiny positive signals, missing/zero heatmaps, redaction, selection, HTML escaping, PNG readability, stale-run exports, ZIP tampering, schema limits, CLI behavior and HTTP contracts. Existing real-model tests remain part of the full suite.

## Reproduce contribution statistics

```sh
python src/contribution_audit.py --revision HEAD --output contribution.md
python src/contribution_audit.py --revision HEAD --json --output contribution.json
```

The pre-expansion snapshot is preserved in `contribution-before-expansion.md`. Git-added lines are counted separately from source/test additions and current blame attribution. Line counts include comments and blank lines and do not measure scientific contribution or code quality.
