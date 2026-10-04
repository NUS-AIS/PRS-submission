# Group 26 — Speaker Script · 演讲稿 · v1 — strict timing · 严格计时版

Timing assumes 120 spoken English words per minute. Numbers are filled from results/ by src/build_deck.py.
> 时长按每分钟 120 个英文词估算；所有数字由 src/build_deck.py 从结果文件自动填入。

| Speaker 讲者 | Topic 主题 | Slides 页 | Words 词数 | Time 时长 | Target 目标 |
|---|---|---|---|---|---|
| A | Background & data · 背景与数据 | 1–5 | 470 | 3:55 | 4:00 |
| B | Model · 模型 | 6–8 | 479 | 3:59 | 4:00 |
| C | Progress & results · 进展与结果 | 9–11 | 478 | 3:59 | 4:00 |
| D | Next steps · 下一步 | 12–14 | 368 | 3:04 | 3:00 |
| **Total** | | | **1795** | **14:57** | **15:00** |

## Slide 1 · Speaker A · ≈ 0:17

Good morning. We are Group 26 — Lai Wendi, Tang Shiyan, Xia Yan and Zhou Jiasheng. Our project is a multimodal imaging assistant that combines chest CT with clinical information to classify lung infections.
> 大家早上好。我们是第 26 组，成员有 Lai Wendi、Tang Shiyan、Xia Yan 和 Zhou Jiasheng。我们的项目是一个多模态医学影像助手：把胸部 CT 和临床信息结合起来，对肺部感染进行分类。

## Slide 2 · Speaker A · ≈ 1:01

Let me start with the problem. These six CT slices come from three groups: Aspergillus infection, other fungal infections, and non-fungal pneumonia. All of them show consolidation, patchy shadows or ground-glass change, so they are very hard to tell apart by eye. This matters because each group needs a different first treatment.
> 先说问题。这六张 CT 切片来自三类病人：曲霉感染、其他真菌感染和非真菌性肺炎。它们都有实变、斑片影或磨玻璃影，肉眼很难区分。而这件事很重要，因为三类病人的一线治疗方案不同。

Our goal is a research prototype that takes one patient's CT and clinical record and returns a three-class prediction with a confidence score — as decision support, not as a diagnosis.
> 我们的目标是做一个科研原型：输入一个病人的 CT 和临床记录，输出三分类的预测结果和置信度。它是辅助决策工具，不是诊断。

We have four objectives: classify the three groups; test whether CT plus clinical data beats either source alone, which is our hypothesis; show which lung regions drove the prediction; and study the effect of pre-training, training-set size and augmentation.
> 我们有四个目标：一，完成三分类；二，检验 CT 加临床数据是否比单独用任何一种更好，这是我们的核心假设；三，展示是哪些肺部区域驱动了预测；四，研究预训练、训练集大小和数据增强的影响。

## Slide 3 · Speaker A · ≈ 0:45

On scope: the core requirements are loading a case, preprocessing it, predicting three classes with probabilities, and showing everything in a viewer. Saliency maps and an "uncertain" flag come next in priority. Severity is only a "could-have", because the dataset has no severity labels.
> 关于范围：核心需求是读入一个病例、做预处理、输出三分类概率，并在一个查看界面里展示。显著性热力图和"不确定"提示的优先级次之。严重程度只是"可以做"的加分项，因为数据集没有严重程度标签。

Every requirement has a priority, so if time runs short, we know exactly which parts to protect and which to drop.
> 每条需求都定了优先级，所以如果时间不够，我们清楚哪些必须保住、哪些可以舍弃。

The techniques we use are transfer learning, multimodal fusion, classical machine-learning baselines and Grad-CAM. Out of scope are clinical validation, hospital deployment and pixel-level lesion segmentation.
> 用到的技术有迁移学习、多模态融合、传统机器学习基线和 Grad-CAM。不在范围内的有：临床验证、医院部署，以及像素级的病灶分割。

## Slide 4 · Speaker A · ≈ 0:54

