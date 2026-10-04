# v4 — final 15-minute narrative (A 3:30 · B 3:45 · C 3:45 · D 3:30 ≈ 14:30)

## Slide 1 · Speaker A
Good morning, everyone. We are Group 26. Our project is a multimodal imaging assistant: we want to find out whether a model that looks at both a chest CT and a few routine clinical facts can tell three kinds of lung infection apart.
> 大家早上好，我们是第 26 组。我们的项目是一个多模态影像助手：我们想知道，一个同时看胸部 CT 和几项常规临床信息的模型，能不能区分三种肺部感染。

## Slide 2 · Speaker A
Let's start with why this is hard. These six slices are real cases from our dataset, two per class: Aspergillus infection, other fungal infections, and non-fungal pneumonia. All of them show white patches in the lungs, and they are very hard to tell apart by eye. Yet each group needs a different first treatment, so a wrong first guess costs the patient time.
> 先说为什么这件事难。这六张切片是数据集里的真实病例，每类两张：曲霉感染、其他真菌感染和非真菌性肺炎。它们的肺里都有白色斑片，肉眼很难区分。但三类的一线治疗不同，第一判断出错，病人就要多等。

Doctors do not decide from the image alone; they also look at the patient's immune status and blood tests. That is our hypothesis: CT plus clinical information should classify more reliably than either alone.
> 医生也不会只看影像，还会看病人的免疫状态和血液检查。这就是我们的假设：CT 加临床信息，应该比单独用任何一种分得更准。

So we are building a research prototype that gives a three-class prediction with a confidence score, to support a clinician, not replace one. Our four objectives follow from this: classify, compare the data sources, explain where the model looks, and learn what helps a small dataset most.
> 所以我们在做一个科研原型：给出三分类预测和置信度，用来辅助医生，而不是取代医生。四个目标由此而来：分类、比较不同数据来源、解释模型看的是哪里，以及找出对小数据集最有帮助的方法。

## Slide 3 · Speaker A
From that goal we set our scope. The core requirements are the full pipeline — load a case, preprocess, predict with probabilities — and a viewer to show the result. Severity is only a "could-have", for a reason you will see on the next slide. Just as clearly, we will not do clinical validation, hospital deployment or pixel-level lesion segmentation.
> 根据这个目标，我们确定了范围。核心需求是完整的流程——读入病例、预处理、输出带概率的预测——以及一个展示结果的界面。严重程度只是"可以有"，原因在下一页。同样明确的是，我们不做临床验证、不做医院部署，也不做像素级的病灶分割。

## Slide 4 · Speaker A
Our data is PAC569, a public dataset released in September 2026: 569 chest CT scans from four hospitals, with {n_asp} Aspergillus, {n_naf} other fungal and {n_nf} non-fungal cases.
> 我们的数据是 2026 年 9 月公开的 PAC569：来自四家医院的 569 例胸部 CT，其中曲霉 {n_asp} 例、其他真菌 {n_naf} 例、非真菌 {n_nf} 例。

We checked every file: each CT matches exactly one clinical record with the same label. Each record has twelve variables, including AIDS and diabetes status, two blood tests and two fungal markers, G and GM. But there are no lesion outlines and no severity scores — which is why severity is only a "could-have".
> 我们逐个核对过：每个 CT 恰好对应一条标签一致的临床记录。每条记录有 12 个变量，包括是否有艾滋病和糖尿病、两项血液指标，以及 G 和 GM 两个真菌标志物。但数据里没有病灶轮廓，也没有严重程度评分——这就是严重程度只能算"可以有"的原因。

## Slide 5 · Speaker A
Before building any model, we explored the data, and three findings changed our decisions.
> 在建模之前，我们先做了数据探索，有三个发现改变了我们的决定。

First, clinical risk factors do differ by class — for example, {aids_naf} of the {aids_total} AIDS patients are in the other-fungal group — but no single marker separates the classes. So clinical data can help, but not alone.
> 第一，各类的临床危险因素确实不同，比如 {aids_total} 个艾滋病患者里有 {aids_naf} 个在其他真菌组；但没有任何单一指标能把三类分开。所以临床数据有帮助，但单靠它不够。

Second, G and GM are themselves diagnostic tests, so a model could simply copy them. We therefore always test with and without them.
> 第二，G 和 GM 本身就是诊断检查，模型可能直接照抄它们。所以我们始终同时测试用和不用这两项。

