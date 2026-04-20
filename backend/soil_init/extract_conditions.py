"""
Extract initial soil conditions for the 20×20 simulation grid from real GeoTIFFs.

Barcelona exhibition region:
    41.25°–41.55°N, 1.90°–2.35°E (~30km × 40km)
    At 2.5km GeoTIFF resolution: ~12×16 cells → bilinearly interpolated to 20×20.

Reuses existing data_loader functions — no new rasterio logic needed at top level.
Saxton & Rawls (2006) pedotransfer functions for field capacity and wilting point.
"""
import os
import warnings
import numpy as np

# ── Region definition ─────────────────────────────────────────────────────
REGION = {
    "lat_min": 41.25, "lat_max": 41.55,
    "lon_min": 1.90,  "lon_max": 2.35,
    "grid_rows": 20,  "grid_cols": 20,
}

# ── Saxton & Rawls 2006 pedotransfer functions ────────────────────────────

def _saxton_rawls_fc(sand_pct: np.ndarray, clay_pct: np.ndarray, om_pct: np.ndarray) -> np.ndarray:
    """
    Field capacity at -33 kPa (m³/m³).
    Equation 2 from Saxton & Rawls 2006, SSSAJ 70(5):1569-1578.
    """
    s = np.clip(sand_pct, 1, 98) / 100.0
    c = np.clip(clay_pct, 1, 60) / 100.0
    om = np.clip(om_pct, 0.01, 8.0) / 100.0
    # Eq. 2
    theta_33 = (
        0.299
        - 0.251 * s
        + 0.195 * c
        + 0.011 * om
        + 0.006 * s * om
        - 0.027 * c * om
        + 0.452 * s * c
        + 0.299  # constant term correction (Table 1)
    )
    # Simplified: use published coefficients from Saxton & Rawls Table 1 (Eq 2 rearranged)
    # θ_33t = 0.299 - 0.251*S + 0.195*C + 0.011*OM + 0.006*S*OM - 0.027*C*OM + 0.452*S*C
    theta_33t = 0.299 - 0.251*s + 0.195*c + 0.011*om + 0.006*s*om - 0.027*c*om + 0.452*s*c
    theta_fc = theta_33t + (1.283 * theta_33t**2 - 0.374 * theta_33t - 0.015)
    return np.clip(theta_fc, 0.05, 0.70)


def _saxton_rawls_wp(sand_pct: np.ndarray, clay_pct: np.ndarray, om_pct: np.ndarray) -> np.ndarray:
    """
    Wilting point at -1500 kPa (m³/m³).
    Equation 4 from Saxton & Rawls 2006.
    """
    s = np.clip(sand_pct, 1, 98) / 100.0
    c = np.clip(clay_pct, 1, 60) / 100.0
    om = np.clip(om_pct, 0.01, 8.0) / 100.0
    theta_1500t = (-0.024*s + 0.487*c + 0.006*om
                  + 0.005*s*om - 0.013*c*om + 0.068*s*c + 0.031)
    theta_wp = theta_1500t + (0.14 * theta_1500t - 0.02)
    return np.clip(theta_wp, 0.01, 0.50)


def _compute_ksat(sand_pct: np.ndarray, clay_pct: np.ndarray) -> np.ndarray:
    """
    Saturated hydraulic conductivity (mm/hr).
    Saxton & Rawls 2006 Eq. 9.
    """
    s = np.clip(sand_pct, 1, 98) / 100.0
    c = np.clip(clay_pct, 1, 60) / 100.0
    lambda_b = (np.log(- 0.037 * s + 0.636 * c + 0.003) + 2.0) / 0.319
    lambda_b = np.clip(lambda_b, 0.05, 5.0)
    Ksat = (1930 * (1 - c - s + 0.5 * s) ** (3 - lambda_b))
    return np.clip(Ksat, 0.01, 2000.0)


def _load_raster_window_np(path: str, lat_min: float, lat_max: float,
                             lon_min: float, lon_max: float,
                             target_shape: tuple) -> np.ndarray | None:
    """
    Load a GeoTIFF window and bilinearly interpolate to target_shape (rows, cols).
    Returns float64 array or None on failure.
    """
    if not path or not os.path.isfile(path):
        return None
    try:
        import rasterio
        from rasterio.windows import from_bounds
        from rasterio.errors import NotGeoreferencedWarning
        import scipy.ndimage
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                nodata = src.nodata
                window = from_bounds(lon_min, lat_min, lon_max, lat_max, src.transform)
                data = src.read(1, window=window, masked=True)
        arr = data.astype(np.float64).filled(np.nan)  # cast to float FIRST (SoilGrids is uint8/uint16)
        if nodata is not None:
            arr[np.abs(arr - nodata) < 1e-3 * abs(nodata) + 1e-3] = np.nan
        # Replace NaN with nearest-neighbor fill before resize
        if np.any(np.isnan(arr)):
            from scipy.ndimage import distance_transform_edt
            nan_mask = np.isnan(arr)
            if not np.all(nan_mask):
                idx = distance_transform_edt(nan_mask, return_distances=False, return_indices=True)
                arr = arr[tuple(idx)]
            else:
                arr = np.zeros(arr.shape)
        # Zoom to target shape
        zoom_r = target_shape[0] / max(arr.shape[0], 1)
        zoom_c = target_shape[1] / max(arr.shape[1], 1)
        arr = scipy.ndimage.zoom(arr, (zoom_r, zoom_c), order=1)  # bilinear
        return arr[:target_shape[0], :target_shape[1]]
    except Exception:
        return None


