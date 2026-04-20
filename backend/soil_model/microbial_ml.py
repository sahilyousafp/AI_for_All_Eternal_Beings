"""
ML-based microbial indicator prediction.

Loads the trained RandomForest models produced by
`backend/ml_models/train_microbial.py` and provides a vectorised prediction
function that matches the old formula-based `compute_all_indicators` API.

Prediction uncertainty
----------------------
We report the standard deviation of predictions across the individual trees
in each RandomForest as an honest uncertainty measure. This captures
disagreement between the trees, which grows when the input is in a poorly-
sampled region of feature space.

Graceful degradation
--------------------
If the saved models are missing (e.g. on first deploy before training),
this module falls back to the formula-based predictors in
`microbial_indicators.py`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any

import numpy as np

try:
    import joblib
except ImportError:
    joblib = None

_MODELS_DIR = Path(__file__).parent.parent / "ml_models" / "saved_models"
_MODELS: Dict[str, Any] = {}
_METADATA: Dict[str, Any] = {}
_LOADED = False


def _try_load() -> bool:
    """Attempt to load the 4 saved models + metadata."""
    global _LOADED, _MODELS, _METADATA
    if _LOADED:
        return True
    if joblib is None:
        return False
    try:
        for name in ("mbc", "fb", "qco2", "amf"):
            path = _MODELS_DIR / f"microbial_{name}.joblib"
            if not path.is_file():
                return False
            _MODELS[name] = joblib.load(path)
        meta_path = _MODELS_DIR / "microbial_metadata.json"
        if meta_path.is_file():
            with open(meta_path) as f:
                _METADATA = json.load(f)
        _LOADED = True
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[microbial_ml] Failed to load models: {exc}")
        return False


def is_available() -> bool:
    """True iff the ML path is ready to use."""
    return _try_load()


def get_metadata() -> dict:
    """Return training metadata + feature importance for the API/frontend."""
    _try_load()
    return _METADATA


# ──────────────────────────────────────────────────────────────────────────
#  Feature builder — keep in sync with train_microbial.FEATURE_NAMES
# ──────────────────────────────────────────────────────────────────────────

_SPECIES_ORDER = ["holm_oak", "maquis", "agroforestry", "eucalyptus", "annual_crop"]

def _build_features(
    soc_g_kg: np.ndarray,
    clay_pct: np.ndarray,
    sand_pct: np.ndarray,
    soil_ph: np.ndarray,
    temp_c: float,
    precip_mm: float,
    canopy_cover: np.ndarray,
    tillage: bool,
    fert_n_kg_ha: float,
    species: str | None,
    biochar: bool,
    compost: bool,
    cover_crops: bool,
    moisture_ratio: np.ndarray,
) -> np.ndarray:
    """
    Build a (n_cells, 18) feature matrix matching the training data layout.
    18 features: 9 physical + 5 species + 3 amendments + 1 moisture_ratio.
    """
    soc   = np.asarray(soc_g_kg, dtype=float).ravel()
    clay  = np.asarray(clay_pct, dtype=float).ravel()
    sand  = np.asarray(sand_pct, dtype=float).ravel()
    ph    = np.asarray(soil_ph, dtype=float).ravel()
    can   = np.asarray(canopy_cover, dtype=float).ravel()
    mr    = np.asarray(moisture_ratio, dtype=float).ravel()
    n = soc.shape[0]

    feats = np.zeros((n, 18), dtype=float)
    feats[:, 0] = soc
    feats[:, 1] = clay
    feats[:, 2] = sand
    feats[:, 3] = ph
    feats[:, 4] = float(temp_c)
    feats[:, 5] = float(precip_mm)
    feats[:, 6] = can
    feats[:, 7] = 1.0 if tillage else 0.0
    feats[:, 8] = float(fert_n_kg_ha)

    sp_name = species if species in _SPECIES_ORDER else "annual_crop"
    sp_col  = 9 + _SPECIES_ORDER.index(sp_name)
    feats[:, sp_col] = 1.0

    feats[:, 14] = 1.0 if biochar     else 0.0
    feats[:, 15] = 1.0 if compost     else 0.0
    feats[:, 16] = 1.0 if cover_crops else 0.0

    # Broadcast moisture_ratio: may come as scalar, per-cell, or wrong-shaped
    if mr.shape[0] == n:
        feats[:, 17] = np.clip(mr, 0.05, 1.0)
    elif mr.shape[0] == 1:
        feats[:, 17] = float(np.clip(mr[0], 0.05, 1.0))
    else:
        feats[:, 17] = float(np.clip(mr, 0.05, 1.0).mean())

    return feats


def _predict_with_uncertainty(model, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (mean, std) prediction per row using the RF's ensemble of trees."""
    tree_preds = np.stack([est.predict(X) for est in model.estimators_], axis=0)
    return tree_preds.mean(axis=0), tree_preds.std(axis=0)