Third, {n_dup_rows} records look like repeat scans of the same patient. We grouped them, so one patient can never appear in both training and test.
> 第三，有 {n_dup_rows} 条记录看起来是同一个病人的重复扫描。我们把它们归成一组，保证同一个病人不会同时出现在训练集和测试集。

With the data understood, B will explain how we turn it into a model.
> 数据讲清楚了，接下来由 B 介绍我们如何把它变成模型。

## Slide 6 · Speaker B
Thank you. A CT scan is a stack of about sixty images, but an image network needs one fixed-size input. So each scan goes through four steps: a lung window, a lung mask, a crop around the chest, and sixteen slices taken evenly from the bottom to the top of the lungs. Three neighbouring slices form one colour image, which gives the network a little depth. Why sixteen? Patients have between {nz_min} and {nz_max} slices, so a fixed number gives everyone the same input.
> 谢谢。一次 CT 大约是六十张图叠在一起，但图像网络需要固定大小的输入。所以每个扫描要经过四步：肺窗、肺部掩膜、围绕胸部裁剪，然后从肺底到肺尖均匀取 16 张切片。相邻三张合成一张彩色图，让网络能看到一点深度。为什么是 16 张？病人的层数在 {nz_min} 到 {nz_max} 之间，固定数量能让每个人的输入一致。

Checking the output taught us a lesson: our first crop missed one lung in {crop_fail} patients — the sickest ones, whose lung was completely white and no longer looked like air. We fixed it and re-ran everything.
> 检查结果时我们得到一个教训：最初的裁剪在 {crop_fail} 个病人身上漏掉了一侧肺——恰恰是病得最重的人，整片肺发白，已经不像空气了。我们修好了它，并全部重跑。

At the bottom is our split: 70, 15 and 15 percent, balanced by class and kept by patient group, as A described. Augmentation — small rotations and shifts — is applied to training data only.
> 下方是数据划分：70/15/15，各部分类别比例一致，并且像 A 说的那样按病人组划分。数据增强（小角度旋转和平移）只用在训练集上。

## Slide 7 · Speaker B
The model has two branches. The image branch sends all sixteen slices through a ResNet-18 pretrained on ImageNet. With only about four hundred training patients, we cannot train a deep network from scratch, so we start from one that already recognises edges and textures, and average the slices into one summary per patient.
> 模型有两个分支。图像分支把 16 张切片送进一个在 ImageNet 上预训练过的 ResNet-18。我们只有约 400 个训练病人，没法从零训练深层网络，所以从一个已经会识别边缘和纹理的网络起步，再把 16 张切片平均成每个病人的一个综合特征。

The clinical branch cleans and scales the twelve variables, using training data only, and passes them through a small network. The two summaries are joined, and a classifier outputs the three probabilities. Grad-CAM later shows which image regions drove the answer. We train with a class-weighted loss, so the smaller Aspergillus class counts fully, and keep the epoch with the best validation score.
> 临床分支只用训练集的统计量对 12 个变量做清洗和标准化，再送进一个小网络。两个特征拼接后，由分类器输出三类的概率。之后用 Grad-CAM 显示是哪些图像区域决定了结果。训练时用类别加权的损失函数，让样本较少的曲霉类同样受重视，并保留验证集分数最好的那一轮。

Why not a full 3D network? The slices are five millimetres thick, so there is little detail along that direction, and 2D lets us reuse pretrained weights on our 8-gigabyte GPU.
> 为什么不用完整的 3D 网络？层厚 5 毫米，那个方向上的细节本来就少；而 2D 可以复用预训练权重，在我们 8 GB 的显卡上也跑得动。

## Slide 8 · Speaker B
To test our ideas fairly, we organise every comparison into two experiments. Experiment 1 is about the data: preprocessing such as lung masking, how much augmentation, and how much training data. Experiment 2 is about the model: CT, clinical or both, how to fuse them, and a smaller or larger backbone. The orange tags show that all three of our supervisor's requests are covered.
> 为了公平地检验我们的想法，我们把所有对比归成两组实验。实验一关于数据：比如遮肺这类预处理、增强的强度、训练数据的多少。实验二关于模型：只用 CT、只用临床还是两者结合，怎么融合，以及较小或较大的骨干网络。橙色标签说明导师的三项要求都覆盖到了。

