# PRS_project · Group 26

Multimodal pulmonary infection classification: chest CT + clinical information → Aspergillus / other fungi / non-fungal. The dataset is PAC569 (NGDC OMIX014539, 569 cases).

## Branches

| Branch | Contents |
|---|---|
| `main` | Initial empty repository |
| `baseline` | Data processing pipeline, baseline models, freezing experiments, and first presentation materials |

To check out the branch:

```
git fetch origin
git switch baseline
```

## Repository Contents

| Path | Contents |
|---|---|
| `src/` | All code: extraction, preprocessing, splitting, training, Grad-CAM, plotting, and presentation and report generation |
| `web/` | PULMO AI interface for training results and case inference |
| `PULMO_UI.md` | Instructions for launching the local interface, CT upload formats, and inference |
| `data/splits.csv` | Fixed training / validation / test split (grouped by patient, seed 42); **do not regenerate the split** |
| `data/raw/OMIX014539-08.csv` | Clinical data table (original file, 28 KB) |
| `results/` | All results in JSON / CSV format |
| `figures/` | Figures used in the presentation and reports |
| `script/` | Speaker script source files (v1–v4) and prepared Q&A |
| `template/base.pptx` | Template used to generate the presentation |
| `Group 26_..._First Presentation.pptx` | First presentation (14 slides, with the v4 script in the speaker notes) |
| `Group 26_Speaker Script_v4 final 15-min (EN-ZH).md` | Final speaker script (15 minutes, bilingual English and Chinese); v1 is strictly timed, while v3 is an untimed reference version |
| `Frozen vs Fine-tuned Backbone.md` | Comparative experiment report on frozen backbone vs full fine-tuning |

## Large Files Excluded from Git

| Files | Size | How to obtain them |
|---|---|---|
| Raw CT scans (3 ZIP files) | 13 GB | Download separately; see step 2 below |
| Preprocessed slices `data/processed/*.npy` | Approximately 1.3 GB | Download `processed_npy.zip` from GitHub **Releases → `baseline-v1`** and extract it to `data/processed/` |
| Model weights `runs/*.pt` | Approximately 520 MB | Download `models.zip` from the same Release and extract it to `runs/` |

Download using the gh command-line tool:

```
gh release download baseline-v1 -R NUS-AIS/PRS_project
```

**Once you have `data/processed/`, you can train directly without the raw CT scans.** Raw CT scans are only needed when modifying the preprocessing code.

## Current Results (Local Reproduction in October 2026, Untuned Baselines)

The scores below correspond to the current `results/` and `figures/`, using the original fixed split and models retrained on an RTX 5070 Laptop GPU. The original first presentation materials have not been regenerated, so their scores may differ. Model weights in the `baseline-v1` Release remain the historical versions; the Release was not updated in this reproduction. To obtain weights matching the current results, retrain the models. Do not treat the historical weights and these metrics as outputs from the same run.

Test macro-F1 (random guessing: approximately 0.33):

| Model | Result |
|---|---|
| Clinical only (random forest, 5-fold cross-validation) | 0.569 ± 0.035 |
| CT only (ResNet-18, 3 seeds) | **0.595 ± 0.054** |
| CT + clinical fusion (3 seeds) | 0.593 ± 0.045 |
| CT only, frozen backbone | 0.501 ± 0.012 (underfitting; see `Frozen vs Fine-tuned Backbone.md`) |

Notes:
- Fusion has not yet outperformed CT alone.
- Grad-CAM shows that the model focuses on the mediastinal region rather than the lesions. The next step is to mask out regions outside the lungs.
- Future comparisons should use only the validation set or cross-validation; **reserve the test set for final evaluation**.

## Environment

Run `pip install -r requirements.txt`. Install PyTorch from pytorch.org according to your CUDA version. The development environment uses Python 3.12 and an RTX 4060 Laptop GPU (8 GB VRAM).

## Reproduction Steps

If you obtained `data/processed/` from the Release, you can start directly at step 5.

1. **Install dependencies:** See "Environment" above.
2. **Download raw CT scans:** Download `OMIX014539-03/04/05.zip` from https://ngdc.cncb.ac.cn/omix/release/OMIX014539 and place them in `data/raw/`. FTP is recommended (host: `download.cncb.ac.cn`, path: `/OMIX/OMIX014539/`). Alternatively, use `curl -C - -O https://download.cncb.ac.cn/OMIX/OMIX014539/OMIX014539-03.zip`.
3. **Extract:** Run `python src/extract_ct.py`. It extracts the scans to `data/ct/` and prints the dimensions of each scan.
4. **Preprocess:** Run `python src/ct_preprocess.py 8` to generate `data/processed/`. This takes approximately 4 minutes with 8 processes.
5. **Clinical baseline:** Run `python src/clinical_baseline.py`.
6. **Train:** Run `bash src/run_ct_baselines.sh`. It trains the CT-only and fusion models with 3 seeds each, then automatically runs Grad-CAM, generates figures, and builds the presentation. The entire process takes approximately 25 minutes. For a single run, use `python src/train_ct.py --mode ct --seed 0`; add `--freeze --lr 1e-3` to freeze the backbone.
7. **Reports:** Run `python src/report_freeze.py` to generate the freezing comparison report; run `python src/build_deck.py` to regenerate the presentation and speaker script.

## Local Inference Interface

Install the baseline dependencies, a compatible PyTorch version, and the UI dependencies with `pip install -r requirements-ui.txt`. After preparing the weights in `runs/` that match the current results, launch the server from the repository root:

```sh
python -m uvicorn pulmo_server:app --app-dir src --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765 . The interface supports uploading 3D CT scans in `.nii` / `.nii.gz` format, CT-only / clinical fusion inference, slice browsing, and Grad-CAM. The validation-set demo also requires `data/processed/`. See [PULMO_UI.md](PULMO_UI.md) for details. For research use only.

## Contribution Guidelines

- Do not regenerate the data split; everyone must use `data/splits.csv`.
- If preprocessing changes (for example, lung masking), rerun the baselines before comparing results.
- Compare configurations using only the validation set or cross-validation. Use the test set only once for each final configuration.
- Keep large files out of Git; update the Release when needed.
