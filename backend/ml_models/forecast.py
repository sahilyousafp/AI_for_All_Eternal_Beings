"""
forecast.py — Linear trend fitted on the depth profile, extrapolated deeper.

We fit scipy.stats.linregress to the 6 known depth values (0–200 cm) and
project the trend to hypothetical deeper layers (250, 300, 400, 500, 600 cm).
This shows how the soil property is likely to continue changing with depth
and provides slope + significance statistics.

`years` parameter is accepted for API compatibility but controls how many
extrapolation steps beyond 200 cm to return.
"""

import numpy as np
from scipy import stats

from backend.ml_models.data_loader import load_depth_profile

# Extrapolation depths beyond 200 cm
_EXTRA_DEPTHS = [250, 300, 400, 500, 600, 800, 1000]


def forecast_model(selected, years: int = 5):
    dataset_name = selected["name"]
    profile = load_depth_profile(dataset_name)

    if len(profile) < 3:
        return {
            "dataset":  dataset_name,
            "error":    "Not enough depth layers to fit a trend.",
            "forecast": [],
        }

    depths = np.array([p["depth_cm"] for p in profile], dtype=float)
    values = np.array([p["value"]    for p in profile], dtype=float)

    slope, intercept, r_value, p_value, std_err = stats.linregress(depths, values)

    # 95 % confidence interval half-width for a new prediction
    n      = len(depths)
    t_crit = stats.t.ppf(0.975, df=n - 2)
    s_res  = np.sqrt(np.sum((values - (intercept + slope * depths)) ** 2) / (n - 2))
    depth_mean = depths.mean()

    def ci_half(x):
        return t_crit * s_res * np.sqrt(
            1 + 1 / n + (x - depth_mean) ** 2 / np.sum((depths - depth_mean) ** 2)
        )

    # Known depth points (fitted)
    fitted = [
        {
            "year":      int(d),
            "value":     round(float(intercept + slope * d), 4),
            "observed":  round(float(v), 4),
            "ci_lower":  round(float(intercept + slope * d - ci_half(d)), 4),
            "ci_upper":  round(float(intercept + slope * d + ci_half(d)), 4),
            "extrapolated": False,
        }
        for d, v in zip(depths, values)
    ]

    # Extrapolated depths
    extra_depths = _EXTRA_DEPTHS[:max(1, years)]
    extrapolated = [
        {
            "year":         int(d),
            "value":        round(float(intercept + slope * d), 4),
            "ci_lower":     round(float(intercept + slope * d - ci_half(d)), 4),
            "ci_upper":     round(float(intercept + slope * d + ci_half(d)), 4),
            "extrapolated": True,
        }
        for d in extra_depths
    ]

    return {
        "dataset":   dataset_name,
        "x_label":   "Depth (cm)",
        "units":     selected.get("units", ""),
        "trend": {
            "slope":       round(float(slope),     6),
            "intercept":   round(float(intercept), 4),
            "r_squared":   round(float(r_value**2), 4),
            "p_value":     round(float(p_value),   6),
            "significant": bool(p_value < 0.05),
            "direction":   "decreasing with depth" if slope < 0 else "increasing with depth",
        },
        "forecast": fitted + extrapolated,
    }
