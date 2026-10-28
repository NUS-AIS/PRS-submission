# Explanation Review browser acceptance

Date: 2026-10-28. Local submission application: `http://127.0.0.1:8766/#inference`.

## Tested environment

- Windows desktop, in-app Chromium browser.
- Existing local seed-0 checkpoint and validation case 004.
- GPU inference through the existing prediction workflow.
- Data, weights, downloaded ZIPs and screenshots remain outside Git.

## Performed checks

| Action | Observed result |
|---|---|
| Reload the application after loading the new backend | Explanation Review panel appeared beneath inference |
| Load validation case 004 and run inference | Prediction completed and enabled review actions |
| Enter `1,4,8,16` and refresh statistics | Four rows appeared, with denominator 16 and threshold 0.5 |
| Sort by attention mass | Order became 4, 8, 1, 16 |
| Export full review ZIP | Browser saved a ZIP from the current run |
| Select that downloaded ZIP in the verifier | File selection enabled verification |
| Verify archive integrity | UI reported 13 verified files and the current run identifier |

## Numerical observations

These are regression observations, not model-accuracy measurements.

| Position | Mean attention | Maximum | Above threshold | Selected mass share | Entropy |
|---|---:|---:|---:|---:|---:|
| 1 | 0.2053 | 0.3804 | 0.0% | 24.3% | 0.9869 |
| 4 | 0.3056 | 1.0000 | 24.6% | 36.2% | 0.9673 |
| 8 | 0.2630 | 0.5560 | 3.0% | 31.1% | 0.9867 |
| 16 | 0.0713 | 0.2970 | 0.0% | 8.4% | 0.9323 |

Rounded percentages may differ slightly from sums calculated using full precision. The selected mass denominator includes only the four selected positions.

## Automated validation

The final full run passed 121 Python tests with no skips and 12 Node tests. JavaScript syntax and Git whitespace checks also passed. The Python suite includes actual locally available model integration tests and synthetic tests that do not need model assets.

Archive tests cover byte modifications, changed sizes, added or missing members, changed run IDs, unsafe paths, duplicate entries, symlinks, oversized data, invalid JSON, non-finite numbers, unsupported versions and inconsistent image selections.

The browser acceptance table records manual tool-driven interaction. It is not an unattended Playwright test suite. HTML was checked for escaped content, a restrictive content policy and decodable image assets; cross-browser printing and a browser matrix were not tested.
