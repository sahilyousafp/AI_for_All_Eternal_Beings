# Beneath the Surface — Technical Report
*(formerly: OpenLandMap Analytics Platform)*

This document is a complete technical handover brief for anyone continuing development
on this project. It covers what the project is, how every part works, the data it uses,
the ML models, the API, the frontend, known limitations, and where to go next.

> **Status note (April 2026).** The project has pivoted from a general-purpose
> soil-and-climate web analytics tool ("OpenLandMap Analytics Platform") into the
> **AI for ALL / IAAC MaAI 2026 finals submission**: an interactive pavilion called
> *Beneath the Surface* for UIA Barcelona, June 2026. The canonical exhibition
> submission document is `EXHIBITION_SUBMISSION.md`. This file (`PROJECT_REPORT.md`)
> remains the technical reference for backend developers.

---

## 0. Honest framing — what we built, what is novel, what is not

A literature scan completed in April 2026 (`research/related_work.md`) tested every
framing claim in the deck against the existing soil-science and exhibition literature.
Three findings should govern how this codebase is described in any external write-up:

1. **The soil-science engine is derivative, not novel.** Lugato et al. (2014, JRC)
   already published SSP-conditioned RothC projections of European soil organic carbon
   with the same management-scenario branching this codebase implements. Bruni et al.
   (2021) quantified the warming penalty. Poggio et al. (2021, SoilGrids 2.0) is both
   our training data and a stronger uncertainty methodology than ours. Helfenstein
   et al. (2024) is the spatiotemporal soil-mapping work the in-progress XGBoost
   upgrade is chasing. The codebase is best described as **a reduced-form ML emulator
   of peer-reviewed European soil models, conditioned on IPCC AR6 SSP trajectories
   and exposed via a public-facing physical interface.**

2. **The Random Forest "93% accuracy" headline is not defensible.** It was computed
   under random-split cross-validation on spatially autocorrelated SoilGrids pixels,
   which Wadoux et al. (2021) is explicit about being the wrong evaluation method.
   Phase 3 of the current work cycle re-benchmarks the classifier under spatial
   k-fold CV; until that lands, the "93%" line should be removed from any document
   that goes outside the team. The replacement number will live in
   `backend/ml_models/BENCHMARK.md`.

3. **The genuine novelty is the integration medium and the microbial indicator
   layer.** No prior Critical Zones (Latour & Weibel, 2020), climate-physicalization
   (Eliasson, Anadol), or soil exhibition (Mel Chin, Maria Thereza Alves, Anaïs
   Tondeur) appears to combine a servo-actuated stratigraphic column with live ML
   inference and visitor-conditioned scenario branching. And no prior soil-science
   exhibition we found surfaces microbial indicators (MBC, F:B, qCO₂, AMF
   colonisation) in a public-facing form. These are the two contributions worth
   claiming externally.

The full literature scan, with verdicts per angle and 24 cited references, lives at
`research/related_work.md`. The exhibition write-up at `EXHIBITION_SUBMISSION.md`
implements the recommended rephrasings.

---

## 0a. The soil simulation pipeline (canonical entry points)

The exhibition stack lives under `backend/soil_model/` and `backend/ml_models/`.
Pipeline summary:

```
visitor selects (SSP scenario × land-management philosophy)
                ↓
backend/exhibition_api.py /api/exhibition/simulate
                ↓
backend/soil_model/engine.simulate()
    ├── climate_scenarios/ssp_data.get_climate()      [IPCC AR6 SSP tables → ΔT, ΔP, CO₂]
    ├── soil_model/philosophies.get_philosophy()      [5 management strategies → params]
    ├── soil_model/carbon.rothc_step()                [Coleman & Jenkinson 1996]
    ├── soil_model/water.annual_water_balance()
    ├── soil_model/vegetation.vegetation_step()
    ├── soil_model/biology.biology_step()             [BII, mycorrhizal, earthworm, aggregate stability]
    ├── soil_model/erosion.compute_erosion()          [RUSLE]
    ├── soil_model/disturbances.check_disturbances()  [fire + drought stochastic]
    └── soil_model/microbial_indicators.compute_all_indicators()
                                                       [MBC, F:B, qCO₂, AMF, Living Soil Index]
                ↓
returns: timeseries (mean / p10 / p90 per metric per year),
         spatial_timeseries (snapshots every 10 yr),
         spatial_final, events_log, confidence tiers
                ↓
frontend/exhibition/ renders charts + Living Layer panel
```

