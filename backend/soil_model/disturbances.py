"""
Stochastic disturbance events: fire, drought, flood.

10-member ensemble supported via per-member seeds.
Fire probability model accounts for fuel load, drought, and climate warming.
"""
import numpy as np


def check_disturbances(
    year: int,
    state: dict,
    climate: dict,
    params: dict,
    ensemble_seed: int,
) -> dict:
    """
    Determine disturbance events for this year.

    Parameters
    ----------
    year           : int — simulation year index (0 = start, not calendar year)
    state          : dict — current simulation state (biomass, moisture_ratio, etc.)
    climate        : dict from ssp_data.get_climate()
    params         : dict — philosophy parameters
    ensemble_seed  : int — unique seed per ensemble member for reproducibility

    Returns
    -------
    dict:
        fire             : bool
        severity         : str | None  ('high', 'low', or None)
        drought_year     : int  (consecutive drought years counter)
        flood            : bool
        hydrophobic      : bool  (post-fire water repellency)
        post_fire_year   : int   (years since last fire, 0 = no fire history)
    """
    rng = np.random.default_rng(ensemble_seed + year * 997)

    biomass       = float(np.mean(state.get("biomass", np.array([50.0]))))
    moisture_mean = float(np.mean(state.get("moisture_ratio", np.array([0.5]))))
    Bmax          = params.get("Bmax", 100.0)
    temp          = climate.get("temp", 16.2)
    drought_index = climate.get("drought_index", 0.0)

    # ── Fire probability ──────────────────────────────────────────────────
    p_fire_base   = 0.02   # 2%/yr Mediterranean scrub baseline
    managed_fire  = params.get("managed_fire", False)

    if managed_fire:
        # Prescribed burn: low probability of natural fire (managed)
        p_fire_base = 0.01
        severity_override = "low"
    else:
        severity_override = None

    # Fuel factor: more standing biomass → higher fire probability
    fuel_factor   = np.clip(1.0 + biomass / max(Bmax, 1.0), 1.0, 3.0)
    # Drought factor: dry conditions elevate fire risk
    drought_factor = 1.0 + 2.0 * max(0.0, 0.5 - moisture_mean)
    # Temperature factor: warming increases fire weather days
    delta_temp    = max(0.0, temp - 16.2)  # above baseline
    temp_factor   = 1.0 + 0.15 * max(0.0, delta_temp - 2.0)

    p_fire = np.clip(
        p_fire_base * fuel_factor * drought_factor * temp_factor,
        0.0, 0.20
    )

    fire_occurs = bool(rng.random() < p_fire)

    # ── Fire severity ─────────────────────────────────────────────────────
    severity = None
    if fire_occurs:
        if severity_override:
            severity = severity_override
        else:
            # Higher fuel load → more likely crown fire (high severity)
            p_high = np.clip(0.30 + 0.40 * (biomass / max(Bmax, 1.0)), 0.1, 0.9)
            severity = "high" if rng.random() < p_high else "low"

    # ── Drought tracking ──────────────────────────────────────────────────
    prev_drought_yr = state.get("drought_year", 0)
    if drought_index > 0.65:
        drought_year = prev_drought_yr + 1
    elif drought_index > 0.50:
        drought_year = max(0, prev_drought_yr - 1)   # partial recovery
    else:
        drought_year = 0  # drought broken

    # ── Flood ─────────────────────────────────────────────────────────────
    # Rare but possible after severe drought + intense precipitation
    extreme_days = climate.get("extreme_precip_days", 4.5)
    p_flood = 0.005 * (1 + max(0, drought_year - 1)) * (extreme_days / 5.0)
    flood = bool(rng.random() < min(p_flood, 0.05))

    # ── Post-fire tracking ────────────────────────────────────────────────
    prev_post_fire = state.get("post_fire_year", 0)
    if fire_occurs and severity == "high":
        post_fire_year = 1
    elif prev_post_fire > 0 and prev_post_fire < 3:
        post_fire_year = prev_post_fire + 1   # hydrophobicity lasts ~2 years
    else:
        post_fire_year = 0

    hydrophobic = post_fire_year > 0 and severity == "high"

    return {
        "fire":          fire_occurs,
        "severity":      severity,
        "drought_year":  drought_year,
        "flood":         flood,
        "hydrophobic":   hydrophobic,
        "post_fire_year": post_fire_year,
    }
