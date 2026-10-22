"""Confusion matrix of the fusion model (seed 0) on the test set -> figures/fusion_cm.png"""
import json

import matplotlib.pyplot as plt
import numpy as np

from common import CLASSES, FIG, RESULTS, SHORT

r = json.loads((RESULTS / "fusion_aug-basic_seed0.json").read_text())
cm = np.array(r["test_cm"])
norm = cm / cm.sum(axis=1, keepdims=True)
INK = "#1E2433"
plt.rcParams.update({"font.family": "Arial", "font.size": 11})
fig, ax = plt.subplots(figsize=(4.4, 3.8))
ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
for i in range(3):
    for j in range(3):
        ax.text(j, i, f"{cm[i, j]}\n{norm[i, j]:.0%}", ha="center", va="center",
                color="white" if norm[i, j] > 0.55 else INK, fontsize=11)
ticks = [SHORT[c] for c in CLASSES]
ax.set_xticks(range(3), ticks, rotation=15)
ax.set_yticks(range(3), ticks)
ax.set_xlabel("Predicted")
ax.set_ylabel("True")
ax.set_title(f"CT + clinical fusion (seed 0)\ntest set (n = {cm.sum()}), macro-F1 {r['test_macro_f1']:.3f}",
             color=INK, fontsize=11, loc="left")
for s in ax.spines.values():
    s.set_visible(False)
fig.tight_layout()
fig.savefig(FIG / "fusion_cm.png", dpi=200)

# ---- training curves: mean ± SD over 3 seeds, one panel per measure (no dual axis)
MODEL_COLORS = {"ct": "#3466A8", "fusion": "#D1495B"}  # validated with dataviz validate_palette.js
MODEL_NAMES = {"ct": "CT only", "fusion": "CT + clinical"}
fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.45))
for mode in ("ct", "fusion"):
    hs = [json.loads((RESULTS / f"{mode}_aug-basic_seed{s}.json").read_text())["history"] for s in range(3)]
    ep = np.arange(1, len(hs[0]) + 1)
    for ax, key in zip(axes, ("train_loss", "val_f1")):
        v = np.array([[h[key] for h in run] for run in hs])
        m, sd = v.mean(0), v.std(0)
        ax.plot(ep, m, color=MODEL_COLORS[mode], lw=2, label=MODEL_NAMES[mode])
        ax.fill_between(ep, m - sd, m + sd, color=MODEL_COLORS[mode], alpha=0.15, lw=0)
for ax, title in zip(axes, ("Training loss", "Validation macro-F1")):
    ax.set_title(title, color=INK, fontsize=11, loc="left", fontweight="bold")
    ax.yaxis.grid(True, color="#E5E7EB")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
axes[1].axhline(1 / 3, color="#8A8F98", lw=1, ls="--")
axes[1].text(25, 1 / 3 + 0.01, "chance", color="#8A8F98", ha="right", fontsize=9)
for ax in axes:
    ax.set_xlabel("Epoch")
axes[0].legend(frameon=False)
fig.tight_layout()
fig.savefig(FIG / "training_curves.png", dpi=200)
