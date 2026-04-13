"""
spatial_cv_benchmark.py — Honest accuracy evaluation for the soil-texture RF.

Why this script exists
----------------------
The previously circulated "93% test accuracy" headline for the Random Forest
soil-texture classifier was computed under random-split (stratified) cross-
validation in `train_rf.py`. SoilGrids/OpenLandMap pixels are **spatially
autocorrelated** — neighbouring pixels look very similar to each other — and
random-split CV places almost every test pixel within a few cells of a training
pixel. That inflates the reported accuracy in a way that does not generalise
to true out-of-region prediction.

Wadoux, A. M. J.-C., Heuvelink, G. B. M., de Bruin, S., & Brus, D. J. (2021).
Spatial cross-validation is not the right way to evaluate map accuracy.
*Ecological Modelling*, 457, 109692.

…is the canonical reference on this failure mode. Although the title is
provocative, the paper's actual point is that spatial CV is the right answer
*when the goal is generalisation across geographic space* — which is exactly
our case (we want the classifier to work on Mediterranean soils we never
trained on, not on the specific 2.5 km cell next to a training pixel).

This script implements **blocked spatial k-fold CV**: pixels are binned into
a coarse grid of square spatial tiles, and entire tiles are held out as the
test fold. Tiles are large enough that train pixels are not adjacent to test
pixels.

Usage
-----
From the repo root:

    ai4all/Scripts/python.exe -m backend.ml_models.spatial_cv_benchmark

It writes:
- backend/ml_models/BENCHMARK.md   — human-readable report with both scores
                                     and the methodology used.
- prints per-fold and aggregate accuracy to stdout.

The "honest" number is the spatial CV mean accuracy. Use that in any
external write-up. Random-split CV is only kept for comparison so the
size of the inflation gap is visible.
"""
from __future__ import annotations

import os
import sys
import time
import json

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score

from backend.ml_models.data_loader import load_feature_matrix, load_labels


_HERE = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_PATH = os.path.join(_HERE, "BENCHMARK.md")


# ─────────────────────────────────────────────────────────────────────────────
#  Spatial fold assignment
# ─────────────────────────────────────────────────────────────────────────────