### The microbial indicators module (`backend/soil_model/microbial_indicators.py`)

This is the *one* module in the soil pipeline that has no direct precedent in either
the soil-science literature surveyed or in any prior Critical Zones / climate
exhibition. It is a pure derivation layer over existing RothC pools and biology
state — no new training data, no new calibration parameters. Every coefficient
comes from a published empirical relationship documented in the module's docstring.

**Indicators surfaced:**

| Indicator | Function | Source |
|---|---|---|
| Microbial Biomass Carbon (g C/kg) | `microbial_biomass_c()` — uses RothC BIO pool directly when available, else Wardle-1992 empirical fallback | Anderson & Domsch (1989); Wardle (1992) |
| Fungal:Bacterial ratio | `fungal_bacterial_ratio()` — driven by pH, SOC, canopy, tillage flag, fertiliser N, grazing | Bardgett & McAlister (1999); Fierer et al. (2009); de Vries et al. (2006) |
| Metabolic quotient qCO₂ (mg CO₂-C / g MBC / h) | `metabolic_quotient_qco2()` — converts annual respiration to per-MBC stress index | Anderson & Domsch (1990) |
| AMF colonisation % | `amf_colonisation_pct()` — wraps biology.mycorrhizal onto Treseder scale, applies tillage + N penalties | Treseder (2004) meta-analysis |
| Living Soil Index 0–100 | `living_soil_index()` — composite weighting of the four | weighting per Bünemann et al. (2018), open for team tuning |

Single entry point: `compute_all_indicators(...)`, called from `engine.simulate()`
once per ensemble member per year. Outputs flow through the existing `timeseries`
and `spatial_timeseries` dicts and are exposed automatically by
`/api/exhibition/simulate`. No API contract change was required.

The frontend renders them in the **Living Layer** panel below the main chart grid
(see `frontend/exhibition/index.html` and `simulation.js → renderLivingLayer()`).

---

## 1. What This Project Is

> **Note.** Section 1 below is the legacy description of the original OpenLandMap
> analytics platform. It is preserved here because the file browser, ML models,
> and GeoTIFF inference paths are still the substrate the exhibition stack draws
> on. For the exhibition framing itself, see `EXHIBITION_SUBMISSION.md` and
> Section 0 above.

---

## 1. What This Project Is

A **soil and environmental analytics web application** focused on the **Barcelona / Spain region**.

The user can:
- Visualise real satellite-derived soil and climate data on an interactive map
- Browse individual GeoTIFF files by dataset, depth layer, or year
- Run ML models to predict future values for any year
- Generate a predicted full spatial map (a new GeoTIFF) for a target year
- View analysis charts: depth profiles, cross-dataset correlations, depth-trend forecasts

The tech stack is:
- **Backend**: Python, FastAPI, rasterio, scikit-learn, numpy, joblib
- **Frontend**: Vanilla JavaScript, Leaflet.js, GeoRasterLayer (client-side GeoTIFF renderer), Chart.js
- **Data source**: Google Earth Engine (GEE), pre-downloaded as local GeoTIFF files

There is no database. All data lives as files on disk. All ML models are saved as `.joblib` files.

---

## 2. Folder Structure