Our data is PAC569, a public dataset released in September 2026 by Wuxi People's Hospital. It contains 569 CT scans from four hospitals: 153 Aspergillus, 209 other fungal and 207 non-fungal cases.
> 我们的数据是 PAC569，由无锡市人民医院于 2026 年 9 月公开发布，包含来自四家医院的 569 例 CT：曲霉 153 例、其他真菌 209 例、非真菌 207 例。

We downloaded all 13 gigabytes and checked that every CT matches exactly one clinical record with the same label. The scans are 512 by 512 pixels with 5-millimetre slices.
> 我们下载了全部 13 GB 数据，并核对过：每个 CT 都恰好对应一条临床记录，标签一致。图像为 512×512 像素，层厚 5 毫米。

The classes are reasonably balanced, so we use a class-weighted loss rather than resampling the data.
> 三类数量比较均衡，所以我们用类别加权的损失函数，而不是对数据重采样。

The clinical file has twelve variables: age and gender, comorbidities such as AIDS and diabetes, immunosuppressant use, two blood tests, and two fungal markers — the G test and the GM antigen.
> 临床表有 12 个变量：年龄、性别，艾滋病和糖尿病等合并症，是否使用免疫抑制剂，两项血液指标，以及两个真菌标志物——G 试验和 GM 抗原。

## Slide 5 · Speaker A · ≈ 0:57

Before modelling, we explored the data and found three important things. First, risk factors differ by class — for example, 39 of the 41 AIDS patients have a non-Aspergillus fungal infection — but no single factor separates the classes.
> 建模之前我们先做了数据探索，有三个重要发现。第一，各类的危险因素不同，比如 41 个艾滋病患者里有 39 个属于非曲霉真菌感染；但没有任何单一因素能把三类分开。

Second, the G and GM tests are themselves used to diagnose fungal infection, so we always compare results with and without them. Missing values are rare: D-dimer is missing in 33 cases, which we fill with the training median.
> 第二，G 试验和 GM 抗原本身就是真菌感染的诊断依据，所以我们始终同时报告用和不用这两项的结果。缺失值很少：D-二聚体缺 33 例，用训练集的中位数填补。

Third, 21 records repeat the previous patient exactly — probably repeat scans — so we grouped them into 548 patient groups. Finally, there are no lesion masks or severity labels. Now B will explain our model.
> 第三，有 21 条记录和上一位病人完全相同，很可能是同一人的重复扫描，所以我们把数据合并成 548 个病人组。另外，数据集没有病灶标注，也没有严重程度标签。接下来由 B 介绍我们的模型。

## Slide 6 · Speaker B · ≈ 1:25

Thank you. I will cover how we process the data, the model, and how we will evaluate it.
> 谢谢。我会讲三部分：数据怎么处理、模型结构，以及怎么评估。

First, the CT pipeline. Each scan goes through four steps: a lung window to highlight lung tissue, a simple lung mask, a crop around the chest, and then sixteen slices sampled evenly from the bottom to the top of the lungs. Each sample stacks three neighbouring slices as colour channels, so a 2D network still sees some 3D context. Why sixteen? Patients have between 31 and 81 slices, so a fixed number gives every patient the same input size.
> 先是 CT 预处理流程，共四步：用肺窗突出肺组织；做一个简单的肺部掩膜；围绕胸部裁剪；然后从肺底到肺尖均匀取 16 张切片。每个样本把相邻三层叠成 RGB 三个通道，这样 2D 网络也能看到一点 3D 信息。为什么取 16 张？病人的层数在 31 到 81 之间，固定数量能让每个病人的输入尺寸一致。

Quality checking found that 12 scans were first cropped to only one lung, because a fully consolidated lung no longer looks like air. We fixed the crop and re-ran everything.
> 质量检查时发现，有 12 例最初只裁到了一侧肺，因为整片实变的肺在图像上已经不像空气了。我们修好了裁剪，并全部重跑。

