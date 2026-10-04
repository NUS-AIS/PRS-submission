# Group 26 — Speaker Script · 演讲稿 · v3 — reference narrative, no time limit · 参考版（完整叙述、不限时）

Timing assumes 120 spoken English words per minute. Numbers are filled from results/ by src/build_deck.py.
> 时长按每分钟 120 个英文词估算；所有数字由 src/build_deck.py 从结果文件自动填入。

| Speaker 讲者 | Topic 主题 | Slides 页 | Words 词数 | Time 时长 | Target 目标 |
|---|---|---|---|---|---|
| A | Background & data · 背景与数据 | 1–5 | 963 | 8:01 | — |
| B | Model · 模型 | 6–8 | 937 | 7:48 | — |
| C | Progress & results · 进展与结果 | 9–11 | 762 | 6:21 | — |
| D | Next steps · 下一步 | 12–14 | 732 | 6:06 | — |
| **Total** | | | **3394** | **28:17** | **—** |

> This version is a reference for understanding and rehearsal; it is longer than 15 minutes. Use v1 or v2 for timing.
> 这一版用于理解和排练，篇幅超过 15 分钟；控制时间请参考 v1 或 v2。

**The story in one paragraph · 一段话讲清整条故事线**

Three kinds of lung infection look alike on CT but need different treatment. We want to know whether a model that sees both the CT and a few routine clinical facts can tell them apart. We first studied the data, and what we found changed how we split and evaluate it. We then built a pipeline and a two-branch model, and ran one default baseline from start to finish. The baseline works — but it also revealed four problems: overfitting, attention on the wrong region, weak fusion and overconfidence. The rest of the project fixes these in a deliberate order, runs the three experiments our supervisor asked for, and only then touches the test set.
> 三种肺部感染在 CT 上看起来很像，但治疗方法不同。我们想知道：一个同时看 CT 和几项常规临床信息的模型，能不能把它们区分开。我们先研究了数据，发现的问题改变了我们划分和评估数据的方式。接着搭建了数据处理流程和一个双分支模型，并把一个默认配置的基线从头到尾跑通。基线能用，但也暴露了四个问题：过拟合、关注区域不对、融合效果弱、过度自信。项目剩下的部分，就是按既定顺序修复这些问题，完成导师要求的三组实验，最后才动用测试集。

**Who tells which part · 每个人讲故事的哪一段**

A sets up the question and the data — why the problem is hard and what we have to work with. B explains how we turn that data into a model and how we will judge it. C shows where we are and what the first run revealed. D explains what that means and what we will do next.
> A 提出问题、介绍数据：为什么难、我们手里有什么。B 讲怎么把数据变成模型、怎么评判模型。C 讲我们目前走到哪一步、第一次运行发现了什么。D 讲这些发现意味着什么、接下来怎么做。

## Slide 1 · Speaker A · ≈ 0:44

Good morning, everyone. We are Group 26: Lai Wendi, Tang Shiyan, Xia Yan and Zhou Jiasheng.
> 大家早上好，我们是第 26 组，成员有 Lai Wendi、Tang Shiyan、Xia Yan 和 Zhou Jiasheng。

Our project is a multimodal medical imaging assistant. In one sentence: we want to find out whether a model that looks at both a patient's chest CT and a few routine clinical facts can tell three kinds of lung infection apart.
> 我们的项目是一个多模态医学影像助手。一句话概括：我们想知道，一个同时看病人胸部 CT 和几项常规临床信息的模型，能不能区分三种肺部感染。

I will start with why this problem matters and what data we have. Then B will explain our model, C will show where we are, and D will explain what comes next.
> 我先讲这个问题为什么重要、我们有什么数据；然后 B 介绍模型，C 介绍目前的进展，D 讲接下来的计划。

## Slide 2 · Speaker A · ≈ 2:07

Let's begin with the clinical problem. On the left are six real CT slices from our dataset, two from each class. The first column is Aspergillus infection, the second is infection by other fungi, and the third is non-fungal pneumonia — usually bacterial or viral.
> 先从临床问题说起。左边是数据集里的六张真实 CT 切片，每类两张。第一列是曲霉感染，第二列是其他真菌感染，第三列是非真菌性肺炎，通常是细菌或病毒引起的。

If you try to tell the columns apart, you will find it very difficult. All of them show patches of white in the lungs — consolidation, nodules, ground-glass shadows. Radiologists face exactly this problem.
> 如果试着分辨这三列，会发现非常困难。它们的肺里都有白色斑片——实变、结节、磨玻璃影。放射科医生面对的正是这个难题。