```
AI_for_All_Eternal_Beings/
├── backend/
│   ├── app.py                          # FastAPI entry point — all API routes
│   ├── data_downloader/
│   │   ├── download_gee_data.py        # Script to pull GeoTIFFs from GEE
│   │   ├── soil/                       # Soil GeoTIFFs (static, depth-banded)
│   │   │   ├── Organic_Carbon.b0.tif
│   │   │   ├── Organic_Carbon.b10.tif
│   │   │   └── ... (6 depth bands × 6 soil datasets = 36 files)
│   │   ├── climate/
│   │   │   ├── Precipitation_CHIRPS.precipitation.tif   # fallback static file
│   │   │   └── year=2000/
│   │   │       └── Precipitation_CHIRPS.precipitation.tif
│   │   │   └── year=2001/ ... year=2024/
│   │   └── land_cover/
│   │       ├── MODIS_Land_Cover.LC_Type1.tif            # fallback static file
│   │       └── year=2001/ ... year=2023/
│   │           └── MODIS_Land_Cover.LC_Type1.tif
│   └── ml_models/
│       ├── utils.py                    # Dataset registry, path helpers
│       ├── data_loader.py              # rasterio-based GeoTIFF loaders
│       ├── train.py                    # Model training entry point
│       ├── temporal_inference.py       # Predict dataset mean value for a year
│       ├── spatial_inference.py        # Generate predicted GeoTIFF for a year
│       ├── forecast.py                 # Depth-profile linear trend + extrapolation
│       ├── time_series.py              # Depth profile series data
│       ├── prediction.py               # Bbox-based spatial mean prediction
│       ├── change_detection.py         # Compare two depth layers
│       ├── correlation.py              # Cross-dataset Pearson correlation
│       ├── precompute_forecasts.py     # Pre-bakes forecast results to JSON cache
│       └── saved_models/               # Trained .joblib files live here
│           ├── Organic_Carbon_ridge.joblib
│           ├── Organic_Carbon_temporal_ridge.joblib
│           └── ...
├── frontend/
│   ├── index.html                      # Single-page app shell + all CSS
│   ├── main.js                         # Predictions tab logic + chart rendering
│   ├── gee-map.js                      # Predictions map rendering + GeoRasterLayer
│   └── local-data.js                   # Local Data tab, file browser, map layers
└── PROJECT_REPORT.md                   # This file
```

---

## 3. The Datasets

All data covers **Spain** at **~2.5 km resolution**, downloaded via Google Earth Engine.

### 3.1 Soil Datasets (Static — single 2020 composite snapshot)

These are from **OpenLandMap / SoilGrids**. Each dataset has **6 depth bands**:

| Band key | Depth range |
|----------|-------------|
| b0       | 0–5 cm      |
| b10      | 10–30 cm    |
| b30      | 30–60 cm    |
| b60      | 60–100 cm   |
| b100     | 100–200 cm  |
| b200     | 200 cm+     |

| Dataset name (internal) | Display name          | Units  | Description                          |
|-------------------------|-----------------------|--------|--------------------------------------|
| Organic_Carbon          | Organic Carbon        | g/kg   | Organic carbon concentration         |
| Soil_pH                 | Soil pH               | pH     | Water-extracted pH (USDA calibration)|
| Bulk_Density            | Bulk Density          | t/m³   | Fine-earth bulk density              |
| Sand_Content            | Sand Content          | %      | Sand fraction                        |
| Clay_Content            | Clay Content          | %      | Clay fraction                        |
| Soil_Texture            | Soil Texture Class    | class  | USDA 12-class texture classification |

File naming: `{InternalName}.{band}.tif` e.g. `Organic_Carbon.b0.tif`

Soil Texture is **uint8** with nodata sentinel value **255** (not declared in GeoTIFF metadata).
This caused a colour rendering bug that was fixed with gap-detection in `computeDisplayRange`.

### 3.2 Temporal Datasets (Year-by-year files)

| Dataset name (internal)  | Years available | Primary band     | Units  |
|--------------------------|-----------------|------------------|--------|
| Precipitation_CHIRPS     | 2000–2024       | precipitation    | mm/yr  |
| MODIS_Land_Cover         | 2001–2023       | LC_Type1         | class  |

File path pattern: `data_downloader/{typology}/year={YYYY}/{DatasetName}.{band}.tif`

MODIS Land Cover uses the **IGBP classification** (17 discrete classes, 0–16):
Water, Evergreen Needleleaf Forest, Evergreen Broadleaf Forest, Deciduous Needleleaf Forest,
Deciduous Broadleaf Forest, Mixed Forest, Closed Shrubland, Open Shrubland, Woody Savanna,
Savanna, Grassland, Permanent Wetland, Cropland, Urban/Built-up, Cropland/Veg Mosaic,
Snow/Ice, Barren, Unclassified.

---

## 4. Dataset Registry (how the backend finds files)

`backend/ml_models/utils.py` scans the `data_downloader/` folder at startup and builds two
in-memory registries. These are module-level globals — no database, no config file.

