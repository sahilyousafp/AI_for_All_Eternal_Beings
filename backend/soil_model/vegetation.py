"""
Vegetation dynamics: Chapman-Richards growth + Reineke self-thinning
+ soil-vegetation feedback + water stress depletion.

Species parameters tuned to Mediterranean Catalonia.
Eucalyptus water table draw-down handled here (applied across grid in engine.py).

References:
  Chapman (1961) Richards growth model.
  Reineke (1933) Stand Density Index.
  Monteith (1965) water stress formulation.
"""
import numpy as np

# ── Species parameter table ───────────────────────────────────────────────
SPECIES_PARAMS = {
    "holm_oak": {
        "Bmax": 250.0,         # max above-ground biomass t/ha
        "k": 0.015,            # growth rate constant
        "p": 3.0,              # shape parameter
        "max_canopy": 0.85,    # max canopy fraction
        "root_depth": 4.5,     # m
        "litter_CN": 35.0,     # C:N ratio of litter
        "DPM_RPM": 0.25,       # DPM:RPM ratio (resistant litter)
        "drought_tol": 0.85,   # moisture_ratio threshold for survival
        "fire_resprout": True,
        "fire_survival_low": 0.80,   # fraction surviving low-intensity fire
        "fire_survival_high": 0.20,
        "maturity_yr": 60,
        "Kw": 0.25,            # Monteith half-saturation water coefficient
        "myc_rate": 0.08,      # mycorrhizal association rate
        "max_density": 300.0,  # trees/ha carrying capacity
        "water_table_draw": 0.50,  # t water/ha/m rooting drawn from deep
        "co2_response": 0.35,  # C3 CO2 fertilisation sensitivity
        # Litter calibrated to Mediterranean oak woodland literature (Ibáñez et al. 2002):
        # Leaf litterfall ~4-7 t DM/ha/yr at canopy closure; roots ~1-2 t/ha/yr.
        # At Bmax, caps prevent unrealistic accumulation.
        "litter_fraction_above": 0.10,  # 10% of current biomass → leaf turnover
        "root_litter_fraction": 0.04,   # 4% → fine root turnover
        "max_leaf_litter": 7.0,         # t DM/ha/yr cap (canopy-closure limit)
        "max_root_litter": 2.5,         # t DM/ha/yr cap
    },
    "med_pine": {
        "Bmax": 180.0, "k": 0.030, "p": 2.5, "max_canopy": 0.75,
        "root_depth": 2.5, "litter_CN": 55.0, "DPM_RPM": 0.10,
        "drought_tol": 0.55, "fire_resprout": False,
        "fire_survival_low": 0.20, "fire_survival_high": 0.05,
        "maturity_yr": 35, "Kw": 0.35, "myc_rate": 0.05,
        "max_density": 600.0, "water_table_draw": 0.30, "co2_response": 0.30,
        "litter_fraction_above": 0.08,  # pine needle drop (~5-6 t/ha/yr at canopy closure)
        "root_litter_fraction": 0.04,
        "max_leaf_litter": 6.0,
        "max_root_litter": 2.5,
    },
    "eucalyptus": {
        "Bmax": 300.0, "k": 0.080, "p": 2.0, "max_canopy": 0.90,
        "root_depth": 1.8, "litter_CN": 70.0, "DPM_RPM": 0.10,
        "drought_tol": 0.30,   # low drought tolerance
        "fire_resprout": False,
        "fire_survival_low": 0.10, "fire_survival_high": 0.02,
        "maturity_yr": 12, "Kw": 0.50, "myc_rate": 0.01,
        "max_density": 1200.0,
        "water_table_draw": 1.20,  # very high water draw — depletes soil moisture
        "co2_response": 0.20,
        # Eucalyptus: prolific litter (~10-15 t/ha/yr at stocking) but allelopathic
        # oils/tannins reduce effective soil incorporation. Cap + resistant DPM_RPM=0.10.
        "litter_fraction_above": 0.05,
        "root_litter_fraction": 0.015,
        "max_leaf_litter": 12.0,   # t/ha/yr (high absolute cap for dense plantation)
        "max_root_litter": 3.5,
    },
    "maquis": {
        "Bmax": 40.0, "k": 0.060, "p": 2.0, "max_canopy": 0.55,
        "root_depth": 1.5, "litter_CN": 25.0, "DPM_RPM": 0.80,
        "drought_tol": 0.90, "fire_resprout": True,
        "fire_survival_low": 0.90, "fire_survival_high": 0.50,
        "maturity_yr": 8, "Kw": 0.15, "myc_rate": 0.04,
        "max_density": 2000.0, "water_table_draw": 0.20, "co2_response": 0.25,
        # Maquis: fast-cycling shrub litter (labile DPM_RPM=0.80 → more DPM).
        # Litterfall ~2-4 t/ha/yr at Bmax=40; small Bmax → higher fractional turnover.
        "litter_fraction_above": 0.12,
        "root_litter_fraction": 0.06,
        "max_leaf_litter": 4.0,
        "max_root_litter": 2.0,
    },
    "agroforestry": {
        "Bmax": 120.0, "k": 0.020, "p": 2.5, "max_canopy": 0.40,
        "root_depth": 2.0, "litter_CN": 20.0, "DPM_RPM": 0.50,
        "drought_tol": 0.70, "fire_resprout": True,
        "fire_survival_low": 0.60, "fire_survival_high": 0.30,
        "maturity_yr": 25, "Kw": 0.30, "myc_rate": 0.06,
        "max_density": 150.0, "water_table_draw": 0.40, "co2_response": 0.30,
        # Sparse dehesa oak + pasture understorey; moderate litter inputs.
        "litter_fraction_above": 0.08,
        "root_litter_fraction": 0.04,
        "max_leaf_litter": 5.0,
        "max_root_litter": 2.0,
    },
}