Why does it matter? Because the three groups are treated differently. Each needs a different first-line drug, so if the first guess is wrong, the patient may wait days for the right treatment.
> 为什么这很重要？因为三类病人的治疗不同，一线用药各不相同。如果第一判断错了，病人可能要多等好几天才能用上对的药。

Doctors do not rely on the image alone. They also look at the patient: is the immune system weakened, are fungal markers positive in the blood? That gave us our hypothesis, shown at the bottom right: combining the CT with routine clinical information should classify these infections more reliably than either source alone.
> 医生不会只看影像，还会看病人本身：免疫功能是否低下？血液里的真菌标志物是否阳性？这就引出了我们的假设，在右下角：把 CT 和常规临床信息结合起来，应该比单独用任何一种都分得更准。

So our goal is a research prototype that reads one patient's CT and clinical record and returns a three-class prediction with a confidence score. It is meant to support a clinician, not to replace one.
> 所以我们的目标是做一个科研原型：读入一个病人的 CT 和临床记录，给出三分类预测和置信度。它是用来辅助医生的，不是取代医生。

From this goal come four objectives. First, classify the three infection types. Second, test the hypothesis by comparing CT only, clinical only and the combination. Third, explain each prediction by showing which lung regions the model relied on. And fourth, because our dataset is small, study what helps most: pre-training, more data, or data augmentation.
> 由这个目标引出四个具体目标：第一，区分三种感染；第二，通过比较只用 CT、只用临床和两者结合来检验假设；第三，展示模型依据了哪些肺部区域，解释每个预测；第四，因为我们的数据集很小，研究什么最有帮助——预训练、更多数据，还是数据增强。

## Slide 3 · Speaker A · ≈ 1:18

With the goal set, we defined what the prototype must do. The table on the left lists eight functional requirements.
> 目标确定之后，我们定义了原型需要具备的功能。左边的表格列出了八条功能需求。

The "must-haves" form the core pipeline: load a case, preprocess the CT, encode the clinical data, predict the three classes with probabilities, and show it all in a viewer. Next come the "should-haves": an "uncertain" flag when the model is not confident, and a saliency map showing where it looked. Severity is only a "could-have" — I will explain why in a moment, when we look at the data.
> "必须有"的部分构成核心流程：读入病例、预处理 CT、编码临床数据、输出三分类概率，并在一个查看界面里展示。其次是"应该有"的部分：模型没把握时给出"不确定"提示，以及显示模型关注区域的热力图。严重程度只是"可以有"——原因待会儿看数据时会讲到。

On the right are the pattern-recognition techniques we use: transfer learning from ImageNet, fusion of two data sources, classical machine-learning baselines, and Grad-CAM for explanation.
> 右边是我们用到的模式识别技术：基于 ImageNet 的迁移学习、两种数据来源的融合、传统机器学习基线，以及用于解释的 Grad-CAM。

It is just as important to be clear about what we will not do. This is a course prototype, so there is no clinical validation and no hospital deployment. And because the dataset has no lesion outlines, we will not attempt pixel-level segmentation.
> 同样重要的是说清楚我们不做什么。这是课程原型，所以不做临床验证，也不做医院部署。另外数据集没有病灶轮廓标注，我们也不做像素级的分割。

## Slide 4 · Speaker A · ≈ 1:40

Now the data. We use PAC569, a public dataset released in September 2026 by Wuxi People's Hospital through China's National Genomics Data Center. It contains 569 chest CT scans collected at four hospitals: 153 Aspergillus, 209 other fungal and 207 non-fungal cases. The classes are fairly balanced, which helps.
> 接下来是数据。我们使用 PAC569，这是无锡市人民医院于 2026 年 9 月通过国家基因组科学数据中心公开的数据集，包含来自四家医院的 569 例胸部 CT：曲霉 153 例、其他真菌 209 例、非真菌 207 例。三类比较均衡，这对我们有利。

Before doing anything else, we checked the data carefully. We downloaded all four files, about 13 gigabytes, and confirmed that every CT file has exactly one clinical record and that the labels agree. The scans are very uniform: all are 512 by 512 pixels with 5-millimetre slices, and each patient has between 31 and 81 slices. That uniformity makes preprocessing simpler — and the thick slices will matter later, when we choose the model.
> 在做任何事之前，我们先仔细核对了数据。我们下载了全部四个文件，约 13 GB，确认每个 CT 文件都恰好对应一条临床记录，标签也一致。图像非常统一：全部是 512×512 像素、层厚 5 毫米，每个病人有 31 到 81 层。这种统一让预处理简单很多；而层厚较厚这一点，之后选模型时会再用到。

