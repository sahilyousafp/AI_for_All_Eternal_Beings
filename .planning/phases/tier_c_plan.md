# Tier C — Data-Driven Vegetation from Sentinel-2

*Master plan. Drafted 2026-04-13. Execution halted awaiting user go-ahead.*

## Motivation

The production soil model currently drives vegetation with a species-level
Chapman-Richards growth curve (`backend/soil_model/vegetation.py`). The curve's
parameters (Bmax, k, p) come from global forestry literature, not from Barcelona
specifically. Tier C replaces that curve with a machine-learning model **trained
by us, on ten years of European Space Agency Sentinel-2 satellite observations
of the Iberian Peninsula**, so that the vegetation layer of every visitor
scenario is grounded in real, locally observed patterns.

This is the one change that moves the pavilion from *"AI-as-wrapper-around-
published-science"* to *"AI-as-an-ML-model-we-trained-ourselves-on-10-years-of-
Barcelona-satellite-imagery."* For the AI for ALL course brief that cares about
civic legibility of AI, the shift is substantial — visitors can meaningfully be
told *"the model learned from this many real images of this specific ground."*

## Scientific honest-framing guardrails

Before the first line of code is written, the team must agree on these
limitations so the eventual deck framing stays defensible:

1. **Sentinel-2 gives observed history, not counterfactuals.** We cannot train
   directly on *"Barcelona under intensive regenerative agriculture"* because
   that management has not been applied to Barcelona at the scale we would need
   to observe. The workaround: train across Spain on pixels already under each
   management class (using MODIS Land Cover + ESA WorldCover as the class
   label) and extrapolate to Barcelona's starting state. This is defensible —
   Estel et al. (2016) does exactly this for European agricultural abandonment —
   but it is **not** counterfactual ML. The deck must describe the model as
   "an observational model trained across Spanish land-use classes, applied to
   Barcelona" rather than "an experimental model."
2. **Cloud cover will eat some of the signal.** Barcelona has cloud / haze days
   especially in spring. We must cloud-mask using the Sentinel-2 SCL (scene
   classification) band, gap-fill, and publish the gap-fill methodology.
3. **Seasonality will dominate any raw NDVI signal.** A naive model will just
   learn "plants are green in spring." We must de-seasonalise (subtract the
   monthly climatology) before training, and predict the *anomaly* not the raw
   NDVI. This is the single biggest modelling decision and it goes in Phase 6.
4. **The target is next-year NDVI, not next-day.** We do not need (and should
   not promise) daily-forecast granularity. Annual-mean NDVI is the right
   resolution to couple with the soil simulation's annual timestep.

## Overall shape

Six phases. Phases 4 and 5 can run in parallel after Phase 4.1. Phases 6, 7,
and 8 must run sequentially. Phase 9 runs after 8.

```
Phase 4  GEE infrastructure setup  (blocking — user needed once)
   │
   ├──► Phase 5  Sentinel-2 NDVI acquisition        [data engineering]
   │
   └──► Phase 6  Feature engineering + training data [data science]
              │
              ▼
         Phase 7  Model training + validation        [ML]
              │
              ▼
         Phase 8  Integration into soil engine        [backend integration]
              │
              ▼
         Phase 9  Frontend provenance + docs           [doc + UX]
```

Rough timeline, assuming weekend-shaped sessions and Claude running with
/gsd: **5–7 focused working days**, compressible to 4 with parallelism.
Calendar realistic estimate: **2–3 weeks**.

Full phase specs below.

---

## Phase 4 — GEE infrastructure setup

**Goal.** Be able to query and export Sentinel-2 imagery for arbitrary
Iberian Peninsula tiles from Python, authenticated against a personal
Google account, with all data-handling code skeletons in place.

**Blocked by.** Phase 1–3 of the current milestone (already complete).

**Preconditions (user action required).**
- [ ] **USER** creates a free Google Cloud project at
      https://console.cloud.google.com — project ID will be written into
      `backend/data_downloader/gee_config.json`. ~5 minutes.
