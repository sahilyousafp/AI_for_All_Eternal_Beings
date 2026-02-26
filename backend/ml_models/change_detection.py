"""
change_detection.py — Surface vs deep-layer comparison.

True temporal change detection requires data from two different years.
The downloaded dataset is a single 2020 snapshot. Rather than returning
meaningless fake deltas, we compare the *surface layer* (b0, 0 cm) against
the *deepest layer* (b200, 200 cm) — a real, meaningful vertical gradient.

year_a / year_b are accepted for API compatibility but are mapped to depth
layers: year_a → surface (b0), year_b → deep (b200).
"""

import numpy as np

from backend.ml_models.data_loader import load_raster, get_soil_path


def change_detection_model(selected, year_a, year_b):
    dataset_name = selected["name"]

    surface_path = get_soil_path(dataset_name, "b0")
    deep_path    = get_soil_path(dataset_name, "b200")

    try:
        arr_surface, _ = load_raster(surface_path)
        arr_deep,    _ = load_raster(deep_path)
    except Exception as exc:
        return {
            "dataset": dataset_name,
            "error":   f"Could not load rasters: {exc}",
            "earlier_year": 0,
            "later_year":   200,
            "earlier_value": None,
            "later_value":   None,
            "delta":         None,
        }

    valid = np.isfinite(arr_surface) & np.isfinite(arr_deep)
    if not np.any(valid):
        return {
            "dataset": dataset_name,
            "error":   "No valid pixels found.",
            "earlier_year": 0, "later_year": 200,
            "earlier_value": None, "later_value": None, "delta": None,
        }

    mean_surface = float(np.mean(arr_surface[valid]))
    mean_deep    = float(np.mean(arr_deep[valid]))
    delta        = mean_deep - mean_surface

    pct_change = (delta / mean_surface * 100) if mean_surface != 0 else None

    return {
        "dataset":       dataset_name,
        "note":          "Vertical gradient: surface (0 cm) vs deep (200 cm)",
        "earlier_year":  0,     # depth in cm — surface
        "later_year":    200,   # depth in cm — deep
        "earlier_value": round(mean_surface, 4),
        "later_value":   round(mean_deep,    4),
        "delta":         round(delta, 4),
        "pct_change":    round(pct_change, 2) if pct_change is not None else None,
        "units":         selected.get("units", ""),
    }
