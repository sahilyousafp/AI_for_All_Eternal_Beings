"""
Main simulation engine: couples all soil model modules.

Runs on a 20×20 spatial grid × 3 depth layers × N ensemble members.
All operations vectorized across n_ensemble × n_cells simultaneously.
Only loop is over years (outer) and depth layers (inner, 3 iterations).

Performance target: <3s for 100yr simulation (10 ensemble × 400 cells).

Output schema matches /api/exhibition/simulate response contract.
"""
import warnings
import numpy as np

from backend.climate_scenarios.ssp_data import get_climate
from backend.soil_model.carbon import initialize_pools, rothc_step, total_soc, surface_soc
from backend.soil_model.water import annual_water_balance
from backend.soil_model.vegetation import vegetation_step, SPECIES_PARAMS, ANNUAL_CROP_PARAMS
from backend.soil_model.biology import biology_step
from backend.soil_model.erosion import compute_erosion
from backend.soil_model.disturbances import check_disturbances
from backend.soil_model.philosophies import get_philosophy


def _init_veg_state(philosophy: dict, ic: dict, n_cells: int) -> dict:
    """Initialise vegetation state from philosophy parameters and initial conditions."""
    species_name = philosophy.get("species")
    params = SPECIES_PARAMS.get(species_name, ANNUAL_CROP_PARAMS) if species_name else ANNUAL_CROP_PARAMS

    initial_cover = philosophy.get("initial_cover", 0.15)
    density       = philosophy.get("planting_density", 0.0)
    Bmax = params.get("Bmax", 50.0)
    k    = params.get("k", 0.02)
    p    = params.get("p", 2.0)

    initial_biomass = max(1.0, initial_cover * Bmax * 0.1)

    # Initialise stand_age to match initial_biomass via Chapman-Richards inverse
    # B = Bmax × (1 - exp(-k×age))^p  →  age = -ln(1 - (B/Bmax)^(1/p)) / k
    frac = (initial_biomass / max(Bmax, 0.01)) ** (1.0 / max(p, 0.1))
    frac = min(frac, 1.0 - 1e-6)
    stand_age_0 = -np.log(1.0 - frac) / max(k, 1e-6)

    return {
        "stand_age":     np.full(n_cells, stand_age_0),
        "biomass":       np.full(n_cells, initial_biomass),
        "density":       np.full(n_cells, float(density)),
        "canopy_cover":  np.full(n_cells, initial_cover),
        "is_alive":      np.ones(n_cells, dtype=bool),
        "drought_year":  0,
        "post_fire_year": 0,
    }


def _init_bio_state(n_cells: int) -> dict:
    """Initialise biological state at typical degraded Mediterranean values."""
    return {
        "bii":                 np.full(n_cells, 0.35),
        "mycorrhizal":         np.full(n_cells, 0.25),
        "earthworm":           np.full(n_cells, 0.20),
        "aggregate_stability": np.full(n_cells, 0.45),
    }


def _pools_to_flat(pools_3layer: dict, n_cells: int) -> list[dict]:
    """Convert (n_cells, 3) pool arrays into list of 3 layer-dicts for rothc_step."""
    layers = []
    for l in range(3):
        layers.append({k: v[:, l] for k, v in pools_3layer.items() if k != "_leach_DPM"})
    return layers


def _flat_to_pools(layers: list[dict]) -> dict:
    """Reconstruct (n_cells, 3) pool dict from list of layer dicts."""
    pools = {}
    for key in ("DPM", "RPM", "BIO", "HUM", "IOM"):
        pools[key] = np.stack([l[key] for l in layers], axis=1)
    return pools