Each clinical record has twelve usable variables: age and gender; comorbidities such as solid tumours, diabetes, kidney problems and AIDS; whether the patient takes immunosuppressants; two blood tests, lymphocyte count and D-dimer; and two fungal markers, the G test and the GM antigen. A thirteenth column has the same value for every patient, so we removed it.
> 每条临床记录有 12 个可用变量：年龄和性别；合并症，比如实体瘤、糖尿病、肾功能不全和艾滋病；是否使用免疫抑制剂；两项血液指标，淋巴细胞计数和 D-二聚体；以及两个真菌标志物，G 试验和 GM 抗原。还有第 13 列，所有病人的值都一样，我们把它删掉了。

Notice what is missing: there are no lesion outlines and no severity scores. That is why severity is only a "could-have".
> 也请注意缺了什么：没有病灶轮廓，也没有严重程度评分。这就是为什么严重程度只是"可以有"。

## Slide 5 · Speaker A · ≈ 2:10

Before building any model, we explored the data, and this changed several of our decisions. There are three findings I want to highlight.
> 在建任何模型之前，我们先做了数据探索，这改变了我们的好几个决定。我想重点讲三个发现。

The first is in the chart. Clinical risk factors do differ between the classes. For example, 39 of the 41 AIDS patients have a non-Aspergillus fungal infection, and the GM antigen is positive most often in Aspergillus cases. But every bar is well below 50 percent — no single marker separates the classes. So clinical data should help, but they cannot solve the problem alone. That supports combining them with the CT.
> 第一个发现在左边的图里。各类之间的临床危险因素确实不同，比如 41 个艾滋病患者中有 39 个是非曲霉真菌感染，GM 抗原阳性则在曲霉组最常见。但每根柱子都远低于 50%——没有任何单一指标能把三类分开。所以临床数据应该有帮助，但单靠它解决不了问题，这也支持把它和 CT 结合起来。

The second finding is a warning. The G test and the GM antigen are themselves used by doctors to diagnose fungal infection, so a model could simply learn to copy them. Throughout the project, we will therefore report results both with and without these two markers.
> 第二个发现是一个警示。G 试验和 GM 抗原本身就是医生诊断真菌感染的依据，模型可能只是学会了照抄它们。所以整个项目中，我们都会同时报告用和不用这两个指标的结果。

The third finding is on the right. 21 records are identical to the record just before them, with consecutive case numbers. These are very likely repeat scans of the same patient. If one scan went into training and the other into testing, the model would be tested on a patient it had already seen, and the score would be too optimistic. So we grouped these records into 548 patient groups, and every split keeps a group together.
> 第三个发现在右边。有 21 条记录和紧挨着的上一条完全相同，病例编号也是连续的，很可能是同一个病人的重复扫描。如果一次扫描进了训练集、另一次进了测试集，模型就等于在考它见过的病人，分数会偏高。所以我们把这些记录合并成 548 个病人组，每次划分都保证同组不拆开。

We also found a few smaller issues — 33 missing D-dimer values and some inconsistent coding — which we cleaned.
> 我们还发现了一些小问题，比如 33 个缺失的 D-二聚体值和一些编码不一致，都已经清理好了。

So by now we know the problem, the data and its traps. B will explain how we turn this data into a model.
> 到这里，我们已经清楚了问题、数据以及数据里的陷阱。接下来由 B 讲我们如何把这些数据变成模型。

## Slide 6 · Speaker B · ≈ 2:29

Thank you. My part is about how we go from raw scans to a trained model, and how we will judge it. I will start with the data pipeline, because a model can only be as good as its input.
> 谢谢。我负责讲怎么从原始扫描得到训练好的模型，以及怎么评判它。我先讲数据处理流程，因为输入的质量决定了模型的上限。

A CT scan is a stack of about sixty images, but a standard image network expects a single picture of a fixed size. So we process every scan in four steps, shown at the top.
> 一次 CT 扫描大约是六十张图像叠在一起，但标准的图像网络需要的是固定尺寸的单张图片。所以每个扫描都要经过上方所示的四个步骤。