- [ ] **USER** enables the Earth Engine API in the GCP project.
- [ ] **USER** runs `earthengine authenticate` once in a terminal, signs in
      with a Google account, pastes the token back. ~5 minutes.

This is the halt point. Without these three user actions Phase 4 cannot
finish, and nothing downstream can start.

**Deliverables.**
- `backend/data_downloader/sentinel2/` new package directory
- `backend/data_downloader/sentinel2/__init__.py`
- `backend/data_downloader/sentinel2/gee_client.py` — thin wrapper over
  `earthengine-api` with authentication check, project binding, and a
  `fetch_image_collection(roi, start, end, bands)` helper
- `backend/data_downloader/sentinel2/gee_config.json` — user's GCP project ID
  + data paths (gitignored — contains personal identifiers)
- `backend/data_downloader/sentinel2/regions.py` — definitions of the
  Barcelona 20×20 installation ROI and the wider Spanish training ROI as
  `ee.Geometry` objects
- Updated `requirements.txt` or equivalent: adds `earthengine-api` +
  `google-auth` + `google-cloud-storage`
- Quick-sanity test in `tests/test_gee_client.py`: can the client
  authenticate? Can it return one tile metadata for a 1-week window?

**Acceptance.** `python -c "from backend.data_downloader.sentinel2.gee_client import ping; ping()"`
prints the number of Sentinel-2 L2A images available over the Barcelona
ROI in April 2024 without raising an auth error.

**Estimated effort.** 2–4 hours of claude time + 15 minutes of user time.

**Failure modes to watch.**
- Windows Python + `earthengine-api` can be fussy about `pyasn1` versions.
  Pin early.
- Corporate Google accounts sometimes block Earth Engine — use a personal
  Google account if possible.
- GEE has a 5000-request-per-hour quota; not a concern at this phase but
  will matter in Phase 5.

---

## Phase 5 — Sentinel-2 NDVI acquisition for Iberian training set

**Goal.** Download and locally cache 10 years of monthly NDVI composites
for the Iberian Peninsula (training) and for the exact Barcelona
installation ROI (inference target). Cloud-mask and gap-fill.

**Blocked by.** Phase 4.

**Preconditions.** User has confirmed Phase 4 acceptance test passes.

**Deliverables.**
- `backend/data_downloader/sentinel2/fetch_ndvi.py` — the download pipeline.
  For each (ROI, year, month) tuple:
  1. Query Sentinel-2 L2A collection filtered by ROI and date window
  2. Apply SCL cloud mask (drop pixels classified as clouds/shadows)
  3. Compute NDVI = (B8 − B4) / (B8 + B4)
  4. Reduce to monthly median composite
  5. Export as 30 m GeoTIFF to Google Drive OR via Google Cloud Storage OR
     directly via `.getDownloadURL()` (decide in Phase 4 during testing —
     direct download is simpler but caps at ~30 MB per request)
- `backend/data_downloader/sentinel2_ndvi/` raster cache directory:
  - `iberia/ndvi_YYYY_MM.tif` — ~120 files (10 years × 12 months),
    each ~50–150 MB
  - `barcelona/ndvi_YYYY_MM.tif` — higher resolution, smaller area, ~120
    files at ~1–5 MB each
- `backend/data_downloader/sentinel2/gap_fill.py` — temporal linear
  interpolation module that fills NaN pixels (from cloud masking) with
  the mean of the neighbouring months, and flags months where >30 % of
  pixels remain invalid
- `backend/ml_models/sentinel2_prep.py` — thin loader that stacks the
  cached GeoTIFFs into `(N_pixels, N_months)` arrays ready for Phase 6

**Acceptance.**
1. For the Barcelona ROI, every month from 2015-01 to 2025-12 has a
   non-empty NDVI raster
2. Cloud-mask fraction per month is reported and logged — any month
   with >30 % cloud cover gets a warning
3. Aggregate disk usage under `backend/data_downloader/sentinel2_ndvi/`
   is between 5 GB and 15 GB (order-of-magnitude sanity check)
