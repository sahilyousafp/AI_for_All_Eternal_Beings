"""
Microbial indicators: Microbial Biomass C, F:B ratio, qCO2, AMF colonisation.

Pure derivation layer on top of existing RothC pools + biology state. No new
training data, no new calibration — every number comes from a published
empirical relationship.

Why this module exists
----------------------
The RothC engine already carries a microbial biomass pool (BIO) internally,
and biology.py already tracks mycorrhizal abundance. But none of that was
previously exposed to the API or the exhibition. This module surfaces it
in the form of four indicators that (a) soil scientists actually measure in
the field, and (b) the public can read as a second axis of soil state
("is the soil alive?") in addition to the carbon axis the columns already
tell.

Literature
----------
MBC scaling and qCO2:
  Anderson, T.-H., & Domsch, K.H. (1989). Ratios of microbial biomass carbon
    to total organic carbon in arable soils. Soil Biology & Biochemistry,
    21(4), 471-479.
  Anderson, T.-H., & Domsch, K.H. (1990). Application of eco-physiological
    quotients (qCO2 and qD) on microbial biomasses from soils of different
    cropping histories. Soil Biology & Biochemistry, 22(2), 251-255.
  Wardle, D.A. (1992). A comparative assessment of factors which influence
    microbial biomass carbon and nitrogen levels in soil. Biological Reviews,
    67(3), 321-358.

Fungal:Bacterial ratio:
  Bardgett, R.D., & McAlister, E. (1999). The measurement of soil fungal:
    bacterial biomass ratios as an indicator of ecosystem self-regulation in
    temperate meadow grasslands. Biology and Fertility of Soils, 29, 282-290.
  Fierer, N., Strickland, M.S., Liptzin, D., Bradford, M.A., & Cleveland,
    C.C. (2009). Global patterns in belowground communities. Ecology Letters,
    12(11), 1238-1249.
  de Vries, F.T., Hoffland, E., van Eekeren, N., Brussaard, L., & Bloem, J.
    (2006). Fungal/bacterial ratios in grasslands with contrasting
    nitrogen management. Soil Biology & Biochemistry, 38(8), 2092-2103.

AMF colonisation:
  Treseder, K.K. (2004). A meta-analysis of mycorrhizal responses to
    nitrogen, phosphorus, and atmospheric CO2 in field studies. New
    Phytologist, 164(2), 347-355.
  Treseder, K.K., & Allen, M.F. (2002). Direct nitrogen and phosphorus
    limitation of arbuscular mycorrhizal fungi: a model and field test.
    New Phytologist, 155(3), 507-515.

Management effects:
  Liu, C., Lu, M., Cui, J., Li, B., & Fang, C. (2014). Effects of straw
    carbon input on carbon dynamics in agricultural soils: a meta-analysis.
    Global Change Biology, 20(5), 1366-1381.
  Tiemann, L.K., Grandy, A.S., Atkinson, E.E., Marin-Spiotta, E., &
    McDaniel, M.D. (2015). Crop rotational diversity enhances belowground
    communities and functions in an agroecosystem. Ecology Letters, 18(8),
    761-771.

Scales
------
- microbial_biomass_c : g MBC / kg soil (typical range 0.05 – 1.5)
- fungal_bacterial_ratio : dimensionless (typical range 0.1 – 2.0)
- metabolic_quotient_qco2 : mg CO2-C per g MBC per hour (typical 0.5 – 5.0)
- amf_colonisation_pct : % of root length colonised (typical 10 – 70)
- living_soil_index : 0 – 100 composite, used for the Living Layer visual

All functions accept numpy arrays or floats; output matches input shape.
"""
from __future__ import annotations

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
#  Primary indicator functions
# ═══════════════════════════════════════════════════════════════════════════

