#!/usr/bin/env bash
# CT-only and fusion models, 3 seeds each, then Grad-CAM and a deck rebuild.
set -eo pipefail
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
for seed in 0 1 2; do
  for mode in ct fusion; do
    echo "=== $mode seed $seed ==="
    python train_ct.py --mode "$mode" --seed "$seed" 2>&1 | grep -v -i warning
  done
done
cd .. && python src/gradcam.py runs/fusion_aug-basic_seed0.pt
cd src && python fig_results.py && python build_deck.py
echo "ALL DONE"
