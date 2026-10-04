# PRS_project · Group 26

多模态肺部感染分类：胸部 CT + 临床信息 → 曲霉 / 其他真菌 / 非真菌。数据集是 PAC569（NGDC OMIX014539，569 例）。

## 分支

| 分支 | 内容 |
|---|---|
| `main` | 初始空仓库 |
| `baseline` | 数据处理流程、基线模型、冻结实验、首次答辩材料 |

拉取方式：

```
git fetch origin
git switch baseline
```

## 仓库里有什么

| 路径 | 内容 |
|---|---|
| `src/` | 全部代码：解压、预处理、划分、训练、Grad-CAM、出图、生成 PPT 和报告 |
| `data/splits.csv` | 固定的训练 / 验证 / 测试划分（按病人组，seed 42），**不要重新划分** |
| `data/raw/OMIX014539-08.csv` | 临床数据表（原始文件，28 KB） |
| `results/` | 所有结果的 JSON / CSV |
| `figures/` | PPT 和报告用到的图 |
| `script/` | 讲稿源文件（v1–v4）和问答预案 |
| `template/base.pptx` | 生成 PPT 用的模板 |
| `Group 26_..._First Presentation.pptx` | 首次答辩 PPT（14 页，演讲备注里是 v4 讲稿） |
| `Group 26_Speaker Script_v4 final 15-min (EN-ZH).md` | 正式讲稿（15 分钟，中英对照）；v1 是严格计时版，v3 是不限时的参考版 |
| `Frozen vs Fine-tuned Backbone.md` | 冻结骨干 vs 全部微调的对比实验报告 |

## 不在 git 里的大文件

| 文件 | 大小 | 怎么获取 |
|---|---|---|
| 原始 CT（3 个 zip） | 13 GB | 自己下载，见下文第 2 步 |
| 预处理后的切片 `data/processed/*.npy` | 约 1.3 GB | GitHub **Releases → `baseline-v1`** 下载 `processed_npy.zip`，解压到 `data/processed/` |
| 模型权重 `runs/*.pt` | 约 520 MB | 同一个 Release 下载 `models.zip`，解压到 `runs/` |

用 gh 命令行下载：

```
gh release download baseline-v1 -R NUS-AIS/PRS_project
```

**有了 `data/processed/`，不需要原始 CT 也能直接训练。** 只有修改预处理代码时，才需要原始 CT。

## 当前结果（未调参的基线）

测试集 macro-F1（随机猜约 0.33）：

| 模型 | 结果 |
|---|---|
| 只用临床（随机森林，5 折交叉验证） | 0.569 ± 0.035 |
| 只用 CT（ResNet-18，3 个种子） | **0.642 ± 0.014** |
| CT + 临床融合（3 个种子） | 0.618 ± 0.020 |
| 只用 CT，冻结骨干 | 0.468 ± 0.022（欠拟合，见 `Frozen vs Fine-tuned Backbone.md`） |

几点说明：
- 融合暂时没有超过只用 CT。
- Grad-CAM 显示模型的注意力在纵隔一带，不在病灶上，下一步要遮掉肺以外的区域。
- 之后比较方案只看验证集或交叉验证，**测试集留到最后**。

## 环境

`pip install -r requirements.txt`。PyTorch 请按自己的 CUDA 版本，从 pytorch.org 安装。开发环境是 Python 3.12、RTX 4060 Laptop（8 GB 显存）。

## 复现步骤

从 Release 拿到 `data/processed/` 的话，可以直接从第 5 步开始。

1. **装依赖：** 见上面「环境」。
2. **下载原始 CT：** 从 https://ngdc.cncb.ac.cn/omix/release/OMIX014539 下载 `OMIX014539-03/04/05.zip`，放进 `data/raw/`。推荐用 FTP（地址 `download.cncb.ac.cn`，路径 `/OMIX/OMIX014539/`），也可以用 `curl -C - -O https://download.cncb.ac.cn/OMIX/OMIX014539/OMIX014539-03.zip`。
3. **解压：** `python src/extract_ct.py`，会解压到 `data/ct/`，并输出每个扫描的尺寸信息。
4. **预处理：** `python src/ct_preprocess.py 8`，生成 `data/processed/`，8 个进程约 4 分钟。
5. **临床基线：** `python src/clinical_baseline.py`
6. **训练：** `bash src/run_ct_baselines.sh`。只用 CT 和融合各跑 3 个种子，之后自动做 Grad-CAM、出图、生成 PPT，总共约 25 分钟。单独跑一次：`python src/train_ct.py --mode ct --seed 0`；冻结骨干加 `--freeze --lr 1e-3`。
7. **报告：** `python src/report_freeze.py` 生成冻结对比报告；`python src/build_deck.py` 重新生成 PPT 和讲稿。

## 协作约定

- 不重新划分数据，所有人都用 `data/splits.csv`。
- 改了预处理（比如遮肺），要重跑基线再比较。
- 比较方案只看验证集或交叉验证，测试集每个最终配置只用一次。
- 大文件不进 git，需要时更新 Release。
