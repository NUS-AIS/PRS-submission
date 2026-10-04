"""Patient-level CT classifier: ImageNet ResNet-18 on K 2.5D slices -> mean-pool -> head.

--mode ct      CT-only baseline
--mode fusion  CT features ⊕ clinical-MLP features -> MLP head (proposal §6)

Model selected on validation macro F1; test evaluated once with that checkpoint.
Usage: python train_ct.py --mode ct --seed 0
"""
import argparse
import json
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from torchvision.models import ResNet18_Weights, resnet18

from common import BINARY, CATEGORICAL, NUMERIC, RESULTS, ROOT, SPLIT_CSV, load_clinical

p = argparse.ArgumentParser()
p.add_argument("--mode", choices=["ct", "fusion"], default="ct")
p.add_argument("--seed", type=int, default=0)
p.add_argument("--epochs", type=int, default=25)
p.add_argument("--bs", type=int, default=8)
p.add_argument("--lr", type=float, default=1e-4)
p.add_argument("--aug", choices=["none", "basic"], default="basic")
p.add_argument("--freeze", action="store_true", help="freeze the whole ResNet backbone; train only the heads")
args = p.parse_args()

torch.manual_seed(args.seed)
np.random.seed(args.seed)
dev = "cuda"
PROC = ROOT / "data" / "processed"

df = load_clinical().join(pd.read_csv(SPLIT_CSV, index_col=0)["split"])
pre = ColumnTransformer([
    ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), NUMERIC),
    ("bin", "passthrough", BINARY),
    ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
])
pre.fit(df.loc[df.split == "train", NUMERIC + BINARY + CATEGORICAL])  # train-only statistics
clin = pre.transform(df[NUMERIC + BINARY + CATEGORICAL]).astype(np.float32)
clin = pd.DataFrame(clin, index=df.index)

MEAN = torch.tensor([0.485, 0.456, 0.406], device=dev).view(1, 1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225], device=dev).view(1, 1, 3, 1, 1)


class Cases(torch.utils.data.Dataset):
    def __init__(self, split):
        self.ids = df.index[df.split == split].tolist()
        self.x = {i: np.load(PROC / f"Case{i:03d}.npy") for i in self.ids}  # ~2.4 MB each, fits in RAM

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, j):
        i = self.ids[j]
        return torch.from_numpy(self.x[i]), torch.from_numpy(clin.loc[i].values), int(df.label[i]), i


def augment(x):
    """basic: small rotation (±10°) + translation (±5%), same transform for all slices of a case."""
    b = x.shape[0]
    ang = (torch.rand(b, device=dev) * 2 - 1) * np.deg2rad(10)
    t = (torch.rand(b, 2, device=dev) * 2 - 1) * 0.1  # grid units: 0.1 = 5% of the image
    cos, sin = torch.cos(ang), torch.sin(ang)
    theta = torch.stack([torch.stack([cos, -sin, t[:, 0]], 1), torch.stack([sin, cos, t[:, 1]], 1)], 1)
    k = x.shape[1]
    theta = theta.repeat_interleave(k, 0)
    flat = x.flatten(0, 1)
    grid = F.affine_grid(theta, flat.shape, align_corners=False)
    return F.grid_sample(flat, grid, align_corners=False, padding_mode="zeros").view_as(x)


class Net(nn.Module):
    def __init__(self, fusion, n_clin):
        super().__init__()
        bb = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        bb.fc = nn.Identity()
        self.bb, self.fusion = bb, fusion
        d = 512
        if fusion:
            self.clin = nn.Sequential(nn.Linear(n_clin, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 64), nn.ReLU())
            d += 64
        self.head = nn.Sequential(nn.Dropout(0.3), nn.Linear(d, 128), nn.ReLU(), nn.Dropout(0.3), nn.Linear(128, 3))

    def forward(self, x, c):
        b, k = x.shape[:2]
        f = self.bb(x.flatten(0, 1)).view(b, k, -1).mean(1)  # slice features -> patient feature
        if self.fusion:
            f = torch.cat([f, self.clin(c)], 1)
        return self.head(f)


loaders = {s: torch.utils.data.DataLoader(Cases(s), batch_size=args.bs, shuffle=(s == "train"), num_workers=0)
           for s in ("train", "val", "test")}
model = Net(args.mode == "fusion", clin.shape[1]).to(dev)
if args.freeze:
    for prm in model.bb.parameters():
        prm.requires_grad = False
counts = np.bincount(df.label[df.split == "train"], minlength=3)
w = torch.tensor(counts.sum() / (3 * counts), dtype=torch.float32, device=dev)  # inverse class frequency
crit = nn.CrossEntropyLoss(weight=w)
opt = torch.optim.AdamW([q for q in model.parameters() if q.requires_grad], lr=args.lr, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
scaler = torch.cuda.amp.GradScaler()


def prep(x):
    return ((x.to(dev).float() / 255) - MEAN) / STD


@torch.no_grad()
def predict(split):
    model.eval()
    ys, ps, ids = [], [], []
    for x, c, y, i in loaders[split]:
        with torch.autocast("cuda", dtype=torch.float16):
            ps.append(model(prep(x), c.to(dev)).float().softmax(1).cpu())
        ys += y.tolist()
        ids += i.tolist()
    return np.array(ys), torch.cat(ps).numpy(), ids


if __name__ == "__main__":
    tag = f"{args.mode}_aug-{args.aug}_seed{args.seed}" + (f"_frozen-lr{args.lr:g}" if args.freeze else "")
    ckpt = ROOT / "runs" / f"{tag}.pt"
    ckpt.parent.mkdir(exist_ok=True)
    best, hist = -1, []
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        if args.freeze:
            model.bb.eval()  # frozen means BatchNorm running statistics stay at their ImageNet values too
        tot = 0
        for x, c, y, _ in loaders["train"]:
            x = prep(x)
            if args.aug == "basic":
                x = augment(x)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = crit(model(x, c.to(dev)), y.to(dev))
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tot += loss.item() * len(y)
        sched.step()
        yv, pv, _ = predict("val")
        f1 = f1_score(yv, pv.argmax(1), average="macro")
        hist.append({"epoch": ep, "train_loss": tot / len(loaders["train"].dataset), "val_f1": f1})
        if f1 > best:
            best = f1
            torch.save(model.state_dict(), ckpt)
        print(f"ep {ep:2d} loss {hist[-1]['train_loss']:.3f} val F1 {f1:.3f} (best {best:.3f}) {time.time() - t0:.0f}s",
              flush=True)

    model.load_state_dict(torch.load(ckpt))
    yt, pt, ids = predict("test")
    pred = pt.argmax(1)
    out = {"args": vars(args), "best_val_f1": best, "test_macro_f1": f1_score(yt, pred, average="macro"),
           "test_balanced_acc": balanced_accuracy_score(yt, pred),
           "test_recall_per_class": recall_score(yt, pred, average=None).tolist(),
           "test_cm": confusion_matrix(yt, pred, labels=[0, 1, 2]).tolist(), "history": hist,
           "train_minutes": (time.time() - t0) / 60}
    (RESULTS / f"{tag}.json").write_text(json.dumps(out, indent=2))
    pd.DataFrame(pt, index=ids, columns=["p0", "p1", "p2"]).assign(y=yt).to_csv(RESULTS / f"{tag}_test_probs.csv")
    print(json.dumps({k: v for k, v in out.items() if k != "history"}, indent=1))