First, a lung window. CT values are measured in Hounsfield units, and we keep the range that shows lung tissue best. Second, we find the lungs with a simple threshold, since healthy lung is mostly air. Third, we crop around the chest. Fourth, we take sixteen slices spread evenly from the bottom of the lungs to the top, so every patient gives the same number of images, however many slices they had. Each image combines three neighbouring slices as its red, green and blue channels, which gives the network a little information about depth.
> 第一步是肺窗：CT 的数值单位是 Hounsfield 单位，我们只保留最能显示肺组织的那段范围。第二步用一个简单的阈值找出肺部，因为健康的肺主要是空气。第三步围绕胸部裁剪。第四步从肺底到肺尖均匀取 16 张切片，这样不管原来有多少层，每个病人都给出相同数量的图像。每张图把相邻三层分别作为红、绿、蓝三个通道，让网络也能获得一点深度信息。

This pipeline also taught us a lesson. When we checked the crops, we found that 12 patients had been cropped to only one lung. These were the sickest patients: one lung was so consolidated that it no longer looked like air, so our threshold missed it. We fixed the crop so that both sides are always kept, and re-ran everything. All results today use the corrected version.
> 这个流程也给了我们一个教训。检查裁剪结果时，我们发现有 12 个病人只裁到了一侧肺。这些恰恰是病得最重的病人：一侧肺实变得太严重，已经不像空气了，所以阈值把它漏掉了。我们修改了裁剪方法，保证两侧肺都被保留，并重新跑了所有流程。今天展示的结果全部基于修正后的版本。

At the bottom is how we split the data: 70 percent for training, 15 for validation and 15 for testing. It is stratified, so each part has the same mix of classes, and it is done by patient group, as A explained, so no patient appears on both sides. Augmentation — small rotations and shifts — is applied only to the training set.
> 下方是数据划分：70% 训练、15% 验证、15% 测试。划分按类别分层，保证每一部分的类别比例相同；同时按 A 刚才讲的病人组来切分，保证同一个病人不会同时出现在两边。数据增强（小角度旋转和平移）只用在训练集上。

## Slide 7 · Speaker B · ≈ 2:04

Now the model itself. It has two branches, one for each kind of data.
> 下面是模型本身。它有两个分支，分别处理两种数据。

The top branch handles the CT. All sixteen images go through the same network, a ResNet-18. This network was pretrained on ImageNet, a large collection of everyday photos. With only about four hundred training patients, we cannot train a deep network from scratch, so we start from one that already knows how to detect edges, textures and shapes. Each slice becomes 512 numbers, and we average over the sixteen slices to get one summary for the patient.
> 上面的分支处理 CT。16 张图都送进同一个网络 ResNet-18。这个网络已经在 ImageNet——一个大规模日常照片数据集——上预训练过。我们只有大约 400 个训练病人，不可能从零训练一个深层网络，所以从一个已经会识别边缘、纹理和形状的网络开始。每张切片变成 512 个数，再对 16 张取平均，得到这个病人的一个综合特征。

The bottom branch handles the clinical record. Missing values are filled with the median from the training set, numbers are scaled, and categories are encoded — again using training data only, so no information leaks from the test set. A small two-layer network turns the record into 64 numbers.
> 下面的分支处理临床记录。缺失值用训练集的中位数填补，数值做标准化，类别变量做编码——同样只用训练集的数据，保证测试集的信息不会泄漏进来。然后一个两层的小网络把这条记录变成 64 个数。

On the right, the two summaries are joined, and a small classifier outputs the probability of each of the three classes. Separately, Grad-CAM uses the CT branch to show which regions drove the prediction.
> 在右边，两个综合特征拼接在一起，由一个小分类器输出三类各自的概率。另外，Grad-CAM 作用在 CT 分支上，用来显示是哪些区域驱动了预测。

Why not a full 3D network? Remember that the slices are five millimetres thick. Along that direction there is little fine detail for a 3D network to exploit. A 2D approach also lets us reuse pretrained weights directly, and it fits on our 8-gigabyte GPU.
> 为什么不用完整的 3D 网络？还记得层厚是 5 毫米吗？在这个方向上，3D 网络能利用的细节很少。用 2D 还能直接复用预训练权重，而且在我们 8 GB 的显卡上跑得动。

This design also makes our baselines easy and fair: CT-only simply removes the clinical branch, and clinical-only uses the clinical record with classical models. Everything else stays the same.
> 这样的设计也让基线模型简单而公平：只用 CT 的模型就是去掉临床分支，只用临床的模型就是用传统机器学习方法处理临床记录，其他部分都保持不变。