4. A single plot in `backend/data_downloader/sentinel2_ndvi/qc_plots/
   barcelona_monthly_timeseries.png` showing 2015–2025 NDVI — it should
   visibly show summer peaks, winter troughs, and the 2017 European
   heatwave drought signal. If that signal is missing, the pipeline is
   broken.

**Estimated effort.** 1–2 days of claude time + long-running GEE export
jobs (exports can take hours; claude can dispatch and wait). **User
input needed only if the chosen export path fails** — e.g. Google Drive
quota blocked — in which case claude asks the user to clear space or
switch to GCS bucket export.

**Data volume sanity check.** 30 m NDVI rasters at Iberia scale
(~600,000 km²) = ~670 million pixels per month. At float32 that's 2.7 GB
per month raw, ~50–100 MB compressed TIFF. × 120 months = 6–12 GB.
Within the 15 GB user commitment.

**Failure modes.**
- GEE export jobs silently hanging — add timeout + retry with exponential backoff
- `.getDownloadURL()` 30 MB cap — may force us into the `ee.batch.Export.image.toDrive` path with polling
- Drive API OAuth scopes sometimes need a separate consent step — could
  require a second user auth step partway through

---

## Phase 6 — Feature engineering + training data assembly

**Goal.** Convert the raw monthly NDVI stack plus existing CHIRPS /
MODIS / WorldCover layers into a clean supervised-learning dataset that
is free of seasonal leakage and blocked for spatial cross-validation.

**Blocked by.** Phase 5 (needs the Iberia NDVI cache to exist).

**Deliverables.**
- `backend/ml_models/vegetation_features.py`:
  - `build_training_frame()` — returns a pandas DataFrame with one row
    per (pixel, year, month) sample and columns:
    - `ndvi_raw` — observed NDVI for the month
    - `ndvi_anomaly` — observed NDVI minus the pixel's 10-year monthly
      mean (this is the **de-seasonalised target**)
    - `ndvi_anom_t_minus_1` through `ndvi_anom_t_minus_12` — lagged
      anomaly features
    - `temp_anomaly`, `precip_anomaly` — climate anomalies from CHIRPS
    - `land_use_class` — categorical from MODIS / WorldCover
    - `elevation`, `slope`, `aspect` — static topography from SRTM
    - `lat`, `lon` — for the spatial-block fold assignment, **not used
      as features to prevent leakage**
    - `target_ndvi_anomaly_t_plus_12` — what we want to predict
  - `spatial_fold_assignment()` — wraps the logic already written for
    Phase 3's `spatial_cv_benchmark.py`
- `backend/ml_models/sentinel2_training_data.parquet` — the cached
  training frame. Parquet because pandas CSV is slow at this size.
- `backend/ml_models/sentinel2_training_data.md` — one-page data card:
  number of samples, class balance, date range, missing-value rate

**Acceptance.**
1. Training frame has at least 1 M rows after cloud-mask filtering and
   gap-fill. (Iberia has ~500k 30m pixels × 120 months × 50 % usable
   = ~30 M rows raw; we subsample down to ~1–2 M for training speed.)
2. De-seasonalisation sanity check: the mean of `ndvi_anomaly` per
   calendar month must be very close to zero (< 0.005). If not, the
   climatology subtraction is broken.
3. Spatial fold assignment gives 5 folds each with ≥ 100k samples and
   reasonable class balance.
4. No `lat`, `lon`, or any column containing them is in the final
   feature list used for training.

**Estimated effort.** 1 day of claude time.

**Design call needed from user (halt point).** One question:
**"Should we include MODIS land-use class as a feature, or as an
output target?"**

- *As a feature:* gives the model a strong signal about what kind of
  land each pixel already is, which improves per-pixel NDVI prediction
  but weakens generalisation to hypothetical management (because at
  inference time we would have to pretend a Barcelona pixel is under
  a different class to simulate a scenario).
- *As an output:* train two heads — one predicting NDVI, one predicting
  land-use class — and at inference time condition the NDVI prediction
  on the *user-chosen* management philosophy translated to a WorldCover
  class. Harder to train, closer to what we actually want for the
  exhibition.

Claude will propose **option 2** with a fallback to **option 1** if
option 2 does not converge; user confirms.

