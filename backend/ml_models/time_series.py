"""
time_series.py — Real soil depth profile from downloaded GeoTIFFs.

The OpenLandMap soil datasets are static (single best-estimate snapshots),
not time series. Instead of faking temporal data, we return the vertical
depth profile: mean property value at each of the 6 depth layers
(0, 10, 30, 60, 100, 200 cm).

The frontend chart re-uses the "year" field to hold depth_cm, which is
clearly labelled in the API response so clients can display it correctly.
start_year / end_year are accepted but ignored (API compatibility).
"""

from backend.ml_models.data_loader import load_depth_profile


def time_series_model(selected, start_year, end_year):
    dataset_name = selected["name"]

    # Soil Texture is a classification — depth profile is still meaningful
    # but mean of integer classes is less interpretable; we include it anyway.
    profile = load_depth_profile(dataset_name)

    if not profile:
        return {
            "dataset":    dataset_name,
            "profile_type": "depth",
            "x_label":    "Depth (cm)",
            "points":     [],
            "error":      "Could not load raster data for this dataset.",
        }

    points = [
        {
            "year":     entry["depth_cm"],   # "year" re-used as depth_cm
            "value":    round(entry["value"], 4),
            "min":      round(entry["min"],   4),
            "max":      round(entry["max"],   4),
            "std":      round(entry["std"],   4),
        }
        for entry in profile
    ]

    return {
        "dataset":      dataset_name,
        "profile_type": "depth",
        "x_label":      "Depth (cm)",
        "units":        selected.get("units", ""),
        "points":       points,
    }