**LOCAL_REGISTRY** — static/depth-banded files:
```python
{
  "Organic_Carbon": {
    "name": "Organic_Carbon",
    "typology": "soil",
    "local_files": {
      "b0": "/path/to/Organic_Carbon.b0.tif",
      "b10": "/path/to/Organic_Carbon.b10.tif",
      ...
    },
    "display": "Organic Carbon (g/kg)",
    "units": "g/kg",
    "description": "..."
  },
  ...
}
```

**TEMPORAL_REGISTRY** — year-indexed files:
```python
{
  "Precipitation_CHIRPS": {
    2000: {"precipitation": "/path/to/year=2000/Precipitation_CHIRPS.precipitation.tif"},
    2001: {"precipitation": "..."},
    ...
  },
  ...
}
```

**DATASETS** — flat ordered list combining both registries, used by `/api/datasets`.
Each entry has an `is_temporal` flag (True if 2+ years exist) and an `available_years` list.

Key helper functions in `utils.py`:
- `find_dataset(display_name)` — look up a dataset by its UI display name
- `primary_band(ds)` — returns the best single-band path (b0 for soil, first for others)
- `temporal_primary_band(name, year)` — returns the path for a specific year
- `available_years(name)` — sorted list of years with real data

---

## 5. The Backend API

Run with: `uvicorn backend.app:app --reload` from the project root.
Base URL: `http://127.0.0.1:8000`

### Core endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/status` | Health check, returns `gee_available` flag |
| GET | `/api/datasets` | Full list of datasets with metadata |
| GET | `/api/years` | Available years per temporal dataset |
| GET | `/api/local-datasets` | All files grouped by typology for the file browser |
| GET | `/api/files/{path}` | Serve any GeoTIFF file under data_downloader/ as bytes |
| GET | `/api/map` | Get the map tile URL or local file URL for a dataset+year |
| GET | `/api/infer` | Real data for a year, or ML mean-value prediction if year not downloaded |
| GET | `/api/statistics` | Click-to-sample: pixel stats at a lat/lon point |
| GET | `/api/predict-map` | Generate a full predicted GeoTIFF raster for a year |
| GET | `/api/model-status` | Which .joblib files exist for each dataset |
| POST | `/api/train` | Kick off model training in background thread |
| GET | `/api/train/status` | Poll training progress |

### Analysis endpoints

| Route | What it returns |
|-------|-----------------|
| `/api/analysis/time-series` | Depth profile (value at each of 6 soil depths) |
| `/api/analysis/prediction` | Spatial mean prediction for a year range + bbox |
| `/api/analysis/change-detection` | Pixel-level change between two depth layers |
| `/api/analysis/correlation` | Pearson correlation of each soil property vs Soil Texture |
| `/api/analysis/forecast` | Depth-profile linear trend extrapolated beyond 200 cm |
| `/api/forecasts/cached` | Pre-computed forecast from JSON cache |

### Key `/api/infer` behaviour

This endpoint is what the Predictions tab uses when you move the year slider.

1. If the dataset has no temporal files at all (all soil datasets) → returns `{supported: false}`
2. If the year has a real downloaded file → returns `{has_data: true}`
3. If the year is outside downloaded range → calls `temporal_inference.predict_year()` and
   returns a predicted mean value with confidence bounds

### Key `/api/predict-map` behaviour

Returns raw GeoTIFF bytes (float32) for a predicted spatial map.

Accepts `model_type`:
- `rf` — uses the Random Forest influence model
- `temporal_ridge` — uses the temporal Ridge model to scale the existing raster
- `temporal_mlp` — uses the temporal MLP model to scale the existing raster
- `ridge` and `mlp` are **rejected with HTTP 400** (they were depth-band proxies, not temporal)

---

## 6. The ML Models

### 6.1 Training

Training is triggered via `POST /api/train` or `python -m backend.ml_models.train`.
All models are saved as `.joblib` files under `backend/ml_models/saved_models/`.

`train_all()` in `train.py` loops over every dataset in `LOCAL_REGISTRY` and trains:

**Per dataset:**

**Ridge (depth-band)** — `{name}_ridge.joblib`
- Input: depth in cm (0, 10, 30, 60, 100, 200)
- Output: soil property value
- Model: `PolynomialFeatures(degree=2) + Ridge(alpha=10)`
- Training data: up to 1000 pixel samples per depth band
- Purpose: models how a soil property changes with depth

