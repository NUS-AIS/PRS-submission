# v2 — free allocation (A 3:30 · B 3:30 · C 4:00 · D 3:15 ≈ 14:15, 45 s buffer)

Same format as v1. "KEY:" lines are the one-sentence message of the slide (not spoken).
[Square brackets] are stage cues — where to point — and are not counted as spoken words.

## Slide 1 · Speaker A
KEY: Who we are, and the project in one sentence.
> 要点：我们是谁，一句话说清项目。

Good morning. We are Group 26. Our project asks one question: can a computer tell three kinds of lung infection apart by combining a chest CT with a few routine clinical facts?
> 大家早上好，我们是第 26 组。我们的项目想回答一个问题：把胸部 CT 和几项常规临床信息结合起来，计算机能不能区分三种肺部感染？

## Slide 2 · Speaker A
KEY: The three classes look alike, and that is the clinical problem.
> 要点：三类病例看起来很像，这就是临床难点。

[Point to the six images] Here are six real scans from our dataset, two per class: Aspergillus, other fungi, and non-fungal pneumonia. Try to tell them apart — it is very hard. All of them show patchy white shadows. Yet each group needs a different first treatment, so a wrong first guess costs time.
> 【指向六张图】这是数据集里的六张真实 CT，每类两张：曲霉、其他真菌和非真菌性肺炎。大家可以试着分辨一下——非常难，它们都有斑片状的白色阴影。但三类的一线治疗不同，第一判断出错就会耽误时间。

So we are building a research prototype that reads one patient's CT and clinical record and gives a three-class prediction with a confidence score. It supports a doctor; it does not replace one.
> 所以我们在做一个科研原型：读入一个病人的 CT 和临床记录，给出三分类预测和置信度。它辅助医生，而不是取代医生。

[Point to the hypothesis box] Our hypothesis is simple: CT plus clinical data should beat either one alone. Our four objectives follow from it: classify, compare the data sources, explain the prediction, and study what helps a small dataset.
> 【指向假设框】我们的假设很简单：CT 加临床数据应该比单独任何一种更好。四个目标都由此展开：分类、比较不同数据来源、解释预测，以及研究什么方法对小数据集有帮助。

## Slide 3 · Speaker A
KEY: What we will build, and what we deliberately will not.
> 要点：我们要做什么，以及刻意不做什么。

The table lists eight requirements with priorities. The "must-haves" are the classification pipeline and a viewer. Severity is only a "could-have", because the data has no severity labels. To build it, we use four techniques from this course: transfer learning, multimodal fusion, classical machine-learning baselines, and Grad-CAM for explanation.
> 表里列了八条需求和优先级。"必须有"的是分类流程和查看界面。严重程度只是"可以有"，因为数据没有严重程度标签。实现上我们用到本课程的四类技术：迁移学习、多模态融合、传统机器学习基线，以及用于解释的 Grad-CAM。

Just as important is what we will not do: no clinical validation, no hospital deployment, and no pixel-level lesion segmentation.
> 同样重要的是我们不做什么：不做临床验证，不做医院部署，也不做像素级的病灶分割。

## Slide 4 · Speaker A
KEY: A clean, public, well-matched dataset of 569 scans.
> 要点：一个干净、公开、匹配良好的 569 例数据集。

Our data is PAC569, released in September 2026 by Wuxi People's Hospital: 569 chest CT scans from four hospitals, with {n_asp} Aspergillus, {n_naf} other fungal and {n_nf} non-fungal cases. The classes are fairly balanced, so a class-weighted loss is enough — no resampling needed.
> 数据是 PAC569，由无锡市人民医院在 2026 年 9 月发布：来自四家医院的 569 例胸部 CT，其中曲霉 {n_asp} 例、其他真菌 {n_naf} 例、非真菌 {n_nf} 例。三类比较均衡，用类别加权损失就够了，不需要重采样。

