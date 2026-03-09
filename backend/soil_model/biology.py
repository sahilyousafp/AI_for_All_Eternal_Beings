"""
Biological integrity model: mycorrhizal network, earthworm activity,
aggregate stability, and biological integrity index (BII).

BII is a functional proxy for soil biodiversity — it tracks ecosystem
service delivery rather than species counts.

All arrays shape (n_cells,) unless noted.
"""
import numpy as np


def biology_step(
    state: dict,
    climate: dict,
    params: dict,
    disturbance: dict,
    soil_oc: np.ndarray,
    soil_ph: np.ndarray,
    moisture_ratio: np.ndarray,
    veg_state: dict,
) -> dict:
    """
    One annual timestep of soil biology dynamics.

    Parameters
    ----------
    state : dict with keys:
        bii              : np.ndarray (n_cells,) 0-1 biological integrity index
        mycorrhizal      : np.ndarray (n_cells,) 0-1 mycorrhizal network density
        earthworm        : np.ndarray (n_cells,) 0-1 earthworm activity index
        aggregate_stability : np.ndarray (n_cells,) 0-1
    climate : dict from ssp_data.get_climate()
    params  : dict — species params (myc_rate etc.)
    disturbance : dict from disturbances.check_disturbances()
    soil_oc   : np.ndarray (n_cells,) — surface OC g/kg
    soil_ph   : np.ndarray (n_cells,) — pH
    moisture_ratio : np.ndarray (n_cells,) 0-1
    veg_state : dict — from vegetation_step(), has canopy_cover, density, biomass

    Returns
    -------
    Updated state dict with same keys.
    """
    bii  = state["bii"].copy()
    myc  = state["mycorrhizal"].copy()
    ew   = state["earthworm"].copy()
    agg  = state["aggregate_stability"].copy()

    n_cells = bii.shape[0]
    temp = climate.get("temp", 16.2)
    precip = climate.get("precip", 580.0)

    fire        = disturbance.get("fire", False)
    severity    = disturbance.get("severity", None)
    tillage     = params.get("tillage", False)
    drought_yr  = disturbance.get("drought_year", 0)

    canopy_cover = veg_state.get("canopy_cover", np.zeros(n_cells))
    root_density = veg_state.get("biomass", np.zeros(n_cells)) * 0.30  # root biomass proxy

    # ── BII recovery dynamics ─────────────────────────────────────────────
    # dBII/dt = recovery_rate × (1 - BII) × f(OC, moisture, pH, veg)
    recovery_rate = 0.04  # ~25yr to fully recover from bare (established in lit.)

    # Favourable conditions for recovery:
    f_oc   = np.clip(soil_oc / 12.0, 0, 1)   # normalised OC (12 g/kg = good)
    f_mois = np.clip(moisture_ratio, 0, 1)
    f_ph   = np.clip(1.0 - np.abs(soil_ph - 6.5) / 3.0, 0, 1)  # optimum pH 6.5
    f_veg  = np.clip(canopy_cover, 0, 1)
    f_env  = (f_oc + f_mois + f_ph + f_veg) / 4.0

    bii_recovery = recovery_rate * (1.0 - bii) * f_env
    bii = np.clip(bii + bii_recovery, 0, 1)

    # ── Disturbance losses ────────────────────────────────────────────────
    if tillage:
        bii  *= 0.30   # severe disruption of soil food web
        myc  *= 0.20   # destroys hyphal networks
        ew   *= 0.50   # mechanical damage + burial

    if fire:
        if severity == "high":
            bii  *= 0.10   # topsoil sterilisation
            myc  *= 0.10
            ew   *= 0.15
            agg  *= 0.30   # hydrophobicity reduces stability
        elif severity == "low":
            bii  *= 0.60   # partial disruption
            myc  *= 0.50
            ew   *= 0.70

    # Drought: pull BII toward a drought equilibrium (target-based, not compounding multiplication)
    # Prevents permanent collapse under sustained warming — microbes adapt or form spores
    if drought_yr >= 1:
        drought_bii_eq = np.clip(moisture_ratio * 0.5, 0.05, 0.30)
        bii = bii + 0.08 * (drought_bii_eq - bii)   # converge ~8%/yr → recover in ~12yr
        # Earthworms are more drought-sensitive — harder moisture threshold
        if drought_yr >= 2:
            ew_factor = np.clip(moisture_ratio * 2.0, 0.30, 1.0)
            ew = ew * ew_factor

    # ── Mycorrhizal network dynamics ──────────────────────────────────────
    # dMyc/dt = myc_rate × root_density × f(moisture) - 0.15 × Myc
    myc_rate     = params.get("myc_rate", 0.05)
    root_density_norm = np.clip(root_density / max(params.get("Bmax", 100.0) * 0.3, 1), 0, 1)
    f_myc_mois   = np.clip(moisture_ratio - 0.1, 0, 0.9) / 0.9   # myc need some moisture
    myc_growth   = myc_rate * root_density_norm * f_myc_mois
    myc_decay    = 0.15 * myc
    myc          = np.clip(myc + myc_growth - myc_decay, 0, 1)

    # ── Earthworm activity index ──────────────────────────────────────────
    # Active when: pH > 4.5, moisture > WP*1.2, temp < 32°C
    ew_active = (soil_ph > 4.5) & (moisture_ratio > 0.15) & (temp < 32.0)
    # Labile C (approx = OC / 50, fast-cycling fraction)
    labile_c    = np.clip(soil_oc / 50.0, 0, 1)
    ew_growth   = np.where(ew_active, 0.15 * labile_c * f_mois, 0.0)
    ew_decay    = 0.08 * ew
    ew          = np.clip(ew + ew_growth - ew_decay, 0, 1)

    # ── Aggregate stability dynamics ──────────────────────────────────────
    # dAgg/dt = root_binding + glomalin + earthworm_casting
    #           - raindrop_impact - tillage_reset
    root_binding        = root_density_norm * 0.01
    glomalin            = myc * 0.05           # fungal glycoprotein
    earthworm_casting   = ew  * 0.03

    # Raindrop impact: greater when bare, high intensity rain
    extreme_days  = climate.get("extreme_precip_days", 4.5)
    rainfall_intensity = extreme_days / 15.0   # normalise
    bare_fraction = np.clip(1.0 - canopy_cover, 0, 1)
    # Mulch fraction from params (0 if not specified)
    mulch = params.get("C_factor_mulch", 0.0)
    raindrop_impact = bare_fraction * (1.0 - mulch) * rainfall_intensity * 0.008

    tillage_loss = -0.60 * agg if tillage else np.zeros(n_cells)

    agg = np.clip(
        agg + root_binding + glomalin + earthworm_casting - raindrop_impact + tillage_loss,
        0.05, 1.0
    )

    # ── BII ceiling by soil pH ────────────────────────────────────────────
    # pH sets a MAXIMUM BII (calcareous high-pH soils can be biodverse but at lower ceiling)
    # NOT an annual multiplicative penalty — just a cap on potential
    ph_bii_max = np.where(
        soil_ph <= 8.5, 1.0,
        np.where(soil_ph <= 9.0, 0.55, 0.30)
    )
    ph_bii_max = np.where(soil_ph >= 4.5, ph_bii_max, 0.30)  # strong acid also limits
    bii = np.minimum(bii, ph_bii_max)

    return {
        "bii":                 np.clip(bii, 0, 1),
        "mycorrhizal":         np.clip(myc, 0, 1),
        "earthworm":           np.clip(ew,  0, 1),
        "aggregate_stability": np.clip(agg, 0, 1),
    }