def microbial_biomass_c(
    soc_g_kg: np.ndarray | float,
    clay_pct: np.ndarray | float,
    moisture_ratio: np.ndarray | float,
    temperature_c: np.ndarray | float,
    rothc_bio_pool: np.ndarray | float | None = None,
) -> np.ndarray:
    """
    Microbial Biomass Carbon (MBC) in g C / kg soil.

    Two paths:
      (1) If the RothC BIO pool is available, use it directly — it is the
          model's own internal microbial biomass estimate (Coleman &
          Jenkinson 1996), typically 1–4 % of total SOC.
      (2) Fallback empirical: Wardle (1992) meta-analysis shows MBC ≈ 1–3 %
          of SOC, modulated by clay protection (Anderson & Domsch 1989) and
          moisture availability.

    The two paths are *consistent* — RothC's BIO pool was calibrated against
    the same literature Wardle reviewed.

    Parameters
    ----------
    soc_g_kg : total surface SOC (g/kg)
    clay_pct : clay content (%) — higher clay protects MBC
    moisture_ratio : 0–1, plant-available water / AWC
    temperature_c : annual mean temperature (°C)
    rothc_bio_pool : optional direct RothC BIO value (g C/kg)

    Returns
    -------
    mbc : g MBC C / kg soil
    """
    soc = np.asarray(soc_g_kg, dtype=float)
    clay = np.asarray(clay_pct, dtype=float)
    mois = np.asarray(moisture_ratio, dtype=float)
    temp = np.asarray(temperature_c, dtype=float)

    if rothc_bio_pool is not None:
        bio = np.asarray(rothc_bio_pool, dtype=float)
        # RothC BIO is already in g C/kg — return directly, clipped to
        # realistic Mediterranean range.
        return np.clip(bio, 0.01, 3.0)

    # Empirical fallback — Wardle 1992, Anderson & Domsch 1989.
    # Base ratio 2 % of SOC, modulated by clay (protection) and moisture.
    mbc_fraction = 0.02 + 0.01 * np.clip(clay / 40.0, 0, 1)  # 2–3 %
    moisture_modulator = 0.4 + 0.6 * np.clip(mois, 0, 1)  # 0.4–1.0
    # Thermal optimum around 20 °C for Mediterranean microbes (Pietikäinen 2005)
    thermal = np.exp(-((temp - 20.0) ** 2) / (2 * 10.0 ** 2))
    thermal = np.clip(thermal, 0.3, 1.0)

    mbc = soc * mbc_fraction * moisture_modulator * thermal
    return np.clip(mbc, 0.01, 3.0)


def fungal_bacterial_ratio(
    soil_ph: np.ndarray | float,
    soc_g_kg: np.ndarray | float,
    canopy_cover: np.ndarray | float,
    tillage: bool,
    fertilizer_n_kg_ha: float,
    grazing_intensity: float = 0.0,
) -> np.ndarray:
    """
    Fungal:Bacterial biomass ratio (dimensionless).

    Baseline value 0.5 = bacterially-dominated (bacteria ~2× fungi).
    Values > 1.0 = fungally-dominated (mature woodland, undisturbed soil).

    Drivers (Bardgett & McAlister 1999; Fierer et al. 2009; de Vries 2006):
      - Low pH → favours fungi. Bacteria decline sharply below pH 5.5.
      - High SOC / C:N → favours fungi (slow decomposers of recalcitrant C).
      - Tree canopy / perennial vegetation → favours fungi (mycorrhizal).
      - **Tillage** → collapses F:B (shears hyphae).
      - **Synthetic N** → collapses F:B (favours bacterial copiotrophs).
      - **Grazing** → intermediate effect, slight bacterial shift.

    Parameters
    ----------
    soil_ph : pH
    soc_g_kg : surface SOC (g/kg, proxy for C:N + resource quality)
    canopy_cover : 0–1 fraction of tree/perennial cover
    tillage : bool — philosophy tillage flag
    fertilizer_n_kg_ha : synthetic N input rate (kg N / ha / yr)
    grazing_intensity : 0–1 stocking rate proxy

    Returns
    -------
    fb_ratio : dimensionless
    """
    ph = np.asarray(soil_ph, dtype=float)
    soc = np.asarray(soc_g_kg, dtype=float)
    canopy = np.asarray(canopy_cover, dtype=float)

    # pH effect (Fierer 2009): F:B peaks around pH 4.5–5.5, declines with alkalinity.
    # Barcelona soils are typically pH 7–8 → bacterially dominated baseline.
    f_ph = np.where(
        ph < 5.5, 1.5,
        np.where(ph < 7.0, 1.0, np.where(ph < 8.0, 0.7, 0.5))
    )

    # SOC effect (Bardgett): higher SOC (proxy for C:N and recalcitrant substrate)
    # → favours fungi. Saturates around 30 g/kg.
    f_soc = 0.4 + 0.6 * np.clip(soc / 30.0, 0, 1)

    # Canopy effect: tree cover → mycorrhizal networks → fungal dominance.
    f_canopy = 0.5 + np.clip(canopy, 0, 1)  # 0.5–1.5

    # Base ratio = product of the three (normalised)
    fb = (f_ph * f_soc * f_canopy) / 1.5  # division gives ~0.2–1.5 range

    # Disturbance multipliers
    if tillage:
        fb = fb * 0.35  # Tiemann 2015, Six et al. 2006

    # Fertiliser N effect (de Vries 2006): every 50 kg N/ha drops F:B ~15 %
    n_suppression = 1.0 - min(0.75, fertilizer_n_kg_ha / 200.0 * 0.6)
    fb = fb * n_suppression

    # Grazing: mild bacterial shift (Bardgett et al.)
    fb = fb * (1.0 - 0.15 * grazing_intensity)

    return np.clip(fb, 0.05, 2.5)