We checked every file: each CT matches exactly one clinical record, and all labels agree. Each record has twelve variables, including age, AIDS and diabetes status, two blood tests, and two fungal markers called G and GM. The scans are also uniform — 512 by 512 pixels, five-millimetre slices, {nz_min} to {nz_max} slices per patient — which keeps preprocessing simple.
> 我们逐个核对过：每个 CT 恰好对应一条临床记录，标签全部一致。每条记录有 12 个变量，包括年龄、是否有艾滋病和糖尿病、两项血液指标，以及两个真菌标志物 G 和 GM。图像也很统一：512×512 像素，层厚 5 毫米，每个病人 {nz_min} 到 {nz_max} 层，预处理因此比较简单。

## Slide 5 · Speaker A
KEY: Exploring the data first changed how we split and evaluate.
> 要点：先做数据探索，改变了我们划分和评估的方式。

Exploring the data first taught us three things that shaped the whole project.
> 先做数据探索，我们得到三点认识，影响了整个项目。

One: clinical signals are real but weak. [Point to AIDS] Almost all AIDS patients are in the other-fungal group, but no single marker separates the classes.
> 第一：临床信号真实存在，但比较弱。【指向 AIDS】艾滋病患者几乎都在其他真菌组，但没有任何单一指标能把三类分开。

Two: G and GM are themselves diagnostic tests, so a model could cheat by copying them. We therefore always test with and without them.
> 第二：G 和 GM 本身就是诊断检查，模型可能靠照抄它们来"作弊"，所以我们始终同时测试用和不用这两项。

Three: {n_dup_rows} records look like repeat scans of the same patient. We grouped them, so one patient can never sit in both training and test.
> 第三：有 {n_dup_rows} 条记录看起来是同一个病人的重复扫描。我们把它们归成一组，保证同一个病人不会同时出现在训练集和测试集。

Now B will show how we turned this data into a model.
> 接下来由 B 介绍我们如何把这些数据变成模型。

## Slide 6 · Speaker B
KEY: Every CT becomes 16 standard images; the split is leak-free.
> 要点：每个 CT 变成 16 张标准图像；数据划分无泄漏。

Thank you. A CT scan is a stack of about sixty images, so first we standardise it. [Point left to right] We apply a lung window, find the lungs, crop the chest, and pick sixteen slices from bottom to top. Three neighbouring slices form one colour image, which gives a 2D network a little depth. Why sixteen? Patients have different numbers of slices, so a fixed number gives every patient the same input size.
> 谢谢。一次 CT 大约是六十张图像叠在一起，所以第一步是标准化。【从左往右指】我们用肺窗、找到肺部、裁剪胸部，再从下到上取 16 张切片。相邻三张合成一张彩色图，让 2D 网络也能看到一点深度信息。为什么取 16 张？每个病人的层数不同，固定数量能让每个人的输入尺寸一致。

One lesson: our first crop missed one lung in {crop_fail} patients — exactly the sickest ones, whose lung was completely white. We caught it by checking the images, fixed it, and re-ran everything.
> 一个教训：最初的裁剪在 {crop_fail} 个病人身上漏掉了一侧肺——恰恰是病得最重、整片肺都发白的那些人。我们通过检查图像发现了问题，修好之后全部重跑。

[Point to the table] We split patients 70, 15, 15, keeping class proportions and patient groups intact. Augmentation — small rotations and shifts — is used on training data only.
> 【指向表格】我们按 70/15/15 划分病人，保持类别比例，同时不拆散病人组。数据增强（小角度旋转和平移）只用于训练集。

## Slide 7 · Speaker B
KEY: Two branches — image and clinical — joined before the classifier.
> 要点：图像和临床两个分支，在分类器之前汇合。

Our model has two branches. [Top row] The image branch sends all sixteen slices through one ResNet-18, a network pretrained on everyday photos, and averages them into one summary per patient.
> 模型有两个分支。【上面一行】图像分支把 16 张切片送入同一个 ResNet-18——这是在日常照片上预训练过的网络——再取平均，得到每个病人的一个综合特征。

[Bottom row] The clinical branch cleans and scales the twelve variables and passes them through a small network. Missing values are filled with the training median, and all scaling uses training data only, so nothing leaks from the test set. Note the sizes: the image summary has 512 numbers, the clinical one only 64 — we will come back to this.
> 【下面一行】临床分支对 12 个变量做清洗和标准化，再送入一个小网络。缺失值用训练集中位数填补，所有标准化只用训练集统计量，测试集的信息不会泄漏进来。注意两边的大小：图像特征有 512 维，临床特征只有 64 维——后面会再讲到这一点。