## Slide 8 · Speaker B · ≈ 3:15

Having a model is not enough — we also need a fair way to test our ideas. We organise every comparison into two experiments: one about the data that goes into the model, and one about the model itself.
> 有了模型还不够，我们还需要公平地检验自己的想法。我们把所有对比归成两组实验：一组关于输入模型的数据，一组关于模型本身。

Experiment 1, on the left, is about the data. First, preprocessing: for example, whether masking out everything outside the lungs helps. Second, augmentation: none, basic rotations and shifts, or an extended version that adds scaling, mild intensity changes, noise and random cut-outs. Third, training-set size: we train on 25, 50, 75 and 100 percent of the training patients, keeping validation and test fixed. If performance is still rising at 100 percent, more data would help.
> 左边的实验一关于数据。第一是预处理，比如把肺以外的区域遮掉是否有帮助。第二是数据增强：不增强、基础的旋转和平移，或者再加上缩放、轻微亮度变化、噪声和随机遮挡的扩展版本。第三是训练集规模：分别用 25%、50%、75% 和 100% 的训练病人训练，验证集和测试集保持不变。如果到 100% 时性能还在上升，就说明更多数据还会有帮助。

Experiment 2, on the right, is about the model. First, the input: CT only, clinical only, or both — this tests our hypothesis directly, and we also check the clinical model with and without the G and GM tests. Second, how to fuse the two sources: joining their features, as now, or combining the two models' predicted probabilities. Third, the backbone: ResNet-18 against the larger ResNet-50. And optionally, a two-step structure that first decides fungal or not, and then Aspergillus or other fungi, which mirrors how doctors decide on treatment.
> 右边的实验二关于模型。第一是输入：只用 CT、只用临床还是两者都用——这直接检验我们的假设，同时也会比较临床模型用和不用 G、GM 两项。第二是两种数据的融合方式：像现在这样拼接特征，或者把两个模型预测的概率结合起来。第三是骨干网络：ResNet-18 对比更大的 ResNet-50。另外还有一个可选方案：分两步，先判断是不是真菌，再区分曲霉和其他真菌，这和医生决定治疗的思路一致。

Our supervisor asked for three specific comparisons: a pre-trained baseline, training-set size, and augmentation. The orange tags show where each one sits, so all three are covered.
> 导师要求了三项具体对比：预训练基线、训练集规模和数据增强。橙色标签标出了每一项所在的位置，三项都覆盖到了。

The order matters. We run the data experiment first, and its best setting becomes the starting point for the model experiment. Within each, we change one thing at a time against the baseline — ResNet-18, all the training data and basic augmentation — so any difference can be traced to that one change. As the green bars show, the baseline is the only setting we have run so far; everything else is still ahead.
> 顺序很重要。先做数据实验，它的最佳设置作为模型实验的起点。每组实验内部，每次只相对基线改变一个因素——基线是 ResNet-18、全部训练数据、基础增强——这样任何差异都能归因到那一个改动上。正如绿色条所示，基线是目前唯一跑过的设置，其余的都还在后面。

Two more points about measurement. Our main metric is macro-F1, which gives each class equal weight, so a model cannot look good just by favouring the biggest class. And because the test set has only 83 scans, a single number would be noisy. So we run every setting three times with different random seeds, choose between options using validation data only, and use the test set just once for each final configuration.
> 关于评估还有两点。主要指标是 macro-F1，它给每一类相同的权重，模型不能靠偏向最大的那一类来获得好分数。另外，测试集只有 83 例，单次结果噪声会很大。所以每个配置都用不同的随机种子跑三次，只用验证集在方案之间做选择，测试集对每个最终配置只用一次。

With the plan clear, C will now show how far we have got.
> 计划讲清楚了，接下来由 C 介绍我们目前的进展。

## Slide 9 · Speaker C · ≈ 2:07

Thank you. To show where we are, we drew the whole project as six phases.
> 谢谢。为了说明我们走到了哪一步，我们把整个项目画成了六个阶段。

We have completed the first two. Phase zero is the data foundation: everything A described — checking, cleaning and grouping the data — and the pipeline B described. Phase one is the baseline: the default configuration from the previous slide, run from start to finish with three seeds.
> 我们完成了前两个阶段。阶段 0 是数据基础：包括 A 讲的数据核对、清洗和分组，以及 B 讲的处理流程。阶段 1 是基线：上一页那个默认配置，从头到尾完整跑通，用了三个随机种子。