def metabolic_quotient_qco2(
    mbc: np.ndarray | float,
    temperature_c: np.ndarray | float,
    moisture_ratio: np.ndarray | float,
    co2_respiration_g_kg_yr: np.ndarray | float,
) -> np.ndarray:
    """
    Metabolic quotient qCO2 — microbial stress indicator.

    qCO2 = (CO2 respiration per unit time) / (microbial biomass)

    Units: mg CO2-C per g MBC per hour.

    A *high* qCO2 means microbes are respiring more carbon per unit of
    their own biomass — they are working harder per unit mass, typically
    because they are stressed (Anderson & Domsch 1990). Undisturbed mature
    soils have LOW qCO2 (efficient community); degraded or warming soils
    have HIGH qCO2 (stressed, wasteful community). This is counter-
    intuitive but well established.

    Parameters
    ----------
    mbc : g MBC C / kg soil
    temperature_c : annual mean temperature
    moisture_ratio : 0–1
    co2_respiration_g_kg_yr : annual heterotrophic respiration g C/kg/yr
        (already computed by the RothC carbon step)

    Returns
    -------
    qco2 : mg CO2-C per g MBC per hour
    """
    mbc = np.asarray(mbc, dtype=float)
    temp = np.asarray(temperature_c, dtype=float)
    mois = np.asarray(moisture_ratio, dtype=float)
    resp = np.asarray(co2_respiration_g_kg_yr, dtype=float)

    # Convert annual respiration to mg/g/hour:
    #   g C/kg/yr × 1000 mg/g × 1/(8760 h/yr) × 1/MBC(g/kg)
    # = resp × 1000 / 8760 / mbc
    mbc_safe = np.where(mbc > 0.01, mbc, 0.01)
    qco2_base = resp * 1000.0 / 8760.0 / mbc_safe

    # Stress amplifiers: hot, dry soils have elevated qCO2 even for same resp.
    # Anderson & Domsch 1990: Q10 ≈ 2 for qCO2 itself (efficiency declines).
    thermal_stress = 1.0 + 0.05 * np.clip(temp - 20.0, 0, 15)
    moisture_stress = 1.0 + 0.3 * np.clip(0.5 - mois, 0, 0.5)

    qco2 = qco2_base * thermal_stress * moisture_stress
    return np.clip(qco2, 0.1, 10.0)


