"""
Train ML models from local GeoTIFF data.

Models trained per dataset:
  {name}_ridge.joblib          — Ridge + PolynomialFeatures on depth profile
  {name}_mlp.joblib            — MLPRegressor on depth profile
  {name}_rf.joblib             — RandomForestRegressor cross-dataset influence model
  {name}_temporal_ridge.joblib — Ridge on (year → spatial mean), requires ≥6 years
  {name}_temporal_mlp.joblib   — MLP  on (year → spatial mean), requires ≥6 years
  {name}_spatiotemporal.joblib — XGBoost spatiotemporal (year, lat, lon, dT, dP) → value

Run standalone:
  python -m backend.ml_models.train
"""
import os
import warnings

import numpy as np
import joblib
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from backend.ml_models.utils import DEPTH_ORDER, LOCAL_REGISTRY, TEMPORAL_REGISTRY

from sklearn.model_selection import LeaveOneOut, cross_val_predict
try:
    from xgboost import XGBRegressor
    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False

SAVED_DIR = os.path.join(os.path.dirname(__file__), "saved_models")

# Depth band → depth in cm
DEPTH_CM = {"b0": 0, "b10": 10, "b30": 30, "b60": 60, "b100": 100, "b200": 200}

# Maximum pixels sampled per band to keep training fast
_MAX_PER_BAND = 5000
_MAX_CROSS = 10000  # pixels for cross-dataset RF model
_MAX_SPATIO = 5000   # pixels sampled per year for spatiotemporal model


# ── Utility ──────────────────────────────────────────────────────────────────

def _read_pixels(path: str, max_n: int = _MAX_PER_BAND) -> np.ndarray | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data = src.read(1, masked=True)
        arr = data.compressed().astype(np.float32)
        if len(arr) == 0:
            return None
        if len(arr) > max_n:
            step = max(1, len(arr) // max_n)
            arr = arr[::step][:max_n]
        return arr
    except Exception:
        return None


def _read_mean_pixels(path: str, max_n: int = _MAX_SPATIO) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Read (values, lats, lons) arrays from a raster, sampling up to max_n pixels."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data = src.read(1, masked=True)
                transform = src.transform
        mask = ~np.ma.getmaskarray(data)
        rows_idx, cols_idx = np.where(mask)
        vals = data.data[rows_idx, cols_idx].astype(np.float64)
        valid = np.isfinite(vals)
        rows_idx, cols_idx, vals = rows_idx[valid], cols_idx[valid], vals[valid]
        if len(vals) == 0:
            return None
        if len(vals) > max_n:
            rng = np.random.default_rng(42)
            idx = rng.choice(len(vals), max_n, replace=False)
            rows_idx, cols_idx, vals = rows_idx[idx], cols_idx[idx], vals[idx]
        # Convert pixel indices to geographic coordinates
        xs, ys = rasterio.transform.xy(transform, rows_idx, cols_idx)
        lons = np.array(xs, dtype=np.float64)
        lats = np.array(ys, dtype=np.float64)
        return vals, lats, lons
    except Exception:
        return None


# ── Ridge Regression (Temporal Regression) ───────────────────────────────────

def train_ridge(entry: dict) -> Pipeline | None:
    """Fit depth_cm → property_value using Ridge with polynomial features."""
    files = entry.get("local_files", {})
    X, y = [], []
    for band, cm in DEPTH_CM.items():
        if band not in files:
            continue
        p = _read_pixels(files[band])
        if p is not None:
            X.extend([[cm]] * len(p))
            y.extend(p.tolist())
    if not X:
        return None
    model = Pipeline([
        ("poly", PolynomialFeatures(degree=2, include_bias=True)),
        ("ridge", Ridge(alpha=10.0)),
    ])
    model.fit(np.array(X, dtype=np.float32), np.array(y, dtype=np.float32))
    return model


# ── MLP Regressor (Neural-Network / LSTM proxy) ───────────────────────────────

def train_mlp(entry: dict) -> Pipeline | None:
    """Fit depth_cm → property_value using a small MLP (neural-network proxy for LSTM)."""
    files = entry.get("local_files", {})
    X, y = [], []
    for band, cm in DEPTH_CM.items():
        if band not in files:
            continue
        p = _read_pixels(files[band], max_n=500)
        if p is not None:
            X.extend([[cm]] * len(p))
            y.extend(p.tolist())
    if not X:
        return None
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            max_iter=500,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=20,
        )),
    ])
    model.fit(np.array(X, dtype=np.float32), np.array(y, dtype=np.float32))
    return model