**MLP (depth-band)** — `{name}_mlp.joblib`
- Same inputs/outputs as Ridge
- Model: `StandardScaler + MLPRegressor(hidden=(64,32), relu, early_stopping)`
- Purpose: same as Ridge but non-linear

**Random Forest (influence)** — `{name}_rf.joblib`
- Input: primary-band pixel values of ALL OTHER datasets (same pixel location)
- Output: target dataset pixel value
- Model: `StandardScaler + RandomForestRegressor(n_estimators=100, max_depth=8)`
- Purpose: "How much do OC, pH, Sand, Clay etc. influence Soil Texture?" — feature importance
- Requires at least 3 datasets to be usable
- Training data: up to 2000 co-located pixel samples

**Temporal Ridge** — `{name}_temporal_ridge.joblib`
- Only trained for datasets with 6+ years of data (CHIRPS: 25 years, MODIS: 23 years)
- Input: year (e.g. 2015)
- Output: spatial mean value for that year
- Model: `PolynomialFeatures(degree=2) + Ridge(alpha=1)`
- Train/test split: chronological 80/20 (last 20% of years held out as test)
- Refit on all data after evaluation before saving

**Temporal MLP** — `{name}_temporal_mlp.joblib`
- Same as Temporal Ridge but neural network
- Model: `StandardScaler + MLPRegressor(hidden=(64,32), relu, early_stopping)`

**Best model** — `{name}_temporal_best.joblib`
- Whichever of Ridge/MLP had lower test RMSE is saved again under this name
- `temporal_inference.py` tries this first

### 6.2 Temporal Inference (mean value prediction)

`temporal_inference.predict_year(dataset_name, target_year)` is called by `/api/infer`.

Fallback chain (tries each in order, returns first success):
1. Load `{name}_temporal_best.joblib` — best model by test RMSE
2. Load `{name}_temporal_mlp.joblib`
3. Load `{name}_temporal_ridge.joblib`
4. Fit a Ridge polynomial on-the-fly from the TEMPORAL_REGISTRY year data (no saved model needed)
5. If none of the above work → return `{supported: false}`

Returns:
```json
{
  "predicted_value": 42.5,
  "model": "Temporal Ridge (best)",
  "confidence_low": 40.1,
  "confidence_high": 44.9,
  "year_range": [2000, 2024],
  "extrapolated": true,
  "test_metrics": {"rmse": 1.2, "mae": 0.9, "r2": 0.94}
}
```

Confidence bands are approximated as `1.645 × std(training residuals)` (90% CI assumption).

### 6.3 Spatial Inference (full predicted map)

`spatial_inference.predict_map_raster(dataset_name, year, model_type)` is called by `/api/predict-map`.

Returns GeoTIFF bytes (float32) or `None` on failure.

**RF strategy (`model_type="rf"`):**
1. Load primary-band rasters for all OTHER datasets aligned to the same grid
2. Stack them as feature columns `[h*w, n_features]`
3. Apply the saved RF model to predict pixel-by-pixel
4. If RF fails, fall back to returning the raw primary-band raster

**Temporal scaling strategy (`model_type="temporal_ridge"` or `"temporal_mlp"`):**
1. Load the temporal model
2. Predict the mean value for `target_year`
3. Compute `scale = predicted_mean / actual_mean` (ratio)
4. Multiply every valid pixel in the existing raster by `scale`
5. Return the scaled raster as GeoTIFF bytes

The scaling approach is a simplification — it shifts the entire raster up or down proportionally.
It preserves spatial patterns but does not change spatial variation. A more sophisticated approach
would be to train a model that predicts per-pixel values spatially.

---

## 7. The Frontend

Three JavaScript files, loaded in this order in `index.html`:
1. `local-data.js` — defines `API_BASE`, shared utilities, Local Data tab
2. `gee-map.js` — Predictions tab map rendering
3. `main.js` — Predictions tab controls, charts, dashboard init

### 7.1 Local Data Tab (`local-data.js`)

**What it does:**
- Calls `/api/local-datasets` to get all available GeoTIFF files
- Renders a collapsible file tree grouped by typology (soil / climate / land_cover)
- Each file item, when clicked, fetches the GeoTIFF from `/api/files/{path}` and renders it
  on the Leaflet map using GeoRasterLayer
