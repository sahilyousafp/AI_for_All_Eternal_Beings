"""
RothC simplified 5-pool carbon model × N depth layers.

Pools: DPM (decomposable plant material, k=10/yr),
       RPM (resistant plant material, k=0.3/yr),
       BIO (microbial biomass, k=0.66/yr),
       HUM (humified organic matter, k=0.02/yr),
       IOM (inert organic matter, k≈0, not decomposed)

Bradford (2008) thermal acclimation: Q10 decreases under sustained warming.
All array operations fully vectorized. Shape: (n_cells, n_layers) for depth layers.
n_layers is read from the trailing axis of the SOC input; engine.py currently
drives the model with n_layers=6 matching SoilGrids 2.0 depth bands.

References:
  Coleman & Jenkinson (1996) RothC-26.3 model description.
  Falloon et al. (1998) IOM estimation.
  Bradford et al. (2008) Thermal acclimation of soil carbon.
"""
import numpy as np

# Pool decomposition rate constants (per year)
POOL_RATES = {
    "DPM": 10.00,
    "RPM":  0.30,
    "BIO":  0.66,
    "HUM":  0.02,
    "IOM":  0.00,
}

# Depth-layer carbon input fractions (surface receives most)
DEPTH_INPUT_FRAC = np.array([0.70, 0.25, 0.05])  # layers 0, 1, 2


def initialize_pools(
    total_soc: np.ndarray,
    clay_pct: np.ndarray,
    climate: dict,
    veg_cover: np.ndarray,
) -> dict:
    """
    RothC equilibrium pool initialization from known total SOC.

    IOM = 0.049 × total_soc^1.139  (Falloon et al. 1998)
    Active SOC distributed to DPM:RPM:BIO:HUM by equilibrium ratios.

    Parameters
    ----------
    total_soc : np.ndarray, shape (n_cells, 3)
        Total SOC per depth layer (g/kg).
    clay_pct  : np.ndarray, shape (n_cells,)
    climate   : dict — not used here but available for future use
    veg_cover : np.ndarray, shape (n_cells,)

    Returns
    -------
    dict with keys 'DPM','RPM','BIO','HUM','IOM', each shape (n_cells, 3)
    """
    n_cells = total_soc.shape[0]
    n_layers = total_soc.shape[1] if total_soc.ndim > 1 else 1

    if total_soc.ndim == 1:
        total_soc = total_soc[:, np.newaxis]

    # IOM (Falloon et al. 1998) — applies to rooting zone.
    iom = 0.049 * (np.clip(total_soc, 0.01, None) ** 1.139)

    # At depth, radiocarbon studies routinely show soil C ages of 500–10000 yr
    # (Mathieu et al. 2015; Trumbore 2009). That age is inconsistent with a
    # HUM pool alone — it requires a much larger fraction of genuinely
    # inert / mineral-stabilised C than Falloon predicts for surface samples.
    # We apply a depth-dependent IOM boost so deep layers are dominated by
    # the inert pool and do not artificially decay on 50-yr timescales.
    # Cap at 92 % of total SOC so there is always a small active fraction.
    if n_layers == 6 and total_soc.ndim == 2:
        depth_iom_boost = np.array([1.0, 1.8, 3.0, 5.0, 7.5, 10.0])
        iom_boosted = iom * depth_iom_boost[np.newaxis, :]
        iom = np.minimum(iom_boosted, total_soc * 0.92)

    active_soc = np.clip(total_soc - iom, 0.01, None)

    # Depth-dependent pool partitioning.
    # Surface soil (root zone) is dominated by fast-cycling fresh inputs:
    #     DPM 2 %, RPM 30 %, BIO 3 %, HUM 65 %.
    # Deep soil is dominated by mineral-stabilised / ancient carbon:
    #     DPM < 1 %, RPM < 5 %, BIO < 1 %, HUM > 93 %.
    # The gradient is rooted in turnover-time constraints — deep soil C
    # with measured ages of hundreds of years cannot have >10 % in RPM
    # (half-life 3 yr) or it would have already decomposed.
    # References: Jobbágy & Jackson (2000); Mathieu et al. (2015, Global Change
    # Biology) on vertical 14C age gradients; Rumpel & Kögel-Knabner (2011,
    # Plant & Soil) on depth partitioning of pool stability.
    if n_layers == 6:
        dpm_frac = np.array([0.020, 0.015, 0.010, 0.005, 0.003, 0.001])
        rpm_frac = np.array([0.300, 0.220, 0.150, 0.080, 0.050, 0.020])
        bio_frac = np.array([0.030, 0.025, 0.020, 0.015, 0.010, 0.005])
        hum_frac = np.array([0.650, 0.740, 0.820, 0.900, 0.937, 0.974])
        # Broadcast into shape (1, n_layers) for row-wise multiplication
        dpm = active_soc * dpm_frac[np.newaxis, :]
        rpm = active_soc * rpm_frac[np.newaxis, :]
        bio = active_soc * bio_frac[np.newaxis, :]
        hum = active_soc * hum_frac[np.newaxis, :]
    else:
        dpm = active_soc * 0.02
        rpm = active_soc * 0.30
        bio = active_soc * 0.03
        hum = active_soc * 0.65

    # Legacy 3-layer mode (0-30, 30-100, 100-200 cm averages) needs explicit
    # down-scaling because each input layer represents a thick composite with
    # no intrinsic depth attenuation. SoilGrids-native 6-layer mode does NOT
    # need this — each layer's input IS the real SOC measurement at that
    # depth already, so we trust the raw data and let the initial totals
    # equal the SoilGrids values exactly.
    if n_layers == 3:
        layer_scale = np.array([1.0, 0.35, 0.12])
        for l_idx in range(n_layers):
            scale = float(layer_scale[l_idx])
            dpm[:, l_idx] *= scale
            rpm[:, l_idx] *= scale
            bio[:, l_idx] *= scale
            hum[:, l_idx] *= scale

    return {
        "DPM": dpm,
        "RPM": rpm,
        "BIO": bio,
        "HUM": hum,
        "IOM": iom,
    }