# ── Random Forest (Influence / Feature-Importance model) ─────────────────────

def train_rf_influence(target_name: str, all_entries: dict) -> tuple:
    """
    Train RandomForestRegressor: predict target dataset's primary-band pixel values
    from all other datasets' primary-band pixel values.

    Returns (fitted_pipeline, feature_display_names) or (None, []).
    """
    arrays: dict[str, np.ndarray] = {}
    for name, entry in all_entries.items():
        files = entry.get("local_files", {})
        primary = next(
            (files[b] for b in DEPTH_ORDER if b in files),
            next(iter(files.values()), None),
        )
        p = _read_pixels(primary, max_n=_MAX_CROSS)
        if p is not None:
            arrays[name] = p

    if target_name not in arrays or len(arrays) < 3:
        return None, []

    feature_names = [
        entry["display"]
        for name, entry in all_entries.items()
        if name != target_name and name in arrays
    ]
    feature_data = [arrays[n] for n in all_entries if n != target_name and n in arrays]
    target_data = arrays[target_name]

    n = min(len(target_data), *[len(a) for a in feature_data])
    X = np.column_stack([a[:n] for a in feature_data])
    y = target_data[:n]

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestRegressor(
            n_estimators=100, max_depth=8, random_state=42, n_jobs=-1,
        )),
    ])
    model.fit(X, y)
    return model, feature_names


# ── Temporal training (year-by-year real data) ────────────────────────────────

_MIN_YEARS  = 6    # minimum years needed to train + evaluate a temporal model
_TEST_FRAC  = 0.20 # fraction of most-recent years held out as test set


def _build_temporal_series(name: str) -> tuple[np.ndarray, np.ndarray] | None:
    """
    Read the spatial mean of each year's GeoTIFF for a temporal dataset.
    Returns (years, mean_values) as 1-D arrays, sorted chronologically.
    Skips years where the file is unreadable.
    """
    year_data = TEMPORAL_REGISTRY.get(name, {})
    if len(year_data) < _MIN_YEARS:
        return None
    years, values = [], []
    for yr in sorted(year_data.keys()):
        path = next(iter(year_data[yr].values()), None)
        px = _read_pixels(path, max_n=5000)
        if px is not None and len(px) > 0:
            years.append(float(yr))
            values.append(float(np.nanmean(px)))
    if len(years) < _MIN_YEARS:
        return None
    return np.array(years), np.array(values)