[Right] We join both summaries and predict the three classes. Grad-CAM later shows which image regions drove the answer.
> 【右边】两个特征拼接后预测三分类。之后用 Grad-CAM 显示是哪些图像区域决定了结果。

Why not a full 3D network? Our slices are five millimetres thick, so 3D adds little, and 2D lets us reuse pretrained weights on an 8-gigabyte GPU. We train with a class-weighted loss, so the smaller Aspergillus class counts fully, and choose the best epoch on validation F1.
> 为什么不用完整的 3D 网络？层厚 5 毫米，3D 带来的收益有限；而 2D 可以复用预训练权重，在 8 GB 显卡上也跑得动。训练时用类别加权损失，保证样本较少的曲霉类不被忽视，并按验证集 F1 选最佳 epoch。

## Slide 8 · Speaker B
KEY: Two experiment groups — data first, then model — one factor at a time, test set reserved.
> 要点：两组实验——先数据、后模型——每次只改一个因素，测试集留到最后。

How will we know what works? We group every comparison into two experiments. [Left box] Experiment 1 is about the data: preprocessing such as lung masking, how much augmentation, and how much training data. [Right box] Experiment 2 is about the model: CT, clinical or both, two ways of fusing them, and a smaller or larger backbone.
> 我们怎么判断什么方法有效？我们把所有对比归成两组实验。【左框】实验一关于数据：比如是否遮肺这类预处理、用多强的数据增强、用多少训练数据。【右框】实验二关于模型：只用 CT、只用临床还是两者都用，两种融合方式，以及较小或较大的骨干网络。

[Point to the orange tags] These tags show that all three of our supervisor's requests are covered. [Point to the arrow] We run the data experiment first, and its best setting carries into the model experiment. [Point to the green bars] Only the default — our baseline — has been run so far.
> 【指向橙色标签】这些标签说明导师的三个要求都覆盖到了。【指向箭头】先做数据实验，它的最佳设置带入模型实验。【指向绿色条】目前只跑了默认配置，也就是基线。

We use macro-F1, which treats all three classes equally, and we pick models on validation data only. The test set is touched once, at the very end. Each configuration runs with three seeds, because our test set has only {n_test} scans and a single number would be noisy. Now C will show where we are.
> 我们用 macro-F1，三个类别同等对待；只用验证集选模型，测试集只在最后用一次。每个配置跑三个随机种子，因为测试集只有 {n_test} 例，单次结果噪声太大。接下来由 C 介绍目前的进展。

## Slide 9 · Speaker C
KEY: We have finished the foundation and one baseline — the main work is ahead.
> 要点：我们完成了基础工作和一个基线，主体工作还在后面。

Thank you. [Point to "we are here"] This is our whole plan in six phases, and we are here — after the first two.
> 谢谢。【指向"WE ARE HERE"】这是完整的六阶段计划，我们现在在这里，刚完成前两个阶段。

Phase zero, the data foundation, is done: data checked, cleaned, split, and the CT pipeline working. Phase one, the baseline, is done: one default model, run with three seeds. Everything is written as scripts, so every number on these slides can be regenerated from the raw data. And one baseline run takes only about {run_min} minutes on a laptop GPU, so the full plan is realistic.
> 阶段 0 数据基础已完成：数据核对、清洗、划分，CT 流程跑通。阶段 1 基线已完成：一个默认模型，跑了三个随机种子。所有步骤都写成了脚本，这几页上的每个数字都能从原始数据重新生成。在笔记本 GPU 上跑一次基线只要约 {run_min} 分钟，所以完整的计划是现实可行的。

Let me be clear about the baseline. It is not tuned and not final. It proves the pipeline works end to end and gives a reference for every later experiment. The real experiments — phases two to five — have not started.
> 我要说清楚基线的定位：它没有调参，也不是最终模型。它证明整个流程能端到端跑通，并为后续每个实验提供参照。真正的实验——阶段 2 到 5——还没有开始。

