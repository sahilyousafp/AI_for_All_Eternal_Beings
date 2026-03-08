"""
RUSLE erosion model + D8 sediment routing across the 20×20 grid.

RUSLE: A = R × K × LS × C × P  [t/ha/yr]

References:
  Wischmeier & Smith (1978) USDA Agriculture Handbook 537.
  Ferro et al. (1999) western Mediterranean rainfall erosivity.
  Foster et al. (1977) LS factor.
"""
import numpy as np


def _init_slope_grid(region: dict) -> tuple:
    """
    Generate a realistic slope distribution for the Barcelona exhibition region.
    Barcelona terrain: Collserola hills (NW), Garraf massif (SW), Llobregat plain (centre).
    Returns (slope_degrees, flow_direction) as (20,20) arrays.
    flow_direction: integer 1-8 (D8 encoding: 1=E, 2=SE, 3=S, 4=SW, 5=W, 6=NW, 7=N, 8=NE)
    """
    rows = region.get("grid_rows", 20)
    cols = region.get("grid_cols", 20)

    # Create a synthetic elevation surface for Barcelona region
    # Collserola range in NW (higher), Garraf in SW, Llobregat plain in centre-east
    row_idx, col_idx = np.mgrid[0:rows, 0:cols]
    # Normalise to [0,1]
    row_n = row_idx / (rows - 1)   # 0 = north (Collserola), 1 = south (coast)
    col_n = col_idx / (cols - 1)   # 0 = west, 1 = east

    # Synthetic elevation (m): hills in NW, plain in centre, slight rise SW (Garraf)
    elev = (
        300.0 * np.exp(-((row_n - 0.0)**2 + (col_n - 0.15)**2) / 0.04)   # Collserola
        + 180.0 * np.exp(-((row_n - 0.8)**2 + (col_n - 0.1)**2) / 0.05)  # Garraf
        + 20.0 * (1.0 - col_n)  # slight W-E gradient
        + np.random.default_rng(42).normal(0, 5, (rows, cols))             # roughness
    )

    # Slope from elevation gradient (degrees)
    cell_size_m = 2500.0  # ~2.5km GeoTIFF resolution in metres
    dy, dx = np.gradient(elev, cell_size_m)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    slope_deg = np.clip(slope_deg, 0.5, 35.0)

    # D8 flow direction from steepest descent
    flow_dir = np.ones((rows, cols), dtype=np.int32) * 3  # default: south
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            # 8-neighbour elevation differences
            neighbours = [
                (elev[r, c] - elev[r, c+1],   1),   # E
                (elev[r, c] - elev[r+1, c+1], 2),   # SE
                (elev[r, c] - elev[r+1, c],   3),   # S
                (elev[r, c] - elev[r+1, c-1], 4),   # SW
                (elev[r, c] - elev[r, c-1],   5),   # W
                (elev[r, c] - elev[r-1, c-1], 6),   # NW
                (elev[r, c] - elev[r-1, c],   7),   # N
                (elev[r, c] - elev[r-1, c+1], 8),   # NE
            ]
            best = max(neighbours, key=lambda x: x[0])
            flow_dir[r, c] = best[1]

    return slope_deg, flow_dir


# Pre-compute slope grid once (fixed for Barcelona region)
_DEFAULT_REGION = {"grid_rows": 20, "grid_cols": 20}
_SLOPE_GRID, _FLOW_DIR = _init_slope_grid(_DEFAULT_REGION)