def _chrono_split(years: np.ndarray, values: np.ndarray, test_frac: float = _TEST_FRAC):
    """
    Chronological train/test split — last `test_frac` of years become the test set.
    Returns X_train, X_test, y_train, y_test (X arrays are column vectors).
    """
    n_test  = max(1, int(round(len(years) * test_frac)))
    n_train = len(years) - n_test
    X       = years.reshape(-1, 1)
    X_tr, X_te = X[:n_train], X[n_train:]
    y_tr, y_te = values[:n_train], values[n_train:]
    return X_tr, X_te, y_tr, y_te


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute RMSE, MAE, R² for a set of predictions."""
    residuals = y_true - y_pred
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    mae  = float(np.mean(np.abs(residuals)))
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2   = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4)}


def _make_ridge_pipeline() -> Pipeline:
    return Pipeline([
        ("poly",  PolynomialFeatures(degree=2, include_bias=False)),
        ("ridge", Ridge(alpha=1.0)),
    ])


def _make_mlp_pipeline(n_train: int) -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            max_iter=2000,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.15 if n_train >= 8 else 0.0,
            n_iter_no_change=30,
            learning_rate_init=0.001,
        )),
    ])


def train_spatiotemporal(name: str, ssp_scenario: str = "ssp245") -> dict:
    """
    Build (year, lat, lon, delta_T, delta_P) -> pixel_value training set from
    all years in TEMPORAL_REGISTRY, then train XGBoost.

    delta_T, delta_P derived from SSP scenario benchmarks (Barcelona baseline:
    T=16.2degC, P=580mm/yr). No new data download required.

    Uses LeaveOneOut CV on annual means for honest temporal generalization metric.
    Saves: {name}_spatiotemporal.joblib
    """
    if not _XGBOOST_AVAILABLE:
        return {f"{name}_spatiotemporal": "skipped — xgboost not installed"}

    year_data = TEMPORAL_REGISTRY.get(name, {})
    if len(year_data) < _MIN_YEARS:
        return {f"{name}_spatiotemporal": f"skipped — only {len(year_data)} years"}

    # SSP2-4.5 benchmark deltas (IPCC AR6, Mediterranean region)
    # Barcelona baseline: T_mean=16.2C, precip=580mm/yr
    _SSP245_DT = {2000: -0.2, 2010: 0.0, 2020: 0.2, 2025: 0.3,
                  2030: 0.5, 2040: 0.8, 2050: 1.5, 2060: 1.9,
                  2070: 2.2, 2080: 2.4, 2090: 2.6, 2100: 2.7}
    _SSP245_DP = {2000: 0.0, 2010: -0.02, 2020: -0.05, 2025: -0.07,
                  2030: -0.09, 2040: -0.11, 2050: -0.15, 2060: -0.17,
                  2070: -0.18, 2080: -0.19, 2090: -0.19, 2100: -0.20}

    def _get_climate_deltas(yr: int):
        yrs = sorted(_SSP245_DT.keys())
        if yr <= yrs[0]:
            return _SSP245_DT[yrs[0]], _SSP245_DP[yrs[0]]
        if yr >= yrs[-1]:
            return _SSP245_DT[yrs[-1]], _SSP245_DP[yrs[-1]]
        for i in range(len(yrs) - 1):
            if yrs[i] <= yr <= yrs[i+1]:
                t = (yr - yrs[i]) / (yrs[i+1] - yrs[i])
                dt = _SSP245_DT[yrs[i]] + t * (_SSP245_DT[yrs[i+1]] - _SSP245_DT[yrs[i]])
                dp = _SSP245_DP[yrs[i]] + t * (_SSP245_DP[yrs[i+1]] - _SSP245_DP[yrs[i]])
                return dt, dp
        return 0.0, 0.0

    rows_X, rows_y = [], []
    annual_means = {}

    for yr in sorted(year_data.keys()):
        path = next(iter(year_data[yr].values()), None)
        result = _read_mean_pixels(path, max_n=_MAX_SPATIO)
        if result is None:
            continue
        vals, lats, lons = result
        dt, dp = _get_climate_deltas(yr)
        delta_T = dt                    # degC above baseline
        delta_P = dp * 580.0           # mm/yr change from baseline
        n = len(vals)
        yr_col  = np.full(n, float(yr))
        dT_col  = np.full(n, delta_T)
        dP_col  = np.full(n, delta_P)
        rows_X.append(np.column_stack([yr_col, lats, lons, dT_col, dP_col]))
        rows_y.append(vals)
        annual_means[yr] = float(np.mean(vals))

    if len(rows_X) < _MIN_YEARS:
        return {f"{name}_spatiotemporal": "skipped — insufficient readable years"}

    X = np.vstack(rows_X)
    y = np.concatenate(rows_y)

    print(f"  Spatiotemporal training set: {len(X):,} observations from {len(rows_X)} years")

    model = XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, n_jobs=-1, tree_method="hist",
        verbosity=0,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X, y)

    # LOO-CV on annual means for honest temporal metric
    ann_yrs = sorted(annual_means.keys())
    if len(ann_yrs) >= _MIN_YEARS:
        ann_X = np.array([[float(yr), 41.4, 2.15,
                           _get_climate_deltas(yr)[0],
                           _get_climate_deltas(yr)[1] * 580.0]
                          for yr in ann_yrs])
        ann_y = np.array([annual_means[yr] for yr in ann_yrs])
        loo_model = XGBRegressor(n_estimators=100, max_depth=4,
                                  random_state=42, n_jobs=-1,
                                  tree_method="hist", verbosity=0)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
            loo_preds = cross_val_predict(loo_model, ann_X, ann_y, cv=LeaveOneOut())
            metrics = _regression_metrics(ann_y, loo_preds)
            print(f"  LOO-CV annual means: RMSE={metrics['rmse']:.4f}  R²={metrics['r2']:.4f}")
        except Exception as exc:
            metrics = {"rmse": None, "r2": None}
            print(f"  LOO-CV failed: {exc}")
    else:
        metrics = {"rmse": None, "r2": None}

    out_path = os.path.join(SAVED_DIR, f"{name}_spatiotemporal.joblib")
    joblib.dump({
        "model": model,
        "features": ["year", "lat", "lon", "delta_T_degC", "delta_P_mm"],
        "n_train": len(X),
        "n_years": len(rows_X),
        "loo_metrics": metrics,
    }, out_path)
    print(f"  [OK] Spatiotemporal XGBoost -> {os.path.basename(out_path)}")
    return {f"{name}_spatiotemporal": f"saved  n={len(X):,}  loo_r2={metrics['r2']}"}


def train_temporal_models(name: str) -> dict:
    """
    Train Ridge and MLP on (year → spatial_mean) series for a temporal dataset.
    Both models are saved individually for use in spatial inference.
    Requires at least 6 years of data (with 80/20 chronological train/test split).
    """
    series = _build_temporal_series(name)
    if series is None:
        n = len(TEMPORAL_REGISTRY.get(name, {}))
        return {f"{name}_temporal": f"skipped — only {n} usable year(s), need {_MIN_YEARS}"}

    years, values = series
    X_tr, X_te, y_tr, y_te = _chrono_split(years, values)
    train_yrs = [int(y) for y in X_tr.flatten()]
    test_yrs  = [int(y) for y in X_te.flatten()]
    print(f"  train years: {train_yrs[0]}–{train_yrs[-1]}  "
          f"test years: {test_yrs[0]}–{test_yrs[-1]}")

    candidates = {
        "Ridge": _make_ridge_pipeline(),
        "MLP":   _make_mlp_pipeline(len(X_tr)),
    }

    log = {}
    X_all = years.reshape(-1, 1)
    key_map = {"Ridge": "temporal_ridge", "MLP": "temporal_mlp"}

    for model_name, pipe in candidates.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pipe.fit(X_tr, y_tr)
            y_pred_te = pipe.predict(X_te)
            metrics   = _regression_metrics(y_te, y_pred_te)
            print(f"  {model_name:5s}: test RMSE={metrics['rmse']:.4f}  "
                  f"MAE={metrics['mae']:.4f}  R²={metrics['r2']:.4f}")

            # Refit on ALL data before saving for production use
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pipe.fit(X_all, values)
            path = os.path.join(SAVED_DIR, f"{name}_{key_map[model_name]}.joblib")
            joblib.dump(pipe, path)
            log[f"{name}_{key_map[model_name]}"] = f"saved  test_rmse={metrics['rmse']}"
            print(f"  [OK] {model_name} -> {os.path.basename(path)}")
        except Exception as exc:
            print(f"  {model_name}: FAILED — {exc}")
            log[f"{name}_{key_map[model_name]}"] = f"failed: {exc}"

    return log


# ── Main training routine ─────────────────────────────────────────────────────

def train_all() -> dict:
    os.makedirs(SAVED_DIR, exist_ok=True)
    log: dict[str, str] = {}

    for name, entry in LOCAL_REGISTRY.items():
        print(f"\n[{name}]")

        # 1. Ridge — depth-band regression (soil: depth cm → property value)
        m = train_ridge(entry)
        if m:
            p = os.path.join(SAVED_DIR, f"{name}_ridge.joblib")
            joblib.dump(m, p)
            log[f"{name}_ridge"] = "saved"
            print(f"  [OK] Ridge (depth-band) -> {os.path.basename(p)}")
        else:
            log[f"{name}_ridge"] = "skipped (no depth bands)"
            print("  [--] Ridge: no depth bands")

        # 2. MLP — Neural-network on depth profile
        m = train_mlp(entry)
        if m:
            p = os.path.join(SAVED_DIR, f"{name}_mlp.joblib")
            joblib.dump(m, p)
            log[f"{name}_mlp"] = "saved"
            print(f"  [OK] MLP (depth-band)   -> {os.path.basename(p)}")
        else:
            log[f"{name}_mlp"] = "skipped (no depth bands)"
            print("  [--] MLP: no depth bands")

        # 3. RF cross-dataset influence model
        m, feat_names = train_rf_influence(name, LOCAL_REGISTRY)
        if m:
            p = os.path.join(SAVED_DIR, f"{name}_rf.joblib")
            joblib.dump({"model": m, "features": feat_names}, p)
            log[f"{name}_rf"] = "saved"
            print(f"  [OK] RF (influence)     -> {os.path.basename(p)}")
        else:
            log[f"{name}_rf"] = "skipped (insufficient datasets)"
            print("  [--] RF: insufficient datasets")

        # 4. Temporal models — Ridge, MLP, RF on (year → value) with train/test split
        temporal_log = train_temporal_models(name)
        log.update(temporal_log)

        # 5. Spatiotemporal XGBoost — (year, lat, lon, dT, dP) → pixel value
        spatio_log = train_spatiotemporal(name)
        log.update(spatio_log)

    return log


if __name__ == "__main__":
    print("=== Training ML Models ===")
    results = train_all()
    print("\n=== Summary ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("\nDone.")
