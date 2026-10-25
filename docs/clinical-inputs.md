# Clinical inputs and fusion prediction

How the research UI checks clinical fields, fills missing values, reports what the fusion model actually
received, and how the clinical input → fusion prediction → input summary path is tested.

Code: `src/pulmo_clinical.py` (rules, training-fitted preprocessing, summaries), `src/pulmo_prediction.py`
(predict request → response), `src/pulmo_runtime.py` (model loading and `infer`),
`web/modules/clinical-form.js` and `web/modules/prediction.js` (page), `web/styles/clinical.css`.
Field names and order come from `src/common.py` and are unchanged.

## Field rules

| Field | Kind | Accepted | Left blank | Error message starts with |
|---|---|---|---|---|
| `Age` | numeric | finite number, 0–120 (years) | training median **63** | `Age must be …` |
| `Lymphocyte Count` | numeric | finite number ≥ 0 | training median **1.195** | `Lymphocyte Count must be …` |
| `D-Dimer` | numeric | finite number ≥ 0 | training median **420** | `D-Dimer must be …` |
| `Solid Tumor`, `Diabetes`, `Renal dysfunction`, `Immunosuppressants`, `AIDS`, `(1,3)-β-D-Glucan (G)`, `Aspergillus Antigen (GM)` | binary | `0` (no / negative) or `1` (yes / positive) | **rejected** | `Please specify …` / `… must be 0 (no) or 1 (yes).` |
| `Gender` | categorical | `M` or `F`, as coded in the dataset | **rejected** | `Please specify sex …` |

- Numbers may be sent as JSON numbers or numeric strings (`"63"`). `null`, `""`, whitespace and `NaN` count as blank.
- Booleans, lists and objects are rejected for every field; `true` is not accepted as `1`.
- Training had no "unknown" category for binary fields or sex, so a missing value is an error. It is
  **never** encoded as 0.
- All invalid fields are reported in one response, not just the first.
- Fields not listed above are ignored and named in the summary (`ignored_fields`).

### Units

The dataset table (`data/raw/OMIX014539-08.csv`) gives no units for `Lymphocyte Count` or `D-Dimer`.
**The units need to be checked against the original data source.** Until then, enter values in the
same units as that table. The page and the API both say this next to the two fields.

## Missing values and training statistics

Preprocessing is fitted once on the **402 training rows** of `data/splits.csv` (`split == 'train'`) and
never on validation or test rows:

1. Numeric fields: median imputation, then standardisation with the training mean and SD.
2. Binary fields: passed through as 0/1.
3. Sex: one-hot (`M`, `F`).

This is the same `ColumnTransformer` that `train_ct.py` used, so the fusion input vector (12 values) is
unchanged. Medians over all 569 rows would differ (Age would be 64, not 63); a test checks this.

`training_reference()` reports this provenance, including `split_sha256`: the first 12 hex digits of
the SHA-256 of `splits.csv` with line endings normalised to LF (currently `aa7ca0910321`). Model
manifests can use it to match a checkpoint to the split it was trained on.

## API

### `GET /api/clinical`

Returns the rules the form uses: for each field its `kind`, `required`, `min`/`max`, `unit`, the
`median` used when blank and the allowed `options`, plus the `preprocessing` provenance.

### `POST /api/predict`

The request is unchanged: `{token, model, clinical, explain}`. The response keeps every earlier key
(`probabilities`, `predicted_class`, `run_id`, `has_overlay`, `clinical`, …) and adds `inputs`.

Fusion model, with `D-Dimer` left blank:

```json
"inputs": {
  "used": true,
  "fields": [
    {"field": "Age", "kind": "numeric", "submitted": 45.0, "used": 45.0, "source": "user input", "unit": "years"},
    {"field": "D-Dimer", "kind": "numeric", "submitted": null, "used": 420.0, "source": "training median",
     "unit": "not stated in the dataset; check the original source"}
  ],
  "imputed": ["D-Dimer"],
  "ignored_fields": [],
  "preprocessing": {"train_rows": 402, "split_file": "splits.csv", "split_sha256": "aa7ca0910321", "...": "..."}
}
```

(`fields` lists all 11 fields; two are shown.) CT-only models return
`"inputs": {"used": false, "note": "CT-only model: clinical inputs were not used."}` and
`"clinical": {}`, whatever was sent.

### Errors

| Situation | HTTP | `code` | Extra |
|---|---|---|---|
| One or more invalid clinical fields (fusion only) | 400 | `invalid_clinical` | `field_errors`: field → message |
| Model not in the local catalogue | 400 | `model_unavailable` | `field_errors.model` |
| Case token expired or unknown | 404 | `case_expired` | — |
| Inference raised (for example GPU out of memory) | 503 | `inference_failed` | — |