[Point to the curves] Even so, it already tells us something: training loss drops to about {loss_lo}, while validation F1 stalls near {val_hi}. The model learns the training set far better than new patients.
> 【指向曲线】即便如此，它已经说明了一些问题：训练损失降到约 {loss_lo}，验证集 F1 却停在 {val_hi} 左右。模型学训练集远比学新病人好。

## Slide 10 · Speaker C
KEY: CT alone is best so far; fusion does not help yet; these are starting numbers.
> 要点：目前只用 CT 最好；融合暂时没有帮助；这些只是起点数字。

Here are the baseline numbers. They are macro-F1 scores, where guessing gives 0.33.
> 这是基线的结果，指标是 macro-F1，随机猜是 0.33。

[First four rows] Clinical data alone reach about {rf_cv}. Removing G and GM costs only {rf_drop}, so the model is not just copying the tests. Logistic regression and LightGBM do worse, at {lr_cv} and {lgb_cv}.
> 【前四行】只用临床数据约为 {rf_cv}。去掉 G 和 GM 只下降 {rf_drop}，说明模型不是在照抄检查结果。逻辑回归和 LightGBM 更低，分别为 {lr_cv} 和 {lgb_cv}。

[CT-only row] CT alone is our best model: {ct_mean} plus or minus {ct_sd}. The ranges come from three random seeds. Per class, it finds {rec_asp} percent of Aspergillus, {rec_naf} percent of other fungal and {rec_nf} percent of non-fungal cases.
> 【CT 那一行】只用 CT 是目前最好的模型：{ct_mean} ± {ct_sd}。正负范围来自三个随机种子。分类别看，它能找出 {rec_asp}% 的曲霉、{rec_naf}% 的其他真菌和 {rec_nf}% 的非真菌病例。

[Last row] Combining CT and clinical data gives {fu_mean} — so far, fusion does not help. That is the opposite of our hypothesis, and we report it honestly; the next section explains why.
> 【最后一行】CT 加临床数据为 {fu_mean}——目前融合没有帮助。这和我们的假设相反，我们如实报告，后面会解释原因。

[Point to the matrix] The hardest class is other fungi: the most common error is calling them non-fungal, {err_n} of {err_tot} cases. Remember: this is one untuned configuration with three seeds — a starting point, not a conclusion.
> 【指向混淆矩阵】最难的是其他真菌这一类：最常见的错误是把它判成非真菌，{err_tot} 例中有 {err_n} 例。请记住：这只是一个未调参的配置、三个随机种子——是起点，不是结论。

## Slide 11 · Speaker C
KEY: The model looks at the centre of the chest, not the infection — a warning sign.
> 要点：模型看的是胸部中央，而不是感染部位——这是警示信号。

A good score is not enough; we also need the right reason. Grad-CAM highlights the regions that drove each prediction, in red. Technically, it looks at the last layer of the image network and measures which areas would most change the score of the predicted class. For each case we show the four slices it relies on most. These are cases the model got right, with high confidence — so you might expect it to look at the lesions.
> 分数好还不够，还要"理由对"。Grad-CAM 用红色标出决定预测的区域。技术上，它看的是图像网络的最后一层，衡量哪些区域对预测类别的分数影响最大。每个病例展示模型最依赖的四张切片。这些都是模型判断正确、而且很有把握的病例——按理说它应该看着病灶。

[Sweep across the rows] In all three cases, the red sits on the heart and main airways — not on the patchy lung shadows at the edges. So the model may be using anatomy or scanner details, not the infection. A model like that could fail at a new hospital. This is not a failure of the project — it is exactly the kind of problem a baseline should reveal early, before we spend weeks on the full experiments.
> 【依次扫过三行】三个病例的红色都在心脏和主气道上，而不是外周的斑片影。所以模型可能依赖的是解剖结构或扫描设备的细节，而不是感染本身。这样的模型换到新医院可能就会失效。这不是项目的失败——这正是基线应该尽早暴露的问题，最好在我们花几周做完整实验之前就发现。

Also, every prediction says one point zero — the model is overconfident. D will explain how we will fix both.
> 另外，每个预测的概率都是 1.00，模型过度自信。D 会说明我们打算怎么解决这两个问题。