I want to be precise about what this baseline is. It is not a tuned model, and it is not a result we would defend as final. Its job is to prove that the whole pipeline works end to end, and to give us a reference point for every experiment that follows. The real experiments — phases two to five, which contain most of the work — have not started yet.
> 我想准确说明基线的定位。它不是调过参的模型，也不是我们会当作最终结论的结果。它的作用是证明整个流程能端到端跑通，并为之后的每个实验提供参照点。真正的实验——阶段 2 到 5，也是工作量的大头——还没有开始。

Two practical notes. Everything is written as scripts, so every number on these slides can be regenerated from the raw data. And one baseline run takes about 3.3 minutes on a laptop GPU, so the full experiment plan, with three seeds per setting, is realistic.
> 补充两点实际情况。所有步骤都写成了脚本，这几页上的每个数字都能从原始数据重新生成。另外，在笔记本 GPU 上跑一次基线大约 3.3 分钟，所以每个配置跑三个种子的完整实验计划是现实可行的。

Even this first run already tells us something. Look at the curves at the bottom. On the left, the training loss falls almost to zero, to about 0.05. On the right, the validation score only climbs to about 0.59 to 0.63. In other words, the model learns the training patients almost perfectly but does much worse on patients it has not seen. Keep this gap in mind — it comes back on the next slides.
> 即使只是第一次运行，也已经说明了一些问题。请看下方的曲线：左边的训练损失几乎降到零，大约 0.05；右边的验证集分数只升到 0.59 到 0.63 左右。也就是说，模型几乎完美地学会了训练集里的病人，但对没见过的病人表现差很多。请记住这个差距，后面几页还会用到。

## Slide 10 · Speaker C · ≈ 2:04

Here are the baseline numbers. Everything is macro-F1; random guessing would score about 0.33.
> 这是基线的结果，指标都是 macro-F1，随机猜测大约是 0.33。

The first four rows use clinical data only. The best is a random forest, at about 0.57 in cross-validation; logistic regression and LightGBM reach 0.50 and 0.52. When we remove the G test and the GM antigen, the random forest drops by only 0.037. So the clinical model is genuinely using the other variables, not just copying the diagnostic tests — which answers the concern A raised earlier.
> 前四行只用临床数据。最好的是随机森林，交叉验证约 0.57；逻辑回归和 LightGBM 分别为 0.50 和 0.52。去掉 G 试验和 GM 抗原后，随机森林只下降 0.037。说明临床模型确实在利用其他变量，而不只是照抄诊断检查——这回答了 A 前面提出的担忧。

The CT-only ResNet-18 is our best model so far, at 0.642 plus or minus 0.014 on the test set; the plus-or-minus comes from the three seeds. Broken down by class, it correctly finds 67 percent of Aspergillus cases, 56 percent of other fungal cases and 71 percent of non-fungal cases.
> 只用 CT 的 ResNet-18 是目前最好的模型，测试集上为 0.642 ± 0.014，正负范围来自三个随机种子。分类别看，它能正确找出 67% 的曲霉病例、56% 的其他真菌病例和 71% 的非真菌病例。

The combined model reaches 0.618 plus or minus 0.020. So at this stage, adding clinical data does not improve on CT alone. That is not what our hypothesis predicted, and we report it as it is. D will explain why we think this happens and what we will change.
> 融合模型为 0.618 ± 0.020。也就是说，在现阶段，加入临床数据并没有比只用 CT 更好。这和我们的假设不一致，我们如实报告。D 会解释我们认为的原因，以及我们打算怎么改。

On the right is the confusion matrix of the combined model. Rows are the true class and columns are the prediction. The weakest class is other fungi: the most common mistake is predicting them as non-fungal, in 7 of 29 cases.
> 右边是融合模型的混淆矩阵，行是真实类别，列是预测类别。表现最弱的是其他真菌这一类：最常见的错误是把它们预测成非真菌，29 例中有 7 例。

Please read all of these numbers as a starting point from one untuned configuration. They tell us where we stand, not what the final system can do.
> 请把这些数字都看作一个未调参配置给出的起点。它们说明的是我们现在的位置，而不是最终系统能达到的水平。

## Slide 11 · Speaker C · ≈ 2:09

