"""
IPCC AR6 WG1 climate projections for the Barcelona/Catalonia region.

SSP benchmark data: IPCC AR6 WG1, Chapter 4 & Atlas, Mediterranean regional values.
Barcelona baseline (from CHIRPS 2000–2024 mean): T_mean=16.2°C, precip=580mm/yr.

Scenarios: SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5
"""
import os
import warnings
import numpy as np
from scipy.interpolate import interp1d

# ── Baseline (Barcelona, CHIRPS-calibrated) ────────────────────────────────
BASELINE_TEMP_C   = 16.2    # mean annual temperature °C
BASELINE_PRECIP   = 580.0   # mm/yr total annual precipitation
BASELINE_SUMMER_PRECIP = 85.0  # mm (Jun-Aug), Mediterranean dry summer
BASELINE_CO2_PPM  = 420.0   # 2023 atmospheric CO2
# Barcelona lat for Hargreaves PET
BARCELONA_LAT_RAD = np.radians(41.4)
# Annual mean extraterrestrial radiation at 41.4°N (MJ/m²/day)
RA_BARCELONA = 37.5

# ── SSP benchmark tables (IPCC AR6, Mediterranean) ────────────────────────
# ΔT above pre-industrial (1850–1900 mean ≈ baseline - 1.1°C offset already in baseline)
# Values here are ΔT above 2020 levels (≈ baseline)
_BENCH_YEARS = np.array([2020, 2025, 2030, 2040, 2050, 2060, 2075, 2100])

_DT = {
    "ssp126": np.array([0.0, 0.3,  0.5,  0.7,  1.0,  1.1,  1.2,  1.3]),
    "ssp245": np.array([0.0, 0.3,  0.6,  1.0,  1.5,  1.9,  2.3,  2.7]),
    "ssp370": np.array([0.0, 0.4,  0.7,  1.2,  1.8,  2.4,  3.0,  3.6]),
    "ssp585": np.array([0.0, 0.5,  0.9,  1.5,  2.4,  3.1,  4.0,  5.0]),
}

# Precipitation fractional change (negative = drier)
_DP_FRAC = {
    "ssp126": np.array([0.00, -0.03, -0.04, -0.04, -0.05, -0.05, -0.05, -0.05]),
    "ssp245": np.array([0.00, -0.05, -0.07, -0.10, -0.15, -0.17, -0.19, -0.20]),
    "ssp370": np.array([0.00, -0.06, -0.09, -0.14, -0.18, -0.22, -0.26, -0.30]),  # CHANGED: was -0.28 at 2100
    "ssp585": np.array([0.00, -0.08, -0.12, -0.18, -0.22, -0.26, -0.30, -0.35]),
}

# Summer precip declines faster (Mediterranean amplification)
_DP_SUMMER_FRAC = {
    "ssp126": np.array([0.00, -0.04, -0.06, -0.07, -0.08, -0.08, -0.08, -0.08]),
    "ssp245": np.array([0.00, -0.07, -0.11, -0.16, -0.22, -0.25, -0.27, -0.30]),
    "ssp370": np.array([0.00, -0.09, -0.14, -0.21, -0.27, -0.32, -0.37, -0.42]),
    "ssp585": np.array([0.00, -0.12, -0.18, -0.27, -0.33, -0.39, -0.43, -0.48]),
}

# CO2 ppm (AR6 Table SPM.2)
_CO2 = {
    "ssp126": np.array([420, 430, 435, 440, 440, 435, 430, 400]),
    "ssp245": np.array([420, 445, 465, 510, 560, 590, 600, 600]),
    "ssp370": np.array([420, 450, 480, 540, 620, 720, 790, 860]),
    "ssp585": np.array([420, 460, 500, 600, 750, 900, 980, 1100]),
}