At the bottom is our split: 70, 15 and 15 percent, stratified by class and done by patient group, so the same patient never appears in both training and test. Augmentation — small rotations and shifts — is applied to training data only.
> 下方是数据划分：按 70/15/15 的比例，按类别分层、按病人组切分，保证同一个病人不会同时出现在训练集和测试集里。数据增强（小角度旋转和平移）只用在训练集上。

## Slide 7 · Speaker B · ≈ 1:16

Next, the architecture, which has two branches. The CT branch passes the sixteen slices through the same ImageNet-pretrained ResNet-18 and averages them into one 512-number vector per patient.
> 接下来是模型结构，分两个分支。CT 分支把 16 张切片送入同一个在 ImageNet 上预训练过的 ResNet-18，再取平均，得到每个病人一个 512 维的向量。

The clinical branch fills missing values, scales the variables using training data only, and passes them through a small network to get 64 numbers. We join the two vectors, and a small classifier outputs the probabilities of the three classes. Grad-CAM uses the CT branch to show which regions mattered.
> 临床分支先填补缺失值，只用训练集的统计量做标准化，再通过一个小网络得到 64 维向量。两个向量拼接后，由一个小分类器输出三类的概率。Grad-CAM 作用在 CT 分支上，显示哪些区域起了作用。

We chose 2.5D rather than full 3D because the slices are 5 millimetres thick, so there is little detail along that axis; pretrained 2D weights can be reused directly; and it fits our 8-gigabyte GPU. Our baselines simply remove one branch, which keeps comparisons fair.
> 我们选 2.5D 而不是完整的 3D，原因有三：层厚 5 毫米，层间方向的细节本来就少；可以直接复用 2D 预训练权重；而且能放进我们 8 GB 的显卡。基线模型只是去掉其中一个分支，保证比较公平。

For training, we use a class-weighted loss so that the smaller Aspergillus class is not ignored, the AdamW optimiser and mixed precision. The best epoch is chosen on validation macro-F1.
> 训练时我们用类别加权损失，避免样本较少的曲霉类被忽视，优化器用 AdamW，并开启混合精度。最佳的 epoch 按验证集 macro-F1 选取。

## Slide 8 · Speaker B · ≈ 1:18

Finally, how we will evaluate the model. We group all comparisons into two experiments. Experiment 1 is about the data: preprocessing such as lung masking; no, basic or extended augmentation; and training on 25 to 100 percent of the data. Experiment 2 is about the model: CT, clinical or combined input, two ways of fusing them, and ResNet-18 against ResNet-50.
> 最后是评估方式。我们把所有对比归成两组实验。实验一关于数据：比如是否遮肺这类预处理；不增强、基础增强和扩展增强；以及用 25% 到 100% 的数据训练。实验二关于模型：只用 CT、只用临床还是两者结合，两种融合方式，以及 ResNet-18 和 ResNet-50 的对比。

The orange tags show where each of our supervisor's three requests is covered. We run the data experiment first, and its best setting becomes the starting point for the model experiment. Each comparison changes one factor against the baseline, which, as the green bars show, is the only setting run so far.
> 橙色标签标出了导师的三个要求分别在哪里覆盖。我们先做数据实验，它的最佳设置作为模型实验的起点。每组对比只相对基线改变一个因素；如绿色条所示，基线是目前唯一跑过的设置。

Our main metric is macro-F1, which treats the three classes equally. We choose models on validation data only, and the 83-scan test set is used once for each final configuration, with three random seeds. Now C will show what we have done so far.
> 主要指标是 macro-F1，三个类别权重相同。我们只用验证集选模型；83 例的测试集对每个最终配置只用一次，跑三个随机种子。接下来由 C 介绍目前的进展。

## Slide 9 · Speaker C · ≈ 1:16

Thank you. This bar shows our whole plan in six phases. We have completed the first two. Phase zero is the data foundation: downloading, checking, cleaning, the leak-free split and the CT pipeline. Phase one is the baseline: one default configuration, run end to end with three seeds. Everything is written as scripts, so every number on these slides can be regenerated from the raw data. One baseline run takes about 3.3 minutes on our laptop GPU, so the full experiment plan is feasible.
> 谢谢。这条进度条是我们完整的计划，分六个阶段，目前完成了前两个。阶段 0 是数据基础：下载、核对、清洗、无泄漏的划分和 CT 流程。阶段 1 是基线：一个默认配置，完整跑通，三个随机种子。所有步骤都写成了脚本，这几页上的每个数字都能从原始数据重新生成。在笔记本 GPU 上跑一次基线约 3.3 分钟，所以完整的实验计划是可行的。

