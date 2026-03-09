"""
Annual water balance model per grid cell.

Drives RothC moisture modifier and vegetation water stress.
Uses simplified annual bucket model with Hargreaves PET.
Saxton-Rawls Ksat for infiltration capacity.

Reference: Hargreaves & Samani (1985) for PET.
"""
import numpy as np

# Barcelona annual mean extraterrestrial radiation (MJ/m²/day)
RA_BARCELONA = 37.5
# Temperature range for Barcelona (°C, used in Hargreaves)
T_RANGE_BARCELONA = 12.0


def _hargreaves_pet(temp: float) -> float:
    """
    Simplified Hargreaves PET (mm/yr).
    PET_daily = 0.0023 × Ra × (Tmean + 17.8) × ΔTrange^0.5
    Annual = PET_daily × 365.
    """
    pet_daily = 0.0023 * RA_BARCELONA * (temp + 17.8) * (T_RANGE_BARCELONA ** 0.5)
    return max(0.0, pet_daily * 365.0)


def annual_water_balance(
    precip: float,
    pet: float,
    field_capacity: np.ndarray,
    wilting_point: np.ndarray,
    current_moisture: np.ndarray,
    canopy_cover: np.ndarray,
    impervious_fraction: np.ndarray = None,
    ksat: np.ndarray = None,
) -> dict:
    """
    Simple annual bucket water balance.

    Parameters
    ----------
    precip : float — annual precipitation mm/yr
    pet    : float — potential evapotranspiration mm/yr
    field_capacity   : np.ndarray (n_cells,) or (rows,cols) — m³/m³
    wilting_point    : np.ndarray — m³/m³
    current_moisture : np.ndarray — current volumetric moisture m³/m³
    canopy_cover     : np.ndarray — fractional, 0–1
    impervious_fraction : np.ndarray | None — fraction impervious (roads etc.)
    ksat : np.ndarray | None — saturated hydraulic conductivity mm/hr

    Returns
    -------
    dict with keys: soil_moisture, moisture_ratio, actual_et, runoff,
                    water_stress, deep_drainage
    """
    shape = field_capacity.shape
    if impervious_fraction is None:
        impervious_fraction = np.zeros(shape)
    if ksat is None:
        ksat = np.full(shape, 10.0)  # mm/hr default

    # ── Runoff ────────────────────────────────────────────────────────────
    # Infiltration capacity (mm/yr) = Ksat (mm/hr) × 8760 hr/yr × availability
    # Simplified: fraction of precip that runs off increases with saturation
    saturation_index = np.clip(current_moisture / np.maximum(field_capacity, 0.01), 0, 1)
    # CN-like runoff coefficient: 0 when dry, higher when wet
    runoff_coeff = np.clip(saturation_index ** 2, 0, 0.8)
    runoff_coeff = np.where(impervious_fraction > 0,
                            runoff_coeff + impervious_fraction * (1 - runoff_coeff),
                            runoff_coeff)
    runoff = precip * runoff_coeff  # mm/yr

    # ── Infiltration → soil storage ───────────────────────────────────────
    infiltrated = precip - runoff
    # Convert mm/yr to m³/m³: assuming 1m soil depth reference
    moisture_input = infiltrated / 1000.0  # rough: mm → fraction

    new_moisture = current_moisture + moisture_input

    # ── Actual ET — Budyko-constrained ────────────────────────────────────
    # Crop coefficient by canopy cover (FAO-56 style)
    Kc = 0.4 + 0.6 * canopy_cover   # bare=0.4, full canopy=1.0
    pet_kc_mm = pet * Kc             # cell-specific annual PET demand (mm/yr)

    # Fu (1981) Budyko parametric curve (w=2.0) — correctly handles
    # Mediterranean seasonality: soil refills in wet winter, drains in dry summer.
    # Annual AET is constrained by both water supply (P) and energy demand (PET).
    phi = pet_kc_mm / max(float(precip), 1.0)
    phi_arr = np.full(shape, phi) if np.isscalar(phi) else np.asarray(phi)
    w = 2.0
    aet_fraction = np.clip(1 + phi_arr - (1 + phi_arr ** w) ** (1.0 / w), 0.0, 1.0)
    budyko_aet_m3 = aet_fraction * precip / 1000.0   # m³/m³ (1 m depth reference)

    # Actual ET further limited by soil water availability
    available_water = np.maximum(new_moisture - wilting_point, 0.0)
    actual_et = np.minimum(budyko_aet_m3, available_water)

    new_moisture = np.clip(new_moisture - actual_et, wilting_point, None)

    # ── Deep drainage ─────────────────────────────────────────────────────
    # Excess above field capacity drains downward (half drains each year)
    excess = np.maximum(new_moisture - field_capacity, 0.0)
    deep_drainage = excess * 0.5
    new_moisture = new_moisture - deep_drainage
    new_moisture = np.clip(new_moisture, wilting_point, field_capacity)

    # ── Moisture ratio (0–1 where 1 = at field capacity) ─────────────────
    fc_range = np.maximum(field_capacity - wilting_point, 0.001)
    moisture_ratio = np.clip(
        (new_moisture - wilting_point) / fc_range, 0.0, 1.0
    )

    # ── Water stress ──────────────────────────────────────────────────────
    # 0 = no stress (plenty of water), 1 = severe stress
    water_stress = np.clip(1.0 - moisture_ratio, 0.0, 1.0)

    return {
        "soil_moisture":   new_moisture,
        "moisture_ratio":  moisture_ratio,
        "actual_et":       float(np.mean(actual_et)) * 1000.0,  # back to mm/yr for reporting
        "runoff":          runoff,
        "water_stress":    water_stress,
        "deep_drainage":   deep_drainage,
    }


def compute_awc(
    sand_pct: np.ndarray,
    clay_pct: np.ndarray,
    om_pct: np.ndarray,
) -> np.ndarray:
    """
    Available water capacity = FC - WP (m³/m³).
    Uses Saxton & Rawls 2006 pedotransfer functions.
    """
    s = np.clip(sand_pct, 1, 98) / 100.0
    c = np.clip(clay_pct, 1, 60) / 100.0
    om = np.clip(om_pct, 0.01, 8.0) / 100.0

    # FC (Saxton & Rawls Eq. 2)
    theta_33t = 0.299 - 0.251*s + 0.195*c + 0.011*om + 0.006*s*om - 0.027*c*om + 0.452*s*c
    fc = np.clip(theta_33t + (1.283 * theta_33t**2 - 0.374 * theta_33t - 0.015), 0.05, 0.70)

    # WP (Saxton & Rawls Eq. 4)
    theta_1500t = (-0.024*s + 0.487*c + 0.006*om
                  + 0.005*s*om - 0.013*c*om + 0.068*s*c + 0.031)
    wp = np.clip(theta_1500t + (0.14 * theta_1500t - 0.02), 0.01, 0.50)

    return np.clip(fc - wp, 0.01, 0.40)