def compute_erosion(
    climate: dict,
    soil_state: dict,
    veg_state: dict,
    params: dict,
    slope_grid: np.ndarray = None,
    flow_direction: np.ndarray = None,
) -> dict:
    """
    Compute RUSLE erosion and D8 sediment routing for the 20×20 grid.

    Parameters
    ----------
    climate    : dict from ssp_data.get_climate()
    soil_state : dict with keys: sand_pct, clay_pct, silt_pct, organic_carbon,
                 aggregate_stability — all shape (20,20)
    veg_state  : dict with canopy_cover (20,20), stand_age, params
    params     : dict — philosophy params (P_factor, C_factor_mulch, tillage, etc.)
    slope_grid, flow_direction : override defaults if DEM available

    Returns
    -------
    dict:
        erosion_rate        : (20,20) t/ha/yr
        soc_erosion_loss    : (20,20) t C/ha/yr
        sediment_deposition : (20,20) t/ha/yr
        R_factor            : float (scalar)
    """
    # Determine grid shape from soil_state (not from slope_grid, which may be 20×20 default)
    _oc_ref = soil_state.get("organic_carbon", soil_state.get("clay_pct", None))
    if _oc_ref is not None and hasattr(_oc_ref, "shape") and _oc_ref.ndim == 2:
        rows, cols = _oc_ref.shape
    elif slope_grid is not None:
        rows, cols = slope_grid.shape
    else:
        rows, cols = 20, 20

    # Regenerate slope / flow grids if size doesn't match
    if slope_grid is None or slope_grid.shape != (rows, cols):
        slope_grid, flow_direction = _init_slope_grid({"grid_rows": rows, "grid_cols": cols})
    elif flow_direction is None or flow_direction.shape != (rows, cols):
        _, flow_direction = _init_slope_grid({"grid_rows": rows, "grid_cols": cols})
    precip      = climate.get("precip", 580.0)
    extreme_days = climate.get("extreme_precip_days", 4.5)

    # ── R factor: Rainfall erosivity ──────────────────────────────────────
    # Ferro et al. (1999) western Mediterranean equation
    # R = 0.29 × P^1.23 + 1.8 × extreme_days
    R = 0.29 * (precip ** 1.23) + 1.8 * extreme_days

    # ── K factor: Soil erodibility (Wischmeier nomograph) ────────────────
    sand = soil_state.get("sand_pct", np.full((rows, cols), 35.0))
    clay = soil_state.get("clay_pct", np.full((rows, cols), 25.0))
    silt = soil_state.get("silt_pct", np.full((rows, cols), 40.0))
    oc   = soil_state.get("organic_carbon", np.full((rows, cols), 8.0))

    # OM = OC × 1.724 (Van Bemmelen factor); OC in g/kg → OM in %
    OM = np.clip(oc * 1.724 / 10.0, 0.1, 8.0)  # %
    # M = (silt + very_fine_sand) × (100 - clay): use silt as proxy for silt+VFS
    M  = np.clip((silt + 0.15 * sand) * (100.0 - clay), 100, 80000)
    # Structure code=2 (medium granular), permeability=3 (moderate)
    s_code = 2.0
    p_code = 3.0
    K = (2.1e-4 * (M ** 1.14) * (12.0 - OM) + 3.25 * (s_code - 2) + 2.5 * (p_code - 3)) / 100.0
    K = np.clip(K, 0.01, 0.65)  # realistic range for Mediterranean soils

    # ── LS factor: Slope length-steepness ────────────────────────────────
    # Assume uniform slope length of 100m (standard RUSLE field scale)
    slope_length_m = 100.0
    slope_rad = np.radians(np.clip(slope_grid, 0.1, 35.0))
    m = 0.4   # slope length exponent for Mediterranean
    n = 1.3   # slope steepness exponent
    LS = ((slope_length_m / 22.1) ** m) * ((np.sin(slope_rad) / 0.0896) ** n)
    LS = np.clip(LS, 0.1, 25.0)

    # ── C factor: Cover-management ────────────────────────────────────────
    canopy = veg_state.get("canopy_cover", np.zeros((rows, cols)))
    understory = np.clip(canopy * 0.5, 0, 0.4)   # proxy for understory
    mulch_frac = params.get("C_factor_mulch", 0.0)

    # Post-fire hydrophobicity: C=0.85 for 2 years
    post_fire_yr = soil_state.get("post_fire_year", 0)
    if post_fire_yr > 0:
        C_fire = np.full((rows, cols), 0.85)
    else:
        C_fire = None

    C = np.maximum(
        0.001,
        (1.0 - canopy) * (1.0 - understory) * (1.0 - mulch_frac)
    )
    if C_fire is not None:
        C = np.maximum(C, C_fire)
    C = np.clip(C, 0.001, 1.0)

    # ── P factor: Conservation practice ──────────────────────────────────
    P = params.get("P_factor", 1.0)

    # ── RUSLE: A = R × K × LS × C × P ────────────────────────────────────
    erosion_rate = R * K * LS * C * P
    erosion_rate = np.clip(erosion_rate, 0.0, 500.0)  # t/ha/yr

    # ── SOC erosion loss ──────────────────────────────────────────────────
    # SOC loss proportional to erosion, enriched in surface organic particles
    agg_stab = soil_state.get("aggregate_stability", np.full((rows, cols), 0.5))
    # Enrichment ratio: more erosion of fine, OC-rich particles when unstable
    enrichment_ratio = np.clip(1.5 + 1.5 * (1.0 - agg_stab), 1.0, 3.0)
    surface_oc_conc  = oc / 1000.0  # g/kg → kg/kg (t C / t soil)
    soc_erosion_loss = erosion_rate * enrichment_ratio * surface_oc_conc  # t C/ha/yr
    soc_erosion_loss = np.clip(soc_erosion_loss, 0, erosion_rate * 0.1)

    # ── D8 Sediment routing ───────────────────────────────────────────────
    # Route eroded sediment downslope; downstream cell receives deposition
    sediment_deposition = np.zeros((rows, cols))

    # D8 direction offsets: 1=E, 2=SE, 3=S, 4=SW, 5=W, 6=NW, 7=N, 8=NE
    D8_OFFSETS = {
        1: (0, 1), 2: (1, 1), 3: (1, 0), 4: (1, -1),
        5: (0, -1), 6: (-1, -1), 7: (-1, 0), 8: (-1, 1),
    }

    canopy_flat = canopy  # for delivery ratio computation
    for r in range(rows):
        for c in range(cols):
            d = int(flow_direction[r, c])
            if d not in D8_OFFSETS:
                continue
            dr, dc = D8_OFFSETS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                # Delivery ratio: fraction of eroded sediment reaching downstream cell
                delivery = 0.3 * (1.0 - float(canopy_flat[nr, nc]))
                delivery = np.clip(delivery, 0.0, 0.3)
                sediment_deposition[nr, nc] += float(erosion_rate[r, c]) * delivery

    return {
        "erosion_rate":        erosion_rate,
        "soc_erosion_loss":    soc_erosion_loss,
        "sediment_deposition": sediment_deposition,
        "R_factor":            float(R),
    }