A score tells us how often the model is right. It does not tell us whether it is right for the right reason. So we also asked: where is the model looking?
> 分数只能告诉我们模型对的频率，却不能告诉我们它是不是因为对的理由而答对。所以我们还问了一个问题：模型到底在看哪里？

For this we used Grad-CAM. It looks at the last layer of the image network and measures which parts of the image most affect the score of the predicted class; red means a strong influence. We picked three test cases, one per class, that the model classified correctly and with high confidence, and for each we show the four slices it relied on most. If the model had learned what we hoped, the red should sit on the white patches of infection.
> 为此我们用了 Grad-CAM。它看的是图像网络的最后一层，衡量图像的哪些部分对预测类别的分数影响最大，红色表示影响强。我们挑了三个测试病例，每类一个，都是模型判断正确而且很有把握的；每个病例展示模型最依赖的四张切片。如果模型学到的是我们希望的东西，红色应该落在感染的白色斑片上。

It does not. In all three cases, the red sits in the middle of the chest — on the heart, the large vessels and the main airways — not on the patchy shadows in the outer lung. This suggests the model may be using anatomy or scanner-related details that happen to differ between the classes, instead of the infection itself. A model like that could fail as soon as it sees data from another hospital.
> 但实际上并没有。三个病例的红色都在胸部中央——心脏、大血管和主气道上——而不是外周肺野的斑片影上。这说明模型可能利用的是恰好在各类之间有差异的解剖结构或扫描设备相关的细节，而不是感染本身。这样的模型一换到另一家医院的数据，就可能失效。

There is a second warning: every one of these predictions has a probability of one point zero. The model is far too confident, which is a problem for the "uncertain" flag we promised.
> 还有第二个警示：这些预测的概率全都是 1.00。模型过于自信了，这会影响我们承诺的"不确定"提示功能。

We see this as a useful result. It is exactly the kind of problem a baseline should expose early, before we spend weeks on the main experiments. D will now explain what we will do about it.
> 我们认为这是一个有价值的发现。这正是基线应该尽早暴露的问题，最好在我们花几周做主体实验之前就发现。接下来由 D 讲我们打算怎么处理。

## Slide 12 · Speaker D · ≈ 3:15

Thank you. We treat the baseline as a diagnosis, and this slide turns what we saw into a plan. Each row of the table is one observation, what it suggests, and what we will change.
> 谢谢。我们把基线当作一次诊断，这一页把我们看到的问题变成行动计划。表格的每一行是一个观察、它说明什么，以及我们要改什么。

The first row is the gap C showed: near-zero training loss, but validation only around 0.63. The network is memorising our four hundred training patients. So we will strengthen augmentation — which is part of our data experiment — freeze part of the pretrained network so that fewer weights can overfit, and add regularisation.
> 第一行是 C 展示的差距：训练损失接近零，验证集却只有 0.63 左右。网络在死记我们大约 400 个训练病人。所以我们会加强数据增强（这也是数据实验的一部分），冻结预训练网络的一部分以减少能过拟合的参数，并加入正则化。

The second row is Grad-CAM pointing at the heart. So we will mask out everything outside the lungs before the image reaches the network. Then the model can only use lung tissue, and we will check again whether the red moves onto the lesions.
> 第二行是 Grad-CAM 指向心脏。所以我们会在图像送入网络之前，把肺以外的区域全部遮掉。这样模型只能利用肺组织，然后我们再检查红色是否转移到了病灶上。

The third row is the weak fusion. Our clinical summary has 64 numbers sitting next to 512 numbers from the CT, and with so few patients the classifier can easily ignore the smaller part. So we will try late fusion: train the CT model and the clinical model separately, then combine their predicted probabilities. That way neither source can drown the other out. This becomes part of the model experiment.
> 第三行是融合效果弱。临床特征只有 64 个数，旁边是 CT 的 512 个数，病人又这么少，分类器很容易忽略较小的那一部分。所以我们会尝试晚期融合：分别训练 CT 模型和临床模型，再把它们预测的概率结合起来。这样任何一方都不会被另一方淹没。这会作为模型实验的一部分。

The fourth row is overconfidence. We will calibrate the probabilities, for example with temperature scaling, before we build the "uncertain" flag.
> 第四行是过度自信。在做"不确定"提示之前，我们会先校准概率，比如用温度缩放的方法。

And the last row reminds us that the crop bug we already fixed was only found because we looked. We will keep that check in the pipeline.
> 最后一行提醒我们：已经修好的那个裁剪问题，是因为我们去检查了才发现的。我们会把这项检查保留在流程里。