def _make_lat_lon_grids(region: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return (lat_grid, lon_grid) of shape (grid_rows, grid_cols)."""
    lats = np.linspace(region["lat_max"], region["lat_min"], region["grid_rows"])
    lons = np.linspace(region["lon_min"], region["lon_max"], region["grid_cols"])
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return lat_grid, lon_grid


def extract_initial_conditions(
    lat: float = None,
    lon: float = None,
    use_grid: bool = True,
    region: dict = None,
) -> dict:
    """
    Extract initial soil conditions from real GeoTIFFs.

    Parameters
    ----------
    use_grid : bool
        If True: returns 20×20 arrays for the exhibition region.
        If False: returns scalar values for point (lat, lon).
    lat, lon : float
        Used only when use_grid=False.
    region : dict | None
        Override REGION constant if needed.

    Returns
    -------
    dict with keys documented in plan — arrays of shape (20,20) or scalars.
    """
    from backend.ml_models.utils import LOCAL_REGISTRY, DEPTH_ORDER, TEMPORAL_REGISTRY

    reg = region or REGION
    rows, cols = reg["grid_rows"], reg["grid_cols"]
    target_shape = (rows, cols)

    if not use_grid and lat is not None and lon is not None:
        # Point extraction: use a tiny window around the point
        half_deg = 0.05
        reg = {
            "lat_min": lat - half_deg, "lat_max": lat + half_deg,
            "lon_min": lon - half_deg, "lon_max": lon + half_deg,
            "grid_rows": 3, "grid_cols": 3,
        }
        target_shape = (3, 3)
        rows, cols = 3, 3

    lat_grid, lon_grid = _make_lat_lon_grids(reg)
    lat_min, lat_max = reg["lat_min"], reg["lat_max"]
    lon_min, lon_max = reg["lon_min"], reg["lon_max"]

    def load(name, band=None):
        """Load a raster and return array of target_shape. Falls back to default."""
        entry = LOCAL_REGISTRY.get(name, {})
        files = entry.get("local_files", {})
        if band:
            path = files.get(band)
        else:
            # Use first depth band or primary file
            path = next((files[b] for b in DEPTH_ORDER if b in files),
                       next(iter(files.values()), None))
        result = _load_raster_window_np(path, lat_min, lat_max, lon_min, lon_max, target_shape)
        return result

    # ── Six-layer SoilGrids loader ────────────────────────────────────────
    # SoilGrids 2.0 native depth intervals: 0-5, 5-15, 15-30, 30-60, 60-100, 100-200 cm
    # We load all six for carbon AND texture, bulk density, pH — the cross-section
    # visualizer and the 6-layer RothC integration both need per-depth data.
    SOIL_BANDS = ("b0", "b10", "b30", "b60", "b100", "b200")
    N_LAYERS = 6

    def load_six_bands(variable_name: str, scale: float, default: float,
                       lo: float, hi: float) -> np.ndarray:
        """Load 6 SoilGrids depth bands for one variable, returning (rows, cols, 6)."""
        layers = []
        for band in SOIL_BANDS:
            arr = load(variable_name, band)
            if arr is None:
                arr = np.full(target_shape, default)
            else:
                arr = arr / scale
            layers.append(np.clip(arr, lo, hi))
        return np.stack(layers, axis=-1)  # (rows, cols, 6)

    # Organic carbon — SoilGrids stores cg/kg, scale=10 gives g/kg
    organic_carbon_6layer = load_six_bands(
        "Organic_Carbon", scale=10.0, default=8.0, lo=0.01, hi=200.0
    )
    oc_layer0 = organic_carbon_6layer[:, :, 0]  # surface (0-5cm) alias

    # Sand / clay — SoilGrids stores g/kg, scale=10 gives %
    sand_6layer = load_six_bands(
        "Sand_Content", scale=10.0, default=350.0 / 10.0, lo=1.0, hi=98.0
    )
    clay_6layer = load_six_bands(
        "Clay_Content", scale=10.0, default=250.0 / 10.0, lo=1.0, hi=60.0
    )
    silt_6layer = np.clip(100.0 - sand_6layer - clay_6layer, 0.0, 90.0)

    # Bulk density — SoilGrids stores cg/cm³, scale=100 gives g/cm³ = t/m³
    bulk_density_6layer = load_six_bands(
        "Bulk_Density", scale=100.0, default=1.35, lo=0.8, hi=2.2
    )

    # pH — SoilGrids stores pH×10, scale=10 gives pH units
    soil_ph_6layer = load_six_bands(
        "Soil_pH", scale=10.0, default=7.2, lo=3.5, hi=9.5
    )

    # Surface aliases — every legacy consumer that expected a 2-D (rows, cols) array
    # continues to work from the surface layer (0-5 cm band).
    sand_pct     = sand_6layer[:, :, 0]
    clay_pct     = clay_6layer[:, :, 0]
    silt_pct     = silt_6layer[:, :, 0]
    bulk_density = bulk_density_6layer[:, :, 0]
    soil_ph      = soil_ph_6layer[:, :, 0]

    # The engine consumes `organic_carbon` as the full per-layer stack.
    # The shape changes from (rows, cols, 3) to (rows, cols, 6) — engine.py
    # reads N_LAYERS from the trailing axis.
    organic_carbon_layered = organic_carbon_6layer

    # ── Texture class (USDA) ──────────────────────────────────────────────
    tex_arr = load("Soil_Texture")
    if tex_arr is not None:
        texture_class = np.clip(np.round(tex_arr), 1, 12).astype(np.int32)
    else:
        texture_class = np.full(target_shape, 3, dtype=np.int32)  # Sandy loam default

    # ── Pedotransfer: FC, WP, AWC ─────────────────────────────────────────
    om_pct = oc_layer0 * 1.724 / 10.0  # OC g/kg → OM % (Van Bemmelen factor)
    field_capacity = _saxton_rawls_fc(sand_pct, clay_pct, om_pct)
    wilting_point  = _saxton_rawls_wp(sand_pct, clay_pct, om_pct)
    awc            = np.clip(field_capacity - wilting_point, 0.01, 0.40)

    # ── Derived properties ────────────────────────────────────────────────
    porosity = np.clip(1.0 - bulk_density / 2.65, 0.20, 0.65)

    # Aggregate stability (0-1): proxy from OC and clay content
    # Based on Six et al. 2004 — higher OC + clay → more stable aggregates
    aggregate_stability = np.clip(
        0.3 + 0.04 * oc_layer0 + 0.005 * clay_pct, 0.1, 1.0
    )

    # Initial soil moisture: assume field capacity at start
    initial_moisture = field_capacity.copy()

    # ── CHIRPS baseline stats ─────────────────────────────────────────────
    try:
        from backend.climate_scenarios.ssp_data import get_chirps_variance, BASELINE_PRECIP
        var = get_chirps_variance()
        chirps_baseline = BASELINE_PRECIP
        chirps_std = var["precip_std"]
    except Exception:
        chirps_baseline = 580.0
        chirps_std = 45.0

    result = {
        "organic_carbon":       organic_carbon_layered,   # (rows, cols, 6) g/kg
        "organic_carbon_layer0": oc_layer0,                # (rows, cols) surface alias

        # 6-layer SoilGrids stacks — consumed by the cross-section visualiser and by
        # the 6-layer RothC integration. Shape (rows, cols, 6) for each.
        "organic_carbon_6layer": organic_carbon_6layer,
        "sand_pct_6layer":       sand_6layer,
        "clay_pct_6layer":       clay_6layer,
        "silt_pct_6layer":       silt_6layer,
        "bulk_density_6layer":   bulk_density_6layer,
        "soil_ph_6layer":        soil_ph_6layer,

        "soil_ph":              soil_ph,
        "bulk_density":         bulk_density,
        "sand_pct":             sand_pct,
        "clay_pct":             clay_pct,
        "silt_pct":             silt_pct,
        "texture_class":        texture_class,
        "porosity":             porosity,
        "field_capacity":       field_capacity,
        "wilting_point":        wilting_point,
        "awc":                  awc,
        "initial_moisture":     initial_moisture,
        "aggregate_stability":  aggregate_stability,
        "ksat":                 _compute_ksat(sand_pct, clay_pct),
        "lat_grid":             lat_grid,
        "lon_grid":             lon_grid,
        "valid_mask":           np.ones(target_shape, dtype=bool),
        "chirps_baseline_precip": chirps_baseline,
        "chirps_precip_std":    chirps_std,
        "region":               reg,
    }

    # For single-point extraction, reduce to scalars by taking the MEAN over
    # the 3×3 window around the point rather than the centre cell. The centre
    # cell alone can hit a SoilGrids outlier (e.g. a built-up or water pixel
    # with OC ≈ 0.3 g/kg), which then sends the legacy 1-cell RothC forecast
    # into physically meaningless territory (a 742 % change on a 0.3-baseline).
    # The mean is robust to single-pixel anomalies while staying local.
    if not use_grid:
        scalar_result = {}
        for k, v in result.items():
            if isinstance(v, np.ndarray) and v.ndim >= 2:
                if v.ndim == 3:
                    scalar_result[k] = v.mean(axis=(0, 1))          # (n_layers,)
                else:
                    scalar_result[k] = float(v.mean())
            else:
                scalar_result[k] = v
        return scalar_result

    return result
