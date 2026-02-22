"""
Soil Erosion Scenario Forecast using trained depth-profile models.

Model priority (best → fallback):
  1. {name}_mlp.joblib   (Neural-Network, learned non-linear depth patterns)
  2. {name}_ridge.joblib (Ridge Regression with polynomial features)
  3. On-the-fly Ridge    (trained instantly from local GeoTIFFs)

The depth profile (0–200 cm) represents EROSION EXPOSURE, not time:
  - b0   (0 cm):   Current surface — what is at the top TODAY
  - b10  (10 cm):  Exposed after moderate topsoil erosion
  - b30  (30 cm):  Exposed after heavy erosion (e.g. tilling + runoff)
  - b60  (60 cm):  Exposed after severe erosion — subsoil becomes surface
  - b100 (100 cm): Critical erosion — parent material approaching
  - b200 (200 cm): Total topsoil loss — near-bedrock properties
  - >200 cm:       Extrapolated into parent material (model extrapolation)

When erosion removes the top X cm, the soil properties at depth X become
the new surface properties. This model shows that transition.
"""
import os
import warnings

import numpy as np
import joblib
import rasterio
from rasterio.errors import NotGeoreferencedWarning

SAVED_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
DEPTH_CM = {"b0": 0, "b10": 10, "b30": 30, "b60": 60, "b100": 100, "b200": 200}


def _read_pixels(path: str, max_n: int = 1000) -> np.ndarray | None:
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


def _train_ridge_onthefly(entry: dict):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import PolynomialFeatures

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


def forecast_model(selected: dict, years: int = 100) -> dict:
    ds_name = selected.get("internal_name", "")

    # Load best available saved model
    model = None
    model_name = ""
    for suffix, label in [("_mlp", "Neural Network (MLP)"), ("_ridge", "Ridge Regression")]:
        path = os.path.join(SAVED_DIR, f"{ds_name}{suffix}.joblib")
        if os.path.isfile(path):
            try:
                model = joblib.load(path)
                model_name = label
                break
            except Exception:
                pass

    if model is None:
        model = _train_ridge_onthefly(selected)
        model_name = "Ridge (on-the-fly)"

    if model is None:
        return {
            "dataset": selected["name"],
            "labels": [], "values": [],
            "model": "no data — no depth bands found",
            "units": selected.get("units", ""),
        }

    # Baseline: predicted surface value (depth = 0 cm, current surface)
    baseline = float(model.predict([[0.0]])[0])

    # Erosion scenario: show properties at each depth band as the surface,
    # plus extrapolated deeper points to model progressive parent-material exposure.
    # Depth labels represent "what is exposed at the surface after X cm of topsoil loss".
    SCENARIO_DEPTHS = [0, 10, 30, 60, 100, 200]
    SCENARIO_LABELS = [
        "Current surface (0 cm)",
        "Moderate erosion (10 cm)",
        "Heavy erosion (30 cm)",
        "Severe erosion (60 cm)",
        "Critical erosion (100 cm)",
        "Total topsoil loss (200 cm)",
    ]

    # Extrapolate 5 more points into parent material beyond 200 cm
    extra_depths  = [250, 300, 350, 400, 500]
    extra_labels  = [f"Parent material ({d} cm)" for d in extra_depths]

    all_depths  = SCENARIO_DEPTHS + extra_depths
    all_labels  = SCENARIO_LABELS + extra_labels

    depth_inputs = np.array([[float(d)] for d in all_depths], dtype=np.float64)
    projected    = model.predict(depth_inputs)

    values = [round(float(v), 2) for v in projected]

    return {
        "dataset":       selected["name"],
        "labels":        all_labels,
        "values":        values,
        "model":         model_name,
        "units":         selected.get("units", ""),
        "baseline":      round(baseline, 2),
        "erosion_mode":  True,
        "subtitle":      "Surface soil properties under progressive topsoil erosion scenarios",
    }


