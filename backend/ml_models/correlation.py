"""
Dataset influence / correlation analysis.

If a trained Random Forest model is available for the target dataset,
signed feature importances are returned (magnitude = RF importance,
sign = Pearson r direction).  Otherwise falls back to raw Pearson r.

Frontend receives Chart.js-ready {labels, values, type, interpretation}.
"""
import os
import warnings

import numpy as np
import joblib
import rasterio
from rasterio.errors import NotGeoreferencedWarning

SAVED_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


def _read_pixels(path: str, max_n: int = 3000) -> np.ndarray | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data = src.read(1, masked=True)
        arr = data.compressed().astype(float)
        if len(arr) == 0:
            return None
        if len(arr) > max_n:
            step = max(1, len(arr) // max_n)
            arr = arr[::step][:max_n]
        return arr
    except Exception:
        return None


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a, b = a[:n], b[:n]
    if np.std(a) < 1e-6 or np.std(b) < 1e-6:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def correlation_model(selected: dict) -> dict:
    from backend.ml_models.utils import LOCAL_REGISTRY, DEPTH_ORDER

    ds_name = selected.get("internal_name", "")
    files = selected.get("local_files", {})
    primary = next(
        (files[b] for b in DEPTH_ORDER if b in files),
        next(iter(files.values()), None),
    )
    ref_pixels = _read_pixels(primary)

    # --- Pearson r for all other datasets ---
    pearson_r: dict[str, float] = {}
    for name, entry in LOCAL_REGISTRY.items():
        if entry["display"] == selected["name"]:
            continue
        other_files = entry.get("local_files", {})
        other_primary = next(
            (other_files[b] for b in DEPTH_ORDER if b in other_files),
            next(iter(other_files.values()), None),
        )
        other_pixels = _read_pixels(other_primary)
        if ref_pixels is not None and other_pixels is not None:
            pearson_r[entry["display"]] = round(_pearson(ref_pixels, other_pixels), 3)

    # --- RF feature importances (if model trained) ---
    rf_path = os.path.join(SAVED_DIR, f"{ds_name}_rf.joblib")
    if os.path.isfile(rf_path):
        try:
            payload = joblib.load(rf_path)
            rf_model = payload["model"]
            feat_names: list[str] = payload["features"]
            rf_step = rf_model.named_steps.get("rf")
            if rf_step is not None:
                importances = rf_step.feature_importances_
                labels, values = [], []
                for feat, imp in zip(feat_names, importances):
                    r = pearson_r.get(feat, 0.0)
                    signed = float(imp) * (1.0 if r >= 0 else -1.0)
                    labels.append(feat)
                    values.append(round(signed, 4))
                # Sort by absolute value descending
                pairs = sorted(zip(labels, values), key=lambda x: abs(x[1]), reverse=True)
                labels, values = zip(*pairs) if pairs else ([], [])
                return {
                    "dataset": selected["name"],
                    "labels": list(labels),
                    "values": list(values),
                    "type": "rf_importance_signed",
                    "interpretation": (
                        "Bar length = how strongly each dataset drives this one. "
                        "Green (+) = increases together · Red (−) = inverse relationship."
                    ),
                }
        except Exception:
            pass

    # Fall back to Pearson r
    pairs = sorted(pearson_r.items(), key=lambda x: abs(x[1]), reverse=True)
    return {
        "dataset": selected["name"],
        "labels": [p[0] for p in pairs],
        "values": [p[1] for p in pairs],
        "type": "pearson_r",
        "interpretation": (
            "Pearson correlation coefficient. "
            "Green (+) = increases together · Red (−) = inverse relationship. "
            "Train models for richer RF-based analysis."
        ),
    }


