"""
Temporal inference: predict a dataset's mean value for any target year.

Fallback chain:
  1. {name}_temporal_best.joblib   (best model chosen by test-set RMSE during training)
  2. {name}_temporal_mlp.joblib    (MLP trained on full year series)
  3. {name}_temporal_ridge.joblib  (Ridge polynomial trained on full year series)
  4. Fit Ridge on-the-fly from TEMPORAL_REGISTRY if ≥ 3 years exist
  5. Depth-band proxy Ridge (soil datasets only)
  6. Static mean (last resort)

Output always includes:
  predicted_value  : float
  model            : str (which model was used)
  confidence_low   : float (approx 90% lower bound — 1.645 × train RMSE)
  confidence_high  : float
  year_range       : [min_year, max_year] of training data (or null)
  extrapolated     : bool (True if target year is outside training range)
  test_metrics     : dict | null  — {rmse, mae, r2} from held-out test set
"""
import os
import json
import warnings

import numpy as np
import joblib
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from backend.ml_models.utils import (
    TEMPORAL_REGISTRY, LOCAL_REGISTRY, DEPTH_ORDER, DEPTH_LABELS,
    temporal_primary_band, primary_band, available_years,
)

SAVED_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


def _read_mean(path: str | None, max_n: int = 2000) -> float | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data = src.read(1, masked=True)
        vals = data.compressed().astype(float)
        valid = vals[~np.isnan(vals)]
        if len(valid) == 0:
            return None
        if len(valid) > max_n:
            valid = np.random.default_rng(42).choice(valid, max_n, replace=False)
        return float(np.nanmean(valid))
    except Exception:
        return None


