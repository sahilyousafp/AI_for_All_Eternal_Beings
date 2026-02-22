"""
Depth-profile time series — returns Chart.js-ready data.

The depth bands (b0→b200) act as the analysis dimension, showing how
a property changes from the soil surface down. Each band's mean pixel
value across the Barcelona region is returned as a data point.
"""
import warnings

import numpy as np
import rasterio
from rasterio.errors import NotGeoreferencedWarning


def _read_mean(path: str) -> float | None:
    if not path:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data = src.read(1, masked=True)
        vals = data.compressed().astype(float)
        return float(np.mean(vals)) if len(vals) > 0 else None
    except Exception:
        return None


def time_series_model(selected: dict, start_year: int, end_year: int) -> dict:
    from backend.ml_models.utils import ordered_bands

    bands = ordered_bands(selected)
    labels, values = [], []
    for label, path in bands:
        m = _read_mean(path)
        if m is not None:
            labels.append(label)
            values.append(round(m, 2))

    return {
        "dataset": selected["name"],
        "labels": labels,
        "values": values,
        "units": selected.get("units", ""),
        "description": "Mean pixel value per depth band — Barcelona region (250 m)",
    }


