"""Grad-CAM on the trained CT model -> figures/gradcam.png

For one correctly classified test case per class, shows the 4 slices with the most
Grad-CAM mass (CAM normalised over the whole case, so slices are comparable).
Usage: python gradcam.py runs/fusion_aug-basic_seed0.pt
"""
import json
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

sys.argv += [] if len(sys.argv) > 1 else ["runs/ct_aug-basic_seed0.pt"]
ckpt = sys.argv[1]
mode = "fusion" if "fusion" in ckpt else "ct"
sys.argv = [sys.argv[0], "--mode", mode]  # reuse train_ct's data + model definitions (training is under __main__)
import train_ct as T  # noqa: E402

from common import CLASSES, COLORS, FIG, RESULTS, ROOT, SHORT  # noqa: E402
from ct_preprocess import K  # noqa: E402

model = T.model
model.load_state_dict(torch.load(ROOT / ckpt))
model.eval()
acts, grads = {}, {}
layer = model.bb.layer4
layer.register_forward_hook(lambda m, i, o: acts.__setitem__("a", o))
layer.register_full_backward_hook(lambda m, gi, go: grads.__setitem__("g", go[0]))

probs = pd.read_csv(RESULTS / f"{mode}_aug-basic_seed0_test_probs.csv", index_col=0)
probs["pred"] = probs[["p0", "p1", "p2"]].values.argmax(1)
probs["conf"] = probs[["p0", "p1", "p2"]].values.max(1)
picks = [probs[(probs.y == c) & (probs.pred == c)].sort_values("conf").index[-1] for c in range(3)]

plt.rcParams.update({"font.family": "Arial", "font.size": 10})
fig, axes = plt.subplots(3, 4, figsize=(8.4, 6.6))
for row, cid in enumerate(picks):
    x = torch.from_numpy(np.load(T.PROC / f"Case{cid:03d}.npy"))[None]
    c = torch.from_numpy(T.clin.loc[cid].values)[None].to(T.dev)
    xin = T.prep(x).requires_grad_(False)
    logits = model(xin, c)
    cls = int(logits.argmax())
    model.zero_grad()
    logits[0, cls].backward()
    a, g = acts["a"].detach(), grads["g"].detach()  # [K, 512, 7, 7]
    cam = F.relu((g.mean((2, 3), keepdim=True) * a).sum(1))  # [K, 7, 7]
    cam = F.interpolate(cam[:, None], size=224, mode="bilinear", align_corners=False)[:, 0]
    cam = (cam / cam.max()).cpu().numpy()
    top = np.argsort(cam.sum((1, 2)))[::-1][:4]
    for j, k in enumerate(sorted(top)):
        ax = axes[row, j]
        ax.imshow(x[0, k, 1], cmap="gray")
        ax.imshow(cam[k], cmap="jet", alpha=0.35 * (cam[k] > 0.2), vmin=0, vmax=1)
        ax.set_xticks([])
        ax.set_yticks([])
        if j == 0:
            name = CLASSES[cls]
            ax.set_ylabel(f"Case {cid:03d}\n{SHORT[name]}\np = {probs.loc[cid, f'p{cls}']:.2f}",
                          color=COLORS[name], fontweight="bold")
        ax.set_title(f"slice {k + 1}/{K}", fontsize=9, color="#555")
fig.tight_layout()
fig.savefig(FIG / "gradcam.png", dpi=180)
(RESULTS / "gradcam_cases.json").write_text(json.dumps([int(c) for c in picks]))
print("cases:", picks)