- Multiple layers can be stacked simultaneously with individual opacity controls
- Clicking the map samples the pixel value using `sampleGeoRaster()`

**Key functions:**
- `computeDisplayRange(gr)` — computes p2–p90/p98 percentile stretch for colour scaling.
  Includes gap-detection heuristic: if p98 > p90 × 5, treats p90 as the true max and flags
  values >= p90 as nodata (handles undeclared uint8 sentinel value 255).
  Caches result on `gr._displayRange` to avoid re-scanning pixels every tile render.
- `makePixelFn(dataset, typology, georaster)` — returns the `pixelValuesToColorFn` callback
  for GeoRasterLayer. Handles MODIS discrete colours separately from continuous ramps.
- `toggleLayer(fileInfo)` — loads or unloads a GeoTIFF layer
- `sampleGeoRaster(gr, lat, lng)` — manual pixel lookup at a coordinate

**Colour palettes (PALETTES object):**
Each dataset has a 5-stop hex colour ramp. MODIS uses a discrete array of 18 colours.

### 7.2 Predictions Tab Map (`gee-map.js`)

Initialises a second Leaflet map (`geeMap`) for the Predictions tab.

**Key functions:**
- `computeDisplayRange(gr)` — same gap-detection logic as local-data.js, cached on `gr._displayRange`
- `visualizeGEEDataset(displayName, internalName, year)` — loads a dataset for a year.
  Calls `/api/map` to get the local file URL, fetches GeoTIFF bytes, renders with GeoRasterLayer.
- `visualizeLocalBand(displayName, internalName, bandKey)` — loads a specific depth band.
- `visualizePredictedMap(displayName, internalName, year, modelType)` — calls `/api/predict-map`
  and renders the returned GeoTIFF as a prediction overlay.
- `updatePredLegend(key, min, max, year, modelType)` — updates the floating legend

**GEE_PALETTES:** same colour ramps as PALETTES in local-data.js but scoped to gee-map.

**MODIS_COLOURS:** 18-entry discrete colour array matching IGBP class indices.

### 7.3 Dashboard Controls (`main.js`)

Initialises the Predictions tab UI, manages dataset selection, year slider, charts.

**Key state:**
- `_currentDatasetIsTemporal` (bool) — whether the selected dataset has temporal files
- `datasetMetadata` (array) — list of datasets from `/api/datasets`
- `activeChart` (string) — which chart tab is active ('timeseries', 'correlation', 'forecast')

**Key functions:**
- `initDashboard()` — called on DOMContentLoaded; fetches datasets + model status + backend health
- `loadDataset(ds)` — called when user picks a new dataset:
  - Updates description, year slider range, model type dropdown visibility
  - Calls `visualizeGEEDataset()` to show the base raster
  - Loads charts automatically
- `updateYearSliderForDataset(ds)` — hides the year slider entirely for soil (static) datasets;
  for temporal datasets, clamps max to `max_downloaded_year + 10`
- `_updateModelTypeForDataset(isTemporal)` — hides temporal-only model options for soil datasets
- `inferAndVisualize(year)` — called by the View button for temporal datasets:
  - Calls `/api/infer` to check if real data exists for that year
  - If real data: calls `visualizeGEEDataset()` with that year
  - If ML prediction needed: calls `visualizePredictedMap()` with the selected model
  - If `supported: false`: shows base raster only, displays a notice
- `runForecast()` — calls `/api/analysis/forecast` and renders a Chart.js line chart
- `loadCharts(ds)` — loads whichever chart tab is active for the current dataset
- Chart renderers: `renderTimeSeriesChart()`, `renderCorrelationChart()`, `renderForecastChart()`

**Year slider label:**
For temporal datasets shows: `"Real data: 2000–2024 · ML extrapolation: 2025–2034"`
For soil datasets: slider group is hidden entirely.

---

## 8. Colour Rendering

This was a major bug source. Here is the complete picture:

