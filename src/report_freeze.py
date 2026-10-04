"""Frozen backbone vs full fine-tuning: figures + a Markdown report built from results/*.json.

Outputs: figures/freeze_scores.png, figures/freeze_curves.png, "Frozen vs Fine-tuned Backbone.md" (project root)
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import torch.nn as nn
from torchvision.models import resnet18

from common import CLASSES, FIG, RESULTS, ROOT, SHORT

SEEDS = [0, 1, 2]
CONFIGS = [  # key, label, mode, result-file suffix
    ("ct_ft", "CT only · fine-tuned", "ct", ""),
    ("ct_fz", "CT only · frozen", "ct", "_frozen-lr0.001"),
    ("fu_ft", "CT + clinical · fine-tuned", "fusion", ""),
    ("fu_fz", "CT + clinical · frozen", "fusion", "_frozen-lr0.001"),
]
ZH = {"ct_ft": "只用 CT · 全部微调", "ct_fz": "只用 CT · 冻结骨干",
      "fu_ft": "CT + 临床 · 全部微调", "fu_fz": "CT + 临床 · 冻结骨干"}
COLORS = {"ct": "#3466A8", "fusion": "#D1495B"}  # same validated pair as the baseline training curves
INK = "#1E2433"

runs = {k: [json.loads((RESULTS / f"{m}_aug-basic_seed{s}{suf}.json").read_text()) for s in SEEDS]
        for k, _, m, suf in CONFIGS}
clin = json.loads((RESULTS / "clinical_baseline.json").read_text(encoding="utf-8"))
rf_cv = clin["cv5_trainval"]["Random forest | all"][0]

# trainable parameters, counted from the same layer sizes as train_ct.Net
bb = resnet18()
bb.fc = nn.Identity()
n_bb = sum(p.numel() for p in bb.parameters())
n_head = {d: sum(p.numel() for p in nn.Sequential(nn.Linear(d, 128), nn.Linear(128, 3)).parameters())
          for d in (512, 576)}
n_clin = sum(p.numel() for p in nn.Sequential(nn.Linear(12, 64), nn.Linear(64, 64)).parameters())
trainable = {"ct_ft": n_bb + n_head[512], "ct_fz": n_head[512],
             "fu_ft": n_bb + n_head[576] + n_clin, "fu_fz": n_head[576] + n_clin}


def stat(k, f):
    v = np.array([f(r) for r in runs[k]], dtype=float)
    return v.mean(), v.std()


summary = {}
for k, *_ in CONFIGS:
    summary[k] = dict(
        val=stat(k, lambda r: r["best_val_f1"]),
        test=stat(k, lambda r: r["test_macro_f1"]),
        bal=stat(k, lambda r: r["test_balanced_acc"]),
        loss=stat(k, lambda r: r["history"][-1]["train_loss"]),
        best_ep=[max(r["history"], key=lambda h: h["val_f1"])["epoch"] + 1 for r in runs[k]],
        minutes=stat(k, lambda r: r["train_minutes"]),
        recall=np.mean([r["test_recall_per_class"] for r in runs[k]], axis=0),
        val_seeds=[r["best_val_f1"] for r in runs[k]], test_seeds=[r["test_macro_f1"] for r in runs[k]],
    )

plt.rcParams.update({"font.family": "Arial", "font.size": 10.5, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#8A8F98"})

# ---- figure 1: scores, bars = mean, dots = individual seeds
fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6), sharey=True)
for ax, metric, title in zip(axes, ("val", "test"), ("Validation macro-F1 (used for decisions)",
                                                      "Test macro-F1 (reference only)")):
    for i, (k, lab, m, suf) in enumerate(CONFIGS):
        frozen = "frozen" in lab
        mu = summary[k][metric][0]
        ax.bar(i, mu, width=0.62, color="white" if frozen else COLORS[m], edgecolor=COLORS[m], lw=1.6,
               hatch="///" if frozen else None)
        ax.scatter([i] * 3, summary[k][f"{metric}_seeds"], color=INK, s=14, zorder=3)
        top = max(mu, *summary[k][f"{metric}_seeds"])
        ax.text(i, top + 0.025, f"{mu:.3f}", ha="center", color=INK, fontsize=10, fontweight="bold")
    ax.axhline(1 / 3, color="#8A8F98", ls="--", lw=1, label="chance (0.33)")
    ax.axhline(rf_cv, color="#C46A0A", ls=":", lw=1.4, label=f"clinical-only RF, 5-fold CV ({rf_cv:.2f})")
    ax.set_xticks(range(4), ["CT only\nfine-tuned", "CT only\nfrozen", "CT + clinical\nfine-tuned",
                             "CT + clinical\nfrozen"], fontsize=9)
    ax.set_title(title, loc="left", color=INK, fontweight="bold", fontsize=11)
    ax.set_ylim(0, 0.8)
    ax.yaxis.grid(True, color="#E5E7EB")
    ax.set_axisbelow(True)
axes[0].set_ylabel("macro-F1")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower left", ncol=2, frameon=False, fontsize=8.5, bbox_to_anchor=(0.06, 0.0))
fig.text(0.99, 0.01, "bars = mean of 3 seeds · dots = each seed · hatched = frozen backbone", ha="right",
         fontsize=8.5, color="#555")
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(FIG / "freeze_scores.png", dpi=200)
plt.close(fig)

# ---- figure 2: training curves, one panel per measure (no dual axis)
fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4))
for k, lab, m, suf in CONFIGS:
    frozen = "frozen" in lab
    for ax, key in zip(axes, ("train_loss", "val_f1")):
        v = np.array([[h[key] for h in r["history"]] for r in runs[k]])
        ep = np.arange(1, v.shape[1] + 1)
        ax.plot(ep, v.mean(0), color=COLORS[m], lw=2, ls="--" if frozen else "-", label=lab)
        ax.fill_between(ep, v.mean(0) - v.std(0), v.mean(0) + v.std(0), color=COLORS[m], alpha=0.12, lw=0)
for ax, title in zip(axes, ("Training loss", "Validation macro-F1")):
    ax.set_title(title, loc="left", color=INK, fontweight="bold", fontsize=11)
    ax.set_xlabel("Epoch")
    ax.yaxis.grid(True, color="#E5E7EB")
    ax.set_axisbelow(True)
axes[1].axhline(1 / 3, color="#8A8F98", ls="--", lw=1)
axes[0].legend(frameon=False, fontsize=8.5)
fig.tight_layout()
fig.savefig(FIG / "freeze_curves.png", dpi=200)
plt.close(fig)

# ---- report
f3 = lambda t: f"{t[0]:.3f} ± {t[1]:.3f}"  # noqa: E731
rows = []
for k, lab, m, suf in CONFIGS:
    s = summary[k]
    rows.append(f"| {ZH[k]} | {trainable[k]:,} | **{f3(s['val'])}** | {f3(s['test'])} | {f3(s['bal'])} | "
                f"{s['loss'][0]:.2f} | {', '.join(map(str, s['best_ep']))} | {s['minutes'][0]:.1f} |")
rec_rows = [f"| {ZH[k]} | " + " | ".join(f"{100 * x:.0f}%" for x in summary[k]["recall"]) + " |"
            for k, *_ in CONFIGS]
d_ct = summary["ct_fz"]["val"][0] - summary["ct_ft"]["val"][0]
d_fu = summary["fu_fz"]["val"][0] - summary["fu_ft"]["val"][0]

md = f"""# 冻结骨干 vs 全部微调 —— 对比实验

