"""CT volume -> fixed stack of 2.5D slices for a 2D ImageNet backbone.

Per case: reorient to RAS -> clip to lung window (HU -1350..150) and scale to 0..1
-> threshold lung mask -> crop to lung bounding box -> sample K axial positions
evenly over the lung z-range -> each sample = (slice-1, slice, slice+1) as 3
channels -> resize to SIZE x SIZE. Saved as uint8 array [K, 3, SIZE, SIZE].

Usage: python ct_preprocess.py            (all cases under data/ct)
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import nibabel as nib
import numpy as np
from scipy import ndimage

from common import CT_DIR, ROOT

OUT = ROOT / "data" / "processed"
K = 16
SIZE = 224
HU_MIN, HU_MAX = -1350, 150  # lung window: level -600, width 1500
PIPELINE_VERSION = 'lung-window-crop-2.5d-v1'  # bump if any step below changes the model input


def load_ras(path):
    img = nib.as_closest_canonical(nib.load(str(path)))
    return img.get_fdata(dtype=np.float32), img.header.get_zooms()


def lung_mask(hu):
    """Air inside the body = lungs. Drop air connected to the slice border (outside the body)."""
    air = hu < -320
    mask = np.zeros_like(air)
    for z in range(air.shape[2]):
        lab, n = ndimage.label(air[:, :, z])
        if n == 0:
            continue
        border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        mask[:, :, z] = np.isin(lab, border, invert=True) & (lab > 0)
    mask = ndimage.binary_opening(mask, iterations=2)
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    keep = np.argsort(sizes)[::-1][:2] + 1  # two largest 3D components = left + right lung
    keep = keep[sizes[keep - 1] > 0.1 * sizes.max()]
    return np.isin(lab, keep)


def process(path, return_debug=False):
    hu, zooms = load_ras(path)
    win = (np.clip(hu, HU_MIN, HU_MAX) - HU_MIN) / (HU_MAX - HU_MIN)
    m = lung_mask(hu)
    area = m.sum(axis=(0, 1))
    zs = np.where(area > 0.05 * area.max())[0] if area.max() > 0 else np.arange(hu.shape[2])
    xs, ys = np.where(m.any(axis=2)) if m.any() else (np.arange(hu.shape[0]), np.arange(hu.shape[1]))
    # A fully consolidated lung is not "air", so the lung mask can miss it (12 cases did in the first
    # version). Mirror the lung box about the body's left-right midline so both sides are always kept.
    zmid = (zs.min() + zs.max()) // 2
    body_x = np.where((hu[:, :, zmid] > -500).any(axis=1))[0]
    mid = np.median(np.where(hu[:, :, zmid] > -500)[0]) if body_x.size else hu.shape[0] / 2
    pad = 10
    x0 = max(int(min(xs.min(), 2 * mid - xs.max())) - pad, 0)
    x1 = min(int(max(xs.max(), 2 * mid - xs.min())) + pad, hu.shape[0])
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, hu.shape[1])
    side = min(max(x1 - x0, y1 - y0), hu.shape[0], hu.shape[1])  # square crop keeps the aspect ratio
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    x0 = int(np.clip(cx - side // 2, 0, hu.shape[0] - side))
    y0 = int(np.clip(cy - side // 2, 0, hu.shape[1] - side))
    crop = win[x0:x0 + side, y0:y0 + side]

    centres = np.linspace(zs.min(), zs.max(), K).round().astype(int)
    stack = np.empty((K, 3, SIZE, SIZE), np.uint8)
    for k, z in enumerate(centres):
        for c, dz in enumerate((-1, 0, 1)):
            zz = int(np.clip(z + dz, 0, hu.shape[2] - 1))
            sl = crop[:, :, zz]
            sl = ndimage.zoom(sl, (SIZE / sl.shape[0], SIZE / sl.shape[1]), order=1)
            # RAS array axes are (x, y); transpose + flip -> radiological display (anterior up)
            stack[k, c] = (np.flipud(sl.T) * 255).clip(0, 255).astype(np.uint8)
    if return_debug:
        return stack, dict(hu=hu, win=win, mask=m, centres=centres, box=(x0, y0, side), zooms=zooms)
    return stack


def summarize(debug):
    """Small JSON-ready view of process(..., return_debug=True); keeps none of the full volumes.

    Indices refer to the RAS-reoriented volume; sampled_slices are the K axial centres (0-based)."""
    x0, y0, side = debug['box']
    return dict(pipeline=PIPELINE_VERSION, window_hu=[HU_MIN, HU_MAX],
                ras_shape=[int(n) for n in debug['hu'].shape],
                ras_spacing_mm=[round(float(z), 4) for z in debug['zooms'][:3]],
                lung_mask_found=bool(debug['mask'].any()),
                crop=dict(x0=int(x0), y0=int(y0), side=int(side)),
                sampled_slices=[int(z) for z in debug['centres']],
                output_shape=[K, 3, SIZE, SIZE])


def _job(path):
    out = OUT / (path.name.replace(".nii.gz", ".npy"))
    if out.exists():
        return path.name, "skip"
    try:
        np.save(out, process(path))
        return path.name, "ok"
    except Exception as e:  # report and continue; failures are listed at the end
        return path.name, f"FAIL {e}"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(CT_DIR.glob("*.nii.gz"))
    print(len(files), "volumes")
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    fails = []
    with ProcessPoolExecutor(workers) as ex:
        for i, (name, status) in enumerate(ex.map(_job, files), 1):
            if status.startswith("FAIL"):
                fails.append((name, status))
            if i % 50 == 0:
                print(i, "done")
    print("failures:", fails)