def simulate(
    philosophy: str,
    climate_scenario: str,
    years: int,
    initial_conditions: dict,
    n_ensemble: int = 10,
) -> dict:
    """
    Run the coupled soil evolution simulation.

    Parameters
    ----------
    philosophy       : str — key from philosophies.PHILOSOPHIES
    climate_scenario : str — 'ssp126' | 'ssp245' | 'ssp370' | 'ssp585'
    years            : int — simulation duration (10–100)
    initial_conditions : dict — from extract_conditions.extract_initial_conditions()
    n_ensemble       : int — number of stochastic ensemble members (default 10)

    Returns
    -------
    dict matching /api/exhibition/simulate response schema.
    """
    years = int(np.clip(years, 10, 100))
    phil  = get_philosophy(philosophy)
    species_name = phil.get("species")
    params = (SPECIES_PARAMS.get(species_name, ANNUAL_CROP_PARAMS)
              if species_name else ANNUAL_CROP_PARAMS)
    # Merge philosophy into params for modules that need combined access
    sim_params = {**params, **phil}

    # ── Flatten 20×20 grid to n_cells=400 ────────────────────────────────
    rows = initial_conditions.get("region", {}).get("grid_rows", 20)
    cols = initial_conditions.get("region", {}).get("grid_cols", 20)
    n_cells = rows * cols

    def _flat(arr):
        if arr is None:
            return None
        if arr.ndim == 3:
            return arr.reshape(n_cells, arr.shape[-1])
        return arr.reshape(n_cells)

    oc_3layer    = _flat(initial_conditions["organic_carbon"])         # (n_cells, 3) g/kg
    clay_pct     = _flat(initial_conditions["clay_pct"])               # (n_cells,) %
    sand_pct     = _flat(initial_conditions["sand_pct"])
    silt_pct     = _flat(initial_conditions["silt_pct"])
    soil_ph_init = _flat(initial_conditions["soil_ph"])
    bulk_density = _flat(initial_conditions["bulk_density"])
    fc           = _flat(initial_conditions["field_capacity"])         # (n_cells,)
    wp           = _flat(initial_conditions["wilting_point"])
    awc_init     = _flat(initial_conditions["awc"])
    ksat         = _flat(initial_conditions.get("ksat", np.full((rows, cols), 10.0)))
    agg_stab     = _flat(initial_conditions["aggregate_stability"])
    lat_grid     = initial_conditions["lat_grid"]
    lon_grid     = initial_conditions["lon_grid"]

    baseline_oc = oc_3layer[:, 0].copy()  # surface layer at t=0 for veg feedback

    # ── Biochar amendment — C goes to IOM (stable, k≈0) ──────────────────
    # Biochar is pyrolytic carbon: >80% refractory, stable for 100-1000 years.
    # Correct: add to IOM pool after initialization, NOT to total OC (which
    # would distribute biochar C to fast-cycling DPM/RPM pools at init ratios).
    # Conversion: biochar_t_ha × 80% C content × 0.238 g/kg per t C/ha
    biochar_t_ha = phil.get("biochar_t_ha", 0)
    biochar_iom_val = biochar_t_ha * 0.80 * 0.238  # g/kg added to IOM if > 0

    # ── Per-ensemble initialisation ───────────────────────────────────────
    # Shape: (n_ensemble, n_cells[, 3]) — broadcast across ensemble dimension
    pools_ens = []
    veg_ens   = []
    bio_ens   = []
    moisture_ens = []

    for e in range(n_ensemble):
        pools_e = initialize_pools(oc_3layer, clay_pct, {}, np.full(n_cells, 0.3))
        # Biochar C added directly to IOM (surface layer) — stable, never decomposes
        if biochar_iom_val > 0:
            pools_e["IOM"][:, 0] += biochar_iom_val
        veg_e   = _init_veg_state(phil, initial_conditions, n_cells)
        bio_e   = _init_bio_state(n_cells)
        moist_e = fc.copy()  # start at field capacity
        pools_ens.append(pools_e)
        veg_ens.append(veg_e)
        bio_ens.append(bio_e)
        moisture_ens.append(moist_e)

    # ── Output storage ────────────────────────────────────────────────────
    ts_keys = [
        "total_soc", "erosion", "biodiversity", "canopy_cover",
        "co2_emitted", "water_stress", "carbon_seq",
    ]
    timeseries = {f"{k}_{s}": [] for k in ts_keys for s in ("mean", "p10", "p90")}
    spatial_timeseries = {}
    events_log = []
    _initial_mean_soc = None   # set at yr_idx=0 for sequestration counter

    start_year = 2025

    # ── Year loop ─────────────────────────────────────────────────────────
    for yr_idx in range(years + 1):
        calendar_year = start_year + yr_idx
        yr_offset = yr_idx  # years from 2025

        # Collect per-ensemble outputs this year
        ens_soc   = np.zeros((n_ensemble, n_cells))
        ens_erode = np.zeros((n_ensemble, n_cells))
        ens_bio   = np.zeros((n_ensemble, n_cells))
        ens_can   = np.zeros((n_ensemble, n_cells))
        ens_co2   = np.zeros((n_ensemble, n_cells))
        ens_wstr  = np.zeros((n_ensemble, n_cells))
        ens_cseq  = np.zeros((n_ensemble, n_cells))   # carbon sequestered vs baseline

        for e in range(n_ensemble):
            # 1. Climate with per-ensemble stochastic seed
            climate = get_climate(climate_scenario, yr_offset, seed=e * 10000 + yr_idx)

            # 2. Disturbances
            disturbance = check_disturbances(
                year=yr_idx,
                state={**veg_ens[e], **bio_ens[e],
                       "moisture_ratio": moisture_ens[e] / np.maximum(fc, 0.01)},
                climate=climate,
                params=sim_params,
                ensemble_seed=e * 997 + 42,
            )

            # 3. Vegetation step — compute surface SOC for soil-veg feedback
            soc_mat = (pools_ens[e]["DPM"] + pools_ens[e]["RPM"] +
                       pools_ens[e]["BIO"] + pools_ens[e]["HUM"] +
                       pools_ens[e]["IOM"])
            current_soc_surface = soc_mat[:, 0] if soc_mat.ndim > 1 else soc_mat

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                veg_new = vegetation_step(
                    state=veg_ens[e],
                    climate=climate,
                    params=sim_params,
                    soil_awc=awc_init,
                    current_oc=current_soc_surface,
                    baseline_oc=baseline_oc,
                )

            # 4. Eucalyptus water table draw-down (reduce neighbour moisture)
            if species_name == "eucalyptus":
                water_draw = veg_new.get("water_draw", np.zeros(n_cells))
                moisture_ens[e] = np.clip(moisture_ens[e] - water_draw * 0.01, wp, fc)

            # Apply fire effects to vegetation
            if disturbance["fire"]:
                sev = disturbance["severity"]
                surv_key = "fire_survival_low" if sev == "low" else "fire_survival_high"
                survival = sim_params.get(surv_key, 0.5)
                veg_new["biomass"]      *= survival
                veg_new["canopy_cover"] *= survival
                if not sim_params.get("fire_resprout", False) and sev == "high":
                    veg_new["is_alive"] = np.where(
                        np.random.default_rng(e + yr_idx).random(n_cells) < survival,
                        veg_new["is_alive"], False
                    )

            # 5. Water balance
            water_result = annual_water_balance(
                precip=climate["precip"],
                pet=climate["pet"],
                field_capacity=fc,
                wilting_point=wp,
                current_moisture=moisture_ens[e],
                canopy_cover=veg_new["canopy_cover"],
                ksat=ksat,
            )
            moisture_ens[e] = water_result["soil_moisture"]
            moisture_ratio   = water_result["moisture_ratio"]

            # 6. Carbon step — 3 depth layers
            # Cumulative warming above baseline for Bradford acclimation
            cumul_warming = np.full(n_cells, max(0.0, climate["temp"] - 16.2) * yr_idx / max(yr_idx, 1))

            carbon_input_surface = veg_new.get("carbon_input", np.full(n_cells, 0.3))
            # Compost amendment: convert t C/ha/yr → g/kg/yr (BD=1.4, depth=0.30m: ×0.238)
            compost_add   = phil.get("compost_t_ha_yr", 0.0)
            compost_years = phil.get("compost_years", 5)   # None = perpetual
            if compost_add > 0 and (compost_years is None or yr_idx <= compost_years):
                carbon_input_surface += compost_add * 0.15 * 0.238  # 15% C return, scaled to g/kg/yr

            # Cover crop C_input during establishment (if specified in philosophy)
            # Cover crops: fast-growing annuals suppress weeds and add labile C during tree establishment
            cover_crop_t_ha_yr = phil.get("cover_crop_t_ha_yr", 0.0)
            cover_crop_years   = phil.get("cover_crop_years", 10)   # typically 10yr establishment
            if cover_crop_t_ha_yr > 0 and yr_idx < cover_crop_years:
                # t DM/ha/yr × 50% C content × 0.238 g/kg per t C/ha
                carbon_input_surface += cover_crop_t_ha_yr * 0.50 * 0.238

            # Base vegetation C_input: perennial understory (grass, herb layer) in agroforestry systems
            # E.g., dehesa has continuous grass/herb root turnover independent of tree layer
            base_veg_cinput = phil.get("base_vegetation_C_input", 0.0)
            if base_veg_cinput > 0:
                carbon_input_surface += base_veg_cinput

            # N-cycling bonus: mycorrhizal networks mobilise N, boosting C input by up to 15%
            # Industrial agriculture suppresses Myc → lower bonus; restoration builds it up
            n_cycling_bonus = bio_ens[e]["mycorrhizal"] * 0.15
            carbon_input_surface = carbon_input_surface * (1.0 + n_cycling_bonus)

            # DPM:RPM ratio from vegetation
            dpm_rpm = veg_new.get("dpm_rpm_ratio", 1.44)

            layer_pools = _pools_to_flat(pools_ens[e], n_cells)
            layer_co2   = np.zeros(n_cells)
            leach_from_above = np.zeros(n_cells)

            # Root C input distributed to deeper layers by exponential depth profile
            # (roots penetrate to root_depth; fraction in each layer follows exponential decay)
            root_depth  = params.get("root_depth", 2.0)
            # Fraction of TOTAL C input attributed to roots (already in carbon_input_surface),
            # re-distributed to layers 1 and 2 proportional to root fraction below 30cm.
            # Deep root contribution: 20% of surface C × (1 - exp(-root_depth_m/1.5))
            deep_root_frac = 0.20 * (1.0 - np.exp(-root_depth / 1.5))
            root_deep_total = carbon_input_surface * deep_root_frac
            # layer 1 (30-100cm): 60% of deep root fraction; layer 2: 40%
            root_to_layer = [root_deep_total * 0.60, root_deep_total * 0.40]

            for l in range(3):
                # Carbon input: surface gets veg litter, deeper gets root litter + DOC leaching
                if l == 0:
                    c_input = carbon_input_surface
                else:
                    c_input = leach_from_above + root_to_layer[l - 1]

                layer_moisture = moisture_ratio * (1.0 - l * 0.15)  # moisture decreases with depth

                updated_layer, co2_l = rothc_step(
                    pools=layer_pools[l],
                    clay_pct=clay_pct,
                    temp=climate["temp"],
                    moisture_ratio=np.clip(layer_moisture, 0, 1),
                    veg_cover=veg_new["canopy_cover"],
                    carbon_input=c_input,
                    cumulative_warming=cumul_warming,
                    depth_layer=l,
                    dpm_rpm_ratio=dpm_rpm,
                )
                leach_from_above = updated_layer.pop("_leach_DPM", np.zeros(n_cells))
                layer_pools[l]   = updated_layer
                layer_co2       += co2_l

            pools_ens[e] = _flat_to_pools(layer_pools)

            # Apply fire effects to carbon pools
            # Fire affects surface LITTER (DPM/BIO) heavily but mineral soil
            # RPM and HUM survive largely intact — fire heat doesn't penetrate the
            # mineral soil. Literature: DeLuca & Aplet (2008), Certini (2005).
            if disturbance["fire"]:
                sev = disturbance["severity"]
                if sev == "high":
                    pools_ens[e]["DPM"][:, 0] *= 0.05   # litter layer almost completely burned
                    pools_ens[e]["BIO"][:, 0] *= 0.25   # most microbial biomass killed by heat
                    pools_ens[e]["RPM"][:, 0] *= 0.60   # partially decomposed material: 40% loss
                    # HUM (mineral-stabilised) and IOM: not affected by surface fire
                    # Deeper layers: slight heat-induced effect
                    for key in ("DPM", "RPM", "BIO"):
                        if pools_ens[e][key].shape[1] > 1:
                            pools_ens[e][key][:, 1:] *= 0.97
                elif sev == "low":
                    pools_ens[e]["DPM"][:, 0] *= 0.60   # partial litter loss
                    pools_ens[e]["BIO"][:, 0] *= 0.70   # microbial suppression
                    # RPM and HUM: minimal impact from low-severity fire

            # 7. Biology step
            bio_new = biology_step(
                state=bio_ens[e],
                climate=climate,
                params=sim_params,
                disturbance=disturbance,
                soil_oc=current_soc_surface,
                soil_ph=soil_ph_init,
                moisture_ratio=moisture_ratio,
                veg_state=veg_new,
            )

            # 8. Erosion (reshape to 20×20 for RUSLE grid calculation)
            # Dynamic P_factor: root systems develop with canopy, providing up to 30%
            # additional erosion protection for non-tillage philosophies
            effective_P = sim_params.get("P_factor", 1.0)
            if not sim_params.get("tillage", False):
                mean_canopy = float(np.mean(veg_new["canopy_cover"]))
                effective_P = max(0.10, effective_P * (1.0 - mean_canopy * 0.30))
            local_erosion_params = {**sim_params, "P_factor": effective_P}

            soc_2d = current_soc_surface.reshape(rows, cols)
            erode_result = compute_erosion(
                climate=climate,
                soil_state={
                    "sand_pct":            sand_pct.reshape(rows, cols),
                    "clay_pct":            clay_pct.reshape(rows, cols),
                    "silt_pct":            silt_pct.reshape(rows, cols),
                    "organic_carbon":      soc_2d,
                    "aggregate_stability": bio_new["aggregate_stability"].reshape(rows, cols),
                    "post_fire_year":      disturbance.get("post_fire_year", 0),
                },
                veg_state={"canopy_cover": veg_new["canopy_cover"].reshape(rows, cols)},
                params=local_erosion_params,
            )
            erosion_flat = erode_result["erosion_rate"].reshape(n_cells)

            # SOC erosion loss: reduce surface layer
            # soc_erosion_loss is in t C/ha/yr; convert to g/kg before subtracting
            # from pools (BD≈1.4 t/m³, depth=0.30m: 1 t C/ha = 0.238 g/kg)
            soc_loss_tcha = erode_result["soc_erosion_loss"].reshape(n_cells)
            soc_loss = soc_loss_tcha * 0.238   # g/kg/yr
            pools_ens[e]["HUM"][:, 0] = np.clip(
                pools_ens[e]["HUM"][:, 0] - soc_loss * 0.5, 0, None
            )
            pools_ens[e]["RPM"][:, 0] = np.clip(
                pools_ens[e]["RPM"][:, 0] - soc_loss * 0.5, 0, None
            )

            # 9. Collect outputs
            soc_all = total_soc(pools_ens[e])  # (n_cells, 3)
            # Track surface SOC (0-30cm layer 0) for timeseries — most responsive to management.
            # Deep layers contribute to spatial output but are excluded from the primary % metric.
            ens_soc[e]   = soc_all[:, 0]   # surface layer only (g/kg, 0-30cm)
            ens_erode[e] = erosion_flat
            ens_bio[e]   = bio_new["bii"]
            ens_can[e]   = veg_new["canopy_cover"]
            ens_co2[e]   = layer_co2
            ens_wstr[e]  = water_result["water_stress"]
            # Carbon sequestration computed below (after _initial_mean_soc is set)

            # Update states
            veg_ens[e]      = veg_new
            bio_ens[e]      = bio_new
            veg_ens[e]["drought_year"]  = disturbance["drought_year"]
            veg_ens[e]["post_fire_year"] = disturbance["post_fire_year"]

            # Log fire/drought events (ensemble member 0 only for display)
            if e == 0 and disturbance["fire"]:
                events_log.append({
                    "year":          calendar_year,
                    "type":          "fire",
                    "severity":      disturbance["severity"],
                    "cells_affected": int(np.sum(veg_new["canopy_cover"] < 0.1)),
                })

        # ── Carbon sequestration counter ──────────────────────────────────
        # Track net SOC change vs initial, converted to t C/ha (×4.2 for BD=1.4, 0-30cm)
        if yr_idx == 0:
            _initial_mean_soc = float(np.mean(ens_soc))
        # (SOC in g/kg) × 4.2 = t C/ha. Negative = net loss, positive = net sequestration
        for e_idx in range(n_ensemble):
            ens_cseq[e_idx] = (ens_soc[e_idx] - _initial_mean_soc) * 4.2

        # ── Aggregate across ensemble ─────────────────────────────────────
        def _agg(arr_ens):
            mean = float(np.mean(arr_ens))
            p10  = float(np.percentile(arr_ens, 10))
            p90  = float(np.percentile(arr_ens, 90))
            return mean, p10, p90

        for k, ens_arr in zip(ts_keys, [ens_soc, ens_erode, ens_bio, ens_can, ens_co2, ens_wstr, ens_cseq]):
            m, lo, hi = _agg(ens_arr)
            timeseries[f"{k}_mean"].append(round(m, 4))
            timeseries[f"{k}_p10"].append(round(lo, 4))
            timeseries[f"{k}_p90"].append(round(hi, 4))

        # ── Spatial snapshots (every 10 years + final) ────────────────────
        if yr_idx % 10 == 0 or yr_idx == years:
            snap_key = str(calendar_year)
            # Use ensemble mean for spatial display
            mean_soc    = np.mean(ens_soc, axis=0).reshape(rows, cols)
            mean_can    = np.mean(ens_can, axis=0).reshape(rows, cols)
            mean_erode  = np.mean(ens_erode, axis=0).reshape(rows, cols)
            mean_bio    = np.mean(ens_bio, axis=0).reshape(rows, cols)
            spatial_timeseries[snap_key] = {
                "soc":         mean_soc.tolist(),
                "canopy":      mean_can.tolist(),
                "erosion":     mean_erode.tolist(),
                "biodiversity": mean_bio.tolist(),
            }

    # ── Final spatial output ──────────────────────────────────────────────
    final_key = str(start_year + years)
    spatial_final = spatial_timeseries.get(final_key, {})

    # ── Confidence tiers (time-based) ────────────────────────────────────
    confidence = {
        "supported_years":  min(30, years),           # green: data-calibrated
        "modeled_years":    min(80, years) - min(30, years),  # amber: RothC valid
        "speculative_years": max(0, years - 80),       # red: extrapolation
    }

    # ── Year list ─────────────────────────────────────────────────────────
    year_list = list(range(start_year, start_year + years + 1))

    return {
        "years":              year_list,
        "grid_shape":         [rows, cols],
        "ensemble_size":      n_ensemble,
        "timeseries":         timeseries,
        "spatial_final":      spatial_final,
        "spatial_timeseries": spatial_timeseries,
        "events":             events_log,
        "confidence":         confidence,
        "philosophy":         philosophy,
        "climate_scenario":   climate_scenario,
    }
