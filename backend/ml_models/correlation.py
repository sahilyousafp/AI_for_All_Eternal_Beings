"""
correlation.py — Real Pearson correlations between soil properties and
                 climate / land-cover drivers.

Uses the downloaded Spain rasters:
  - Soil property (selected dataset, surface b0)
  - CHIRPS Precipitation (2020 mean)
  - MODIS Land Cover Type 1 (2020 mode)

Rasters are resampled to the soil grid (nearest-neighbour via numpy slicing)
before computing correlation. Only pixels valid in all layers are used.
"""

import os
import numpy as np
from scipy import stats
import rasterio
from rasterio.enums import Resampling

from backend.ml_models.data_loader import (
    get_soil_path, get_climate_path, get_lc_path, load_raster
)


def _resample_to_reference(src_path: str, ref_meta: dict) -> np.ndarray:
    """
    Resample src raster to match ref_meta's grid using bilinear resampling.
    Returns a float32 array with nodata → NaN.
    """
    ref_h = ref_meta["height"]
    ref_w = ref_meta["width"]
    ref_transform = ref_meta["transform"]
    ref_crs = ref_meta["crs"]

    with rasterio.open(src_path) as src:
        from rasterio.warp import reproject, Resampling as RS
        dest = np.full((ref_h, ref_w), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dest,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=RS.bilinear,
        )
        nodata = src.nodata
        if nodata is not None:
            dest[dest == nodata] = np.nan
    return dest


def _pearson(x: np.ndarray, y: np.ndarray):
    """Return (r, p_value) for two flat arrays, or (None, None) if too few points."""
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 10:
        return None, None
    r, p = stats.pearsonr(x[mask], y[mask])
    return float(r), float(p)


def correlation_model(selected):
    dataset_name = selected["name"]

    # --- Load reference (soil property, surface) ---
    soil_path = get_soil_path(dataset_name, "b0")
    try:
        soil_arr, soil_meta = load_raster(soil_path)
    except Exception as exc:
        return {"dataset": dataset_name, "error": str(exc), "correlation": {}}

    results      = {}
    p_values     = {}

    # --- Precipitation ---
    precip_path = get_climate_path()
    if os.path.exists(precip_path):
        try:
            precip_arr = _resample_to_reference(precip_path, soil_meta)
            r, p = _pearson(soil_arr.ravel(), precip_arr.ravel())
            if r is not None:
                results["precipitation"]  = round(r, 4)
                p_values["precipitation"] = round(p, 6)
        except Exception:
            pass

    # --- Land Cover ---
    lc_path = get_lc_path("LC_Type1")
    if os.path.exists(lc_path):
        try:
            lc_arr = _resample_to_reference(lc_path, soil_meta)
            r, p = _pearson(soil_arr.ravel(), lc_arr.ravel())
            if r is not None:
                results["landcover"]  = round(r, 4)
                p_values["landcover"] = round(p, 6)
        except Exception:
            pass

    # --- Cross-correlations with other soil properties ---
    other_soil = {
        "organic_carbon": "Organic Carbon",
        "soil_ph":        "Soil pH",
        "bulk_density":   "Bulk Density",
        "sand_content":   "Sand Content",
        "clay_content":   "Clay Content",
    }

    for key, ds_name in other_soil.items():
        # Skip self-correlation
        if ds_name.lower() in dataset_name.lower():
            continue
        other_path = get_soil_path(ds_name, "b0")
        if not os.path.exists(other_path):
            continue
        try:
            other_arr, _ = load_raster(other_path)
            # Both already on same grid
            r, p = _pearson(soil_arr.ravel(), other_arr.ravel())
            if r is not None:
                results[key]  = round(r, 4)
                p_values[key] = round(p, 6)
        except Exception:
            pass

    return {
        "dataset":     dataset_name,
        "n_pixels":    int(np.sum(np.isfinite(soil_arr))),
        "correlation": results,
        "p_values":    p_values,
        "note":        "Pearson r with co-located pixels. p < 0.05 = significant.",
    }