**Problem:** GeoTIFF files for soil datasets do not declare nodata in their metadata
(`gr.noDataValue` is null). The uint8 sentinel value **255** is used for nodata pixels
but is invisible to the library. When `computeDisplayRange` computed p2–p98, it included
these 255 values, producing a range like [4, 255] instead of [4, 12] for Soil Texture.
All valid pixels (values 1–12) compressed to t ≈ 0.01–0.05 (nearly the same light colour),
and nodata pixels rendered at t=1.0 (saturated dark). Different zoom levels showed different
mixes of tile pixels → apparent colour shifts.

**Fix (gap detection heuristic):**
```javascript
const p90 = vals[Math.floor(vals.length * 0.90)];
const p98 = vals[Math.floor(vals.length * 0.98)];
const hasOutlier = p90 > 0 && p98 > p90 * 5;
// If p98 is 5× larger than p90, there is a sentinel cluster at the high end
return {
  min: p02,
  max: hasOutlier ? p90 : p98,
  noDataThreshold: hasOutlier ? p90 : null,
};
```

In all `pixelValuesToColorFn` callbacks:
```javascript
if (noDataThreshold != null && v >= noDataThreshold) return null; // transparent
```

This is implemented identically in both `gee-map.js` and `local-data.js`.

---

## 9. GEE Integration

Google Earth Engine is optional. The backend tries to initialise it at startup:
```python
ee.Initialize(project="abm-sim-485823")
```

If it fails (no credentials, no internet), the app starts anyway and serves local files.
GEE is only used as a fallback in `/api/map` if no local file exists for the requested dataset+year.

The `download_gee_data.py` script is what originally downloaded all the local files from GEE.
You would run this script to add more years or datasets.

---

## 10. Model Training Details

### What gets trained and when

Training only runs on demand (POST `/api/train` or running `train.py` directly).
The app works without trained models — it will fall back to on-the-fly Ridge fitting for
temporal predictions, and will return the raw raster for spatial predictions.

### Pixel sampling limits

To keep training fast, a maximum number of pixels are sampled per raster:
- `_MAX_PER_BAND = 1000` pixels per depth band (Ridge, MLP depth models)
- `_MAX_CROSS = 2000` pixels per dataset (RF cross-dataset model)
- Temporal series: up to 5000 pixels sampled per year, then mean is taken

### Chronological train/test split

For temporal models, the split is chronological (not random) to simulate real forecasting:
- Last 20% of years = test set (e.g. for CHIRPS 2000–2024, test = ~2020–2024)
- Models are evaluated on test set, then **refit on all data** before saving for production

### Metrics saved

Temporal model test metrics (RMSE, MAE, R²) are saved as `{name}_temporal_metrics.json`
in `saved_models/`. These are returned by `/api/infer` in the `test_metrics` field.

---

## 11. Known Limitations and Design Decisions

### What actually works for temporal prediction
- **CHIRPS precipitation**: 25 years of data (2000–2024) → good temporal models
- **MODIS land cover**: 23 years (2001–2023) → good temporal models
- **All soil datasets**: single 2020 snapshot only → NO temporal prediction. The year slider
  is hidden for these. The View button just shows the static raster.

### Spatial prediction is a scaling approximation
The `temporal_ridge` and `temporal_mlp` spatial prediction methods work by:
1. Predicting what the mean value should be for the target year
2. Scaling all pixels proportionally

This preserves spatial patterns but cannot capture spatially heterogeneous change.
A proper pixel-level temporal model would need per-pixel multi-year data.

### RF spatial model uses only primary bands
The Random Forest influence model uses b0 (surface layer) of all soil datasets as features.
It does not use depth profiles or temporal data. It answers "given these soil properties at
this pixel, what is the expected Soil Texture class?" — useful for influence/importance analysis.

### No tile server
The GeoTIFF files are sent as raw bytes to the browser and decoded client-side by `georaster`.
This works but is bandwidth-heavy for large files. For production, a tile server (like TiTiler
or COG-serving via a CDN) would be more appropriate.

### No user authentication
The app is designed for local use. The backend serves files with path traversal protection
but has no login system.

---

## 12. How to Run the Project

### Prerequisites
```
pip install fastapi uvicorn rasterio numpy scikit-learn scipy joblib earthengine-api
```

### Start the backend
```bash
cd "path/to/AI_for_All_Eternal_Beings"
uvicorn backend.app:app --reload --port 8000
```