We run the data experiment first, and its best setting becomes the start of the model experiment. Each comparison changes one thing against the baseline — and, as the green bars show, the baseline is the only setting run so far.
> 我们先做数据实验，它的最佳设置作为模型实验的起点。每组对比只相对基线改变一个因素——如绿色条所示，基线是目前唯一跑过的设置。

We measure macro-F1, which weights all three classes equally, choose models on validation data only, and use the {n_test}-scan test set just once for each final configuration. Now C will show where we are.
> 我们用 macro-F1，三个类别同等加权；只用验证集选模型；{n_test} 例的测试集对每个最终配置只用一次。接下来由 C 介绍我们目前的进展。

## Slide 9 · Speaker C
Thank you. This is our whole plan in six phases, and we are here — after the first two. The data foundation is done, and so is one baseline: the default setting from the previous slide, run end to end with three seeds. Everything is scripted, so every number here can be regenerated, and one run takes about {run_min} minutes on a laptop GPU, so the full plan is realistic.
> 谢谢。这是完整的六阶段计划，我们现在在这里——完成了前两个阶段。数据基础已经完成，基线也已完成：就是上一页的默认配置，完整跑通，用了三个随机种子。所有步骤都写成了脚本，这里的每个数字都能重新生成；在笔记本 GPU 上跑一次约 {run_min} 分钟，所以完整计划是可行的。

To be clear, the baseline is not tuned and not final. It proves the pipeline works and gives us a reference point. The main work — both experiment groups — starts now.
> 需要说清楚：基线没有调参，也不是最终结果。它证明流程能跑通，并提供一个参照点。主体工作——两组实验——从现在开始。

Even so, it already tells us something. On the bottom right, the training loss falls almost to zero, but validation F1 only reaches about {val_lo} to {val_hi}. The model learns its training patients far better than new ones. Keep this gap in mind — it comes back on slide 12.
> 即便如此，它已经说明了一些问题。右下方，训练损失几乎降到零，但验证集 F1 只有 {val_lo} 到 {val_hi} 左右。模型学训练集里的病人，远比学新病人好。请记住这个差距，第 12 页还会讲到。

## Slide 10 · Speaker C
Here are the baseline numbers, all as macro-F1, where guessing gives 0.33.
> 这是基线的结果，指标是 macro-F1，随机猜是 0.33。

Clinical data alone reach about {rf_cv}. Removing G and GM costs only {rf_drop}, so the model is not just copying the tests — which answers the concern A raised.
> 只用临床数据约为 {rf_cv}。去掉 G 和 GM 只下降 {rf_drop}，说明模型不是在照抄检查结果——这回答了 A 提出的担忧。

CT alone is our best model so far, at {ct_mean} plus or minus {ct_sd} over three seeds. Per class, it finds {rec_asp} percent of Aspergillus, {rec_naf} percent of other fungal and {rec_nf} percent of non-fungal cases. Combining CT and clinical data gives {fu_mean}, so at this stage fusion does not help. That is not what our hypothesis predicted, and we report it as it is.
> 只用 CT 是目前最好的模型，三个种子的结果是 {ct_mean} ± {ct_sd}。分类别看，它能找出 {rec_asp}% 的曲霉、{rec_naf}% 的其他真菌和 {rec_nf}% 的非真菌病例。CT 加临床为 {fu_mean}，也就是说现阶段融合没有帮助。这和我们的假设不符，我们如实报告。

In the confusion matrix, rows are the true class and columns the prediction. The weakest row is other fungi, most often mistaken for non-fungal — {err_n} of {err_tot} cases. Please read all of this as a starting point from one untuned setting.
> 混淆矩阵里，行是真实类别，列是预测类别。表现最弱的是其他真菌这一行，最常被误判为非真菌，{err_tot} 例中有 {err_n} 例。请把这些数字都看作一个未调参配置给出的起点。

## Slide 11 · Speaker C
A good score is not enough; the model should also be right for the right reason. So we used Grad-CAM, which shows in red the regions that drove each prediction. These are three test cases the model got right with high confidence, so we expected the red to sit on the infection. For each case we show the four slices it relied on most.
> 分数好还不够，模型还应该"因为对的理由而答对"。所以我们用了 Grad-CAM，它用红色标出决定每个预测的区域。这三个测试病例模型都判对了，而且很有把握，所以我们以为红色会落在感染部位上。每个病例展示模型最依赖的四张切片。