def predict_all(
    soc_surface_g_kg: np.ndarray,
    clay_pct: np.ndarray,
    sand_pct: np.ndarray,
    soil_ph: np.ndarray,
    temperature_c: float,
    precip_mm: float,
    canopy_cover: np.ndarray,
    philosophy_params: dict,
    moisture_ratio: np.ndarray | float = 0.5,
) -> dict:
    """
    Main ML prediction entry point. Mirrors the formula-based
    compute_all_indicators output shape so the engine can swap between them.

    Returns
    -------
    dict with keys:
        mbc_g_kg, fb_ratio, qco2, amf_pct           — mean predictions
        mbc_std, fb_std, qco2_std, amf_std          — per-cell uncertainties
        living_soil_index                           — composite 0–100
        feature_importance                          — dict per target
        model_r2                                    — dict per target
    """
    if not _try_load():
        raise RuntimeError("Microbial ML models not loaded — run train_microbial.py first.")

    species = philosophy_params.get("species")
    tillage = bool(philosophy_params.get("tillage", False))
    fert_n  = float(philosophy_params.get("fertilizer_N_kg_ha_yr", 0.0))
    amendments = set(philosophy_params.get("amendments") or [])
    biochar_flag     = "biochar"    in amendments
    compost_flag     = "compost"    in amendments
    cover_crops_flag = "cover_crops" in amendments

    # Broadcast moisture_ratio scalar → per-cell array if needed
    if np.isscalar(moisture_ratio):
        mr_arr = np.full_like(np.asarray(soc_surface_g_kg, dtype=float).ravel(), float(moisture_ratio))
    else:
        mr_arr = np.asarray(moisture_ratio, dtype=float).ravel()

    X = _build_features(
        soc_g_kg=soc_surface_g_kg,
        clay_pct=clay_pct,
        sand_pct=sand_pct,
        soil_ph=soil_ph,
        temp_c=temperature_c,
        precip_mm=precip_mm,
        canopy_cover=canopy_cover,
        tillage=tillage,
        fert_n_kg_ha=fert_n,
        species=species,
        biochar=biochar_flag,
        compost=compost_flag,
        cover_crops=cover_crops_flag,
        moisture_ratio=mr_arr,
    )

    mbc_mean,  mbc_std  = _predict_with_uncertainty(_MODELS["mbc"],  X)
    fb_mean,   fb_std   = _predict_with_uncertainty(_MODELS["fb"],   X)
    qco2_mean, qco2_std = _predict_with_uncertainty(_MODELS["qco2"], X)
    amf_mean,  amf_std  = _predict_with_uncertainty(_MODELS["amf"],  X)

    # Clip to physically meaningful ranges
    mbc_mean  = np.clip(mbc_mean,  0.01, 3.0)
    fb_mean   = np.clip(fb_mean,   0.05, 2.5)
    qco2_mean = np.clip(qco2_mean, 0.1, 10.0)
    amf_mean  = np.clip(amf_mean,  0.0, 85.0)

    # Living Soil Index composite (same weights as formula path)
    mbc_norm  = np.clip(mbc_mean / 1.5, 0, 1) * 100
    fb_norm   = np.clip(fb_mean  / 1.5, 0, 1) * 100
    qco2_norm = np.clip(1.0 - (qco2_mean - 0.5) / 3.0, 0, 1) * 100
    amf_norm  = np.clip(amf_mean / 60.0, 0, 1) * 100
    lsi = 0.40 * mbc_norm + 0.25 * fb_norm + 0.15 * qco2_norm + 0.20 * amf_norm
    lsi = np.clip(lsi, 0.0, 100.0)

    # Pull training metadata for feature importance / R²
    fi = {}
    r2 = {}
    targets = (_METADATA or {}).get("targets", {})
    for name in ("mbc", "fb", "qco2", "amf"):
        t = targets.get(name, {})
        fi[name] = t.get("feature_importance", {})
        r2[name] = t.get("r2_test")

    return {
        "mbc_g_kg":          mbc_mean,
        "fb_ratio":          fb_mean,
        "qco2":              qco2_mean,
        "amf_pct":           amf_mean,
        "mbc_std":           mbc_std,
        "fb_std":            fb_std,
        "qco2_std":          qco2_std,
        "amf_std":           amf_std,
        "living_soil_index": lsi,
        "feature_importance": fi,
        "model_r2":          r2,
    }
