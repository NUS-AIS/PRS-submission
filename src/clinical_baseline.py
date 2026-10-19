"""Clinical-only baselines on the fixed split + EDA figures.

Outputs: figures/eda_*.png, figures/clinical_cm.png, results/clinical_baseline.json
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import BINARY, CATEGORICAL, CLASSES, COLORS, FIG, NUMERIC, RESULTS, SHORT, SPLIT_CSV, load_clinical

plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#8A8F98", "axes.labelcolor": "#333",
                     "xtick.color": "#555", "ytick.color": "#555"})
INK = "#1E2433"
FIG.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)

df = load_clinical().join(pd.read_csv(SPLIT_CSV, index_col=0)["split"])
y = df["label"].values


# ---------------------------------------------------------------- EDA figures
def eda_class_and_missing():
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3.2), gridspec_kw={"width_ratios": [1.1, 1]})
    counts = df["Diagnosis_Class"].value_counts().reindex(CLASSES)
    bars = a.bar([SHORT[c] for c in CLASSES], counts.values, color=[COLORS[c] for c in CLASSES], width=0.6)
    for r, v in zip(bars, counts.values):
        a.text(r.get_x() + r.get_width() / 2, v + 4, f"{v}", ha="center", color=INK, fontweight="bold")
    a.set_title("CT scans per class (n = 569)", color=INK, loc="left", fontsize=12, fontweight="bold")
    a.set_ylim(0, 245)
    a.yaxis.grid(True, color="#E5E7EB")
    a.set_axisbelow(True)

    miss = df[NUMERIC].isna().sum().sort_values()
    b.barh(miss.index, miss.values, color="#8AA0B8", height=0.5)
    for i, v in enumerate(miss.values):
        b.text(v + 0.6, i, f"{v} ({v / len(df):.1%})", va="center", color=INK)
    b.set_title("Missing values ('/') per field", color=INK, loc="left", fontsize=12, fontweight="bold")
    b.set_xlim(0, 45)
    fig.tight_layout()
    fig.savefig(FIG / "eda_class_missing.png", dpi=200)
    plt.close(fig)


def eda_prevalence():
    feats = ["AIDS", "Renal dysfunction", "(1,3)-β-D-Glucan (G)", "Aspergillus Antigen (GM)", "Solid Tumor",
             "Diabetes", "Immunosuppressants"]
    prev = df.groupby("Diagnosis_Class")[feats].mean().reindex(CLASSES) * 100
    fig, ax = plt.subplots(figsize=(9, 3.4))
    x = np.arange(len(feats))
    w = 0.26
    for i, c in enumerate(CLASSES):
        ax.bar(x + (i - 1) * w, prev.loc[c].values, w - 0.02, color=COLORS[c], label=SHORT[c])
    labels = ["AIDS", "Renal\ndysfunction", "G test +", "GM antigen +", "Solid\ntumour", "Diabetes",
              "Immuno-\nsuppressants"]
    ax.set_xticks(x, labels)
    ax.set_ylabel("% positive within class")
    ax.yaxis.grid(True, color="#E5E7EB")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.set_ylim(0, 40)
    fig.tight_layout()
    fig.savefig(FIG / "eda_prevalence.png", dpi=200)
    plt.close(fig)
    return prev.round(1)


eda_class_and_missing()
prevalence = eda_prevalence()


# ---------------------------------------------------------------- models
MODELS = {
    "Logistic regression": lambda s: LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0),
    "Random forest": lambda s: RandomForestClassifier(n_estimators=500, min_samples_leaf=3,
                                                      class_weight="balanced", random_state=s),
    "LightGBM": lambda s: LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15,
                                         min_child_samples=10, class_weight="balanced",
                                         random_state=s, verbose=-1),
}


def metrics(y_true, y_pred):
    return {"macro_f1": f1_score(y_true, y_pred, average="macro"),
            "balanced_acc": balanced_accuracy_score(y_true, y_pred),
            "recall_per_class": recall_score(y_true, y_pred, average=None).tolist()}


def fit_eval(name, feats, seed, tr, ev):
    # imputer / scaler / encoder live inside the pipeline, so they are fitted on the training rows only
    num = [f for f in NUMERIC if f in feats]
    pre = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), num),
        ("bin", "passthrough", [f for f in BINARY if f in feats]),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])
    pipe = Pipeline([("pre", pre), ("clf", MODELS[name](seed))])
    pipe.fit(df.loc[tr, feats], y[tr])
    return pipe.predict(df.loc[ev, feats])


ALL = NUMERIC + BINARY + CATEGORICAL
NO_FUNGAL_MARKERS = [f for f in ALL if f not in ("(1,3)-β-D-Glucan (G)", "Aspergillus Antigen (GM)")]
tr = (df["split"] == "train").values
va = (df["split"] == "val").values
te = (df["split"] == "test").values
trva = tr | va
SEEDS = [0, 1, 2]

results = {"split_sizes": df["split"].value_counts().to_dict(), "prevalence_pct": prevalence.to_dict(),
           "fixed_split": {}, "cv5_trainval": {}}

for feat_name, feats in [("all", ALL), ("no_G_GM", NO_FUNGAL_MARKERS)]:
    for name in MODELS:
        key = f"{name} | {feat_name}"
        # fixed split: train -> val and train -> test, mean ± sd over 3 seeds
        runs = {"val": [], "test": []}
        for s in SEEDS:
            runs["val"].append(metrics(y[va], fit_eval(name, feats, s, tr, va)))
            runs["test"].append(metrics(y[te], fit_eval(name, feats, s, tr, te)))
        results["fixed_split"][key] = {
            part: {m: [float(np.mean([r[m] for r in rs])), float(np.std([r[m] for r in rs]))]
                   for m in ("macro_f1", "balanced_acc")} | {
                      "recall_per_class": np.mean([r["recall_per_class"] for r in rs], axis=0).tolist()}
            for part, rs in runs.items()}
        # 5-fold group CV on train+val (test untouched) for a more stable estimate
        cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
        idx = np.where(trva)[0]
        f1s = []
        for a, b in cv.split(idx, y[idx], df["group"].values[idx]):
            m_tr = np.zeros(len(df), bool); m_tr[idx[a]] = True
            m_ev = np.zeros(len(df), bool); m_ev[idx[b]] = True
            f1s.append(f1_score(y[m_ev], fit_eval(name, feats, 0, m_tr, m_ev), average="macro"))
        results["cv5_trainval"][key] = [float(np.mean(f1s)), float(np.std(f1s))]
        fs = results["fixed_split"][key]
        print(f"{key:40s} val F1 {fs['val']['macro_f1'][0]:.3f}  test F1 {fs['test']['macro_f1'][0]:.3f}±"
              f"{fs['test']['macro_f1'][1]:.3f}  bal-acc {fs['test']['balanced_acc'][0]:.3f}  "
              f"CV5 F1 {np.mean(f1s):.3f}±{np.std(f1s):.3f}")

# model chosen on validation macro F1 (all features); its test confusion matrix
best = max(MODELS, key=lambda n: results["fixed_split"][f"{n} | all"]["val"]["macro_f1"][0])
pred = fit_eval(best, ALL, 0, tr, te)
cm = confusion_matrix(y[te], pred, labels=[0, 1, 2])
results["best_on_val"] = best
results["best_test_cm_seed0"] = cm.tolist()
print("best on val:", best, "\n", cm)

fig, ax = plt.subplots(figsize=(4.4, 3.8))
norm = cm / cm.sum(axis=1, keepdims=True)
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
ax.set_title(f"Clinical-only {best}\ntest set (n = {te.sum()})", color=INK, fontsize=11, loc="left")
for s in ax.spines.values():
    s.set_visible(False)
fig.tight_layout()
fig.savefig(FIG / "clinical_cm.png", dpi=200)
plt.close(fig)

(RESULTS / "clinical_baseline.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