It does not. In all three, the red sits on the heart and central airways, not on the lung shadows. The model may be relying on anatomy or scanner details — something that could fail at a new hospital. And every prediction says one point zero, so the model is overconfident. We see both as warning signs found early, exactly the kind of problem a baseline should expose before we spend weeks on experiments, and D will explain what we do about them.
> 但并没有。三个病例的红色都在心脏和中央气道上，而不是肺部阴影上。模型可能依赖的是解剖结构或扫描设备的细节——换到新医院就可能失效。另外每个预测都是 1.00，模型过度自信。我们把这两点视为尽早发现的警示信号，这正是基线应该在我们花几周做实验之前暴露出来的问题，接下来由 D 讲我们怎么处理。

## Slide 12 · Speaker D
Thank you. We treat the baseline as a diagnosis. Each row in this table is a problem we saw, what it suggests, and what we will change.
> 谢谢。我们把基线当作一次诊断。表格的每一行是一个看到的问题、它说明了什么，以及我们要改什么。

The training–validation gap means the network memorises our training patients, so we add augmentation and regularisation. Grad-CAM on the heart means we mask out everything except the lungs. Weak fusion means the 64 clinical numbers are drowned out by 512 image numbers, so we will train the two models separately and combine their probabilities. This late fusion is part of Experiment 2. And overconfidence means we calibrate before building the "uncertain" flag. And the crop bug we already fixed reminds us to keep checking the preprocessing.
> 训练和验证的差距，说明网络在死记训练病人，所以要加强数据增强和正则化。Grad-CAM 盯着心脏，说明要把肺以外的区域全部遮掉。融合效果弱，说明 64 个临床数值被 512 个图像数值淹没了，所以我们会分别训练两个模型，再把它们的概率结合起来。这种晚期融合属于实验二。过度自信，就要在做"不确定"提示之前先校准概率。而已经修好的裁剪问题提醒我们，要持续检查预处理。

The arrows show the order, and the order matters. We fix the data first, because every later result depends on it — fixing it later would mean redoing everything. Then the data experiment, then the model experiment, and the test set only at the very end.
> 箭头表示执行顺序，而顺序很重要。先修数据，因为之后所有结果都依赖它——晚改就意味着全部重做。然后做数据实验，再做模型实验，测试集放在最后。

Three rules keep this honest: if the data changes, we re-run everything; augmentation is not extra patients; and today's test numbers were only a first look. If we kept checking the test set while tuning, we would slowly fit our choices to those {n_test} scans, and the final score would look better than it really is.
> 有三条规则保证严谨：数据一改就全部重跑；数据增强不等于增加病人；今天的测试集数字只是初步一看。如果调参时一直看测试集，我们的选择会慢慢迁就这 {n_test} 例，最终分数会比真实水平好看。

## Slide 13 · Speaker D
Finally, what users will see and when. On the left is our interface with a real case: the CT viewer with an optional saliency overlay, the clinical record, the three probabilities, and an "uncertain" message when the model is unsure.
> 最后讲用户会看到什么、什么时候做到。左边是用一个真实病例展示的界面：带可选热力图叠加层的 CT 查看器、临床记录、三类概率，以及模型没把握时的"不确定"提示。

The timeline follows the same order: fixes in week one, the data experiment in week two, the model experiment in weeks three and four together with the severity definition, the interface in week five, and the final test and report in week six. For severity, one simple option is the share of lung that is denser than normal, which needs no extra labels; we will agree it with our supervisor. The main risks — a small dataset, repeat scans and missing lesion masks — each have a mitigation listed below.
> 时间线按同样的顺序：第 1 周修复，第 2 周数据实验，第 3、4 周模型实验并确定严重程度的定义，第 5 周做界面，第 6 周最终测试和报告。关于严重程度，一个简单的方案是计算肺内密度高于正常的区域占比，不需要额外标注；具体会和导师商定。主要风险——数据量小、重复扫描、缺少病灶标注——下方都列了应对方式。

## Slide 14 · Speaker D
To sum up: these infections are hard to tell apart, and we want to know whether CT plus clinical data can do it. The data and pipeline are ready, the baseline runs, and it has shown us exactly what to fix next. Thank you — we are happy to take your questions.
> 总结一下：这几种感染很难区分，我们想知道 CT 加临床数据能不能做到。数据和流程已经就绪，基线已经跑通，而且它明确告诉了我们下一步要修什么。谢谢大家，欢迎提问。
