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
    TEMPORAL_REGISTRY, DEPTH_ORDER, DEPTH_LABELS,
    temporal_primary_band, available_years,
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

    # No valid temporal model exists for this dataset.
    return {
        "supported":       False,
        "predicted_value": None,
        "model":           None,
        "confidence_low":  None,
        "confidence_high": None,
        "year_range":      year_range,
        "extrapolated":    True,
        "test_metrics":    None,
    }


def predict_spatial_year(
    dataset_name: str,
    target_year: int,
    lat_grid: "np.ndarray",
    lon_grid: "np.ndarray",
    ssp_scenario: str = "ssp245",
) -> "np.ndarray | None":
    """
    Predict pixel values for a 2-D lat/lon grid at target_year using the
    spatiotemporal XGBoost model trained by train_spatiotemporal().

    Parameters
    ----------
    dataset_name : str
        Name matching TEMPORAL_REGISTRY key (e.g. 'CHIRPS_Precipitation').
    target_year : int
        Calendar year to predict (e.g. 2045).
    lat_grid, lon_grid : np.ndarray, shape (rows, cols)
        Geographic coordinates of each grid cell.
    ssp_scenario : str
        One of 'ssp126', 'ssp245', 'ssp370', 'ssp585'. Determines climate deltas.

    Returns
    -------
    np.ndarray of same shape as lat_grid, or None if model unavailable.
    """
    path = os.path.join(SAVED_DIR, f"{dataset_name}_spatiotemporal.joblib")
    if not os.path.isfile(path):
        return None

    try:
        bundle = joblib.load(path)
        model  = bundle["model"]
    except Exception:
        return None

    # SSP climate delta lookup (same table as train_spatiotemporal)
    _SSP_DT = {
        "ssp126": {2000: -0.2, 2025: 0.3, 2050: 1.0, 2075: 1.2, 2100: 1.3},
        "ssp245": {2000: -0.2, 2025: 0.3, 2050: 1.5, 2075: 2.1, 2100: 2.7},
        "ssp370": {2000: -0.2, 2025: 0.4, 2050: 1.8, 2075: 2.7, 2100: 3.6},
        "ssp585": {2000: -0.2, 2025: 0.5, 2050: 2.4, 2075: 3.7, 2100: 5.0},
    }
    _SSP_DP = {
        "ssp126": {2000: 0.0, 2025: -0.03, 2050: -0.05, 2100: -0.05},
        "ssp245": {2000: 0.0, 2025: -0.07, 2050: -0.15, 2100: -0.20},
        "ssp370": {2000: 0.0, 2025: -0.08, 2050: -0.18, 2100: -0.28},
        "ssp585": {2000: 0.0, 2025: -0.10, 2050: -0.22, 2100: -0.35},
    }

    def _interp(table: dict, yr: int) -> float:
        keys = sorted(table.keys())
        if yr <= keys[0]:
            return table[keys[0]]
        if yr >= keys[-1]:
            return table[keys[-1]]
        for i in range(len(keys) - 1):
            if keys[i] <= yr <= keys[i+1]:
                t = (yr - keys[i]) / (keys[i+1] - keys[i])
                return table[keys[i]] + t * (table[keys[i+1]] - table[keys[i]])
        return 0.0

    scen = ssp_scenario if ssp_scenario in _SSP_DT else "ssp245"
    delta_T = _interp(_SSP_DT[scen], target_year)
    delta_P = _interp(_SSP_DP[scen], target_year) * 580.0  # fraction → mm/yr

    flat_lat = lat_grid.ravel()
    flat_lon = lon_grid.ravel()
    n = len(flat_lat)
    X = np.column_stack([
        np.full(n, float(target_year)),
        flat_lat,
        flat_lon,
        np.full(n, delta_T),
        np.full(n, delta_P),
    ])

    try:
        preds = model.predict(X)
        return preds.reshape(lat_grid.shape)
    except Exception:
        return None