**问题：** 把 ResNet-18 骨干全部冻结、只训练后面的层，能不能缓解基线的过拟合？

**结论：** 不能。全部冻结后模型反而**欠拟合**：训练 loss 降不下去，验证集 F1 明显下降（只用 CT 的模型 {d_ct:+.3f}，融合模型 {d_fu:+.3f}）。
ImageNet 学到的特征不能直接用在 CT 上，骨干至少要做部分微调。

## 实验设置

两组只差「骨干是否冻结」和学习率，其余完全相同。

| | 全部微调（基线） | 冻结骨干 |
|---|---|---|
| ResNet-18 骨干 | 全部参与训练 | 全部冻结，BatchNorm 统计量也固定 |
| 训练的部分 | 骨干 + 分类头（+ 临床分支） | 只训练分类头（+ 临床分支） |
| 学习率 | 1e-4 | 1e-3（只训练分类头时通常用更大的学习率） |
| 其他 | 25 个 epoch · AdamW · 类别加权损失 · 基础增强（旋转 ±10°、平移 ±5%） · 同一数据划分 · 种子 0/1/2 | 同左 |

**选模型的规则不变：** 每个 epoch 看验证集 macro-F1，保留最好的那一轮；比较不同方案**只看验证集**，测试集分数只作参考。