# Extreme precip days >20mm/day (days/yr), Mediterranean trend
_EXTREME_DAYS = {
    "ssp126": np.array([4.5, 4.6, 4.7, 4.8, 4.9, 4.9, 5.0, 5.0]),
    "ssp245": np.array([4.5, 4.7, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5]),
    "ssp370": np.array([4.5, 4.8, 5.2, 6.0, 7.0, 8.0, 9.0, 10.0]),
    "ssp585": np.array([4.5, 5.0, 5.5, 6.5, 8.0, 9.5, 11.0, 13.0]),
}

# ── Build interpolators at module load ────────────────────────────────────
_INTERP = {}
for _scen in ("ssp126", "ssp245", "ssp370", "ssp585"):
    _INTERP[_scen] = {
        "dT":           interp1d(_BENCH_YEARS, _DT[_scen],           kind="linear", fill_value="extrapolate"),
        "dP_frac":      interp1d(_BENCH_YEARS, _DP_FRAC[_scen],      kind="linear", fill_value="extrapolate"),
        "dP_summer":    interp1d(_BENCH_YEARS, _DP_SUMMER_FRAC[_scen],kind="linear", fill_value="extrapolate"),
        "co2":          interp1d(_BENCH_YEARS, _CO2[_scen],           kind="linear", fill_value="extrapolate"),
        "extreme_days": interp1d(_BENCH_YEARS, _EXTREME_DAYS[_scen],  kind="linear", fill_value="extrapolate"),
    }

# ── CHIRPS variance (cached) ───────────────────────────────────────────────
_chirps_variance_cache: dict | None = None

def get_chirps_variance() -> dict:
    """
    Estimate interannual precipitation variability from CHIRPS registry.
    Returns {'precip_std': float, 'temp_std': float}.
    Called once at module load; result cached.
    """
    global _chirps_variance_cache
    if _chirps_variance_cache is not None:
        return _chirps_variance_cache

    try:
        from backend.ml_models.utils import TEMPORAL_REGISTRY
        year_data = TEMPORAL_REGISTRY.get("Precipitation_CHIRPS", {})
        means = []
        for yr, files in year_data.items():
            path = next(iter(files.values()), None)
            if not path or not os.path.isfile(path):
                continue
            try:
                import rasterio
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    with rasterio.open(path) as src:
                        data = src.read(1, masked=True)
                vals = data.compressed().astype(float)
                if len(vals) > 0:
                    means.append(float(np.nanmean(vals)))
            except Exception:
                continue
        if len(means) >= 3:
            mean_val = float(np.mean(means))
            std_raw  = float(np.std(means))
            # Scale raw CHIRPS units → mm/yr using the known Barcelona baseline
            scale = BASELINE_PRECIP / mean_val if mean_val > 0 else 1.0
            precip_std = std_raw * scale   # ~90 mm/yr for Barcelona (≈15% CV, realistic)
            _chirps_variance_cache = {"precip_std": precip_std, "temp_std": 0.6}
        else:
            _chirps_variance_cache = {"precip_std": 45.0, "temp_std": 0.6}
    except Exception:
        _chirps_variance_cache = {"precip_std": 45.0, "temp_std": 0.6}

    return _chirps_variance_cache


