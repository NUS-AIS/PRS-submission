"""Inference for the historical baseline, without importing its training entry point."""
from functools import lru_cache
import json
import threading

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import resnet18
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import ROOT, RESULTS, SPLIT_CSV, NUMERIC, BINARY, CATEGORICAL, load_clinical

LABELS = ['Aspergillus infection', 'Other fungal infection', 'Non-fungal infection']
LOCK = threading.Lock()
torch.set_num_threads(4)


def catalog():
    records = []
    for mode in ('ct', 'fusion'):
        for seed in range(3):
            tag = f'{mode}_aug-basic_seed{seed}'
            checkpoint, result = ROOT / 'runs' / f'{tag}.pt', RESULTS / f'{tag}.json'
            if checkpoint.is_file() and result.is_file():
                r = json.loads(result.read_text())
                records.append(dict(id=tag, mode=mode, seed=seed,
                    name=f'{"CT only" if mode == "ct" else "Multimodal fusion"} · seed {seed}',
                    **{k: r[k] for k in ('history', 'best_val_f1', 'test_macro_f1', 'test_balanced_acc', 'test_cm')}))
    return records


@lru_cache(maxsize=1)
def clinical_setup():
    df = load_clinical().join(pd.read_csv(SPLIT_CSV, index_col=0)['split'])
    pre = ColumnTransformer([
        ('num', make_pipeline(SimpleImputer(strategy='median'), StandardScaler()), NUMERIC),
        ('bin', 'passthrough', BINARY),
        ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL),
    ])
    pre.fit(df.loc[df.split == 'train', NUMERIC + BINARY + CATEGORICAL])
    return df, pre


class Net(nn.Module):
    def __init__(self, fusion, n_clin):
        super().__init__()
        self.bb = resnet18(weights=None)
        self.bb.fc = nn.Identity()
        self.fusion = fusion
        if fusion:
            self.clin = nn.Sequential(nn.Linear(n_clin, 64), nn.ReLU(), nn.Dropout(.2), nn.Linear(64, 64), nn.ReLU())
        self.head = nn.Sequential(nn.Dropout(.3), nn.Linear(576 if fusion else 512, 128), nn.ReLU(), nn.Dropout(.3), nn.Linear(128, 3))

    def forward(self, x, c):
        b, k = x.shape[:2]
        features = self.bb(x.flatten(0, 1)).view(b, k, -1).mean(1)
        if self.fusion:
            features = torch.cat([features, self.clin(c)], 1)
        return self.head(features)


@lru_cache(maxsize=2)
def load_model(tag):
    available = {r['id']: r for r in catalog()}
    if tag not in available:
        raise ValueError('Select an available trained model.')
    df, pre = clinical_setup()
    n = pre.transform(df.iloc[:1][NUMERIC + BINARY + CATEGORICAL]).shape[1]
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = Net(available[tag]['mode'] == 'fusion', n)
    model.load_state_dict(torch.load(ROOT / 'runs' / f'{tag}.pt', map_location='cpu', weights_only=True), strict=True)
    return model.to(device).eval(), device


def clinical_vector(values):
    row = {}
    for name in NUMERIC:
        val = values.get(name)
        row[name] = np.nan if val is None or val == '' else float(val)
        if not np.isnan(row[name]) and (not np.isfinite(row[name]) or row[name] < 0):
            raise ValueError(f'{name} must be a non-negative number or left blank.')
    if not np.isnan(row['Age']) and row['Age'] > 120:
        raise ValueError('Age must be between 0 and 120.')
    for name in BINARY:
        if values.get(name) not in (0, 1):
            raise ValueError(f'Please specify {name}. This model has no unknown encoding for binary fields.')
        row[name] = int(values[name])
    if values.get('Gender') not in ('M', 'F'):
        raise ValueError('Please specify sex as encoded by the training dataset (M/F).')
    row['Gender'] = values['Gender']
    _, pre = clinical_setup()
    return pre.transform(pd.DataFrame([row])[NUMERIC + BINARY + CATEGORICAL]).astype(np.float32)


def infer(stack, tag, values, explain=True):
    if stack.shape != (16, 3, 224, 224) or stack.dtype != np.uint8:
        raise ValueError('Unexpected preprocessed input.')
    with LOCK:
        model, device = load_model(tag)
        if model.fusion:
            c = torch.from_numpy(clinical_vector(values)).to(device)
        else:
            c = torch.zeros(1, 1, device=device)
        x = torch.from_numpy(stack.copy())[None].to(device).float() / 255
        mean = x.new_tensor([.485, .456, .406]).view(1, 1, 3, 1, 1)
        std = x.new_tensor([.229, .224, .225]).view(1, 1, 3, 1, 1)
        x = (x - mean) / std
        features = []
        hook = model.bb.layer4.register_forward_hook(lambda m, i, o: features.append(o)) if explain else None
        try:
            with torch.set_grad_enabled(explain), torch.autocast(device_type=device, dtype=torch.float16, enabled=device == 'cuda'):
                logits = model(x, c)
            probs = logits.detach().float().softmax(1)[0].cpu().numpy()
            cam = None
            if explain:
                activation = features[0]
                gradient = torch.autograd.grad(logits[0, int(probs.argmax())], activation)[0]
                cam = F.relu((gradient.float().mean((2, 3), keepdim=True) * activation.float()).sum(1))
                cam = F.interpolate(cam[:, None], (224, 224), mode='bilinear', align_corners=False)[:, 0]
                cam = (cam / cam.max().clamp_min(1e-8)).detach().cpu().numpy()
            return dict(probabilities=probs.tolist(), predicted_class=LABELS[int(probs.argmax())],
                        model=tag, device=device, calibrated=False), cam
        finally:
            if hook:
                hook.remove()