## Slide 12 · Speaker D
KEY: The baseline is a diagnosis; each problem maps to a planned fix, in a fixed order.
> 要点：基线是一次诊断；每个问题都对应一个计划中的修复，并按固定顺序进行。

Thank you. We use the baseline as a diagnosis. [Point to the table] Each row is a problem we saw, what it means, and what we will change.
> 谢谢。我们把基线当作一次诊断。【指向表格】每一行是一个观察到的问题、它说明什么、以及我们要改什么。

Overfitting means more augmentation and regularisation. Looking at the heart means masking out everything except the lungs. Weak fusion means combining the two models' outputs instead of their features. Overconfidence means calibration. Late fusion means training the CT and clinical models separately and then averaging their probabilities, so the small clinical signal cannot be drowned out. And the crop bug we already fixed reminds us to keep checking the preprocessing.
> 过拟合，就加强数据增强和正则化；模型盯着心脏看，就把肺以外的区域全部遮掉；融合效果差，就改成把两个模型的输出结合，而不是拼接特征；过度自信，就做概率校准。晚期融合是指分别训练 CT 模型和临床模型，再把两者的概率平均，这样较弱的临床信号就不会被淹没。已经修好的裁剪问题也提醒我们，要持续检查预处理。

[Point to the arrows] The order matters. Data comes first, because every experiment depends on the input; then training, then fusion, then the full experiments — and the test set only at the very end. Why last? If we kept checking the test set while tuning, we would slowly fit our choices to those {n_test} scans, and the final number would look better than it really is.
> 【指向箭头】顺序很重要。先修数据，因为所有实验都依赖输入；然后是训练，再是融合，然后跑完整实验——测试集放在最后。为什么放最后？如果调参时反复看测试集，我们的选择会慢慢迁就这 {n_test} 例，最终分数就会比真实水平偏高。

[Point to the three rules] And three rules keep it fair: change the data, re-run everything; augmentation is not extra patients; and today's test numbers are only a first look. This way, every result in our final presentation will be fair and reproducible.
> 【指向三条规则】还有三条规则保证公平：改了数据就全部重跑；数据增强不等于增加病人；今天的测试集数字只是初步一看。这样，期末汇报里的每个结果都是公平、可复现的。

## Slide 13 · Speaker D
KEY: What the user will see, and a six-week plan that follows the same order.
> 要点：用户会看到什么，以及按同样顺序排的六周计划。

[Left] This is the interface we will build, shown with a real case: the CT viewer, the clinical record and the three probabilities, plus an "uncertain" message when the model is unsure. A user can scroll through slices and switch on the saliency overlay to see what the model looked at.
> 【左边】这是我们要做的界面，用一个真实病例展示：CT 查看器、临床记录和三类概率；当模型没把握时，会显示"不确定"。用户可以翻看切片，也可以打开热力图叠加层，看模型关注了哪里。

[Right] The timeline follows the same order: fixes in week one, the data experiment in week two, the model experiment in weeks three and four, the interface in week five, and final testing in week six. For severity, one idea is the share of lung that is denser than normal, which needs no extra labels; we will agree the definition with our supervisor. By week six, both experiment groups will be reported as mean plus or minus standard deviation over three seeds.
> 【右边】时间线按同样的顺序：第 1 周修数据和训练，第 2 周做数据实验，第 3、4 周做模型实验，第 5 周做界面，第 6 周做最终测试。关于严重程度，一个思路是计算肺内密度高于正常的区域占比，不需要额外标注；具体定义会和导师商定。到第 6 周，两组实验的结果都会以三个种子的均值 ± 标准差报告。

The main risks — a small dataset and no lesion masks — each have a mitigation listed below. Repeat scans are already handled by the group split.
> 主要风险是数据量小、没有病灶标注，每一项下方都列了应对方案。重复扫描的问题已经通过按病人组划分解决了。

## Slide 14 · Speaker D
KEY: Close.
> 要点：结束。

To sum up: the foundation and baseline are done, and the baseline told us exactly what to fix next. Thank you — we are happy to take your questions.
> 总结一下：基础工作和基线已经完成，而基线明确告诉了我们下一步要修什么。谢谢大家，欢迎提问。
