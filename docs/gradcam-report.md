# Member D — Grad-CAM and prediction-bound reports

Contributor: `hanjingmu2004-coder`.

## Scope and existing work

The original application already computed Grad-CAM inside `pulmo_runtime.infer` and rendered a fixed-opacity overlay. This contribution extracts that existing calculation, adds explanation status, optional calculation, validated opacity, and JSON/PNG downloads bound to the prediction ID. It integrates with member B's `pulmo:prediction` and `pulmo:invalidate` events and retains the shared viewer. Existing A/B files and author history are preserved.

## Files

| File | Responsibility |
|---|---|
| `src/pulmo_explain.py` | Exception-safe feature hooks, predicted-logit gradients, finite/zero checks and PNG rendering |
| `src/pulmo_reports.py` | Validate cached run, opacity and sampled position; export report and image |
| `src/pulmo_runtime.py` | Delegate explanation computation without changing model structure or normalization |
| `src/pulmo_server.py` | Register report endpoints and delegate slice rendering |
| `web/modules/explanation.js` | Explanation switch, opacity, lifecycle invalidation and downloads |
| `web/styles/explanation.css` | Scoped controls styling |
| `web/app.js`, `web/index.html` | Request flag and module/style wiring |
| `tests/test_explanation.py` | CPU numerical, hook lifecycle and HTTP contract tests |

## Workflow

1. Start the existing server with `python -m uvicorn pulmo_server:app --app-dir src --host 127.0.0.1 --port 8765`.
2. Load a validation demo or upload a NIfTI CT. Select CT-only or fusion; complete the required clinical fields for fusion.
3. Keep **Compute Grad-CAM on next prediction** checked and run inference.
4. Browse sampled positions, toggle the existing Grad-CAM switch, and adjust **Heatmap opacity**. These display operations reuse the cached result and do not run the model again.
5. Download the explanation JSON and selected PNG. To export the unoverlaid model input, turn off the Grad-CAM display switch first.
6. Change clinical inputs, model or case: the previous explanation controls/downloads become unavailable. Rerun inference to get a new report.

Disabling computation before prediction returns probabilities without an explanation. A zero Grad-CAM signal is explicitly labelled and does not imply absence of disease. The viewer represents cropped model inputs, not original slice numbering.

## Method

The target is the predicted class **logit of the final classifier**. For fusion this classifier depends on both image and clinical features. Gradients are taken with respect to `bb.layer4` activations, spatially averaged per channel, multiplied by activations, summed, passed through ReLU, resized and normalized by the maximum across the case. The hook is always removed in a `finally` path. The model architecture, state-dict keys and clinical preprocessing remain unchanged.

Statuses: `available`, `zero_signal`, `not_requested`. Non-finite explanations are rejected rather than rendered. Scores remain uncalibrated; maps are attention explanations, not lesion boundaries, severity estimates or clinical diagnoses.

## API

All image/report responses disable caching. `index` is zero-based; report `sampled_position` is one-based. `opacity` must be finite and between 0 and 1 (default 0.55).

| Endpoint | Parameters | Response |
|---|---|---|
| `GET /api/cases/{token}/slices/{index}` | Existing `run`, `overlay`; new `opacity` | PNG; overlay requires the current run |
| `GET /api/cases/{token}/explanation/report` | Required `run`; optional `index`, `opacity`, `overlay` | Downloadable JSON snapshot |
| `GET /api/cases/{token}/explanation/image` | Same parameters | Downloadable PNG; requires the current run even for original image |

The report contains a deep copy of the exact prediction, including B's `inputs` summary, run ID, model identifier, sampled position, display settings, quality metadata when available, and explanation limitations. If no model provenance is supplied upstream, it explicitly states that checkpoint/result matching is unverified. No provenance is fabricated and no new inference is performed during export.

Errors retain the shared `{detail, code}` contract: invalid position/opacity returns 400; expired case returns 404; absent/stale run or missing overlay returns 409. Cached state is local and temporary; restarting the server invalidates it. Browser invalidation is not server-side deletion, but downloads still require the current cached run ID.

## Validation

Run all tests from this repository:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
node --check web/modules/explanation.js
node --check web/app.js
```

The D suite needs no trained weights. It uses deterministic small CT/fusion networks to verify identical logits with explanation enabled/disabled, finite map shape, zero maps, rejected non-finite logits, repeated-run hook cleanup and cleanup after exceptions. HTTP tests cover report snapshot consistency, opacity, invalid indices, stale/replaced runs, no-CAM original exports and PNG generation without inference. These tests validate software behavior, not clinical accuracy.

Validation on 2026-10-28: the asset-free run discovered 50 tests, with 48 passing and 2 existing A/B asset-dependent tests skipped. After supplying local seed-0 CT/fusion weights and the validation samples under ignored `runs/` and `data/processed/`, all 50 tests passed (no skips). An intermediate run with only Case004 could not run B's missing-value validation-case test; supplying the required validation samples resolved it without changing the test. No validation assets are committed. JavaScript syntax checks passed. Browser interaction has not been acceptance-tested in this submission and should additionally be checked with the workflow above; syntax checking alone is not a browser acceptance test.

## Commit organization

1. Extract Grad-CAM calculation and preserve runtime compatibility.
2. Add validated overlays and prediction-bound report/image endpoints.
3. Add scoped front-end controls and lifecycle handling.
4. Wire controls into the page, add tests and document the complete chain.

These are actual implementation commits built on the submission repository's existing main branch. They do not reassign authorship of the historical baseline. No weights, CT data, generated predictions or unrelated team files are included.
