"""
prediction.py — RF-based soil texture prediction for a bounding box.

The model is loaded once at first call (lazy init).
If the model file does not exist yet, returns a helpful error message
instead of crashing the API.
"""

import os
import numpy as np

_HERE        = os.path.dirname(os.path.abspath(__file__))
_MODEL_PATH  = os.path.join(_HERE, "models", "rf_soil_classifier.joblib")
_SCALER_PATH = os.path.join(_HERE, "models", "rf_scaler.joblib")

# Lazy-loaded singletons
_clf    = None
_scaler = None

TEXTURE_CLASS_NAMES = {
    1: "Clay",         2: "Silty Clay",      3: "Sandy Clay",
    4: "Clay Loam",    5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam",         8: "Silt Loam",       9: "Silt",
    10: "Sandy Loam",  11: "Loamy Sand",     12: "Sand",
}


def _load_model():
    global _clf, _scaler
    if _clf is not None:
        return True, None
    if not os.path.exists(_MODEL_PATH):
        return False, (
            "RF model not trained yet. "
            "Run: python -m backend.ml_models.train_rf"
        )
    import joblib
    _clf    = joblib.load(_MODEL_PATH)
    _scaler = joblib.load(_SCALER_PATH)
    return True, None


def prediction_model(selected, start_year, end_year,
                     lat_min, lon_min, lat_max, lon_max):
    """
    Predict soil texture class for each pixel in the bounding box.

    start_year / end_year are kept for API compatibility but not used
    (soil data is a static snapshot).

    Returns one entry per depth layer (0–200 cm) so the frontend chart
    shows RF confidence across the vertical soil profile.
    """
    from backend.ml_models.data_loader import load_feature_matrix_bbox, DEPTHS

    ok, err = _load_model()
    if not ok:
        return {"dataset": selected["name"], "error": err, "points": []}

    points = []

    for depth_cm, suffix in DEPTHS:
        X_bbox, mask, meta = load_feature_matrix_bbox(
            suffix, lon_min, lat_min, lon_max, lat_max
        )

        if X_bbox is None or X_bbox.shape[0] == 0:
            continue

        X_sc   = _scaler.transform(X_bbox)
        probas = _clf.predict_proba(X_sc)   # (N, n_classes)
        preds  = _clf.predict(X_sc)          # (N,)

        # Dominant class = most frequent predicted class
        class_counts = np.bincount(
            np.searchsorted(_clf.classes_, preds), minlength=len(_clf.classes_)
        )
        dom_idx   = int(np.argmax(class_counts))
        dom_class = int(_clf.classes_[dom_idx])
        mean_conf = float(np.mean(np.max(probas, axis=1)))

        unique, counts = np.unique(preds, return_counts=True)
        distribution = {
            TEXTURE_CLASS_NAMES.get(int(c), f"Class {c}"): round(cnt / len(preds) * 100, 1)
            for c, cnt in zip(unique, counts)
        }

        points.append({
            "year":           depth_cm,
            "value":          round(mean_conf * 100, 2),
            "dominant_class": TEXTURE_CLASS_NAMES.get(dom_class, f"Class {dom_class}"),
            "distribution":   distribution,
            "n_pixels":       int(len(preds)),
        })

    if not points:
        return {
            "dataset": selected["name"],
            "error":   "Bounding box has no coverage in Spain dataset.",
            "points":  [],
        }

    return {
        "dataset":        selected["name"],
        "bbox":           {"lat_min": lat_min, "lat_max": lat_max,
                           "lon_min": lon_min, "lon_max": lon_max},
        "dominant_class": points[0]["dominant_class"],
        "points":         points,
    }