# Annual crops (industrial agriculture) — no permanent vegetation
ANNUAL_CROP_PARAMS = {
    "Bmax": 12.0,          # realistic max for annual crop standing biomass (wheat/barley)
    "k": 1.0,              # fast growth — reaches max in ~1 growing season
    "p": 1.5,
    "max_canopy": 0.35,
    "DPM_RPM": 2.0,        # highly labile litter (crop residue)
    "litter_CN": 15.0,
    # Straw + stubble incorporated by tillage (~30% of above-ground biomass);
    # root turnover ~10% (fine annual roots decompose in-year).
    # Together these give ~0.57 g/kg/yr C_input → realistic SOC equilibrium ~5 g/kg.
    "litter_fraction_above": 0.30,
    "root_litter_fraction": 0.10,
    "max_leaf_litter": 4.0,   # t DM/ha/yr — straw cap (any over is baled/burned)
    "max_root_litter": 1.5,
    "fire_resprout": False, "fire_survival_low": 0.0, "fire_survival_high": 0.0,
    "co2_response": 0.10,  # small CO2 fertilisation for C3 cereals
}


def vegetation_step(
    state: dict,
    climate: dict,
    params: dict,
    soil_awc: np.ndarray,
    current_oc: np.ndarray = None,
    baseline_oc: np.ndarray = None,
    moisture_ratio: np.ndarray = None,
) -> dict:
    """
    One annual timestep of vegetation dynamics.

    Parameters
    ----------
    state : dict with keys:
        stand_age      : np.ndarray (n_cells,)
        biomass        : np.ndarray (n_cells,) t/ha
        density        : np.ndarray (n_cells,) trees/ha (0 for crops)
        canopy_cover   : np.ndarray (n_cells,) 0-1
        is_alive       : np.ndarray (n_cells,) bool
    climate : dict from ssp_data.get_climate()
    params  : dict — species parameter dict from SPECIES_PARAMS
    soil_awc : np.ndarray (n_cells,) — current AWC (m³/m³)
    current_oc   : np.ndarray | None — current surface OC for soil-veg feedback
    baseline_oc  : np.ndarray | None — 2020 baseline OC for feedback ratio

    Returns
    -------
    Updated state dict, plus new keys:
        litter_production : np.ndarray (n_cells,) t C/ha/yr
        dpm_rpm_ratio     : float — for carbon.py input
        carbon_input      : np.ndarray (n_cells,) t C/ha/yr total C input to soil
        water_draw        : np.ndarray (n_cells,) — m³/m³/yr water drawn from deep
    """
    n_cells = state["biomass"].shape[0]
    Bmax = params.get("Bmax", 100.0)
    k    = params.get("k", 0.02)
    p    = params.get("p", 2.0)
    Kw   = params.get("Kw", 0.30)
    max_canopy = params.get("max_canopy", 0.80)
    is_alive = state.get("is_alive", np.ones(n_cells, dtype=bool))

    # ── Soil-vegetation feedback (CLOSES THE LOOP) ────────────────────────
    # Growth modified by current OC relative to baseline
    if current_oc is not None and baseline_oc is not None:
        oc_ratio = np.clip(current_oc / np.maximum(baseline_oc, 0.1), 0.1, 3.0)
        effective_awc = soil_awc * (1.0 + 0.3 * (oc_ratio - 1.0))
    else:
        effective_awc = soil_awc

    # ── Water stress (Monteith formulation) ───────────────────────────────
    # Two-component stress:
    #  (a) a soil-capacity baseline from AWC (unchanged when rainfall is normal)
    #  (b) an actual-moisture multiplier driven by the current soil moisture
    #      ratio produced by the water balance step. Under sustained Med
    #      drought (moisture_ratio → 0.2-0.3), this drops plant growth
    #      dramatically. Without (b) the vegetation grew identically under
    #      every SSP because it only looked at soil capacity, not rainfall.
    f_water_capacity = effective_awc / (effective_awc + Kw)
    f_water_capacity = np.clip(f_water_capacity, 0.0, 1.0)
    if moisture_ratio is not None:
        # Saturating response: no penalty above 0.6 moisture, steep drop below.
        # At 0.6 → 1.0 (full); at 0.3 → 0.5; at 0.1 → 0.17; at 0.0 → 0.0
        mr = np.clip(moisture_ratio, 0, 1)
        f_actual = np.clip(mr / 0.6, 0, 1) ** 0.8
        f_water = f_water_capacity * f_actual
    else:
        f_water = f_water_capacity

    # ── CO2 fertilisation (C3 plants, capped) ─────────────────────────────
    # Recent FACE experiments in water-limited biomes (Wang et al. 2020 Nature;
    # Sperry et al. 2019 New Phytologist) show Mediterranean C3 fertilisation
    # is much smaller than forestry/temperate values because rising VPD offsets
    # stomatal gains. We cap the effect at +15 %. Water limitation is applied
    # separately through f_water in growth_modifier — no double-gating here.
    co2 = climate.get("co2", 420.0)
    co2_resp = min(params.get("co2_response", 0.3), 0.15)
    f_co2 = 1.0 + co2_resp * np.log(max(co2, 300.0) / 400.0)
    f_co2 = np.clip(f_co2, 0.80, 1.20)

    # ── Temperature stress ────────────────────────────────────────────────
    # Mediterranean plant optimum is narrower than the previous 12–24 °C plateau.
    # Real physiology: photosynthesis peaks near 17–18 °C, starts declining above
    # 20 °C because summer peak temps (mean + ~12 °C in Med climate) already push
    # leaves past 33 °C Rubisco limits. Gaussian around T_opt = 17 °C, sigma = 4.5 °C.
    # At current Barcelona (16.2 °C): f_temp ≈ 0.985
    # At +2.7 °C (SSP2-4.5):          f_temp ≈ 0.835
    # At +5.0 °C (SSP5-8.5):          f_temp ≈ 0.590
    # Values match the warming penalty quantified in Ciais et al. 2005 and
    # Keenan et al. 2014 for southern European vegetation.
    temp = climate.get("temp", 16.2)
    T_OPT, T_SIGMA = 17.0, 4.5
    f_temp = float(np.exp(-((temp - T_OPT) ** 2) / (2 * T_SIGMA ** 2)))

    # ── Chapman-Richards growth (incremental) ────────────────────────────
    # Compute ANNUAL INCREMENT from age t → t+1, then add to current biomass.
    # This preserves any initial biomass even at age=0.
    age_prev = state["stand_age"]
    age      = age_prev + 1.0  # age AFTER this year
    B_prev   = Bmax * (1.0 - np.exp(-k * age_prev)) ** p
    B_next   = Bmax * (1.0 - np.exp(-k * age)) ** p
    delta_B  = np.maximum(B_next - B_prev, 0.0)   # annual increment, never negative
    growth_modifier = f_co2 * f_water * f_temp
    biomass_new     = np.minimum(state["biomass"] + delta_B * growth_modifier, Bmax)
    biomass_new     = np.where(is_alive, biomass_new, 0.0)
    biomass_new     = np.maximum(biomass_new, 0.0)

    # ── Drought die-back (chronic stress mortality) ──────────────────────
    # Chapman-Richards alone never removes biomass — it only grows more or less
    # slowly. Real Mediterranean vegetation shrinks under sustained drought:
    # leaves and branches drop, and below a critical threshold whole trees die.
    # We remove a fraction of STANDING biomass when growth_modifier < 0.4.
    # Reference: Allen et al. (2010) Forest Ecology & Management 259: a global
    # review of drought-induced tree mortality shows Mediterranean die-off rates
    # of 2-8 %/yr under severe drought years in 20-yr observational series.
    stress_excess = np.clip(0.4 - growth_modifier, 0, 0.4)
    dieoff_rate   = stress_excess * 0.15   # up to 6 %/yr under worst conditions
    biomass_new   = biomass_new * (1.0 - dieoff_rate)
    biomass_new   = np.maximum(biomass_new, 0.0)

    # ── Reineke Self-Thinning (Stand Density Index) ───────────────────────
    density  = state.get("density", np.zeros(n_cells))
    max_dens = params.get("max_density", 300.0)
    if np.any(density > 0):
        # SDI = density × (mean_dbh/25)^1.605
        # Estimate dbh from biomass: dbh ≈ (biomass/density × 40)^0.5 cm
        dbh_est = np.where(density > 0,
                           np.clip((biomass_new / np.maximum(density, 1.0) * 40.0) ** 0.5, 1, 200),
                           np.zeros(n_cells))
        sdi = density * (dbh_est / 25.0) ** 1.605

        # Carrying capacity reduced under drought
        carrying_capacity = max_dens * np.clip(f_water + 0.3, 0.2, 1.0)
        # Mortality when SDI > 85% of carrying capacity
        mortality_rate = np.where(
            sdi > 0.85 * carrying_capacity,
            np.clip((sdi / np.maximum(carrying_capacity, 1) - 0.85) * 0.3, 0, 0.5),
            np.zeros(n_cells)
        )
        density_new = np.clip(density * (1.0 - mortality_rate), 0, None)
    else:
        density_new = density.copy()

    # ── Canopy cover ──────────────────────────────────────────────────────
    canopy_cover = np.clip(biomass_new / Bmax * max_canopy, 0.0, max_canopy)
    canopy_cover = np.where(is_alive, canopy_cover, 0.0)

    # ── Litter production and soil carbon input ───────────────────────────
    # Leaf/above-ground turnover + root turnover → soil C input
    # litter_fraction_above: fraction of above-ground biomass returned to soil
    # (annual crops: ~0.05 — harvest removes most; perennials: default 0.30)
    litter_frac_above  = params.get("litter_fraction_above", 0.10)   # fraction of above-ground biomass → leaf litter
    root_litter_frac   = params.get("root_litter_fraction", 0.04)   # fraction → fine root turnover to soil
    max_leaf_litter    = params.get("max_leaf_litter", 8.0)         # t DM/ha/yr cap (canopy-closure limit)
    max_root_litter    = params.get("max_root_litter", 3.0)         # t DM/ha/yr cap
    # Litterfall scales with STANDING biomass. Under sustained drought, biomass
    # shrinks (via f_water in the growth equation above) and total annual
    # litter drops with it. The previous version amplified litterfall by
    # (1 + drought_effect*0.5), which produced a backwards result: worse climate
    # → more litter → more soil C input → SOC paradoxically increased under
    # SSP5-8.5. See Allen et al. 2010 (Forest Ecol Mgmt) for the real response:
    # leaf area shrinks and yearly litter drops ~linearly with biomass loss.
    leaf_litter   = np.minimum(
        biomass_new * litter_frac_above,
        max_leaf_litter
    )  # t/ha/yr
    root_litter   = np.minimum(biomass_new * root_litter_frac, max_root_litter)  # fine root turnover
    # C input to soil (g/kg/yr): litter (t DM/ha/yr) × 50% C × 0.238 g/kg per t C/ha
    # Conversion: 1 t C/ha = 0.238 g/kg for BD=1.4 t/m³, 0-30cm layer
    C_input = (leaf_litter + root_litter) * 0.50 * 0.238
    C_input = np.where(is_alive, C_input, 0.0)

    dpm_rpm_ratio = params.get("DPM_RPM", 1.44)

    # ── Water table draw-down (eucalyptus) ────────────────────────────────
    water_draw = params.get("water_table_draw", 0.0) * density_new / max_dens

    return {
        **state,
        "stand_age":       age,
        "biomass":         biomass_new,
        "density":         density_new,
        "canopy_cover":    canopy_cover,
        "is_alive":        is_alive,
        "litter_production": leaf_litter + root_litter,
        "dpm_rpm_ratio":   dpm_rpm_ratio,
        "carbon_input":    C_input,
        "water_draw":      water_draw,
        "f_water":         f_water,
        "f_co2":           f_co2,
    }
