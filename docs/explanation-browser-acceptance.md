# D: explanation workflow acceptance record

Date: 2026-10-28. Contributor: `hanjingmu2004-coder`.

## Environment

Windows, Python 3.12 baseline environment, CUDA GPU inference, in-app Chromium browser.
Submission repository served at `http://127.0.0.1:8766/#inference` to avoid replacing the original project's service on port 8765.
Existing local seed-0 CT/fusion checkpoints and validation samples were copied into ignored asset directories; none are included in this commit.

## Reproducible browser procedure and observed results

| Step | Operation | Required result | Observed |
|---|---|---|---|
| 1 | Load validation case 004, choose CT-only seed 0, keep Compute Grad-CAM checked, run | CUDA completion, probabilities, diagnostics and 16 position buttons | Passed; displayed scores 32.3%, 20.8%, 46.9% |
| 2 | Click position 3 in gallery | Slider and main image select sampled position 3 | Passed; Slice 3 / 16 |
| 3 | Set opacity to 0.25, uncheck Grad-CAM display | Opacity reads 25%, original image is displayed; no new prediction | Passed; same result remains |
| 4 | Click Download explanation ZIP | Browser saves archive from the current run and position | Passed; actual downloaded archive inspected |
| 5 | Inspect ZIP | original.png, overlay.png, report.json; hashes match; selected position and opacity retained | Passed; position 3, opacity 0.25, SHA256 values matched both images |
| 6 | Uncheck Compute Grad-CAM | Previous result and gallery clear, downloads disable | Passed; disabled ZIP button confirmed |
| 7 | Run again without explanation | Same scores; no heatmap; explanation/opacity disabled | Passed; same displayed three scores; explicit not-requested message |
| 8 | Choose fusion seed 0, enable explanation, run | Fused predicted-logit explanation and clinical input summary | Passed |
| 9 | Change age 45 to 46 | Previous downloads disable and gallery becomes empty | Passed; disabled report and zero position buttons confirmed |
| 10 | Reload final page, load case 004 and fusion seed 0, run | Original case inputs restored; final version usable | Passed; displayed scores 8.9%, 15.8%, 75.3%, measured Grad-CAM time |
| 11 | Quickly select positions 1, 16, then 8 | Final selection and displayed image correspond to 8 | Passed; Slice 8 / 16 and position 8 selected |

Scores above are regression observations, not measures of diagnostic accuracy. Measured Grad-CAM time varies with GPU warm-up and is not a latency guarantee. ZIP always includes both original and overlay when a heatmap exists, even if the on-screen overlay switch is off. Without a heatmap the bundle omits overlay.png explicitly.

## Automated coverage

```sh
python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_explanation_request.cjs
node --check web/modules/explanation.js
node --check web/modules/explanation-request.js
```

The Python suite covers actual available model integration plus deterministic unit/HTTP tests. The Node tests simulate out-of-order response completion, case invalidation during response-body reading, and current server errors. The ZIP concurrency regression replaces the cached run during rendering and expects a stale-explanation error, avoiding mixed-run archives.

The browser table records performed interaction tests, not an unattended browser runner. Download verification includes opening the real ZIP saved by the browser, not just observing a success toast. Raw CT, screenshots containing CT data and downloaded reports are not committed as test fixtures.

## Known boundaries

- This is a local research application; no deployment, browser matrix or load testing was performed.
- UI case invalidation cancels outstanding image/download requests. Server run IDs independently reject replaced prediction exports.
- Thumbnails use the same cached explanation endpoint as the main view; opacity and gallery actions do not recompute Grad-CAM.
- The viewer displays cropped model inputs and attention, not original-volume segmentation.