I want to be clear: the baseline is not a tuned or final model. It proves that the pipeline works and gives us a reference point. Neither of the two experiment groups has been run yet — phases two to five are still ahead.
> 需要说明的是：基线不是调好的模型，也不是最终模型。它证明整个流程能跑通，并提供一个参照点。两组对比实验都还没开始——阶段 2 到 5 都还在后面。

The training curves at the bottom already give a first signal: training loss falls to about 0.05, but validation F1 stays around 0.59 to 0.63.
> 下方的训练曲线已经给出一个初步信号：训练损失降到约 0.05，而验证集 F1 只有 0.59 到 0.63 左右。

## Slide 10 · Speaker C · ≈ 1:27

Here are the baseline numbers. All results are macro-F1, where random guessing gives 0.33.
> 这是基线的结果。所有数字都是 macro-F1，随机猜测是 0.33。

Using clinical data alone, a random forest reaches about 0.57 in cross-validation. Without the two fungal markers it loses only 0.037, so the model is not simply copying the diagnostic tests. Logistic regression and LightGBM reach 0.50 and 0.52, so the random forest is our best clinical model.
> 只用临床数据，随机森林在交叉验证中约为 0.57。去掉两个真菌标志物只下降 0.037，说明模型并不是在照抄诊断检查的结果。逻辑回归和 LightGBM 分别为 0.50 和 0.52，所以随机森林是目前最好的临床模型。

The CT-only ResNet-18 reaches 0.642 plus or minus 0.014 on the test set, the best so far. The combined model reaches 0.618 plus or minus 0.020, so adding clinical data does not help yet. Per class, the CT model finds 67 percent of Aspergillus, 56 percent of other fungal and 71 percent of non-fungal cases, so the other-fungal group is the hardest. The ranges come from three random seeds.
> 只用 CT 的 ResNet-18 在测试集上为 0.642 ± 0.014，是目前最好的。融合模型为 0.618 ± 0.020，也就是说，加入临床数据暂时没有带来提升。分类别看，CT 模型能找出 67% 的曲霉、56% 的其他真菌和 71% 的非真菌病例，其他真菌这一类最难。正负范围来自三个随机种子。

On the right is the confusion matrix of the combined model. The most common mistake is other fungal predicted as non-fungal, in 7 of 29 cases.
> 右边是融合模型的混淆矩阵。最常见的错误是把其他真菌预测成非真菌，29 例中有 7 例。

Please remember that these numbers come from one untuned configuration. They are a starting point, not a conclusion.
> 请注意，这些数字只来自一个未调参的配置，是起点，不是结论。

## Slide 11 · Speaker C · ≈ 1:15

We also checked where the model looks, using Grad-CAM. Grad-CAM looks at the last convolutional layer and asks which areas would most change the score of the predicted class; red areas contributed most. These are three correctly classified test cases, one from each class, each showing its four most important slices.
> 我们还用 Grad-CAM 看了模型在看哪里。Grad-CAM 看的是最后一个卷积层，找出哪些区域对预测类别的分数影响最大，红色就是贡献最大的区域。这里是三个分类正确的测试病例，每类一个，各展示最重要的四张切片。

In all three, the red area sits in the centre of the chest — the heart, the large vessels and the main airways — not on the lung shadows at the edges. This suggests the model may be using anatomy or scanner-related cues instead of the infection itself. That matters, because a model that is right for the wrong reason would fail on data from another hospital.
> 三个病例的红色区域都在胸部中央——心脏、大血管和主气道——而不是外周的肺部阴影。这说明模型可能依赖的是解剖结构或扫描设备相关的线索，而不是感染本身。这一点很关键：一个"答对了但理由不对"的模型，换到另一家医院的数据就会失效。

