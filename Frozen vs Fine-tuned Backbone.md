# Frozen Backbone vs Full Fine-tuning — Comparative Experiment

**Question:** Can freezing the entire ResNet-18 backbone and training only the subsequent layers mitigate overfitting in the baseline?

**Conclusion:** No. Fully freezing the backbone instead causes **underfitting**: training loss remains high, and validation F1 drops noticeably (-0.122 for the CT-only model and -0.013 for the fusion model).
Features learned from ImageNet do not transfer directly to CT images; the backbone needs at least partial fine-tuning.

## Experimental Setup

The two groups differ only in whether the backbone is frozen and in the learning rate. All other settings are identical.

| | Full fine-tuning (baseline) | Frozen backbone |
|---|---|---|
| ResNet-18 backbone | All layers trainable | Fully frozen, including BatchNorm statistics |
| Trainable components | Backbone + classification head (+ clinical branch) | Classification head only (+ clinical branch) |
| Learning rate | 1e-4 | 1e-3 (a higher learning rate is commonly used when training only the classification head) |
| Other settings | 25 epochs · AdamW · class-weighted loss · basic augmentation (rotation ±10°, translation ±5%) · identical data split · seeds 0/1/2 | Same as baseline |

**The model selection rule remains unchanged:** Evaluate validation macro-F1 after each epoch and retain the best epoch. Compare configurations **using only the validation set**; test scores are provided for reference only.

## Overall Results (Mean ± Standard Deviation Across 3 Seeds)

| Configuration | Trainable parameters | Validation macro-F1 | Test macro-F1 | Test balanced accuracy | Final-epoch training loss | Best epoch (3 seeds) | Time per run (minutes) |
|---|---|---|---|---|---|---|---|
| CT only · Full fine-tuning | 11,242,563 | **0.634 ± 0.019** | 0.595 ± 0.054 | 0.600 ± 0.051 | 0.07 | 1, 21, 19 | 4.2 |
| CT only · Frozen backbone | 66,051 | **0.511 ± 0.015** | 0.501 ± 0.012 | 0.501 ± 0.013 | 1.03 | 16, 8, 19 | 2.3 |
| CT + clinical · Full fine-tuning | 11,255,747 | **0.579 ± 0.016** | 0.593 ± 0.045 | 0.600 ± 0.041 | 0.06 | 12, 5, 8 | 4.6 |
| CT + clinical · Frozen backbone | 79,235 | **0.567 ± 0.004** | 0.596 ± 0.012 | 0.597 ± 0.010 | 0.84 | 17, 18, 18 | 2.4 |

For reference, random guessing yields a macro-F1 of 0.333; a clinical-only random forest achieves approximately 0.569 in 5-fold cross-validation.

![Validation and test scores for each configuration](figures/freeze_scores.png)

## Training Dynamics

![Training loss and validation F1 across epochs](figures/freeze_curves.png)

- **Solid lines (full fine-tuning):** Training loss quickly approaches 0, while validation F1 plateaus at around 0.6, indicating **overfitting**.
- **Dashed lines (frozen backbone):** Training loss only falls to 1.03 (CT only) and 0.84 (fusion). The models cannot even fit the training set well, indicating **underfitting**.

## Per-Class Recall (Test Set, Averaged Across 3 Seeds)

| Configuration | Aspergillus | Non-Asp. fungi | Non-fungal |
|---|---|---|---|
| CT only · Full fine-tuning | 57% | 47% | 76% |
| CT only · Frozen backbone | 43% | 39% | 68% |
| CT + clinical · Full fine-tuning | 62% | 55% | 62% |
| CT + clinical · Frozen backbone | 61% | 51% | 68% |

After freezing the CT-only model, recall drops from 57% to 43% for Aspergillus, from 47% to 39% for other fungi, and from 76% to 68% for non-fungal cases. In other words, the frozen features struggle most to distinguish the two fungal classes.

## Interpretation

1. **Neither extreme works well.** Full fine-tuning updates approximately 11.24 million parameters and memorizes the training set of around 400 patients. Freezing the entire backbone leaves only about 66,000 trainable parameters and fails to learn the features needed to distinguish these three CT classes. A suitable approach lies between the two extremes.
2. **With a frozen backbone, fusion outperforms CT alone.** The clinical branch is still being trained. The frozen fusion model's validation F1 (0.567) is close to that of the clinical-only random forest (0.569), suggesting that clinical data provides most of the predictive signal while frozen CT features contribute little.
3. **The only benefit of freezing is speed.** Training time drops from approximately 4.2 to 2.3 minutes per run, at the cost of a substantial drop in accuracy.

## Limitations

- Only one frozen-backbone setting was tested (learning rate 1e-3, 25 epochs). Training loss was still slowly decreasing at the end. More epochs or a higher learning rate might help, but matching full fine-tuning seems unlikely.
- The test set contains only 83 cases, and test scores fluctuate more than validation scores (the frozen fusion model's standard deviation reaches 0.012). Conclusions therefore rely on the validation set.

## Recommended Next Step

**Partial freezing:** Freeze the earlier layers, which learn general features such as edges and textures, and train only the final layer (`layer4`) or the final two layers (`layer3` + `layer4`). Estimated training time is 2–3 minutes per run. This is also the planned "partial freezing" experiment on slide 12 of the presentation.

## Reproduction

```
python src/train_ct.py --mode ct --seed 0 --freeze --lr 1e-3        # Frozen backbone; seeds 0/1/2; --mode ct/fusion
python src/report_freeze.py                                         # Regenerate this file and both figures
```

Result files: `results/*_aug-basic_seed*_frozen-lr0.001.json`; baseline results: `results/*_aug-basic_seed*.json` (unchanged).