def _temporal_training_data(name: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Read (years, mean_values) from TEMPORAL_REGISTRY for a dataset."""
    year_data = TEMPORAL_REGISTRY.get(name, {})
    if len(year_data) < 2:
        return None
    X, y = [], []
    for yr in sorted(year_data.keys()):
        path = temporal_primary_band(name, yr)
        val  = _read_mean(path)
        if val is not None:
            X.append(float(yr))
            y.append(val)
    if len(X) < 2:
        return None
    return np.array(X).reshape(-1, 1), np.array(y)


def _fit_ridge_on_the_fly(X: np.ndarray, y: np.ndarray) -> Pipeline:
    pipeline = Pipeline([
        ('poly',  PolynomialFeatures(degree=2, include_bias=False)),
        ('ridge', Ridge(alpha=10.0)),
    ])
    pipeline.fit(X, y)
    return pipeline


def _load_metrics(dataset_name: str) -> dict | None:
    """Load saved test metrics JSON for a temporal dataset, if it exists."""
    path = os.path.join(SAVED_DIR, f"{dataset_name}_temporal_metrics.json")
    if os.path.isfile(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _confidence_band(residuals: np.ndarray, pred: float, factor: float = 1.645):
    """Simple approximate 90% CI from training residuals."""
    if len(residuals) < 2:
        margin = abs(pred) * 0.10
    else:
        margin = factor * float(np.std(residuals))
    return pred - margin, pred + margin


def predict_year(dataset_name: str, target_year: int, data_years: list[int] | None = None) -> dict:
    """
    Predict the mean value of `dataset_name` for `target_year`.

    Returns a dict compatible with the /api/infer response body.
    """
    years_with_data = data_years or available_years(dataset_name)
    extrapolated    = bool(years_with_data and (
        target_year < min(years_with_data) or target_year > max(years_with_data)
    ))
    year_range   = [min(years_with_data), max(years_with_data)] if years_with_data else None
    saved_metrics = _load_metrics(dataset_name)  # may be None for soil datasets

    def _best_test_metrics(model_key: str) -> dict | None:
        if saved_metrics and "models" in saved_metrics:
            return saved_metrics["models"].get(model_key)
        return None

    # ── 1. Try best model (selected by test-RMSE during training) ────────────
    best_path = os.path.join(SAVED_DIR, f"{dataset_name}_temporal_best.joblib")
    if os.path.isfile(best_path):
        try:
            bundle    = joblib.load(best_path)
            model     = bundle["model"]
            best_name = bundle.get("name", "Best")
            pred      = float(model.predict([[float(target_year)]])[0])
            pair      = _temporal_training_data(dataset_name)
            residuals = pair[1] - model.predict(pair[0]) if pair is not None else np.array([])
            lo, hi    = _confidence_band(residuals, pred)
            tm        = _best_test_metrics(best_name)
            return {
                "predicted_value": round(pred, 3),
                "model":           f"Temporal {best_name} (best)",
                "confidence_low":  round(lo, 3),
                "confidence_high": round(hi, 3),
                "year_range":      year_range,
                "extrapolated":    extrapolated,
                "test_metrics":    tm,
            }
        except Exception:
            pass

    # ── 2. Try saved temporal MLP ─────────────────────────────────────────────
    mlp_path = os.path.join(SAVED_DIR, f"{dataset_name}_temporal_mlp.joblib")
    if os.path.isfile(mlp_path):
        try:
            model = joblib.load(mlp_path)
            pred  = float(model.predict([[float(target_year)]])[0])
            pair  = _temporal_training_data(dataset_name)
            residuals = pair[1] - model.predict(pair[0]) if pair is not None else np.array([])
            lo, hi = _confidence_band(residuals, pred)
            return {
                "predicted_value": round(pred, 3),
                "model":           "Temporal MLP",
                "confidence_low":  round(lo, 3),
                "confidence_high": round(hi, 3),
                "year_range":      year_range,
                "extrapolated":    extrapolated,
                "test_metrics":    _best_test_metrics("MLP"),
            }
        except Exception:
            pass

    # ── 3. Try saved temporal Ridge ───────────────────────────────────────────
    ridge_path = os.path.join(SAVED_DIR, f"{dataset_name}_temporal_ridge.joblib")
    if os.path.isfile(ridge_path):
        try:
            model = joblib.load(ridge_path)
            pred  = float(model.predict([[float(target_year)]])[0])
            pair  = _temporal_training_data(dataset_name)
            residuals = pair[1] - model.predict(pair[0]) if pair is not None else np.array([])
            lo, hi = _confidence_band(residuals, pred)
            return {
                "predicted_value": round(pred, 3),
                "model":           "Temporal Ridge",
                "confidence_low":  round(lo, 3),
                "confidence_high": round(hi, 3),
                "year_range":      year_range,
                "extrapolated":    extrapolated,
                "test_metrics":    _best_test_metrics("Ridge"),
            }
        except Exception:
            pass

    # ── 4. Fit Ridge on-the-fly from TEMPORAL_REGISTRY ────────────────────────
    pair = _temporal_training_data(dataset_name)
    if pair is not None:
        X_tr, y_tr = pair
        model = _fit_ridge_on_the_fly(X_tr, y_tr)
        pred  = float(model.predict([[float(target_year)]])[0])
        residuals = y_tr - model.predict(X_tr)
        lo, hi = _confidence_band(residuals, pred)
        return {
            "predicted_value": round(pred, 3),
            "model":           "Ridge (on-the-fly, temporal)",
            "confidence_low":  round(lo, 3),
            "confidence_high": round(hi, 3),
            "year_range":      year_range,
            "extrapolated":    extrapolated,
            "test_metrics":    None,
        }

    # ── 5. Use depth-band trend (soil datasets) ────────────────────────────────
    entry = LOCAL_REGISTRY.get(dataset_name)
    if entry:
        files = entry.get('local_files', {})
        depth_cm = {"b0": 0, "b10": 10, "b30": 30, "b60": 60, "b100": 100, "b200": 200}
        pts = []
        for band, cm in depth_cm.items():
            if band in files:
                v = _read_mean(files[band])
                if v is not None:
                    pts.append((float(cm), v))
        if len(pts) >= 3:
            Xd = np.array([[x] for x, _ in pts])
            yd = np.array([v for _, v in pts])
            target_depth = float(max(0, target_year - 2025))
            model = _fit_ridge_on_the_fly(Xd, yd)
            pred  = float(model.predict([[target_depth]])[0])
            lo, hi = _confidence_band(yd - model.predict(Xd), pred)
            return {
                "predicted_value": round(pred, 3),
                "model":           "Ridge (depth-band proxy)",
                "confidence_low":  round(lo, 3),
                "confidence_high": round(hi, 3),
                "year_range":      [2025, 2025 + 200],
                "extrapolated":    True,
                "test_metrics":    None,
            }

    # ── 6. Last resort: static mean ───────────────────────────────────────────
    static_mean = None
    if entry:
        path = primary_band(entry)
        static_mean = _read_mean(path)
    val = static_mean or 0.0
    return {
        "predicted_value": round(val, 3),
        "model":           "Static mean (no temporal model)",
        "confidence_low":  round(val * 0.90, 3),
        "confidence_high": round(val * 1.10, 3),
        "year_range":      None,
        "extrapolated":    True,
        "test_metrics":    None,
    }