Also, every case is predicted with probability one point zero, which means the model is overconfident. We treat both as warning signs. D will now explain what we will do about them.
> 另外，每个病例的预测概率都是 1.00，说明模型过度自信。我们把这两点都当作警示信号。接下来由 D 说明我们打算怎么处理。

## Slide 12 · Speaker D · ≈ 1:38

Thank you. This table turns each observation into an action. The gap between training and validation means the network memorises our four hundred training scans, so we will add augmentation and regularisation. The Grad-CAM pattern means we will mask everything outside the lungs.
> 谢谢。这张表把每个观察都对应到一个行动。训练和验证之间的差距说明网络在死记约 400 例训练数据，所以我们会加数据增强和正则化。Grad-CAM 的结果意味着我们要把肺以外的区域全部遮掉。

The weak fusion result means the clinical vector is drowned out by the image features, so we will try late fusion, which combines the two models' probabilities. The overconfident outputs mean we will calibrate the probabilities. And the crop problem we already fixed tells us that preprocessing needs routine checks.
> 融合效果不好，说明临床向量被图像特征淹没了，所以我们会尝试晚期融合，也就是把两个模型的概率结合起来。输出过度自信，所以要做概率校准。而已经修好的裁剪问题提醒我们，预处理需要例行检查。

The arrows show our order: first fix the data and the training, then run the data experiment, then the model experiment, which includes the new fusion, and only at the end use the test set. Data comes first because every later experiment depends on the input; fixing it later would force us to repeat all of them.
> 箭头表示执行顺序：先修数据和训练，然后做数据实验，再做模型实验（包括新的融合方式），最后才动用测试集。数据放在第一步，因为后面所有实验都依赖输入；如果之后才修，所有实验都得重做。

Three rules keep this fair. If we change the data, we re-run everything, including the baseline. Augmentation is a training setting, not extra patients. And today's test numbers are only a first look. This way, every result in our final presentation will be fair and reproducible.
> 有三条规则保证公平：数据一改，就全部重跑，包括基线；数据增强只是训练设置，不等于增加病人；今天的测试集数字只是初步一看。这样，期末汇报里的每个结果都是公平、可复现的。

## Slide 13 · Speaker D · ≈ 1:20

On the left is a mock-up of our interface, using a real case from the dataset. It shows the CT viewer, the patient's clinical record and the predicted probabilities, with a clear research-use disclaimer. A user can scroll through slices, switch on the saliency overlay, and see an "uncertain" message when the model is not confident enough.
> 左边是界面草图，用的是数据集里的真实病例，展示 CT 查看器、病人的临床记录和预测概率，并明确标注仅供科研使用。用户可以翻看切片、打开热力图叠加层；当模型把握不够时，会显示"不确定"。

On the right is our six-week timeline, in the same order: lung masking and regularisation in week one, the data experiment in week two, the model experiment in weeks three and four together with the severity proxy, the interface in week five, and the final test and report in week six.
> 右边是六周的时间线，顺序和上一页一致：第 1 周遮肺和正则化，第 2 周做数据实验，第 3、4 周做模型实验并确定严重程度的定义，第 5 周做界面，第 6 周做最终测试和报告。

For severity, one option is the share of lung that is denser than normal, which needs no extra labels; we will agree the definition with our supervisor. Our main risks are the small dataset, repeat scans, missing lesion masks and the undefined severity target. For each one, we have a plan listed below.
> 关于严重程度，一个可选方案是计算肺内密度高于正常的区域占比，不需要额外标注；具体定义会和导师商定。主要风险是数据量小、重复扫描、缺少病灶标注，以及严重程度的定义尚未确定。每一项下方都列了应对方案。

## Slide 14 · Speaker D · ≈ 0:05

Thank you for listening. We are happy to take your questions.
> 谢谢大家，欢迎提问。

---

## Q&A preparation · 问答预案 (5 min)