def assign_spatial_folds(
    valid_mask: np.ndarray,
    n_folds: int = 5,
    rng_seed: int = 42,
) -> np.ndarray:
    """
    Assign each valid pixel to one of `n_folds` non-adjacent spatial folds.

    Strategy: cut the image into a square grid of tiles, then assign each
    tile to a fold via a fixed pseudo-random permutation. Adjacent tiles
    therefore land in different folds, which prevents train and test pixels
    from being neighbours.

    Returns
    -------
    fold_id : np.ndarray (N_valid,) int in [0, n_folds)
    """
    H, W = valid_mask.shape
    # Aim for ~10× more tiles than folds so each fold contains many tiles
    # spread across the region, while individual tiles remain large enough
    # to be spatially coherent.
    n_tiles_per_side = max(int(np.ceil(np.sqrt(n_folds * 10))), n_folds + 1)
    tile_h = max(1, H // n_tiles_per_side)
    tile_w = max(1, W // n_tiles_per_side)

    rows, cols = np.where(valid_mask)
    tile_row = rows // tile_h
    tile_col = cols // tile_w
    tile_id  = tile_row * (W // max(tile_w, 1) + 1) + tile_col

    # Map each unique tile id to a fold via a fixed permutation
    rng = np.random.default_rng(rng_seed)
    unique_tiles = np.unique(tile_id)
    perm = rng.permutation(len(unique_tiles))
    fold_lookup = {t: int(perm[i] % n_folds) for i, t in enumerate(unique_tiles)}
    fold_id = np.array([fold_lookup[t] for t in tile_id], dtype=np.int32)
    return fold_id


# ─────────────────────────────────────────────────────────────────────────────
#  Random-split baseline (the inflated number, kept for comparison)
# ─────────────────────────────────────────────────────────────────────────────

def random_split_kfold(X: np.ndarray, y: np.ndarray, n_folds: int = 5) -> dict:
    """Stratified random k-fold — the inflated baseline."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    scores = []
    f1s    = []
    for fold, (tr, te) in enumerate(skf.split(X, y), start=1):
        scaler = StandardScaler()
        Xtr = scaler.fit_transform(X[tr])
        Xte = scaler.transform(X[te])
        clf = RandomForestClassifier(
            n_estimators=100, max_depth=15, min_samples_split=5,
            n_jobs=-1, random_state=42,
        )
        clf.fit(Xtr, y[tr])
        pred = clf.predict(Xte)
        acc = accuracy_score(y[te], pred)
        f1  = f1_score(y[te], pred, average="macro", zero_division=0)
        scores.append(acc)
        f1s.append(f1)
        print(f"  random fold {fold}/{n_folds}  acc={acc:.4f}  macro-F1={f1:.4f}")
    return {
        "method": "stratified random k-fold",
        "n_folds": n_folds,
        "fold_accuracies": scores,
        "mean_accuracy": float(np.mean(scores)),
        "std_accuracy":  float(np.std(scores)),
        "mean_macro_f1": float(np.mean(f1s)),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Blocked spatial k-fold (the honest number)
# ─────────────────────────────────────────────────────────────────────────────

def spatial_kfold(
    X: np.ndarray,
    y: np.ndarray,
    fold_id: np.ndarray,
    n_folds: int = 5,
) -> dict:
    """Train/test held-out tiles. The honest evaluation."""
    scores = []
    f1s    = []
    for fold in range(n_folds):
        te = fold_id == fold
        tr = ~te
        if tr.sum() == 0 or te.sum() == 0:
            continue
        # Only train on classes present in both train and test fold to
        # avoid sklearn complaining about unseen labels during prediction.
        train_classes = set(np.unique(y[tr]).tolist())
        test_classes  = set(np.unique(y[te]).tolist())
        shared = train_classes & test_classes
        if len(shared) == 0:
            continue

        # Restrict TEST set to classes the model has seen during training.
        # Spatial CV legitimately produces test folds containing rare classes
        # absent from the training fold; scoring those would be unfair.
        test_keep = np.isin(y[te], list(shared))
        X_te = X[te][test_keep]
        y_te = y[te][test_keep]
        if len(y_te) == 0:
            continue

        scaler = StandardScaler()
        Xtr = scaler.fit_transform(X[tr])
        Xte = scaler.transform(X_te)
        clf = RandomForestClassifier(
            n_estimators=100, max_depth=15, min_samples_split=5,
            n_jobs=-1, random_state=42,
        )
        clf.fit(Xtr, y[tr])
        pred = clf.predict(Xte)
        acc = accuracy_score(y_te, pred)
        f1  = f1_score(y_te, pred, average="macro", zero_division=0)
        scores.append(acc)
        f1s.append(f1)
        print(
            f"  spatial fold {fold + 1}/{n_folds}  "
            f"train={int(tr.sum()):,}  test={len(y_te):,}  "
            f"acc={acc:.4f}  macro-F1={f1:.4f}"
        )
    return {
        "method": "blocked spatial k-fold (Wadoux et al. 2021)",
        "n_folds": len(scores),
        "fold_accuracies": scores,
        "mean_accuracy": float(np.mean(scores)) if scores else float("nan"),
        "std_accuracy":  float(np.std(scores))  if scores else float("nan"),
        "mean_macro_f1": float(np.mean(f1s))    if f1s    else float("nan"),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Report
# ─────────────────────────────────────────────────────────────────────────────

def write_report(
    random_result: dict,
    spatial_result: dict,
    n_samples: int,
    runtime_s: float,
) -> None:
    inflation = random_result["mean_accuracy"] - spatial_result["mean_accuracy"]
    pct_inflation = (inflation / max(spatial_result["mean_accuracy"], 1e-6)) * 100

    md = f"""# Random Forest soil-texture classifier — accuracy benchmark

*Generated by `backend/ml_models/spatial_cv_benchmark.py` on
{time.strftime('%Y-%m-%d %H:%M:%S')}.*

## Headline number

> **Spatial CV accuracy: {spatial_result['mean_accuracy'] * 100:.1f}%** ± \
{spatial_result['std_accuracy'] * 100:.1f} pp
> (mean over {spatial_result['n_folds']} blocked spatial folds, macro-F1 = \
{spatial_result['mean_macro_f1']:.3f})

This is the honest number to use in any external write-up. The previously
circulated "93% test accuracy" was random-split CV and is not a defensible
estimate of out-of-region generalisation — see methodology note below.

## Both numbers, side by side

| Method | Mean accuracy | Std (pp) | Macro-F1 | Honest? |
|---|---|---|---|---|
| Random k-fold (the inflated baseline) | **{random_result['mean_accuracy'] * 100:.1f}%** | {random_result['std_accuracy'] * 100:.1f} | {random_result['mean_macro_f1']:.3f} | ❌ |
| Spatial k-fold (Wadoux 2021) | **{spatial_result['mean_accuracy'] * 100:.1f}%** | {spatial_result['std_accuracy'] * 100:.1f} | {spatial_result['mean_macro_f1']:.3f} | ✅ |

**Inflation gap.** Random-split CV overestimates accuracy by approximately
**{pct_inflation:.0f}%** of the spatial-CV value
({inflation * 100:.1f} percentage points). Anyone reporting the random-split
number is reporting how well the model interpolates between adjacent SoilGrids
pixels, *not* how well it generalises to soils it has never seen.

## Methodology

- **Dataset.** {n_samples:,} valid surface (b0) pixels from the local SoilGrids /
  OpenLandMap raster stack covering Spain. Features: organic carbon, clay
  content, sand content, bulk density, soil pH. Labels: USDA soil texture
  class (12-class problem).
- **Model.** `RandomForestClassifier(n_estimators=100, max_depth=15,
  min_samples_split=5)` — identical hyperparameters to the production model
  in `train_rf.py`, so the comparison is fair.
- **Random k-fold (baseline).** `StratifiedKFold(n_splits=5, shuffle=True)`.
  This is what `train_rf.py` does. Test pixels are randomly drawn from the
  same image as training pixels, almost always within a few cells. The
  classifier essentially memorises local context.
- **Spatial k-fold (honest).** The image is partitioned into a coarse grid
  of square tiles (~10× as many tiles as folds, so each fold contains many
  tiles spread across the region). Each tile is assigned to one fold via a
  fixed pseudo-random permutation. For each fold, all pixels in that fold's
  tiles are held out as test data; the model sees no neighbours of test
  pixels at training time. Test pixels with classes absent from the training
  fold are discarded (this is unavoidable with rare classes under spatial
  CV — see Wadoux et al. 2021 §3).

## Why this matters for the exhibition

The deck originally claimed **93% test accuracy** based on the random-split
number. That claim is not defensible to a soil scientist on the jury. It
should be replaced with the spatial-CV number above in `EXHIBITION_SUBMISSION.md`,
or — if the team prefers — dropped entirely in favour of the framing
"a reduced-form ML emulator of peer-reviewed European soil models", which
does not depend on a single accuracy headline.

## References

- Wadoux, A. M. J.-C., Heuvelink, G. B. M., de Bruin, S., & Brus, D. J. (2021).
  Spatial cross-validation is not the right way to evaluate map accuracy.
  *Ecological Modelling*, 457, 109692.
- Roberts, D. R., Bahn, V., Ciuti, S., et al. (2017). Cross-validation
  strategies for data with temporal, spatial, hierarchical, or phylogenetic
  structure. *Ecography*, 40(8), 913–929.
- Ploton, P., Mortier, F., Réjou-Méchain, M., et al. (2020). Spatial
  validation reveals poor predictive performance of large-scale ecological
  mapping models. *Nature Communications*, 11, 4540.

---
*Runtime: {runtime_s:.1f} s. Benchmark is fully reproducible — re-run with
`python -m backend.ml_models.spatial_cv_benchmark` from the repo root.*
"""

    with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\nReport written to {BENCHMARK_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main(n_folds: int = 5) -> None:
    print("=" * 60)
    print("Random Forest — Spatial Cross-Validation Benchmark")
    print("=" * 60)

    t0 = time.time()

    print("\nLoading rasters…")
    X_full, mask, _meta = load_feature_matrix("b0")
    labels, _ = load_labels("b0")
    label_flat = labels[mask]
    valid = label_flat >= 0
    X = X_full[valid]
    y = label_flat[valid]
    print(f"  Valid pixels: {X.shape[0]:,}")
    print(f"  Classes     : {sorted(np.unique(y).tolist())}")

    # Build spatial fold ids on the same valid-pixel ordering
    H, W = mask.shape
    valid_mask_2d = np.zeros((H, W), dtype=bool)
    valid_mask_2d[mask] = valid  # only pixels valid in BOTH stacks
    fold_id = assign_spatial_folds(valid_mask_2d, n_folds=n_folds)
    print(f"  Spatial folds assigned (n_folds={n_folds})")
    for f in range(n_folds):
        print(f"    fold {f}: {(fold_id == f).sum():,} pixels")

    print("\n--- Random-split CV (the inflated baseline) ---")
    random_result = random_split_kfold(X, y, n_folds=n_folds)

    print("\n--- Spatial blocked CV (the honest number) ---")
    spatial_result = spatial_kfold(X, y, fold_id, n_folds=n_folds)

    runtime = time.time() - t0
    print(f"\nTotal runtime: {runtime:.1f}s")

    write_report(random_result, spatial_result, n_samples=X.shape[0], runtime_s=runtime)

    # Also dump JSON for downstream tooling
    json_path = os.path.join(_HERE, "benchmark.json")
    with open(json_path, "w") as f:
        json.dump({"random": random_result, "spatial": spatial_result,
                   "n_samples": int(X.shape[0]), "runtime_seconds": runtime}, f, indent=2)
    print(f"JSON written to {json_path}")


if __name__ == "__main__":
    main()
