# PULMO AI local interface

In VS Code, choose **Terminal → Run Task → PRS: Start Pulmo AI**, then open http://127.0.0.1:8765. Keep the terminal running; Ctrl+C stops the server. Alternatively run `powershell -ExecutionPolicy Bypass -File .\start_pulmo.ps1`.

The interface reads actual local baseline checkpoints in `runs/` and matching metrics in `results/`. It supports CT-only and multimodal fusion, three seeds each. It preserves `data/splits.csv` and fits clinical preprocessing on training rows only. Do not replace checkpoints without replacing their corresponding results and preserving the clinical dataset/split used during training.

Upload a 3D `.nii` or `.nii.gz` chest CT in Hounsfield units (maximum 200 MB and 64 million voxels), or load a validation demo. Raw DICOM folders and JPG screenshots are not supported. Uploaded files are processed locally and temporary files are deleted afterwards; up to eight preprocessed cases remain in memory until eviction or server shutdown.

Select a model and click **Run Inference**. Fusion requires the actual 11 clinical fields: age, sex, seven binary fields, lymphocyte count and D-dimer. Use the original dataset's laboratory units. Missing numeric values use training-set medians; binary fields require known values. CT-only ignores these inputs.

The viewer shows the 16 cropped model-input positions, not all original slices. Grad-CAM is computed from the predicted class logit back to the CT branch's final convolutional features, after fusion when using a fusion model. It is an explanation, not a segmentation. Scores are uncalibrated; severity and validated uncertainty estimates are not implemented. Research use only.

For another environment install `requirements.txt`, compatible PyTorch/torchvision and `requirements-ui.txt`, then run `python -m uvicorn pulmo_server:app --app-dir src --host 127.0.0.1 --port 8765` from the repository. Integration checks: `python -m unittest discover -s tests -p test_pulmo.py` (requires local baseline assets).