The arrows at the bottom show the order, and the order matters. We fix the data first, because every later experiment depends on the input — if we changed it later, we would have to repeat everything. Then we fix the training, run the data experiment, and then the model experiment, which includes the new fusion. The test set comes last.
> 下方的箭头表示执行顺序，而顺序很重要。先修数据，因为之后所有实验都依赖输入——如果之后再改，所有实验都得重做。然后修训练，做数据实验，再做模型实验（包括新的融合方式），测试集放在最后。

Three rules keep this honest. If the data changes, we re-run everything, including the baseline. Augmentation is a training setting — it does not give us more patients. And today's test numbers were only a first look. From now on, every decision is made on validation data, because if we kept checking the test set while tuning, we would slowly fit our choices to those 83 scans, and our final number would look better than it really is.
> 有三条规则保证这个过程的严谨。数据一变，就全部重跑，包括基线。数据增强只是训练设置，并不等于有了更多病人。今天的测试集数字只是初步看一眼。从现在起，所有决定都基于验证集，因为如果调参时反复查看测试集，我们的选择就会慢慢迁就这 83 例，最终分数会比真实水平好看。

## Slide 13 · Speaker D · ≈ 2:08

Finally, what the user will see, and when we will get there.
> 最后讲用户将会看到什么，以及我们什么时候能做到。

On the left is a mock-up of the interface, using a real case from the dataset. The CT viewer lets the user scroll through slices and switch on the saliency overlay to see what the model looked at. Next to it are the patient's clinical record and the predicted probability for each class. If the model is not confident enough, it will say so with an "uncertain" message. And it states clearly that it is a research prototype, not a diagnostic tool. The probabilities shown here are only illustrative.
> 左边是界面草图，用的是数据集里的一个真实病例。CT 查看器可以翻看切片，也可以打开热力图叠加层，看模型关注了哪里。旁边是病人的临床记录和每一类的预测概率。如果模型把握不够，会显示"不确定"。界面上还明确标注这是科研原型，不是诊断工具。图中的概率只是示意。

On the right is the six-week timeline, which follows the same order as the previous slide. Week one: lung masking and regularisation, then re-run the baseline and check Grad-CAM again. Week two: the data experiment — preprocessing, augmentation and training-set size. Weeks three and four: the model experiment — input, fusion, backbone and the optional fungal-first structure — together with the severity estimate.
> 右边是六周的时间线，顺序和上一页一致。第 1 周：遮肺和正则化，然后重跑基线、重新检查 Grad-CAM。第 2 周：数据实验——预处理、数据增强和训练集规模。第 3、4 周：模型实验——输入组合、融合方式、骨干网络，以及可选的「先分是否真菌」结构，同时确定严重程度的估计方法。

For severity, one simple option is the share of the lung that is denser than normal, which needs no extra labels; we will agree the definition with our supervisor. Week five covers the interface and calibration, and week six the final test-set runs, error analysis and the report.
> 关于严重程度，一个简单的方案是计算肺内密度高于正常的区域所占的比例，不需要额外标注；具体定义会和导师商定。第 5 周做界面和概率校准，第 6 周做最终的测试集运行、错误分析和报告。

Below are our main risks and how we handle them: the small dataset, through pre-training, augmentation and repeated runs; repeat scans, through the group split; missing lesion masks, by treating saliency maps as qualitative; and the open severity definition, by keeping it a stretch goal.
> 下方是主要风险及应对方式：数据量小，靠预训练、数据增强和多次重复运行来应对；重复扫描，靠按病人组划分；缺少病灶标注，把热力图当作定性参考；严重程度的定义尚未确定，就把它作为加分目标。

## Slide 14 · Speaker D · ≈ 0:42

To sum up: three kinds of lung infection are hard to tell apart, and we want to know whether CT plus clinical data can do it. We have prepared and checked the data, built the full pipeline, and run one baseline. That baseline works, and it has shown us exactly what to fix: overfitting, where the model looks, how we fuse the two sources, and overconfidence. The main experiments start now, in that order.
> 总结一下：三种肺部感染很难区分，我们想知道 CT 加临床数据能不能做到。我们已经准备并核对了数据，搭好了完整的流程，跑通了一个基线。这个基线能用，而且明确告诉了我们要修什么：过拟合、模型关注的位置、两种数据的融合方式，以及过度自信。主体实验从现在开始，按这个顺序进行。

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
