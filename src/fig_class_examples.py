"""Two example slices per class, to show how similar the three classes look -> figures/class_examples.png"""
import matplotlib.pyplot as plt

from common import CLASSES, COLORS, CT_DIR, FIG
from ct_preprocess import process

# (case, sampled-slice index) picked by eye from a random contact sheet: slices with visible abnormality
PICKS = {"Aspergillus": [(77, 6), (447, 10)],
         "Non-Aspergillus Fungi": [(437, 6), (252, 6)],
         "Non-Fungi": [(533, 10), (521, 6)]}
TITLE = {"Aspergillus": "Aspergillus", "Non-Aspergillus Fungi": "Non-Aspergillus fungi", "Non-Fungi": "Non-fungal"}

plt.rcParams.update({"font.family": "Arial", "font.size": 11})
fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.0))
for col, cls in enumerate(CLASSES):
    for row, (cid, k) in enumerate(PICKS[cls]):
        ax = axes[row, col]
        ax.imshow(process(CT_DIR / f"Case{cid:03d}.nii.gz")[k, 1], cmap="gray")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(COLORS[cls])
            s.set_linewidth(2.5)
        ax.text(6, 216, f"Case {cid:03d}", color="white", fontsize=8.5)
        if row == 0:
            ax.set_title(TITLE[cls], color=COLORS[cls], fontweight="bold")
fig.tight_layout(pad=0.4)
fig.savefig(FIG / "class_examples.png", dpi=200)