def get_climate(scenario_id: str, year: int, seed: int = None) -> dict:
    """
    Return interpolated climate for a given year relative to 2025 (year=0 means 2025).

    Parameters
    ----------
    scenario_id : str  — 'ssp126' | 'ssp245' | 'ssp370' | 'ssp585'
    year : int         — years from 2025 (0 = present, 50 = 2075)
    seed : int | None  — if set, adds reproducible stochastic interannual noise

    Returns
    -------
    dict with keys:
        temp                : float  (°C mean annual)
        precip              : float  (mm/yr total)
        summer_precip       : float  (mm Jun-Aug)
        extreme_precip_days : float  (days/yr > 20mm)
        co2                 : float  (ppm)
        pet                 : float  (mm/yr potential evapotranspiration)
        drought_index       : float  (0–1, 1=severe drought)
    """
    scen = scenario_id if scenario_id in _INTERP else "ssp245"
    calendar_year = 2025 + int(year)
    interp = _INTERP[scen]

    # Clamp to table range
    cal = float(np.clip(calendar_year, _BENCH_YEARS[0], _BENCH_YEARS[-1] + 50))

    dT      = float(interp["dT"](cal))
    dP_frac = float(np.clip(interp["dP_frac"](cal), -0.60, 0.0))
    dP_sum  = float(np.clip(interp["dP_summer"](cal), -0.70, 0.0))
    co2     = float(np.clip(interp["co2"](cal), 400, 1200))
    ex_days = float(np.clip(interp["extreme_days"](cal), 3.0, 20.0))

    # Stochastic interannual variability
    var = get_chirps_variance()
    if seed is not None:
        rng = np.random.default_rng(seed + int(calendar_year))
        noise_T = rng.normal(0, var["temp_std"])
        noise_P = rng.normal(0, var["precip_std"])
    else:
        noise_T = 0.0
        noise_P = 0.0

    temp   = BASELINE_TEMP_C + dT + noise_T
    precip = max(50.0, BASELINE_PRECIP * (1 + dP_frac) + noise_P)
    summer_precip = max(5.0, BASELINE_SUMMER_PRECIP * (1 + dP_sum))

    # Calibrated annual PET for Barcelona (literature: 800-1000 mm/yr Penman-Monteith,
    # SIAR agroclimatic stations 2000-2024 mean ≈ 950 mm/yr).
    # Temperature sensitivity from Hargreaves proportionality: PET ∝ (Tmean + 17.8).
    # Note: using annual-mean Ra in the Hargreaves formula overestimates by ~3.9×;
    # calibrated directly instead.
    _BASELINE_PET = 950.0  # mm/yr
    pet = _BASELINE_PET * (temp + 17.8) / (BASELINE_TEMP_C + 17.8)

    # Drought index: ratio of moisture deficit
    # 0 = no drought (P >= PET), 1 = severe (P << PET)
    drought_index = float(np.clip(1.0 - precip / max(pet, 1.0), 0.0, 1.0))

    return {
        "temp":                temp,
        "precip":              precip,
        "summer_precip":       summer_precip,
        "extreme_precip_days": ex_days,
        "co2":                 co2,
        "pet":                 pet,
        "drought_index":       drought_index,
    }


def get_scenario_display() -> list:
    """Return scenario metadata list for /api/exhibition/climate-scenarios endpoint."""
    return [
        {
            "id":          "ssp126",
            "name":        "SSP1-2.6 — Sustainability",
            "description": "Strong mitigation. Temperature peaks ~+1.3°C above 2020 levels by 2100, then stabilises. Precipitation declines only slightly (~5%). Most optimistic IPCC scenario.",
            "color":       "#22c55e",
            "delta_T_2100": 1.3,
            "delta_P_2100": -5,
        },
        {
            "id":          "ssp245",
            "name":        "SSP2-4.5 — Middle Road",
            "description": "Moderate mitigation. Temperature rises ~+2.7°C by 2100. Annual precipitation declines ~20%, summer rainfall ~30%. The most likely current trajectory.",
            "color":       "#f59e0b",
            "delta_T_2100": 2.7,
            "delta_P_2100": -20,
        },
        {
            "id":          "ssp370",
            "name":        "SSP3-7.0 — Regional Rivalry",
            "description": "High emissions, fragmented policy. Temperature rises ~+3.6°C by 2100. Severe Mediterranean drying: -30% annual, -40% summer precipitation. Significant fire risk.",
            "color":       "#f97316",
            "delta_T_2100": 3.6,
            "delta_P_2100": -30,
        },
        {
            "id":          "ssp585",
            "name":        "SSP5-8.5 — Fossil-Fuelled",
            "description": "Very high emissions. Temperature rises ~+5.0°C by 2100. Catastrophic Mediterranean drought: -35% annual, -48% summer precipitation. High extreme precipitation intensity.",
            "color":       "#ef4444",
            "delta_T_2100": 5.0,
            "delta_P_2100": -35,
        },
    ]
