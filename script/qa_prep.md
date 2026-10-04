## Q&A preparation · 问答预案 (5 min)

Suggested owner in brackets (A background & data · B model · C progress & results · D next steps); anyone may answer.
> 括号里是建议回答人（A 背景与数据 · B 模型 · C 进展与结果 · D 下一步），其他人也可以补充。

**Q1. Fusion is not better than CT alone. Doesn't that disprove your hypothesis?** [C → D]
> **问 1：融合没有比只用 CT 好，这不是推翻了你们的假设吗？**

Not yet. This is one untuned baseline. Both models fit the training set almost perfectly but reach only {val_lo}–{val_hi} validation macro-F1, and the 64-number clinical vector sits next to 512 image features, so the classifier can ignore it. Clinical data alone already reach about {rf_cv}, so the information is there. Late fusion — averaging the probabilities of separately trained models — cannot drown out either source. If fusion still does not help after that, that is itself a valid finding.
> 还不能这么说。这只是一个未调参的基线。两个模型都几乎完美拟合了训练集，但验证集 macro-F1 只有 {val_lo}–{val_hi}；而且 64 维的临床向量和 512 维的图像特征放在一起，分类器很容易忽略它。只用临床数据就已经约有 {rf_cv}，说明信息是存在的。晚期融合（把分别训练的模型的概率平均）不会让任何一方被淹没。如果那之后融合仍然没用，这本身也是一个有效的结论。

**Q2. Are the G test and GM antigen label leakage?** [A]
> **问 2：G 试验和 GM 抗原算不算标签泄漏？**

They are part of how fungal infection is diagnosed, so they could be a shortcut. That is why we report the clinical model with and without them: removing them lowers random-forest CV macro-F1 by only {rf_drop}. Both versions will be in the final results.
> 它们本身就是真菌感染的诊断依据，确实可能成为捷径。所以我们同时报告用和不用这两项的临床模型：去掉之后随机森林的交叉验证 macro-F1 只下降 {rf_drop}。最终结果里两个版本都会报告。

**Q3. How do you know the {n_dup_rows} repeated rows are the same patient?** [A]
> **问 3：你们怎么确定那 {n_dup_rows} 条重复记录是同一个病人？**

We cannot be certain — the dataset has no patient ID. The rows are identical in all twelve clinical fields and have consecutive case numbers, which is very unlikely by chance. Grouping them is the conservative choice: if they are different patients we lose nothing; if they are the same patient we avoid leakage.
> 无法完全确定，因为数据集没有病人 ID。但这些记录 12 个临床字段完全相同，病例编号又是连续的，偶然出现的可能性很小。合并成组是保守的做法：如果其实是不同病人，我们没有任何损失；如果是同一个病人，就避免了数据泄漏。

**Q4. Why not a 3D CNN?** [B]
> **问 4：为什么不用 3D CNN？**

All scans have 5 mm slices, so there is little information along z, and our GPU has 8 GB. 2.5D lets us use ImageNet weights directly. A 3D comparison can be added later if time allows.
> 所有扫描的层厚都是 5 毫米，层间方向的信息本来就少，而且我们的显卡只有 8 GB。2.5D 可以直接用 ImageNet 预训练权重。时间允许的话，之后可以补一个 3D 的对比。

**Q5. Why macro-F1 and not accuracy?** [B]
> **问 5：为什么用 macro-F1 而不是准确率？**

The classes are unequal ({n_asp} / {n_naf} / {n_nf}) and all three matter clinically. Macro-F1 weights each class equally, so a model cannot look good by favouring the largest class.
> 三类数量不相等（{n_asp} / {n_naf} / {n_nf}），而且三类在临床上都同样重要。macro-F1 对每一类同等加权，模型无法靠偏向最大的那一类来"刷分"。

**Q6. The test set has only {n_test} scans. Are the differences meaningful?** [C]
> **问 6：测试集只有 {n_test} 例，结果之间的差异有意义吗？**

Differences of a few points are within noise — our seed-to-seed SD is {seed_sd_lo}–{seed_sd_hi} and fold-to-fold SD up to {cv_sd_max}. That is why we report mean ± SD over three seeds, use cross-validation for model choices, and keep the test set for final configurations only.
> 几个百分点的差异在噪声范围内：种子之间的标准差是 {seed_sd_lo}–{seed_sd_hi}，折之间的标准差最高到 {cv_sd_max}。所以我们报告三个种子的均值 ± 标准差，用交叉验证选模型，测试集只留给最终配置。

**Q7. How will you evaluate localisation without lesion masks?** [D]
> **问 7：没有病灶标注，你们怎么评估定位效果？**

Quantitatively we can only check that saliency falls inside the lung region. Qualitatively we will review the maps, ideally with a clinician. We will not claim lesion-detection accuracy.
> 定量上，只能检查热力图是否落在肺部区域内。定性上，我们会逐例查看热力图，最好能请临床医生一起看。我们不会声称有病灶检测的准确率。

**Q8. How will you define severity?** [D]
> **问 8：严重程度你们打算怎么定义？**

One option is the fraction of the lung region that is denser than normal aerated lung (for example above −700 HU), which needs no labels. The lung region must come from the mirrored crop or a proper lung segmentation, because a simple air threshold misses fully consolidated lung. We want to agree the definition with our supervisor first.
> 一个方案是计算肺部区域中密度高于正常含气肺组织（比如高于 −700 HU）的比例，不需要额外标注。肺部区域要用镜像裁剪或正式的肺分割来确定，因为简单的空气阈值会漏掉整片实变的肺。具体定义我们想先和导师商定。

**Q9. Can this generalise to other hospitals?** [D]
> **问 9：这个模型能推广到其他医院吗？**

We do not claim that. PAC569 comes from four centres but has no centre label, so we cannot test leave-one-centre-out. The Grad-CAM finding is also a warning here, and lung masking is partly meant to address it. External validation is outside our scope.
> 我们不做这样的声明。PAC569 来自四个中心，但没有中心标签，所以无法做留一中心的测试。Grad-CAM 的发现在这一点上也是一个警示，遮肺的部分目的就是解决它。外部验证不在我们的范围内。
