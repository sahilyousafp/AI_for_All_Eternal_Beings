"""
data_loader.py — rasterio-based loading of downloaded GeoTIFFs.

All rasters live under backend/data_downloader/ and were downloaded for Spain
at 2.5 km resolution via download_gee_data.py.

Depth band naming convention (OpenLandMap):
  b0   → 0–5 cm   (labelled as 0 cm)
  b10  → 5–15 cm  (labelled as 10 cm)
  b30  → 15–30 cm (labelled as 30 cm)
  b60  → 30–60 cm (labelled as 60 cm)
  b100 → 60–100 cm (labelled as 100 cm)
  b200 → 100–200 cm (labelled as 200 cm)
"""

import os
import numpy as np
import rasterio
from rasterio.windows import from_bounds

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_ROOT = os.path.join(_HERE, "..", "data_downloader")

_SOIL_DIR   = os.path.join(_DATA_ROOT, "soil")
_CLIMATE_DIR = os.path.join(_DATA_ROOT, "climate")
_LC_DIR      = os.path.join(_DATA_ROOT, "land_cover")

# Depth labels in centimetres and corresponding file suffix
DEPTHS = [
    (0,   "b0"),
    (10,  "b10"),
    (30,  "b30"),
    (60,  "b60"),
    (100, "b100"),
    (200, "b200"),
]

# Mapping from dataset display name (partial match) → soil file prefix
_SOIL_FILE_MAP = {
    "organic carbon": "Organic_Carbon",
    "soil ph":        "Soil_pH",
    "bulk density":   "Bulk_Density",
    "sand content":   "Sand_Content",
    "clay content":   "Clay_Content",
    "soil texture":   "Soil_Texture",
}


def _resolve_soil_prefix(dataset_name: str) -> str:
    """Return the file prefix for a dataset name (case-insensitive partial match)."""
    key = dataset_name.lower()
    for fragment, prefix in _SOIL_FILE_MAP.items():
        if fragment in key:
            return prefix
    raise ValueError(f"Unknown soil dataset: {dataset_name!r}")


def get_soil_path(dataset_name: str, depth_suffix: str = "b0") -> str:
    """Return the absolute path to a soil raster file."""
    prefix = _resolve_soil_prefix(dataset_name)
    return os.path.join(_SOIL_DIR, f"{prefix}.{depth_suffix}.tif")


def get_climate_path() -> str:
    return os.path.join(_CLIMATE_DIR, "Precipitation_CHIRPS.precipitation.tif")


def get_lc_path(band: str = "LC_Type1") -> str:
    return os.path.join(_LC_DIR, f"MODIS_Land_Cover.{band}.tif")


# ---------------------------------------------------------------------------
# Low-level raster helpers
# ---------------------------------------------------------------------------

def load_raster(path: str):
    """
    Load a single-band GeoTIFF.

    Returns
    -------
    array : np.ndarray  shape (H, W), nodata replaced with np.nan (float32)
    meta  : dict with keys: transform, crs, nodata, width, height
    """
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
        nodata = src.nodata
        meta = {
            "transform": src.transform,
            "crs":       src.crs,
            "nodata":    nodata,
            "width":     src.width,
            "height":    src.height,
            "bounds":    src.bounds,
        }
    if nodata is not None:
        arr[arr == nodata] = np.nan
    return arr, meta


def load_raster_window(path: str, lon_min: float, lat_min: float,
                        lon_max: float, lat_max: float):
    """
    Load only the pixels inside a lat/lon bounding box.

    Returns the same (array, meta) shape as load_raster but clipped.
    If the bbox falls entirely outside the raster extent, returns (None, None).
    """
    with rasterio.open(path) as src:
        bounds = src.bounds
        # Clamp bbox to raster extent
        left   = max(lon_min, bounds.left)
        right  = min(lon_max, bounds.right)
        bottom = max(lat_min, bounds.bottom)
        top    = min(lat_max, bounds.top)

        if left >= right or bottom >= top:
            return None, None

        window = from_bounds(left, bottom, right, top, src.transform)
        arr    = src.read(1, window=window).astype(np.float32)
        nodata = src.nodata
        transform = src.window_transform(window)
        meta = {
            "transform": transform,
            "crs":       src.crs,
            "nodata":    nodata,
            "width":     arr.shape[1],
            "height":    arr.shape[0],
            "bounds":    (left, bottom, right, top),
        }
    if nodata is not None:
        arr[arr == nodata] = np.nan
    return arr, meta


# ---------------------------------------------------------------------------
# Feature matrix builders
# ---------------------------------------------------------------------------

_FEATURE_DATASETS = [
    "Organic Carbon",
    "Soil pH",
    "Bulk Density",
    "Sand Content",
    "Clay Content",
]

_FEATURE_NAMES = ["OrgC", "pH", "BulkDens", "Sand", "Clay"]


def load_feature_matrix(depth_suffix: str = "b0"):
    """
    Stack the 5 soil property rasters into a pixel-level feature matrix.

    Returns
    -------
    X     : np.ndarray  shape (N_valid_pixels, 5)
    mask  : np.ndarray  shape (H, W) bool — True where all features are valid
    meta  : dict — metadata from the first raster (reference grid)
    """
    arrays = []
    ref_meta = None

    for ds_name in _FEATURE_DATASETS:
        path = get_soil_path(ds_name, depth_suffix)
        arr, meta = load_raster(path)
        if ref_meta is None:
            ref_meta = meta
        arrays.append(arr)

    stacked = np.stack(arrays, axis=-1)  # (H, W, 5)
    mask = np.all(np.isfinite(stacked), axis=-1)  # (H, W)
    X = stacked[mask]  # (N_valid, 5)
    return X, mask, ref_meta