---

## Phase 7 — Model training + validation

**Goal.** Train at least two models on the Phase 6 dataset, evaluate
under blocked spatial cross-validation, choose a winner, and save the
winning model alongside a benchmark report.

**Blocked by.** Phase 6.

**Deliverables.**
- `backend/ml_models/train_vegetation_s2.py` — training script with
  CLI flags (`--model lgbm|xgb|mlp`, `--folds 5`, `--subsample N`,
  `--output-dir`)
- Two candidate models:
  1. **LightGBM gradient boosting** — fast, interpretable, strong
     baseline. Trained on the feature frame, with `target_ndvi_anomaly`
     as the regression target.
  2. **1D Temporal Convolutional Network (TCN) or small LSTM** — trained
     on the 12-month lagged anomaly sequence. Expected to outperform
     LightGBM at capturing phenological patterns.
- Blocked spatial k-fold CV (same methodology as Phase 3's
  `spatial_cv_benchmark.py`) as the only evaluation loop.
- Saved artefacts:
  - `backend/ml_models/models/vegetation_s2_lgbm.joblib`
  - `backend/ml_models/models/vegetation_s2_tcn.pt` (if torch path chosen)
  - `backend/ml_models/VEGETATION_BENCHMARK.md` — report with:
    - per-fold R² and MAE
    - feature importances (for LightGBM)
    - prediction-vs-observed scatter plot for a held-out fold
    - comparison against a "last year's NDVI" naive baseline
    - honest discussion of failure modes found

**Acceptance.**
1. The best model beats the "last year's NDVI anomaly" naive baseline
   by at least 20 % MAE reduction on held-out spatial folds. If it
   does not, the feature set is insufficient and we iterate Phase 6.
2. Per-fold R² is reported (not hidden) even if ugly. The BENCHMARK.md
   honest-framing tone from Phase 3 is carried forward.
3. The saved model has a loadable inference path under 100 ms per
   20 × 20 grid, so it does not slow the exhibition simulation.

**Estimated effort.** 1–2 days of claude time. Training itself is
minutes to an hour per model on a laptop, but feature-engineering
iteration eats the time.

**Halt point.** Claude pings the user with the VEGETATION_BENCHMARK.md
before moving on. If the numbers are ugly, user decides whether to
iterate, ship what we have, or abandon Tier C and keep the
Chapman-Richards curve.

---

## Phase 8 — Integration into soil engine

**Goal.** Make the trained Sentinel-2 model the default vegetation
driver in the soil simulation pipeline, with a feature flag to fall
back to Chapman-Richards for debugging.

**Blocked by.** Phase 7 (needs a validated trained model on disk).

**Deliverables.**
- `backend/ml_models/vegetation_inference.py`:
  - Loads the saved Sentinel-2 model once at engine startup
  - Exposes `predict_ndvi_anomaly_next_year(current_ndvi_anomaly,
    climate_features, management_class)` → np.ndarray of shape
    `(n_cells,)`
  - Handles the management-class translation: each of the 5 philosophies
    in `backend/soil_model/philosophies.py` maps to a WorldCover
    land-use class (e.g. `maximum_restoration → Forest`,
    `industrial_agriculture → Cropland`, `let_nature_recover → Shrubland`,
    `traditional_farming → Mosaic`, `fast_fix → Tree plantation`)
- Modified `backend/soil_model/vegetation.py`:
  - New parameter `use_sentinel2_model: bool = True`
  - When the flag is True, the Chapman-Richards `biomass_step` is
    replaced with: (a) call `predict_ndvi_anomaly_next_year`, (b) add
    the anomaly to the pixel's monthly climatology, (c) convert NDVI
    to biomass via a monotone `ndvi_to_biomass(ndvi, species_params)`
    function calibrated against the existing Bmax values so the two
    regimes are comparable
  - When False, fall back to the current Chapman-Richards curve — we
    keep this path forever for debugging and for teaching purposes