def _temp_modifier(temp: float) -> float:
    """
    RothC temperature modifier f(T).
    Coleman & Jenkinson (1996): f_T = 47.9 / (1 + exp(106 / (T + 18.3)))
    Returns 0 for T <= -18.3°C (denominator goes to infinity).
    """
    if temp <= -18.3:
        return 0.0
    return 47.9 / (1.0 + np.exp(106.0 / (temp + 18.3)))


def rothc_step(
    pools: dict,
    clay_pct: np.ndarray,
    temp: float,
    moisture_ratio: np.ndarray,
    veg_cover: np.ndarray,
    carbon_input: np.ndarray,
    cumulative_warming: np.ndarray,
    depth_layer: int = 0,
    n_layers: int = 3,
    dpm_rpm_ratio: float = 1.44,
    dt: float = 1.0,
) -> tuple:
    """
    One annual timestep of RothC for a single depth layer.

    Parameters
    ----------
    pools : dict
        Each value shape (n_cells,) — the layer-specific pools for this step.
    clay_pct : np.ndarray (n_cells,)
    temp : float — mean annual temperature °C
    moisture_ratio : np.ndarray (n_cells,) — soil_moisture / field_capacity, 0–1
    veg_cover : np.ndarray (n_cells,) — fractional vegetation cover 0–1
    carbon_input : np.ndarray (n_cells,) — t C/ha/yr added to this layer
    cumulative_warming : np.ndarray (n_cells,) — degrees above baseline (for acclimation)
    depth_layer : int — 0..n_layers-1 (affects carbon input and leaching)
    n_layers : int — total number of depth layers in the column (default 3)
        Used only to detect the bottom layer (which does not leach further down).
    dpm_rpm_ratio : float — plant material decomposability ratio
    dt : float — timestep in years (default 1.0)

    Returns
    -------
    (updated_pools, co2_emitted)
    co2_emitted: np.ndarray (n_cells,) in t C/ha/yr
    """
    n_cells = pools["DPM"].shape[0] if hasattr(pools["DPM"], "__len__") else 1

    # ── Temperature modifier (Coleman & Jenkinson 1996) ───────────────────
    f_T = _temp_modifier(float(temp))

    # ── Bradford (2008) thermal acclimation ───────────────────────────────
    # Q10 decreases under sustained warming; prevents runaway decomposition
    # acclimation_factor = 1 - 0.0093 * cumulative_warming (Bradford et al. 2008)
    acclimation = np.clip(1.0 - 0.0093 * cumulative_warming, 0.3, 1.0)

    # ── Mediterranean seasonal correction ─────────────────────────────────
    # Annual-average T and moisture overestimate actual decomposition in
    # Mediterranean climates where summer drought coincides with peak T.
    # Palosso (2005), Luo et al. (2012): RothC overestimates Mediterranean
    # mineralisation by ~55% when using annual averages with the standard
    # flat-top f_M. We use 0.45 to compensate and to match empirical
    # mineralisation rates from Catalonia field studies (Rovira & Vallejo 2007).
    _MED_SEASONAL_CORRECTION = 0.45

    f_T_eff = f_T * acclimation * _MED_SEASONAL_CORRECTION

    # ── Moisture modifier ─────────────────────────────────────────────────
    # RothC-style flat-top f_M (Coleman & Jenkinson 1996 Table 1), smoothed:
    #   moisture_ratio ≥ 0.44       → f_M = 1.0 (full activity; subsoil moist)
    #   0.05 ≤ moisture_ratio < 0.44 → linear 0.2 → 1.0
    #   0    ≤ moisture_ratio < 0.05 → linear 0.0 → 0.2 (continuous to floor)
    # Now fully continuous: at mr=0.05 both branches give f_M=0.2, and at
    # mr=0.44 both middle and top branches give f_M=1.0.
    f_M = np.where(
        moisture_ratio >= 0.44,
        1.0,
        np.where(
            moisture_ratio >= 0.05,
            0.2 + 0.8 * (moisture_ratio - 0.05) / 0.39,
            moisture_ratio * 4.0,  # linear ramp 0 → 0.2 over mr [0, 0.05]
        ),
    )

    # ── Soil cover modifier ───────────────────────────────────────────────
    # Bare soil decomposes faster; vegetation provides insulation
    # f_C = 0.6 with full cover, scales to 1.0 at bare
    f_C = np.where(
        veg_cover >= 0.3,
        0.6,
        0.6 + (1.0 - 0.6) * (0.3 - np.clip(veg_cover, 0, 0.3)) / 0.3
    )

    # ── Clay-dependent CO2:BIO:HUM partitioning ───────────────────────────
    # x = CO2 fraction (Coleman & Jenkinson 1996 Eq.)
    clay_f = np.clip(clay_pct / 100.0, 0.01, 0.60)
    x_num  = 1.67 * (1.85 + 1.60 * np.exp(-0.0786 * clay_pct))
    x      = x_num / (1.0 + x_num)              # CO2 fraction
    bio_frac = (1.0 - x) * 0.46                  # BIO fraction of non-CO2 products
    hum_frac = (1.0 - x) * 0.54                  # HUM fraction

    # ── Decomposition ─────────────────────────────────────────────────────
    def decompose(pool_vals: np.ndarray, k: float) -> np.ndarray:
        """Annual decay: amount decomposed this timestep."""
        rate = k * f_T_eff * f_M * f_C
        return np.clip(pool_vals * rate * dt, 0, pool_vals)

    decay_DPM = decompose(pools["DPM"], POOL_RATES["DPM"])
    decay_RPM = decompose(pools["RPM"], POOL_RATES["RPM"])
    decay_BIO = decompose(pools["BIO"], POOL_RATES["BIO"])
    decay_HUM = decompose(pools["HUM"], POOL_RATES["HUM"])
    # IOM does not decompose

    total_decay = decay_DPM + decay_RPM + decay_BIO + decay_HUM
    co2_emitted = total_decay * x
    bio_produced = total_decay * bio_frac
    hum_produced = total_decay * hum_frac

    # ── Carbon inputs (split DPM:RPM by ratio) ────────────────────────────
    input_DPM = carbon_input * dpm_rpm_ratio / (1.0 + dpm_rpm_ratio)
    input_RPM = carbon_input * 1.0 / (1.0 + dpm_rpm_ratio)

    # ── DOC leaching (downward from surface layers) ───────────────────────
    # Small fraction of DPM leaches to deeper layer with percolating water.
    # Bottom layer has nowhere to leach to, so output is zeroed there.
    leach_rate = 0.001 * np.clip(moisture_ratio, 0, 1) * pools["DPM"]
    leach_out  = leach_rate if depth_layer < (n_layers - 1) else np.zeros_like(leach_rate)

    # ── Update pools ──────────────────────────────────────────────────────
    new_pools = {
        "DPM": np.clip(pools["DPM"] - decay_DPM + input_DPM - leach_out, 0, None),
        "RPM": np.clip(pools["RPM"] - decay_RPM + input_RPM, 0, None),
        "BIO": np.clip(pools["BIO"] - decay_BIO + bio_produced, 0, None),
        "HUM": np.clip(pools["HUM"] - decay_HUM + hum_produced, 0, None),
        "IOM": pools["IOM"].copy() if hasattr(pools["IOM"], "copy") else np.array(pools["IOM"]),
        "_leach_DPM": leach_out,  # pass to next layer as input
    }

    return new_pools, co2_emitted


def total_soc(pools: dict) -> np.ndarray:
    """
    Sum all pools to get total SOC.
    If pools have shape (n_cells, 3), returns (n_cells, 3).
    If pools have shape (n_cells,), returns (n_cells,).
    """
    result = np.zeros_like(pools["DPM"])
    for key in ("DPM", "RPM", "BIO", "HUM", "IOM"):
        result = result + pools[key]
    return result


def surface_soc(pools: dict) -> np.ndarray:
    """
    Layer 0 (surface, 0-30cm) total SOC.
    If pools are 2-D (n_cells, 3), returns layer 0: shape (n_cells,).
    """
    soc = total_soc(pools)
    if soc.ndim == 2:
        return soc[:, 0]
    return soc