## 结果总表（3 个种子的均值 ± 标准差）

| 配置 | 训练参数量 | 验证集 macro-F1 | 测试集 macro-F1 | 测试集平衡准确率 | 最后一轮训练 loss | 最佳 epoch（3 个种子） | 每次耗时（分钟） |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

对照：随机猜的 macro-F1 是 0.333；只用临床数据的随机森林，5 折交叉验证约 {rf_cv:.3f}。

![各配置的验证集和测试集分数](figures/freeze_scores.png)

## 训练过程

![训练 loss 和验证集 F1 随 epoch 的变化](figures/freeze_curves.png)

- **实线（全部微调）：** 训练 loss 很快降到接近 0，验证集 F1 却停在 0.6 左右，说明在**过拟合**。
- **虚线（冻结骨干）：** 训练 loss 只降到 {summary['ct_fz']['loss'][0]:.2f}（只用 CT）和 {summary['fu_fz']['loss'][0]:.2f}（融合），连训练集都学不好，说明是**欠拟合**。

## 各类别召回率（测试集，3 个种子平均）

| 配置 | {SHORT[CLASSES[0]]} | {SHORT[CLASSES[1]]} | {SHORT[CLASSES[2]]} |
|---|---|---|---|
{chr(10).join(rec_rows)}

只用 CT 的模型冻结之后，曲霉的召回率从 {100*summary['ct_ft']['recall'][0]:.0f}% 降到 {100*summary['ct_fz']['recall'][0]:.0f}%，其他真菌从 {100*summary['ct_ft']['recall'][1]:.0f}% 降到 {100*summary['ct_fz']['recall'][1]:.0f}%，非真菌只从 {100*summary['ct_ft']['recall'][2]:.0f}% 降到 {100*summary['ct_fz']['recall'][2]:.0f}%。也就是说，冻住的特征最分不清的是两类真菌。

## 怎么理解

1. **两个极端都不好。** 全部微调约 1,124 万个参数，在约 400 个训练病人上会死记训练集；全部冻结只训练约 6.6 万个参数，又学不到区分这三类 CT 所需的特征。合适的做法在两者之间。
2. **冻结后，融合比只用 CT 高。** 因为临床分支仍在训练。冻结版融合的验证集 F1（{summary['fu_fz']['val'][0]:.3f}）和只用临床的随机森林（{rf_cv:.3f}）差不多，说明这时候主要是临床数据在起作用，冻住的 CT 特征贡献很少。
3. **冻结的好处只有速度。** 每次训练从约 {summary['ct_ft']['minutes'][0]:.1f} 分钟降到约 {summary['ct_fz']['minutes'][0]:.1f} 分钟，但代价是准确率明显下降。

## 局限

- 冻结版只试了一组设置（学习率 1e-3、25 个 epoch）。它的训练 loss 到最后还在缓慢下降，多跑几轮或调大学习率可能会好一些，但要追上全部微调的可能性不大。
- 测试集只有 83 例，测试集分数的波动比验证集大（冻结版融合模型的标准差达到 {summary['fu_fz']['test'][1]:.3f}），所以结论以验证集为准。

## 下一步建议

**部分冻结：** 冻结前面的层（它们学的是边缘、纹理这类通用特征），只训练最后一层（`layer4`），或最后两层（`layer3` + `layer4`），预计每次 2–3 分钟。这也是 PPT 第 12 页「partial freezing」要做的事。

## 复现

```
python src/train_ct.py --mode ct --seed 0 --freeze --lr 1e-3        # 冻结版，seed 0/1/2，--mode ct/fusion
python src/report_freeze.py                                         # 重新生成本文件和两张图
```

结果文件：`results/*_aug-basic_seed*_frozen-lr0.001.json`；基线结果：`results/*_aug-basic_seed*.json`（未改动）。
"""
(ROOT / "Frozen vs Fine-tuned Backbone.md").write_text(md, encoding="utf-8")
print("written; val delta ct", round(d_ct, 3), "fusion", round(d_fu, 3))
