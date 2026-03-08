"""
Spatial inference: generate a predicted GeoTIFF for the Barcelona region.

Strategies per model_type:
  rf             → Run the RF influence model using all other datasets as features.
  ridge / mlp    → Scale existing primary raster by depth-model ratio (depth ≡ time proxy).
  temporal_ridge → Scale existing primary raster by temporal-trend ratio.
  temporal_mlp   → Scale existing primary raster by temporal-trend ratio.

All methods return raw GeoTIFF bytes (float32) or None on failure.
"""
import io
import os
import warnings

import numpy as np
import joblib
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS

from backend.ml_models.utils import LOCAL_REGISTRY, primary_band

SAVED_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


# ── Low-level I/O ─────────────────────────────────────────────────────────────

def _read_raster(path: str):
    """Return (data_2d_float32, nodata, meta) or None on error."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data   = src.read(1).astype(np.float32)
                nodata = src.nodata
                meta   = src.meta.copy()
        return data, nodata, meta
    except Exception:
        return None


def _write_raster(data: np.ndarray, meta: dict, nodata: float) -> bytes | None:
    """Encode a 2D float32 array as in-memory WGS84 GeoTIFF bytes."""
    try:
        src_crs = meta.get("crs")
        m = meta.copy()
        m.update({"count": 1, "dtype": "float32", "nodata": float(nodata), "driver": "GTiff"})

        # If the raster is already WGS84, write directly
        wgs84 = CRS.from_epsg(4326)
        if src_crs and CRS.from_user_input(src_crs) != wgs84:
            # Reproject to WGS84 so GeoRasterLayer doesn't need proj4 defs
            transform, width, height = calculate_default_transform(
                src_crs, wgs84, m["width"], m["height"], *rasterio.transform.array_bounds(m["height"], m["width"], m["transform"])
            )
            reprojected = np.full((height, width), float(nodata), dtype=np.float32)
            with rasterio.MemoryFile() as src_mem:
                m_src = m.copy()
                with src_mem.open(**m_src) as src_ds:
                    src_ds.write(data[np.newaxis, :, :])
                with src_mem.open() as src_ds:
                    reproject(
                        source=rasterio.band(src_ds, 1),
                        destination=reprojected,
                        src_transform=m["transform"],
                        src_crs=src_crs,
                        dst_transform=transform,
                        dst_crs=wgs84,
                        resampling=Resampling.bilinear,
                        src_nodata=float(nodata),
                        dst_nodata=float(nodata),
                    )
            m.update({"crs": wgs84, "transform": transform, "width": width, "height": height})
            data = reprojected

        with rasterio.MemoryFile() as memfile:
            with memfile.open(**m) as dst:
                dst.write(data[np.newaxis, :, :])
            return memfile.read()
    except Exception:
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_mask(data: np.ndarray, nodata) -> np.ndarray:
    nd = float(nodata) if nodata is not None else -9999.0
    return (data != nd) & np.isfinite(data)


def _scale_raster(data: np.ndarray, nodata, meta: dict, scale: float) -> bytes | None:
    """Multiply all valid pixels by scale and return GeoTIFF bytes."""
    nd = float(nodata) if nodata is not None else -9999.0
    mask = _valid_mask(data, nodata)
    out  = np.where(mask, np.clip(data * float(scale), 0, None), nd).astype(np.float32)
    return _write_raster(out, meta, nd)


def _load_model(path: str):
    try:
        return joblib.load(path)
    except Exception:
        return None


# ── Strategy: RF spatial prediction ──────────────────────────────────────────

def _predict_rf(dataset_name: str, data: np.ndarray, nodata, meta: dict) -> bytes | None:
    """
    Run the RF influence model across all pixels.
    Features = primary-band values of all OTHER datasets aligned to the same grid.
    """
    path = os.path.join(SAVED_DIR, f"{dataset_name}_rf.joblib")
    saved = _load_model(path)
    if saved is None:
        return None
    model = saved["model"] if isinstance(saved, dict) else saved

    h, w = data.shape
    nd   = float(nodata) if nodata is not None else -9999.0

    # Collect feature rasters (same shape as target)
    features: list[np.ndarray] = []
    for name, entry in LOCAL_REGISTRY.items():
        if name == dataset_name:
            continue
        result = _read_raster(primary_band(entry))
        if result is None:
            continue
        feat, feat_nd, _ = result
        if feat.shape != (h, w):
            continue   # skip mismatched grids
        if feat_nd is not None:
            feat = np.where(feat == float(feat_nd), np.nan, feat)
        features.append(feat)

    if len(features) < 2:
        return None

    n_feats = len(features)
    X_flat  = np.stack(features, axis=-1).reshape(-1, n_feats)  # [h*w, n_feats]

    # Valid pixels: target valid AND all features finite
    flat_valid = _valid_mask(data, nodata).flatten()
    for feat in features:
        flat_valid &= np.isfinite(feat.flatten())

    if flat_valid.sum() < 10:
        return None

    try:
        preds = model.predict(X_flat[flat_valid]).astype(np.float32)
        out   = np.full(h * w, nd, dtype=np.float32)
        out[flat_valid] = preds
        return _write_raster(out.reshape(h, w), meta, nd)
    except Exception:
        return None


# ── Strategy: depth-band scaling ─────────────────────────────────────────────

def _predict_depth_model(
    dataset_name: str, model_suffix: str, year: int,
    data: np.ndarray, nodata, meta: dict, actual_mean: float,
) -> bytes | None:
    """
    Load Ridge/MLP depth model, predict at target_depth, scale raster by ratio.
    Depth proxy: 1 cm ≡ 1 year beyond 2025 (same as temporal_inference.py).
    """
    path  = os.path.join(SAVED_DIR, f"{dataset_name}_{model_suffix}.joblib")
    model = _load_model(path)
    if model is None or actual_mean == 0:
        return None
    try:
        target_depth = max(0.0, float(year - 2025))
        pred_mean    = float(model.predict([[target_depth]])[0])
        scale        = pred_mean / actual_mean
        return _scale_raster(data, nodata, meta, scale)
    except Exception:
        return None


# ── Strategy: temporal-model scaling ─────────────────────────────────────────

def _predict_temporal_model(
    dataset_name: str, model_suffix: str, year: int,
    data: np.ndarray, nodata, meta: dict, actual_mean: float,
) -> bytes | None:
    """
    Load temporal Ridge/MLP, predict mean at target year, scale raster by ratio.
    Falls back to depth model if temporal model not found.
    """
    path  = os.path.join(SAVED_DIR, f"{dataset_name}_{model_suffix}.joblib")
    model = _load_model(path)
    if model is None:
        # Fallback: depth-model proxy
        return _predict_depth_model(dataset_name, "ridge", year, data, nodata, meta, actual_mean)
    if actual_mean == 0:
        return None
    try:
        pred_mean = float(model.predict([[float(year)]])[0])
        scale     = pred_mean / actual_mean
        return _scale_raster(data, nodata, meta, scale)
    except Exception:
        return None


# ── Public entry point ────────────────────────────────────────────────────────

def predict_map_raster(dataset_name: str, year: int, model_type: str) -> bytes | None:
    """
    Generate a GeoTIFF prediction raster for `dataset_name` at `year`.

    Args:
        dataset_name: internal name (e.g. 'Organic_Carbon')
        year:         target year for prediction
        model_type:   one of 'rf', 'ridge', 'mlp', 'temporal_ridge', 'temporal_mlp'

    Returns:
        Raw GeoTIFF bytes (float32), or None if the model is unavailable / inference fails.
    """
    entry = LOCAL_REGISTRY.get(dataset_name)
    if not entry:
        return None

    result = _read_raster(primary_band(entry))
    if result is None:
        return None
    data, nodata, meta = result

    nd    = float(nodata) if nodata is not None else -9999.0
    mask  = _valid_mask(data, nodata)
    if not mask.any():
        return None
    actual_mean = float(np.nanmean(data[mask]))

    if model_type == "rf":
        out = _predict_rf(dataset_name, data, nodata, meta)
        # Fallback: return raw primary-band data if RF fails
        return out if out else _write_raster(data, meta, nd)

    elif model_type in ("temporal_ridge", "temporal_mlp"):
        out = _predict_temporal_model(dataset_name, model_type, year, data, nodata, meta, actual_mean)
        return out if out else _write_raster(data, meta, nd)

    return None