Suggested owner in brackets (A background & data · B model · C progress & results · D next steps); anyone may answer.
> 括号里是建议回答人（A 背景与数据 · B 模型 · C 进展与结果 · D 下一步），其他人也可以补充。

**Q1. Fusion is not better than CT alone. Doesn't that disprove your hypothesis?** [C → D]
> **问 1：融合没有比只用 CT 好，这不是推翻了你们的假设吗？**

Not yet. This is one untuned baseline. Both models fit the training set almost perfectly but reach only 0.59–0.63 validation macro-F1, and the 64-number clinical vector sits next to 512 image features, so the classifier can ignore it. Clinical data alone already reach about 0.57, so the information is there. Late fusion — averaging the probabilities of separately trained models — cannot drown out either source. If fusion still does not help after that, that is itself a valid finding.
> 还不能这么说。这只是一个未调参的基线。两个模型都几乎完美拟合了训练集，但验证集 macro-F1 只有 0.59–0.63；而且 64 维的临床向量和 512 维的图像特征放在一起，分类器很容易忽略它。只用临床数据就已经约有 0.57，说明信息是存在的。晚期融合（把分别训练的模型的概率平均）不会让任何一方被淹没。如果那之后融合仍然没用，这本身也是一个有效的结论。

**Q2. Are the G test and GM antigen label leakage?** [A]
> **问 2：G 试验和 GM 抗原算不算标签泄漏？**

They are part of how fungal infection is diagnosed, so they could be a shortcut. That is why we report the clinical model with and without them: removing them lowers random-forest CV macro-F1 by only 0.037. Both versions will be in the final results.
> 它们本身就是真菌感染的诊断依据，确实可能成为捷径。所以我们同时报告用和不用这两项的临床模型：去掉之后随机森林的交叉验证 macro-F1 只下降 0.037。最终结果里两个版本都会报告。

**Q3. How do you know the 21 repeated rows are the same patient?** [A]
> **问 3：你们怎么确定那 21 条重复记录是同一个病人？**

We cannot be certain — the dataset has no patient ID. The rows are identical in all twelve clinical fields and have consecutive case numbers, which is very unlikely by chance. Grouping them is the conservative choice: if they are different patients we lose nothing; if they are the same patient we avoid leakage.
> 无法完全确定，因为数据集没有病人 ID。但这些记录 12 个临床字段完全相同，病例编号又是连续的，偶然出现的可能性很小。合并成组是保守的做法：如果其实是不同病人，我们没有任何损失；如果是同一个病人，就避免了数据泄漏。

**Q4. Why not a 3D CNN?** [B]
> **问 4：为什么不用 3D CNN？**

All scans have 5 mm slices, so there is little information along z, and our GPU has 8 GB. 2.5D lets us use ImageNet weights directly. A 3D comparison can be added later if time allows.
> 所有扫描的层厚都是 5 毫米，层间方向的信息本来就少，而且我们的显卡只有 8 GB。2.5D 可以直接用 ImageNet 预训练权重。时间允许的话，之后可以补一个 3D 的对比。

**Q5. Why macro-F1 and not accuracy?** [B]
> **问 5：为什么用 macro-F1 而不是准确率？**

The classes are unequal (153 / 209 / 207) and all three matter clinically. Macro-F1 weights each class equally, so a model cannot look good by favouring the largest class.
> 三类数量不相等（153 / 209 / 207），而且三类在临床上都同样重要。macro-F1 对每一类同等加权，模型无法靠偏向最大的那一类来"刷分"。

**Q6. The test set has only 83 scans. Are the differences meaningful?** [C]
> **问 6：测试集只有 83 例，结果之间的差异有意义吗？**

Differences of a few points are within noise — our seed-to-seed SD is 0.014–0.020 and fold-to-fold SD up to 0.06. That is why we report mean ± SD over three seeds, use cross-validation for model choices, and keep the test set for final configurations only.
> 几个百分点的差异在噪声范围内：种子之间的标准差是 0.014–0.020，折之间的标准差最高到 0.06。所以我们报告三个种子的均值 ± 标准差，用交叉验证选模型，测试集只留给最终配置。

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