`detail` is always a displayable string. A rejected request does not create a new `run_id` and does
not replace the last valid prediction.

## Page behaviour

- **Fusion mode**: binary fields and sex are marked `*` and are required; the browser blocks the
  request until they are chosen.
- Under each blank numeric field the page shows the training median that will be used; the two lab
  fields also show the unit warning.
- Values are checked while typing with the same rules and wording as the server. Server
  `field_errors` are shown under the matching field, and the first one gets focus.
- After a prediction, **Inputs used by the model** lists each field's value and source; rows filled
  from the training median are highlighted.
- Changing the case, the model or any field clears the prediction, the Grad-CAM overlay, the input
  summary and the "Inference complete" status.
- **CT-only mode**: the fields are disabled and not required.

### Events for other modules

`prediction.js` dispatches these on `document`; the explanation viewer can listen instead of reading
`app.js` globals:

| Event | When | `detail` |
|---|---|---|
| `pulmo:prediction` | a prediction succeeded | the full response, including `run_id` |
| `pulmo:invalidate` | the current result was cleared | — |
| `pulmo:field-errors` | the server rejected clinical fields | `{field: message}` |

## Tests

```
python -m unittest tests.test_clinical_fusion -v
```

| Group | Needs | Covers |
|---|---|---|
| `ClinicalValidationTest` | committed data only | age bounds (0, 120, −1, 120.5), negative and non-finite values, wrong types, blank numbers stay missing, missing binary rejected and never 0, sex coding, all errors at once |
| `TrainingStatisticsTest` | committed data only | medians and scaling from training rows only, vector equals the fitted transformer, split hash ignores line endings |
| `ClinicalSummaryTest` | committed data only | blank → training median and source, the summary equals what the model receives, unknown fields, `/api/clinical` rules |
| `FusionPredictionApiTest` | fastapi, httpx | `/api/predict` on randomly initialised CT-only and fusion networks: old keys kept, `inputs` added, probabilities equal to calling `infer` directly, `invalid_clinical` field errors, CT-only ignores clinical input, unknown model, a changed input makes the old `run_id` stale (409) |
| `TrainedFusionTest` | `runs/fusion_aug-basic_seed0.pt`, `data/processed/` | a validation case with missing lab values: the summary lists exactly the fields missing in the dataset |

Without local weights and slices, 21 tests run and `TrainedFusionTest` is skipped, with the reason
shown. With them, all 22 pass. `python -m unittest discover -s tests -p "test_*.py"` runs these
together with `tests/test_ct_upload.py`.

**Checked on 2026-10-24** in headless Chrome against a local server, on validation case 004, fusion
seed 0. Each step behaved as described above:

- fusion prediction with D-dimer left blank (summary row "Training median 420");
- age −5 and Diabetes unselected blocked before any request, with inline errors;
- a request with invalid sex and lymphocyte count returned 9 field errors, shown inline;
- editing Age after a prediction cleared the result and emitted `pulmo:invalidate`;
- a CT-only prediction showed "clinical inputs were not used".

The page script raised no errors.

## Limits

- Lab units are unknown (see **Units**). Values in other units are accepted but give wrong inputs.
- Range checks catch impossible values only (negative, non-finite, age > 120); a plausible but wrong
  value is not detected.
- Probabilities are uncalibrated, and the summary describes inputs only. It says nothing about how
  much each field influenced the prediction.
- After a rejected request the server still holds the last valid prediction under its own `run_id`. The page
  clears it as soon as an input changes, so it is not shown.

## Work record (member B)

Effective lines are added or substantially changed code, excluding blank lines, comments and moved code.
Counts are approximate.

| Commit | Kind | Effective lines |
|---|---|---|
| `fc05ab4` refactor(clinical) | move: `clinical_setup` / `clinical_vector` into `pulmo_clinical.py` | 0 (about 40 moved) |
| `31ca419` feat(fusion) | backend: validation, summaries, `pulmo_prediction.py` | about 95 (about 12 lines of the predict route moved from `pulmo_server.py`) |
| `69e8270` feat(fusion-ui) | backend 13 · frontend about 175 (`clinical-form.js` 88, `prediction.js` 72, `clinical.css` 12, `index.html` 3) | about 190 |
| this commit | tests (`tests/test_clinical_fusion.py`) | about 185 |
| | documentation (this file) | not counted |

The total is about 470 effective lines: backend about 110, frontend about 175, tests about 185. This is
below the 500–650 target in the plan. Per the plan, no code was added to reach the number.
