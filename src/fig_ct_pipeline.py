"""Figure: what the CT preprocessing does to one case -> figures/ct_pipeline.png

Usage: python fig_ct_pipeline.py [path/to/CaseXXX.nii.gz]   (default: Case071, Aspergillus)
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from common import CT_DIR, FIG
from ct_preprocess import K, process

path = Path(sys.argv[1]) if len(sys.argv) > 1 else CT_DIR / "Case071.nii.gz"
stack, d = process(path, return_debug=True)
hu, win, mask, centres = d["hu"], d["win"], d["mask"], d["centres"]
z = int(centres[K // 2])


def show(ax, a):  # RAS (x, y) -> radiological display
    ax.imshow(np.flipud(a.T), cmap="gray")
    ax.axis("off")


plt.rcParams.update({"font.family": "Arial", "font.size": 11})
INK = "#1E2433"
fig = plt.figure(figsize=(14.5, 3.3))
gs = fig.add_gridspec(2, 12, width_ratios=[2, 2, 2, 0.25] + [1] * 8, wspace=0.04, hspace=0.04,
                      left=0.005, right=0.995, top=0.8, bottom=0.01)
la = [fig.add_subplot(gs[:, i]) for i in range(3)]
ra = np.array([[fig.add_subplot(gs[r, 4 + c]) for c in range(8)] for r in range(2)])

ax = la[0]
show(ax, np.clip(hu[:, :, z], -1024, 3000))
ax.set_title(f"1. Raw CT\n{hu.shape[0]}×{hu.shape[1]}×{hu.shape[2]}, {d['zooms'][2]:.0f} mm", color=INK, fontsize=10.5)

ax = la[1]
show(ax, win[:, :, z])
ax.set_title("2. Lung window\nHU −1350…150", color=INK, fontsize=10.5)

ax = la[2]
show(ax, win[:, :, z])
ov = np.ma.masked_where(~mask[:, :, z], np.ones_like(win[:, :, z]))
ax.imshow(np.flipud(ov.T), cmap="autumn", alpha=0.35)
x0, y0, s = d["box"]
H = hu.shape[1]
ax.add_patch(Rectangle((x0, H - y0 - s), s, s, fill=False, ec="#0F9AA5", lw=2))
ax.set_title("3. Lung mask\n+ crop box", color=INK, fontsize=10.5)

show_idx = np.arange(K)
for i, k in enumerate(show_idx):
    ax = ra[i // 8, i % 8]
    ax.imshow(stack[k, 1], cmap="gray")
    ax.axis("off")
    ax.text(4, 20, f"z{centres[k]}", color="w", fontsize=7.5)
fig.text(0.68, 0.86, f"4. {K} slices evenly over the lungs; 3 adjacent slices → RGB, 224×224",
         ha="center", color=INK, fontsize=10.5)
fig.savefig(FIG / "ct_pipeline.png", dpi=180, bbox_inches="tight")
print("saved; centre slice", z, "crop", d["box"])

# centre sampled slice on its own, for the UI mock-up
plt.imsave(FIG / "ui_slice.png", stack[K // 2, 1], cmap="gray")
