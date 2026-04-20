"""
Train ML models for microbial indicators from published meta-analyses.

Four targets — all predicted from a common feature vector:
  - MBC        : Microbial Biomass Carbon (g C / kg soil)
  - FB_ratio   : Fungal:Bacterial biomass ratio (dimensionless)
  - qCO2       : Metabolic quotient (mg CO2-C / g MBC / hour)
  - AMF_pct    : AMF root colonisation (% of root length)

Training data source
--------------------
Because this exhibition runs offline on a kiosk, we don't have live access to
the underlying meta-analysis spreadsheets. Instead we SYNTHESISE a training
dataset by sampling plausible Mediterranean soil pedons (n=5000) and applying
the empirical relationships documented in the original papers, with realistic
Gaussian noise calibrated to each paper's reported standard deviation.

This gives us a dataset that is literature-faithful to first order. The
trained RandomForest then captures the non-linear interactions between
features (pH × N fertiliser, canopy × tillage, etc.) that the flat formulas
in `microbial_indicators.py` cannot express.

This is NOT a substitute for training on real measurements. It IS a principled
way to turn structured expert knowledge into a fast, differentiable predictor
with visible feature importance — which is what the exhibition needs to
demonstrate "the predictive power of AI through soil."

References
----------
MBC:
  Wardle, D.A. (1992) "A comparative assessment of factors which influence
    microbial biomass carbon and nitrogen levels in soil." Biological Reviews
    67(3), 321-358. (MBC ≈ 1-3 % of SOC, modulated by clay + moisture + temp)
  Dong et al. (2022) "Global patterns of the response of soil microbial
    biomass to climate." Science of the Total Environment 838.

F:B ratio:
  Bardgett & McAlister (1999) Biology & Fertility of Soils 29, 282-290.
  Fierer et al. (2009) "Global patterns in belowground communities."
    Ecology Letters 12(11), 1238-1249.
  de Vries et al. (2006) Soil Biology & Biochemistry 38(8), 2092-2103.

qCO2:
  Anderson & Domsch (1990) Soil Biology & Biochemistry 22(2), 251-255.
  Dilly (2005) "Metabolic quotients in response to management and land use."

AMF colonisation:
  Treseder (2004) New Phytologist 164(2), 347-355. (meta-analysis n=152)
  Treseder & Allen (2002) New Phytologist 155(3), 507-515.

Usage
-----
    python -m backend.ml_models.train_microbial

Writes:
    backend/ml_models/saved_models/microbial_{mbc,fb,qco2,amf}.joblib
    backend/ml_models/saved_models/microbial_metadata.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

try:
    import joblib
except ImportError:
    from sklearn.externals import joblib  # older sklearn


# ══════════════════════════════════════════════════════════════════════════
#  Feature specification
# ══════════════════════════════════════════════════════════════════════════

FEATURE_NAMES = [
    "soc_g_kg",        # 0.5 – 40
    "clay_pct",        # 5 – 55
    "sand_pct",        # 5 – 90
    "soil_ph",         # 4.0 – 8.5
    "temp_c",          # 5 – 28
    "precip_mm",       # 150 – 1500
    "canopy_cover",    # 0 – 1
    "tillage",         # 0 | 1
    "fert_n_kg_ha",    # 0 – 250
    # Species encoded one-hot (match backend/soil_model/vegetation.py keys)
    "sp_holm_oak",
    "sp_maquis",
    "sp_agroforestry",
    "sp_eucalyptus",
    "sp_annual_crop",
    # Amendment one-hots — what the manager is DOING to the soil.
    # Each has a literature-documented effect on microbial state.
    "amend_biochar",     # Warnock 2007, Lehmann 2011: +MBC, +AMF, -qCO2
    "amend_compost",     # Diacono 2010: +MBC, +F:B, -qCO2
    "amend_cover_crops", # Finney 2017: +MBC, +F:B, +AMF
    # Dynamic soil moisture — separate signal from annual precipitation.
    # Two years with the same rainfall can have very different soil moisture
    # depending on the previous season, soil texture, and canopy cover.
    # This lets the ML distinguish wet from dry years within the same scenario.
    "moisture_ratio",    # 0 – 1 (current soil_moisture / field_capacity)
]

SPECIES = ["holm_oak", "maquis", "agroforestry", "eucalyptus", "annual_crop"]

OUTPUT_DIR = Path(__file__).parent / "saved_models"
OUTPUT_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════
#  Synthetic dataset generator — each function encodes the published
#  empirical relationship for one target with Gaussian noise.
# ══════════════════════════════════════════════════════════════════════════

def _sample_features(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Sample n realistic Mediterranean soil pedons, now with amendments."""
    soc      = np.clip(rng.gamma(2.0, 5.0, n), 0.5, 40.0)
    clay     = rng.uniform(5, 55, n)
    sand     = rng.uniform(5, 90, n)
    ph       = rng.uniform(4.0, 8.5, n)
    temp     = rng.uniform(5, 28, n)
    precip   = rng.uniform(150, 1500, n)
    canopy   = rng.uniform(0, 1, n)
    tillage  = (rng.uniform(0, 1, n) < 0.35).astype(float)
    fert_n   = np.where(tillage > 0,
                        rng.uniform(50, 250, n),
                        rng.uniform(0, 30, n))
    sp_idx = rng.integers(0, len(SPECIES), n)
    sp_one_hot = np.zeros((n, len(SPECIES)))
    sp_one_hot[np.arange(n), sp_idx] = 1.0

    # Amendments are applied more often with perennial systems than with
    # industrial; correlated per pedon but otherwise independent Bernoullis.
    # These are *present / absent* flags, not doses — the effect sizes come
    # from the meta-analyses' average response at typical application rates.
    p_biochar = np.where(tillage > 0.5, 0.05, 0.30)
    p_compost = np.where(tillage > 0.5, 0.10, 0.35)
    p_cover   = np.where(tillage > 0.5, 0.15, 0.25)
    biochar = (rng.uniform(0, 1, n) < p_biochar).astype(float)
    compost = (rng.uniform(0, 1, n) < p_compost).astype(float)
    cover   = (rng.uniform(0, 1, n) < p_cover).astype(float)

    # Dynamic soil moisture — sampled correlated with precip but with
    # independent variation from texture + canopy + season.
    # Typical Mediterranean moisture_ratio is 0.2-0.8 with summer lows ~0.1.
    precip_proxy = np.clip(precip / 1000.0, 0.1, 1.3)
    canopy_moist_bonus = canopy * 0.15  # shaded soils retain more moisture
    clay_bonus         = np.clip(clay / 120.0, 0, 0.25)
    mr_base = 0.25 + 0.4 * precip_proxy + canopy_moist_bonus + clay_bonus
    mr_noise = rng.normal(0, 0.08, n)
    moisture_ratio = np.clip(mr_base + mr_noise, 0.05, 1.0)

    feats = np.column_stack([
        soc, clay, sand, ph, temp, precip, canopy, tillage, fert_n,
        sp_one_hot,
        biochar, compost, cover,
        moisture_ratio,
    ])
    return feats, sp_idx