def load_labels(depth_suffix: str = "b0"):
    """
    Load the Soil_Texture raster as integer class labels.

    Returns
    -------
    labels : np.ndarray  shape (H, W), dtype int, nodata pixels = -1
    meta   : dict
    """
    path = get_soil_path("Soil Texture", depth_suffix)
    arr, meta = load_raster(path)
    # 255 is the GEE integer nodata sentinel for this raster — exclude it
    arr[arr == 255] = np.nan
    # nan_to_num before int cast prevents RuntimeWarning from NaN->int32
    labels = np.where(np.isfinite(arr), np.nan_to_num(arr, nan=0).astype(np.int32), -1)
    return labels, meta


def load_feature_and_label_matrix(depth_suffix: str = "b0"):
    """
    Return aligned (X, y) ready for sklearn.

    Rows where any feature OR label is invalid are dropped.

    Returns
    -------
    X : np.ndarray (N, 5)
    y : np.ndarray (N,)  integer soil texture classes
    feature_names : list[str]
    """
    X_all, feat_mask, _ = load_feature_matrix(depth_suffix)
    labels, _           = load_labels(depth_suffix)

    # Align: only pixels valid in BOTH feature stack and label raster
    label_flat = labels[feat_mask]
    valid       = label_flat >= 0
    X = X_all[valid]
    y = label_flat[valid]
    return X, y, _FEATURE_NAMES


# ---------------------------------------------------------------------------
# Depth profile helpers
# ---------------------------------------------------------------------------

def load_depth_profile(dataset_name: str,
                        lon_min: float = None, lat_min: float = None,
                        lon_max: float = None, lat_max: float = None):
    """
    Load mean pixel value at each of the 6 depth layers.

    If bbox is given, restrict to that window; otherwise uses the full Spain raster.

    Returns
    -------
    list of dicts: [{depth_cm: int, value: float}, ...]  — NaN depths omitted
    """
    results = []
    use_window = all(v is not None for v in [lon_min, lat_min, lon_max, lat_max])

    for depth_cm, suffix in DEPTHS:
        path = get_soil_path(dataset_name, suffix)
        if not os.path.exists(path):
            continue

        if use_window:
            arr, meta = load_raster_window(path, lon_min, lat_min, lon_max, lat_max)
        else:
            arr, meta = load_raster(path)

        if arr is None:
            continue

        valid = arr[np.isfinite(arr)]
        if valid.size == 0:
            continue

        results.append({
            "depth_cm": depth_cm,
            "value":    float(np.mean(valid)),
            "min":      float(np.min(valid)),
            "max":      float(np.max(valid)),
            "std":      float(np.std(valid)),
        })

    return results


def load_point_statistics(dataset_name: str, lat: float, lon: float,
                           window_px: int = 5):
    """
    Compute statistics over a small pixel window centred at (lat, lon).

    window_px controls the half-width of the sample box (in pixels).

    Returns dict with mean, min, max, std — or None if point outside raster.
    """
    path = get_soil_path(dataset_name, "b0")
    if not os.path.exists(path):
        return None

    with rasterio.open(path) as src:
        bounds = src.bounds
        if not (bounds.left <= lon <= bounds.right and
                bounds.bottom <= lat <= bounds.top):
            return None

        # pixel coordinates of the clicked point
        row, col = src.index(lon, lat)
        h, w = src.height, src.width
        r0 = max(0, row - window_px)
        r1 = min(h, row + window_px + 1)
        c0 = max(0, col - window_px)
        c1 = min(w, col + window_px + 1)

        from rasterio.windows import Window
        win = Window(c0, r0, c1 - c0, r1 - r0)
        arr = src.read(1, window=win).astype(np.float32)
        nodata = src.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan

    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return None

    return {
        "mean":   round(float(np.mean(valid)), 4),
        "min":    round(float(np.min(valid)),  4),
        "max":    round(float(np.max(valid)),  4),
        "stdDev": round(float(np.std(valid)),  4),
    }


# ---------------------------------------------------------------------------
# Bbox pixel extraction for RF prediction
# ---------------------------------------------------------------------------

def load_feature_matrix_bbox(depth_suffix: str, lon_min: float, lat_min: float,
                               lon_max: float, lat_max: float):
    """
    Extract feature matrix for all pixels inside a bounding box.

    Returns
    -------
    X    : np.ndarray (N_valid, 5)  or None if no valid pixels
    mask : np.ndarray (H, W) bool
    meta : dict
    """
    arrays   = []
    ref_meta = None

    for ds_name in _FEATURE_DATASETS:
        path = get_soil_path(ds_name, depth_suffix)
        arr, meta = load_raster_window(path, lon_min, lat_min, lon_max, lat_max)
        if arr is None:
            return None, None, None
        if ref_meta is None:
            ref_meta = meta
        arrays.append(arr)

    stacked = np.stack(arrays, axis=-1)  # (H, W, 5)
    mask    = np.all(np.isfinite(stacked), axis=-1)
    X       = stacked[mask]
    return X, mask, ref_meta