- Modified `backend/soil_model/engine.py`:
  - Initial NDVI state loaded from the Phase 5 Barcelona cache for
    start year 2025
  - New `ndvi_state` array threaded through the ensemble loop alongside
    `veg_ens`, `bio_ens`, `pools_ens`
  - A new timeseries key `ndvi_mean/p10/p90` added to the return dict

**Acceptance.**
1. A 50-year simulation with `use_sentinel2_model=True` runs end-to-end
   without errors for all 5 philosophies × 4 SSP scenarios (20 combinations)
2. The 20 resulting NDVI trajectories differ visibly from each other
   (the model is actually responding to the management class)
3. Turning the flag off recovers the current Chapman-Richards behaviour
   bit-for-bit
4. End-to-end simulation runtime remains under 10 seconds for 50 years
   × 10 ensemble members (the installation has an 8-second hardware
   budget for servo refill; the computation must finish first)

**Estimated effort.** 1 day of claude time.

**Halt point.** None — claude should be able to finish this phase
autonomously once Phase 7 is accepted.

---

## Phase 9 — Frontend provenance + documentation

**Goal.** Make the new data-driven vegetation layer visible to
visitors and to the jury. Update all documentation.

**Blocked by.** Phase 8.

**Deliverables.**
- New "Data provenance" section in the exhibition frontend reasoning
  panel showing, in plain language: *"Vegetation prediction: machine-
  learning model trained on 10 years of European Space Agency
  Sentinel-2 satellite imagery (≈ X images of Barcelona, 2015–2025)."*
  with the exact image count pulled from the Phase 5 cache metadata
- Updated `EXHIBITION_SUBMISSION.md`:
  - New paragraph in the "Honest positioning" section describing Tier C
    as the second genuinely novel contribution
  - New citation block: Drusch et al. (2012) on Sentinel-2 mission;
    Gorelick et al. (2017) on Google Earth Engine; Estel et al. (2016)
    on MODIS/Sentinel-2 agricultural phenology; Radoux et al. (2016)
    on Sentinel-2 land-cover classification
  - Rewritten vegetation description mentioning the ML model
- Updated `PROJECT_REPORT.md`:
  - New top-level section documenting the `vegetation_inference.py`
    module
  - New table row in the pipeline overview for the Sentinel-2 inference step
- New `backend/ml_models/VEGETATION_MODEL.md` — card describing the
  trained model, its training data, its limitations, and how to retrain
- Updated `research/related_work.md` — add a new entry under Angle 1
  citing the Sentinel-2 vegetation precedent literature

**Acceptance.**
1. The exhibition frontend shows the data provenance panel during
   every Oracle column refill
2. EXHIBITION_SUBMISSION.md's novelty claims now include the Sentinel-2
   model and the claim is defensible
3. A new reader of PROJECT_REPORT.md can understand how to retrain the
   vegetation model

**Estimated effort.** 0.5–1 day of claude time.

---

## Artefacts checklist (for resuming from a cold cache)

When the user says "start executing Tier C," these must all exist:

- [ ] `.planning/phases/tier_c_plan.md` — this document ✅ (exists)
- [ ] `research/related_work.md` — literature scan ✅ (exists)
- [ ] Phase 1–3 complete ✅
- [ ] Working `ai4all` virtual environment with current dependencies
- [ ] ≥ 20 GB free disk space
- [ ] User has a Google account they are willing to use for GCP + GEE

And the user will be prompted to do these three manual steps exactly once,
at the start of Phase 4:

1. Create a free Google Cloud project → paste project ID
2. Enable Earth Engine API in that GCP project
3. Run `earthengine authenticate` in a terminal

After that, claude can run Phases 4 → 9 with only one more required
halt for user review of the Phase 7 model benchmark.

---

## What the user commits to

- ~30 minutes of total interactive time (GEE setup + Phase 7 model review)
- 10–20 GB disk space
- Letting claude run long-running export / training jobs in background
  sessions across multiple days
- No commits go to a remote without explicit "push" instruction
- Final kick-off requires the user to say *"start executing Tier C from
  Phase 4"* — anything less specific stays halted

---

*Plan drafted. Execution halted. Resume with `/gsd-execute-phase 4`
or by saying "start Tier C" to claude.*