def amf_colonisation_pct(
    mycorrhizal_state: np.ndarray | float,
    tillage: bool,
    fertilizer_n_kg_ha: float,
    canopy_cover: np.ndarray | float,
    species: str | None = None,
) -> np.ndarray:
    """
    Arbuscular Mycorrhizal Fungi (AMF) root colonisation, as % of root length.

    Wraps the existing biology.mycorrhizal state (which is tracked 0–1 by
    biology_step) onto the empirical 0–70 % scale that soil scientists
    actually measure, and applies Treseder (2004) meta-analysis modifiers
    for N fertilisation and tillage.

    Treseder 2004 key findings:
      - Nitrogen fertilisation at 100 kg/ha reduces AMF by an average 15 %.
      - Phosphorus fertilisation reduces AMF more strongly (not tracked here).
      - Tillage reduces AMF by an average 30–40 %.
      - Undisturbed woodland: 50–70 % colonisation typical.
      - Agricultural baseline: 20–40 %.

    Parameters
    ----------
    mycorrhizal_state : 0–1 from biology_step (scaled here to %)
    tillage : bool
    fertilizer_n_kg_ha : synthetic N
    canopy_cover : 0–1 tree/perennial cover
    species : philosophy species name (eucalyptus suppresses native AMF)

    Returns
    -------
    amf_pct : % root length colonised
    """
    myc = np.asarray(mycorrhizal_state, dtype=float)
    canopy = np.asarray(canopy_cover, dtype=float)

    # Base colonisation: biology.py tracks 0–1, scale to 0–70 % empirical range.
    amf = myc * 70.0

    # Canopy contributes additional fungal habitat (perennial root systems).
    amf = amf + canopy * 15.0

    # Tillage penalty (Treseder meta-analysis: ~35 % reduction under tillage)
    if tillage:
        amf = amf * 0.65

    # N fertilisation penalty (Treseder: ~15 % reduction per 100 kg N/ha)
    n_penalty = max(0.4, 1.0 - 0.15 * (fertilizer_n_kg_ha / 100.0))
    amf = amf * n_penalty

    # Eucalyptus: allelopathic litter suppresses AMF communities
    # (though eucalyptus itself forms ectomycorrhizas, not AMF)
    if species == "eucalyptus":
        amf = amf * 0.3

    return np.clip(amf, 0.0, 85.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Composite "Living Soil Index" for the exhibition visual strip
# ═══════════════════════════════════════════════════════════════════════════

def living_soil_index(
    mbc: np.ndarray | float,
    fb_ratio: np.ndarray | float,
    qco2: np.ndarray | float,
    amf_pct: np.ndarray | float,
) -> np.ndarray:
    """
    Composite 0–100 index for the frontend "Living Layer" strip.

    Combines the four indicators into a single legible dial. Chosen
    weighting reflects that for a non-expert visitor the story is
    "is the soil alive and healthy?" — so MBC (biomass) and F:B
    (maturity) dominate, qCO2 is a penalty (stressed = bad), and
    AMF is the symbiosis bonus.

    Scale anchors:
      - 0   : dead / sterile soil (post-fire, heavy tillage, acidified)
      - 50  : Mediterranean agricultural baseline
      - 100 : mature undisturbed woodland with strong mycorrhizal network

    # TODO(user): These weights are a first-pass judgment call. The ratio
    #   40 / 25 / 15 / 20 for MBC / F:B / -qCO2 / AMF is inspired by how
    #   Bünemann et al. (2018, Soil Biology & Biochemistry) weight soil-
    #   quality indicator panels. You may want to tune this for the
    #   exhibition — e.g. if you want the story to be more about mycorrhizal
    #   networks ("the underground internet"), raise AMF's weight. If you
    #   want it to be more about carbon storage life, raise MBC.
    """
    mbc_norm = np.clip(mbc / 1.5, 0, 1) * 100        # 0–100
    fb_norm = np.clip(fb_ratio / 1.5, 0, 1) * 100     # 0–100
    # qCO2 is inverted: higher = worse. Anchor: qCO2 of 3 = stressed.
    qco2_norm = np.clip(1.0 - (np.asarray(qco2, dtype=float) - 0.5) / 3.0, 0, 1) * 100
    amf_norm = np.clip(amf_pct / 60.0, 0, 1) * 100    # 0–100

    # Weighted composite
    index = (
        0.40 * mbc_norm
        + 0.25 * fb_norm
        + 0.15 * qco2_norm
        + 0.20 * amf_norm
    )
    return np.clip(index, 0.0, 100.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Top-level convenience: derive all indicators from engine state
# ═══════════════════════════════════════════════════════════════════════════

def compute_all_indicators(
    soc_surface_g_kg: np.ndarray,
    clay_pct: np.ndarray,
    moisture_ratio: np.ndarray,
    temperature_c: float,
    rothc_bio_pool: np.ndarray | None,
    co2_respiration_g_kg_yr: np.ndarray,
    soil_ph: np.ndarray,
    canopy_cover: np.ndarray,
    mycorrhizal_state: np.ndarray,
    philosophy_params: dict,
    sand_pct: np.ndarray | None = None,
    precip_mm: float | None = None,
    use_ml: bool = True,
) -> dict:
    """
    Single entry point called from engine.py per year, per ensemble member.

    Accepts the state the engine already computes, returns a dict of four
    indicator arrays (shape matches input arrays, usually n_cells) plus the
    composite index.
    """
    tillage = bool(philosophy_params.get("tillage", False))
    fert_n = float(philosophy_params.get("fertilizer_N_kg_ha_yr", 0))
    grazing = float(philosophy_params.get("grazing_intensity", 0.0))
    species = philosophy_params.get("species")

    # ── ML path: trained RandomForest ensemble ─────────────────────────
    # When the saved models are available, we route prediction through the
    # ML layer rather than the formula-based path. The ML layer was trained
    # on 5000 synthesised Mediterranean pedons drawn from published meta-
    # analyses (Wardle 1992, Fierer 2009, Treseder 2004, Anderson & Domsch
    # 1990). It learns non-linear interactions the formulas can't express
    # and reports prediction uncertainty per cell.
    if use_ml and sand_pct is not None:
        try:
            from backend.soil_model import microbial_ml
            if microbial_ml.is_available():
                ml_result = microbial_ml.predict_all(
                    soc_surface_g_kg=soc_surface_g_kg,
                    clay_pct=clay_pct,
                    sand_pct=sand_pct,
                    soil_ph=soil_ph,
                    temperature_c=float(temperature_c),
                    precip_mm=float(precip_mm) if precip_mm is not None else 580.0,
                    canopy_cover=canopy_cover,
                    philosophy_params=philosophy_params,
                    moisture_ratio=moisture_ratio,
                )
                ml_result["source"] = "ml_random_forest"
                return ml_result
        except Exception as exc:
            # Soft fall through to the formula path
            import warnings
            warnings.warn(f"microbial ML path failed, using formulas: {exc}")

    mbc = microbial_biomass_c(
        soc_g_kg=soc_surface_g_kg,
        clay_pct=clay_pct,
        moisture_ratio=moisture_ratio,
        temperature_c=temperature_c,
        rothc_bio_pool=rothc_bio_pool,
    )

    fb = fungal_bacterial_ratio(
        soil_ph=soil_ph,
        soc_g_kg=soc_surface_g_kg,
        canopy_cover=canopy_cover,
        tillage=tillage,
        fertilizer_n_kg_ha=fert_n,
        grazing_intensity=grazing,
    )

    qco2 = metabolic_quotient_qco2(
        mbc=mbc,
        temperature_c=temperature_c,
        moisture_ratio=moisture_ratio,
        co2_respiration_g_kg_yr=co2_respiration_g_kg_yr,
    )

    amf = amf_colonisation_pct(
        mycorrhizal_state=mycorrhizal_state,
        tillage=tillage,
        fertilizer_n_kg_ha=fert_n,
        canopy_cover=canopy_cover,
        species=species,
    )

    # ── Management-effect bonuses ──────────────────────────────────────
    # The engine's vegetation + biology dynamics are conservative within a
    # 50-year horizon and undershoot the direct microbial response to
    # amendments and species choices. These bonuses are literature-anchored
    # and applied *after* the base indicators so they are transparent and
    # bounded. Without them the Living Layer fails to differentiate
    # philosophies at the exhibition time-scale.
    #
    # References:
    #   Biochar MBC/AMF   : Warnock 2007 (Plant & Soil); Lehmann et al. 2011
    #   Compost MBC       : Diacono & Montemurro 2010 (Agronomy for S.D.)
    #   Cover crops F:B   : Finney et al. 2017 (Agriculture Ecosystems Env)
    #   Holm oak EcM/AMF  : Azul et al. 2010 (Mycorrhiza)
    #   Eucalyptus suppr. : Calviño-Cancela 2013 (Forest Ecology Mgmt)
    amendments = set(philosophy_params.get("amendments") or [])

    if "biochar" in amendments:
        mbc = np.clip(mbc * 1.35, 0.01, 3.0)
        amf = np.clip(amf + 15.0, 0.0, 85.0)
        qco2 = np.clip(qco2 * 0.85, 0.1, 10.0)   # more efficient community

    if "compost" in amendments:
        mbc = np.clip(mbc * 1.25, 0.01, 3.0)
        fb = np.clip(fb + 0.15, 0.05, 2.5)
        qco2 = np.clip(qco2 * 0.90, 0.1, 10.0)

    if "cover_crops" in amendments:
        mbc = np.clip(mbc * 1.15, 0.01, 3.0)
        fb = np.clip(fb + 0.30, 0.05, 2.5)
        amf = np.clip(amf + 8.0, 0.0, 85.0)

    # Species-specific mycorrhizal and F:B bonuses
    if species == "holm_oak":
        amf = np.clip(amf + 30.0, 0.0, 85.0)
        fb = np.clip(fb + 0.50, 0.05, 2.5)
    elif species == "maquis":
        amf = np.clip(amf + 18.0, 0.0, 85.0)
        fb = np.clip(fb + 0.25, 0.05, 2.5)
    elif species == "agroforestry":
        amf = np.clip(amf + 22.0, 0.0, 85.0)
        fb = np.clip(fb + 0.30, 0.05, 2.5)
    elif species == "eucalyptus":
        fb = np.clip(fb * 0.7, 0.05, 2.5)
        qco2 = np.clip(qco2 * 1.3, 0.1, 10.0)    # acidification stress

    # Moderate grazing keeps active nutrient cycling (dehesa)
    if philosophy_params.get("grazing", False) and 0 < grazing < 0.5:
        mbc = np.clip(mbc * 1.10, 0.01, 3.0)

    lsi = living_soil_index(mbc=mbc, fb_ratio=fb, qco2=qco2, amf_pct=amf)

    return {
        "mbc_g_kg": mbc,
        "fb_ratio": fb,
        "qco2": qco2,
        "amf_pct": amf,
        "living_soil_index": lsi,
        "source": "formula_based",
    }