def _target_mbc(feats: np.ndarray, sp_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    Microbial Biomass C from Wardle 1992, Dong 2022.
    MBC ≈ (1.5–3.5 %) × SOC, modulated by clay (protection), soil moisture,
    temperature optimum near 20 °C. σ ≈ 25 % of mean (Wardle 1992 Table 2).
    """
    soc, clay, _, _, temp, precip, _, _, _ = feats[:, :9].T
    moisture_ratio = feats[:, 17]
    base_frac = 0.015 + 0.02 * np.clip(clay / 50.0, 0, 1)         # 1.5–3.5 %
    # Dynamic soil moisture is the primary short-term driver (half-weight)
    # combined with the annual precipitation signal (half-weight).
    moisture_proxy = 0.5 * np.clip(precip / 700.0, 0.3, 1.2) + \
                     0.5 * np.clip(moisture_ratio / 0.6, 0.3, 1.2)
    thermal = np.exp(-((temp - 20.0) ** 2) / (2 * 7.0 ** 2))      # Gaussian around 20°C
    thermal = np.clip(thermal, 0.25, 1.0)
    mbc = soc * base_frac * moisture_proxy * thermal

    # Amendment effects on MBC — present/absent × published effect size.
    # Warnock et al. 2007 Plant & Soil 300: biochar boosts MBC ~30–40 %.
    # Diacono & Montemurro 2010 Agronomy SD 30: compost boosts MBC ~20–30 %.
    # Finney et al. 2017 Ag Ecosyst Env 235: cover crops boost MBC ~15 %.
    biochar, compost, cover = feats[:, 14], feats[:, 15], feats[:, 16]
    mbc = mbc * (1.0 + 0.35 * biochar)
    mbc = mbc * (1.0 + 0.25 * compost)
    mbc = mbc * (1.0 + 0.15 * cover)

    noise = rng.normal(1.0, 0.25, len(feats))                     # ±25 % multiplicative
    mbc = mbc * np.clip(noise, 0.4, 2.0)
    return np.clip(mbc, 0.01, 3.0)


def _target_fb_ratio(feats: np.ndarray, sp_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    F:B biomass ratio from Fierer 2009 global meta, de Vries 2006, Bardgett 1999.
    Key drivers:
      - pH: F:B peaks at 4.5-5.5, drops to ~0.3 at pH 8
      - SOC: higher C:N (proxied by SOC) favours fungi
      - Canopy: tree cover → fungi
      - Tillage: collapses F:B to ~0.3 × baseline
      - N fertiliser: every 50 kg/ha drops F:B ~15 %
    Natural ranges observed: 0.05 (industrial) — 2.5 (undisturbed woodland).
    σ ≈ 30 % of mean in field studies.
    """
    soc, clay, sand, ph, temp, precip, canopy, tillage, fert_n = feats[:, :9].T
    # pH effect — piecewise
    f_ph = np.where(ph < 5.0, 1.6,
            np.where(ph < 6.0, 1.2,
             np.where(ph < 7.0, 0.9,
              np.where(ph < 8.0, 0.6, 0.35))))
    # SOC effect
    f_soc = 0.4 + 0.7 * np.clip(soc / 25.0, 0, 1)
    # Canopy → fungi
    f_canopy = 0.5 + 1.0 * np.clip(canopy, 0, 1)
    # Base
    fb = 0.75 * f_ph * f_soc * f_canopy
    # Tillage penalty
    fb = fb * np.where(tillage > 0.5, 0.32, 1.0)
    # N suppression
    fb = fb * np.clip(1.0 - fert_n / 250.0 * 0.55, 0.35, 1.0)
    # Species
    sp_multipliers = {
        "holm_oak":    1.3,
        "maquis":      1.0,
        "agroforestry":1.15,
        "eucalyptus":  0.6,
        "annual_crop": 0.45,
    }
    sp_mult = np.array([sp_multipliers[SPECIES[i]] for i in sp_idx])
    fb = fb * sp_mult

    # Amendment effects on F:B — published absolute shifts (not multipliers).
    # Diacono 2010: compost adds ~0.15 to F:B (stimulates saprotrophic fungi).
    # Finney 2017: cover crops shift F:B upward by ~0.30 via fine-root exudates.
    # Biochar (Warnock 2007) has a smaller F:B effect — we omit.
    biochar, compost, cover = feats[:, 14], feats[:, 15], feats[:, 16]
    fb = fb + 0.15 * compost + 0.30 * cover

    noise = rng.normal(1.0, 0.30, len(feats))
    fb = fb * np.clip(noise, 0.3, 2.0)
    return np.clip(fb, 0.05, 2.5)


def _target_qco2(feats: np.ndarray, sp_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    Metabolic quotient qCO2 from Anderson & Domsch 1990, Dilly 2005.
    High under stress: hot+dry+disturbed soils. Low in mature undisturbed.
    Range: 0.3 (mature forest) to 6.0 (degraded industrial).
    σ ≈ 0.8 absolute.
    """
    soc, clay, sand, ph, temp, precip, canopy, tillage, fert_n = feats[:, :9].T
    moisture_ratio = feats[:, 17]
    # qCO2 responds to real soil moisture (stress signal), not just annual rain
    moisture_proxy = 0.3 * np.clip(precip / 700.0, 0.3, 1.2) + \
                     0.7 * np.clip(moisture_ratio / 0.6, 0.3, 1.2)
    base = 1.3 + 0.05 * np.clip(temp - 15, 0, 15)                 # thermal stress
    base = base * (1.3 - 0.3 * moisture_proxy)                    # drought stress
    base = base * np.where(tillage > 0.5, 1.6, 1.0)               # tillage disturbance
    base = base * (1.0 + canopy * -0.35)                           # canopy cooling effect
    base = base * (1.0 + fert_n / 300.0 * 0.4)                    # synthetic N boosts stress

    # Amendment effects on qCO2 — amendments create a healthier, more efficient
    # microbial community, so qCO2 drops.
    # Warnock 2007: biochar reduces qCO2 ~15 % (more efficient microbes).
    # Diacono 2010: compost reduces qCO2 ~10 %.
    # Finney 2017: cover crops reduce qCO2 ~8 %.
    biochar, compost, cover = feats[:, 14], feats[:, 15], feats[:, 16]
    base = base * (1.0 - 0.15 * biochar)
    base = base * (1.0 - 0.10 * compost)
    base = base * (1.0 - 0.08 * cover)

    noise = rng.normal(0, 0.5, len(feats))
    q = base + noise
    return np.clip(q, 0.1, 10.0)


def _target_amf(feats: np.ndarray, sp_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    AMF colonisation % from Treseder 2004 meta-analysis (n=152).
    Undisturbed woodland: 50-70 %
    Pasture: 30-50 %
    Cropland: 10-30 %
    Severely disturbed / acidified: <5 %
    Eucalyptus forms ectomycorrhiza, not AMF — low AMF signal.
    σ ≈ 12 percentage points.
    """
    soc, clay, sand, ph, temp, precip, canopy, tillage, fert_n = feats[:, :9].T
    base = 30.0 + 40.0 * canopy                                   # 30-70 range
    # Tillage penalty (Treseder meta: ~35 % reduction)
    base = base * np.where(tillage > 0.5, 0.65, 1.0)
    # N fertilisation penalty
    base = base * np.clip(1.0 - fert_n / 300.0 * 0.5, 0.4, 1.0)
    # pH effect — AMF prefers slightly acidic to neutral
    ph_penalty = np.where((ph < 5.5) | (ph > 8.0), 0.7, 1.0)
    base = base * ph_penalty
    # Species
    sp_multipliers = {
        "holm_oak":    1.2,   # dual EcM/AMF association
        "maquis":      1.0,
        "agroforestry":1.1,
        "eucalyptus":  0.3,   # allelopathy + EcM host
        "annual_crop": 0.7,
    }
    sp_mult = np.array([sp_multipliers[SPECIES[i]] for i in sp_idx])
    base = base * sp_mult

    # Amendment effects on AMF colonisation — additive percentage points.
    # Warnock 2007 Plant & Soil: biochar adds ~15 pp to AMF colonisation.
    # Finney 2017: cover crops add ~8 pp via continuous host root presence.
    # Compost has variable effect — omit.
    biochar, _, cover = feats[:, 14], feats[:, 15], feats[:, 16]
    base = base + 15.0 * biochar + 8.0 * cover

    noise = rng.normal(0, 10.0, len(feats))
    return np.clip(base + noise, 0.0, 85.0)


TARGETS = {
    "mbc":  _target_mbc,
    "fb":   _target_fb_ratio,
    "qco2": _target_qco2,
    "amf":  _target_amf,
}


# ══════════════════════════════════════════════════════════════════════════
#  Training
# ══════════════════════════════════════════════════════════════════════════

def train_all(n_samples: int = 5000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    X, sp_idx = _sample_features(n_samples, rng)

    results = {}
    for name, target_fn in TARGETS.items():
        y = target_fn(X, sp_idx, rng)
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=seed)
        model = RandomForestRegressor(
            n_estimators=150,
            max_depth=12,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=seed,
        )
        model.fit(X_tr, y_tr)
        pred_tr = model.predict(X_tr)
        pred_te = model.predict(X_te)
        r2_train = r2_score(y_tr, pred_tr)
        r2_test  = r2_score(y_te, pred_te)
        mae_test = mean_absolute_error(y_te, pred_te)
        fi = dict(zip(FEATURE_NAMES, model.feature_importances_.tolist()))

        # Save model
        model_path = OUTPUT_DIR / f"microbial_{name}.joblib"
        joblib.dump(model, model_path)

        results[name] = {
            "n_train": int(len(X_tr)),
            "n_test":  int(len(X_te)),
            "r2_train": round(r2_train, 3),
            "r2_test":  round(r2_test, 3),
            "mae_test": round(mae_test, 4),
            "feature_importance": {k: round(v, 4) for k, v in fi.items()},
            "model_path": str(model_path.relative_to(Path(__file__).parent.parent.parent)),
        }
        print(f"  {name:5s}: R²(test)={r2_test:.3f}  MAE={mae_test:.3f}  "
              f"top feature: {max(fi, key=fi.get)} ({fi[max(fi, key=fi.get)]:.2f})")

    metadata = {
        "feature_names": FEATURE_NAMES,
        "species_encoding": SPECIES,
        "n_samples": n_samples,
        "training_data": "synthesized from literature meta-analyses",
        "sklearn_version": __import__("sklearn").__version__,
        "targets": results,
    }
    meta_path = OUTPUT_DIR / "microbial_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    return metadata


if __name__ == "__main__":
    print(f"Training microbial ML models (sklearn)...")
    meta = train_all(n_samples=5000, seed=42)
    print(f"\nSaved to {OUTPUT_DIR}")
    print(f"Metadata: {OUTPUT_DIR / 'microbial_metadata.json'}")
