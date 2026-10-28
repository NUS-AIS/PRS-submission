"""Predicted-logit Grad-CAM for CT-only and fusion networks."""
import io
import time
from contextlib import contextmanager

import numpy as np
import torch
from torch.nn import functional as F
from PIL import Image


@contextmanager
def capture_features(layer):
    """Release the hook even when forward or explanation fails."""
    features = []
    hook = layer.register_forward_hook(lambda module, args, output: features.append(output))
    try:
        yield features
    finally:
        hook.remove()


def gradcam(logits, activation, size=(224, 224)):
    """Differentiate the final (possibly fused) predicted logit, never probabilities."""
    if logits.shape != (1, 3) or not torch.isfinite(logits).all():
        raise ValueError('Expected one finite three-class prediction.')
    target = int(logits.detach().argmax(1).item())
    gradients = torch.autograd.grad(logits[0, target], activation)[0]
    weights = gradients.float().mean((2, 3), keepdim=True)
    maps = F.relu((weights * activation.float()).sum(1))
    maps = F.interpolate(maps[:, None], size, mode='bilinear', align_corners=False)[:, 0]
    if not torch.isfinite(maps).all():
        raise ValueError('Explanation contains non-finite values.')
    return (maps / maps.max().clamp_min(1e-8)).detach().cpu().numpy()


def explain_forward(model, x, clinical, device, explain, diagnostics=None):
    """Return unchanged logits plus optional maps; caller serializes model access."""
    with torch.set_grad_enabled(explain), torch.autocast(
        device_type=device, dtype=torch.float16, enabled=device == 'cuda'
    ):
        if not explain:
            return model(x, clinical), None
        with capture_features(model.bb.layer4) as features:
            logits = model(x, clinical)
            if device == 'cuda':
                torch.cuda.synchronize()
            started = time.perf_counter()
            maps = gradcam(logits, features[0], tuple(x.shape[-2:]))
            if diagnostics is not None:
                diagnostics.update(
                    gradcam_ms=round((time.perf_counter() - started) * 1000, 3),
                    target_class_index=int(logits.detach().argmax(1).item()),
                    layer='bb.layer4',
                    zero_signal_positions=np.flatnonzero(~maps.any(axis=(1, 2))).tolist(),
                    sampled_positions=int(len(maps)),
                )
            return logits, maps


def explanation_status(cam):
    if cam is None:
        return 'not_requested'
    if not np.isfinite(cam).all():
        raise ValueError('Explanation contains non-finite values.')
    return 'available' if np.any(cam > 0) else 'zero_signal'


def render_png(gray, cam=None, opacity=.55):
    """Render cached model input; opacity changes never run inference."""
    if not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('Opacity must be a finite number between 0 and 1.')
    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(float)
    if cam is not None:
        if cam.shape != gray.shape or not np.isfinite(cam).all():
            raise ValueError('Invalid explanation image.')
        cam = np.clip(cam, 0, 1)
        alpha = opacity * cam[:, :, None]
        heat = np.stack([np.full_like(cam, 255), 210 * (1-cam), np.zeros_like(cam)], axis=2)
        rgb = rgb * (1-alpha) + heat * alpha
    buffer = io.BytesIO()
    Image.fromarray(rgb.clip(0, 255).astype('uint8')).save(buffer, format='PNG')
    return buffer.getvalue()