### Open the frontend
Open `frontend/index.html` in a browser, or serve it with any static file server:
```bash
cd frontend
python -m http.server 5500
```
Then go to `http://localhost:5500`

### Train the models (optional, first time)
Click the "Train Models" button in the Predictions tab, or run:
```bash
python -m backend.ml_models.train
```

### Download more data (optional)
```bash
python backend/data_downloader/download_gee_data.py
```
Requires a valid GEE account and `earthengine authenticate`.

---

## 13. Adding a New Dataset

To add a completely new dataset (e.g. NDVI, temperature):

1. **Download the data**: Add logic to `download_gee_data.py` to export the new GEE asset
   into `data_downloader/{typology}/year={YYYY}/` or `data_downloader/{typology}/` for static.

2. **Register metadata**: Add an entry to `_DATASET_META` in `utils.py`:
   ```python
   'NDVI': {'display': 'NDVI (index)', 'units': 'index', 'description': '...'}
   ```
   The registry scanner (`_scan_local_files`, `_scan_temporal_files`) will pick up the new
   files automatically as long as the filenames follow the `{Name}.{band}.tif` convention.

3. **Add a colour ramp**: Add an entry to `GEE_PALETTES` in `gee-map.js` and `PALETTES`
   in `local-data.js`.

4. **Train models**: Run `POST /api/train` to generate `.joblib` files for the new dataset.

No changes to `app.py` are needed — the endpoints are generic.

---

## 14. File-by-File Quick Reference

| File | Role |
|------|------|
| `backend/app.py` | All API routes. Import point for all ML modules. |
| `backend/ml_models/utils.py` | Registry builder, path helpers, DATASETS list. |
| `backend/ml_models/data_loader.py` | rasterio wrappers: load raster, load by bbox, depth profiles, point stats. |
| `backend/ml_models/train.py` | Trains Ridge, MLP, RF, Temporal Ridge, Temporal MLP for all datasets. |
| `backend/ml_models/temporal_inference.py` | Predicts a dataset mean for a future year. Fallback chain. |
| `backend/ml_models/spatial_inference.py` | Generates a predicted GeoTIFF for a year. |
| `backend/ml_models/forecast.py` | Linear trend on depth profile, extrapolated beyond 200 cm. |
| `backend/ml_models/time_series.py` | Returns depth profile data points for a dataset. |
| `backend/ml_models/prediction.py` | Spatial mean prediction for a year range + bounding box. |
| `backend/ml_models/change_detection.py` | Pixel change between two depth layers. |
| `backend/ml_models/correlation.py` | Pearson correlation of soil properties vs Soil Texture. |
| `backend/ml_models/precompute_forecasts.py` | Pre-bakes forecast results to `forecasts_cache.json`. |
| `frontend/index.html` | HTML shell, all CSS, script tags. |
| `frontend/local-data.js` | Local Data tab: file browser, multi-layer map, pixel sampling. |
| `frontend/gee-map.js` | Predictions tab map: GeoRasterLayer rendering, legend, colour ramps. |
| `frontend/main.js` | Predictions tab: dataset selector, year slider, charts, model controls. |

---

## 15. Suggested Next Steps

These are natural extensions that fit cleanly into the existing architecture:

- **More datasets**: Add NDVI, LST (Land Surface Temperature), soil moisture from GEE.
  The registry auto-discovers files, only colour ramps need adding.

- **Pixel-level temporal models**: Instead of scaling the whole raster by a ratio, train
  a model per pixel location using its multi-year series. Requires multi-year soil data.

- **Erosion risk composite**: Combine Organic Carbon + Sand/Clay + Precipitation into a
  derived erosion risk index raster. Could be computed on the fly in spatial_inference.py.

- **Region drawing**: Let users draw a polygon on the map and run analysis on just that region
  using rasterio masking. The bbox infrastructure already exists in data_loader.py.

- **Time-lapse animation**: Loop through downloaded years and animate the map layer.

- **Tile server**: Replace raw GeoTIFF serving with Cloud-Optimised GeoTIFF (COG) + TiTiler
  for faster, zoom-level-aware tile delivery.

- **Model comparison view**: Show the test metrics (RMSE, R², MAE) side by side for
  Ridge vs MLP in the UI so users can see which model is more accurate for each dataset.
