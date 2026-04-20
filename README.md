# OpenLandMap Analytics Platform
### Soil Science + Machine Learning + Climate Simulation for the Barcelona / Spain Region

A full-stack geospatial analytics platform built around real satellite-derived soil and climate data. The project has two major systems running on the same backend:

1. **Analytics Platform** — interactive map dashboard to explore, visualize, and ML-predict 6 soil properties across Spain, with depth profiles, trend forecasting, and cross-dataset correlation.
2. **Soil Futures Exhibition System** — a physics-based soil simulation engine where users choose a land management philosophy and watch decades of soil change unfold under four IPCC climate scenarios.

No database. No cloud compute required for ML. All data lives as local GeoTIFF files on disk. All models are `.joblib` files.

---

## The Exhibition: Beneath the Surface

This repository is the technical backbone of **Beneath the Surface** — a public installation built for the UIA Barcelona World Capital of Architecture exhibition at IAAC MaAI 2026.

The installation is called **The Three Columns**. Three tall transparent acrylic cylinders stand side by side. Each contains the same six soil depth layers as coloured physical strata. Left column: 1950, historical baseline. Centre column: 2025, filled with real OpenLandMap GeoTIFF data. Right column: 2075, empty and waiting — filled live by the AI the moment a visitor presses a scenario button.

The organic carbon layer at the top of each column shrinks left to right. Visitors read the trajectory — past, present, future — before reading a single word. When they press SSP5 (worst case climate), the right column refills thinner. When they press SSP1 (best case), it fills fuller. The AI's output is visible in matter, at human scale, in real time.

**How this codebase powers the installation:**

| Backend module | What it does in the exhibition |
|---------------|-------------------------------|
| `backend/soil_model/engine.py` | Runs the 50-year RothC simulation when a visitor presses a scenario button |
| `backend/climate_scenarios/ssp_data.py` | Provides IPCC AR6 temperature/precip/CO₂ trajectories for all 4 SSP buttons |
| `backend/soil_model/philosophies.py` | Defines land management parameters that modify the simulation |
| `backend/soil_init/extract_conditions.py` | Extracts real initial soil conditions from Barcelona-region GeoTIFFs to start the simulation |
| `backend/exhibition_api.py` | FastAPI router that the kiosk calls — receives scenario choice, runs simulation, returns column fill values |
| `backend/ml_models/` | Random Forest (93% accuracy) + Ridge/MLP models that predict soil properties |
| `backend/data_downloader/soil/` | The 36 GeoTIFFs that populate Column 2 (today's real data) |

The Arduino controlling Column 3's physical fill level receives its target height from `POST /api/exhibition/simulate` via serial connection to the laptop running this backend.

→ See [EXHIBITION_SUBMISSION.md](EXHIBITION_SUBMISSION.md) for the full spatial proposal, visitor interaction scenario, and budget.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Project Structure](#2-project-structure)
3. [Quick Start](#3-quick-start)
4. [The Data](#4-the-data)
5. [The Backend API](#5-the-backend-api)
6. [The ML Models (Analytics Platform)](#6-the-ml-models-analytics-platform)
7. [The Exhibition System](#7-the-exhibition-system)
8. [The Frontend](#8-the-frontend)
9. [Colour Rendering & Known Rendering Quirks](#9-colour-rendering--known-rendering-quirks)
10. [GEE Integration](#10-gee-integration)
11. [Adding a New Dataset](#11-adding-a-new-dataset)
12. [Downloading More Data](#12-downloading-more-data)
13. [API Reference](#13-api-reference)
14. [Technical Stack](#14-technical-stack)
15. [Troubleshooting](#15-troubleshooting)
16. [Suggested Next Steps](#16-suggested-next-steps)

---

## 1. What This Project Is

The project was built for an AI-for-All student exhibition focused on soil science, land use, and climate change — specifically centred on the **Barcelona / Catalonia / Spain** region.

There are two things a user can do:

**Analytics Platform (Predictions tab + Local Data tab):**
- Load any of 6 OpenLandMap soil datasets for Spain and display them on an interactive Leaflet map
- Browse raw GeoTIFF files grouped by type (soil, climate, land cover) and layer them on the map
- Click any point in Spain to sample real pixel statistics (mean, min, max, std) from a 5×5 pixel window
- View depth profiles showing how a soil property changes from 0 cm to 200 cm underground
- View cross-dataset correlation charts (how does organic carbon relate to clay? precipitation to soil texture?)
- View linear trend extrapolation: given the 6 known depth points, what does the trend predict beyond 200 cm?
- For temporal datasets (CHIRPS precipitation, MODIS land cover): move a year slider to any year from 2000 to 2034, and either see real downloaded data or get an ML-predicted mean value + confidence interval
- Generate a full predicted spatial GeoTIFF raster for any year using trained ML models

**Exhibition System (Soil Futures):**
- Choose one of 5 land management philosophies (rewilding, traditional farming, agroforestry, intensive regen agriculture, precision sustainable)
- Choose one of 4 IPCC AR6 SSP climate scenarios (SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5)
- Run a 10–100 year forward simulation on a 20×20 spatial grid anchored to real initial soil conditions from the Barcelona region GeoTIFFs
- Watch soil organic carbon, erosion, biodiversity index, and water balance evolve over time with Monte Carlo ensemble uncertainty bands
- Receive structured educational "learn" content explaining the science behind the philosophy

---

## 2. Project Structure

```
AI_for_All_Eternal_Beings/
│
├── backend/
│   ├── app.py                          # FastAPI entry point — all API routes
│   ├── exhibition_api.py               # FastAPI router for /api/exhibition/* endpoints
│   ├── requirements.txt                # All Python dependencies
│   │
│   ├── data_downloader/                # All local GeoTIFF data lives here
│   │   ├── download_gee_data.py        # Script: pulls GeoTIFFs from Google Earth Engine
│   │   ├── soil/                       # 36 static GeoTIFFs (6 datasets × 6 depth bands)
│   │   │   ├── Organic_Carbon.b0.tif
│   │   │   ├── Organic_Carbon.b10.tif
│   │   │   └── ...
│   │   ├── climate/                    # CHIRPS precipitation, year-by-year
│   │   │   ├── year=2000/
│   │   │   │   └── Precipitation_CHIRPS.precipitation.tif
│   │   │   └── year=2001/ ... year=2024/
│   │   └── land_cover/                 # MODIS land cover, year-by-year
│   │       ├── year=2001/
│   │       │   └── MODIS_Land_Cover.LC_Type1.tif
│   │       └── year=2002/ ... year=2023/
│   │
│   ├── ml_models/
│   │   ├── utils.py                    # Dataset registry, path helpers, DATASETS list
│   │   ├── data_loader.py              # rasterio wrappers: load rasters, sample pixels, depth profiles
│   │   ├── train.py                    # Training entry point: Ridge, MLP, RF, Temporal models
│   │   ├── train_rf.py                 # Standalone RF soil texture classifier script
│   │   ├── temporal_inference.py       # Predict dataset mean value for an unseen year
│   │   ├── spatial_inference.py        # Generate a predicted GeoTIFF raster for a year
│   │   ├── forecast.py                 # Depth-profile linear trend + extrapolation beyond 200 cm
│   │   ├── soil_forecast.py            # Soil-specific forecast helpers
│   │   ├── time_series.py              # Returns depth profile data points for a dataset
│   │   ├── prediction.py               # Spatial mean prediction for a bbox + year range
│   │   ├── change_detection.py         # Pixel change between two depth layers
│   │   ├── correlation.py              # Pearson r between soil properties
│   │   ├── precompute_forecasts.py     # Pre-bakes forecast results to JSON cache
│   │   └── saved_models/               # All trained .joblib files live here
│   │       ├── Organic_Carbon_ridge.joblib
│   │       ├── Organic_Carbon_mlp.joblib
│   │       ├── Organic_Carbon_rf.joblib
│   │       ├── Precipitation_CHIRPS_temporal_ridge.joblib
│   │       ├── Precipitation_CHIRPS_temporal_mlp.joblib
│   │       └── ... (3 models × 6 soil datasets + 2 temporal models × 2 temporal datasets)
│   │
│   ├── soil_model/                     # Exhibition simulation engine
│   │   ├── engine.py                   # Main simulation loop: couples all sub-modules
│   │   ├── carbon.py                   # RothC soil carbon model (DPM/RPM/BIO/HUM/IOM pools)
│   │   ├── water.py                    # Annual water balance: PET, AET, soil moisture
│   │   ├── vegetation.py               # Vegetation growth: Chapman-Richards + species params
│   │   ├── biology.py                  # Soil biology: BII, mycorrhizal, earthworm, aggregate stability
│   │   ├── erosion.py                  # RUSLE erosion + D8 sediment routing (20×20 grid)
│   │   ├── disturbances.py             # Stochastic events: drought, wildfire, pest outbreak
│   │   └── philosophies.py             # 5 land management philosophies with all parameters
│   │
│   ├── climate_scenarios/
│   │   └── ssp_data.py                 # IPCC AR6 SSP1-2.6/2-4.5/3-7.0/5-8.5 projections
│   │                                   # Barcelona-calibrated (T, precip, CO2, extreme events)
│   │
│   ├── soil_init/
│   │   └── extract_conditions.py       # Extracts real 20×20 initial conditions from GeoTIFFs
│   │
│   └── tests/                          # Backend test suite
│
├── frontend/
│   ├── index.html                      # Single-page app shell + all CSS
│   ├── local-data.js                   # Local Data tab: file browser, multi-layer map, pixel sampling
│   ├── gee-map.js                      # Predictions tab map: GeoRasterLayer rendering, legend
│   └── main.js                         # Predictions tab: dataset selector, year slider, charts
│
├── gee_master_application.js           # Self-contained Google Earth Engine Code Editor script
├── PLATFORM_ARCHITECTURE.md           # Architecture overview doc
├── ML_IMPLEMENTATION_GUIDE.md         # ML implementation notes
├── PROJECT_REPORT.md                   # Full technical handover document
└── README.md                           # This file
```

---

## 3. Quick Start

### Prerequisites

```bash
pip install -r backend/requirements.txt
```

Key packages: `fastapi`, `uvicorn`, `rasterio`, `numpy`, `scipy`, `scikit-learn`, `joblib`, `xgboost`, `earthengine-api`

### Start the backend

Run from the project root:

```bash
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

The API starts cleanly even without GEE credentials. All ML and analytics endpoints use local rasters.

### Open the frontend

Open `frontend/index.html` directly in any modern browser — no build step, no bundler, no server needed.

Or serve it for a clean URL:

```bash
cd frontend
python -m http.server 5500
# → http://localhost:5500
```

### Train the ML models (first time, optional)

The app works without trained models — it falls back to on-the-fly fitting. For best results:

```bash
# Via API (runs in background thread)
curl -X POST http://127.0.0.1:8000/api/train

# Or directly
python -m backend.ml_models.train
```

Poll training status at `GET /api/train/status`.

---

## 4. The Data

All data covers **Spain + Canary + Balearic Islands** at approximately **2.5 km resolution**, originally downloaded from Google Earth Engine. There are three categories.

### 4.1 Soil Datasets (Static — single 2020 composite snapshot)

From **OpenLandMap / SoilGrids**. Each dataset has **6 depth bands**:

| Band key | Depth range |
|----------|-------------|
| `b0`     | 0–5 cm      |
| `b10`    | 10–30 cm    |
| `b30`    | 30–60 cm    |
| `b60`    | 60–100 cm   |
| `b100`   | 100–200 cm  |
| `b200`   | 200 cm+     |

| Dataset (internal name) | Display name       | Units  | GEE Asset ID |
|-------------------------|--------------------|--------|-------------|
| `Organic_Carbon`        | Organic Carbon     | g/kg   | `SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` |
| `Soil_pH`               | Soil pH            | pH     | `SOL_PH-H2O_USDA-4C1A2A_M/v02` |
| `Bulk_Density`          | Bulk Density       | t/m³   | `SOL_BULK-DENSITY_USDA-6A1C_M/v02` |
| `Sand_Content`          | Sand Content       | %      | `SOL_SAND-FRACTION_USDA-3A1A1A_M/v02` |
| `Clay_Content`          | Clay Content       | %      | `SOL_CLAY-FRACTION_USDA-3A1A1A_M/v02` |
| `Soil_Texture`          | Soil Texture Class | class  | `SOL_TEXTURE-CLASS_USDA-TT_M/v02` |

File naming convention: `{InternalName}.{band}.tif` — e.g. `Organic_Carbon.b0.tif`

**Important**: Soil datasets are static (single 2020 snapshot). There is no real temporal dimension. The "time series" analysis shows a **depth profile** (vertical variation 0→200 cm), which is the real meaningful dimension. The year slider is hidden for soil datasets in the UI.

**Soil Texture** is `uint8` with an undeclared nodata sentinel value of `255`. This caused a major colour rendering bug (see [Section 9](#9-colour-rendering--known-rendering-quirks)).

### 4.2 Temporal Datasets (Year-by-year files)

| Dataset (internal name)  | Coverage    | Band         | Units   | Source |
|--------------------------|-------------|--------------|---------|--------|
| `Precipitation_CHIRPS`   | 2000–2024   | precipitation| mm/yr   | CHIRPS v2.0 |
| `MODIS_Land_Cover`       | 2001–2023   | LC_Type1     | class   | MODIS MCD12Q1 IGBP |

File path pattern: `data_downloader/{typology}/year={YYYY}/{DatasetName}.{band}.tif`

**MODIS IGBP classes (17 + unclassified):** Water, Evergreen Needleleaf Forest, Evergreen Broadleaf Forest, Deciduous Needleleaf Forest, Deciduous Broadleaf Forest, Mixed Forest, Closed Shrubland, Open Shrubland, Woody Savanna, Savanna, Grassland, Permanent Wetland, Cropland, Urban/Built-up, Cropland/Veg Mosaic, Snow/Ice, Barren, Unclassified.

### 4.3 Dataset Registry (how the backend finds files)

`backend/ml_models/utils.py` scans `data_downloader/` at startup and builds two in-memory registries — no database or config file involved.

**`LOCAL_REGISTRY`** — depth-banded static files, keyed by dataset name → band → file path.

**`TEMPORAL_REGISTRY`** — year-indexed files, keyed by dataset name → year → band → file path.

**`DATASETS`** — flat ordered list exposed by `/api/datasets`. Each entry has `is_temporal` (bool) and `available_years` list.

Key helper functions in `utils.py`:
- `find_dataset(display_name)` — look up a dataset by its UI display name
- `primary_band(ds)` — returns the best single-band path (`b0` for soil, first band for others)
- `temporal_primary_band(name, year)` — returns the path for a specific year
- `available_years(name)` — sorted list of years with real downloaded data

---

## 5. The Backend API

Base URL: `http://127.0.0.1:8000`

### Core Endpoints

| Method | Route | What it does |
|--------|-------|--------------|
| `GET` | `/api/status` | Health check. Returns `gee_available` flag |
| `GET` | `/api/datasets` | Full list of all datasets with metadata, `is_temporal`, `available_years` |
| `GET` | `/api/years` | Available years per temporal dataset |
| `GET` | `/api/local-datasets` | All GeoTIFF files grouped by typology — used by the Local Data tab file browser |
| `GET` | `/api/files/{path}` | Serve any GeoTIFF file under `data_downloader/` as raw bytes (path-traversal-protected) |
| `GET` | `/api/map` | Get file URL for a dataset + optional year. Falls back to GEE if no local file exists |
| `GET` | `/api/infer` | For temporal datasets: returns real data if downloaded, or ML prediction if not |
| `GET` | `/api/statistics` | Click-to-sample: pixel stats (mean/min/max/std) at a lat/lon from a 5×5 window |
| `GET` | `/api/predict-map` | Generate a full predicted GeoTIFF raster for a target year |
| `GET` | `/api/model-status` | Lists which `.joblib` files exist in `saved_models/` for each dataset |
| `POST` | `/api/train` | Kick off model training in a background thread |
| `GET` | `/api/train/status` | Poll training progress (returns `running`, `done`, or `error` with log) |

### Analysis Endpoints

| Route | What it returns |
|-------|-----------------|
| `/api/analysis/time-series` | Depth profile: value at each of 6 soil depths (0, 10, 30, 60, 100, 200 cm) |
| `/api/analysis/prediction` | Spatial mean prediction for a year range + bounding box |
| `/api/analysis/change-detection` | Pixel-level change between two depth layers (surface vs deep) |
| `/api/analysis/correlation` | Pearson correlation of each soil property vs all others |
| `/api/analysis/forecast` | Depth-profile linear trend extrapolated well beyond 200 cm with 95% CI |
| `/api/forecasts/cached` | Pre-computed forecast from `forecasts_cache.json` (fast) |

### Exhibition Endpoints (under `/api/exhibition/`)

| Route | What it returns |
|-------|-----------------|
| `/api/exhibition/status` | Health check — confirms all exhibition modules import correctly |
| `/api/exhibition/philosophies` | List of all 5 land management philosophies with display info and educational content |
| `/api/exhibition/climate-scenarios` | List of 4 SSP scenarios with descriptions |
| `/api/exhibition/initial-conditions` | Real 20×20 grid initial soil conditions from local GeoTIFFs at a given lat/lon |
| `POST /api/exhibition/simulate` | Run full multi-year simulation — returns time series for SOC, erosion, BII, water, carbon stocks with ensemble uncertainty |

### `/api/infer` Behaviour

This is the core endpoint for the year slider in the Predictions tab.

1. If the dataset has no temporal files at all (all 6 soil datasets) → returns `{supported: false}`
2. If the requested year has a real downloaded file → returns `{has_data: true, value: ...}`
3. If the year is outside the downloaded range → calls `temporal_inference.predict_year()` and returns:

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

Confidence bounds are approximated as `±1.645 × std(training residuals)` (90% CI).

### `/api/predict-map` Behaviour

Returns raw GeoTIFF bytes (float32) for a predicted spatial raster. Accepts `model_type`:

- `rf` — uses the Random Forest cross-dataset influence model
- `temporal_ridge` — uses the Temporal Ridge model to proportionally scale the existing raster
- `temporal_mlp` — uses the Temporal MLP model to proportionally scale the existing raster
- `ridge` and `mlp` are rejected with HTTP 400 (these are depth-band models, not temporal)

---

## 6. The ML Models (Analytics Platform)

All models are trained by `backend/ml_models/train.py` and saved to `backend/ml_models/saved_models/`.

### 6.1 Per-dataset Static Models (trained for all 6 soil datasets)

**Ridge — depth-band model** (`{name}_ridge.joblib`)
- **Input**: depth in cm (0, 10, 30, 60, 100, 200)
- **Output**: soil property value at that depth
- **Pipeline**: `PolynomialFeatures(degree=2) → Ridge(alpha=10)`
- **Training data**: up to 1,000 pixel samples per depth band
- **Purpose**: models how a soil property changes with depth. Used for the Forecast tab.

**MLP — depth-band model** (`{name}_mlp.joblib`)
- Same inputs/outputs as Ridge, but non-linear
- **Pipeline**: `StandardScaler → MLPRegressor(hidden=(64,32), ReLU, early_stopping=True)`

**Random Forest — cross-dataset influence model** (`{name}_rf.joblib`)
- **Input**: surface-layer (`b0`) pixel values of ALL OTHER datasets at the same location
- **Output**: target dataset value at that pixel
- **Pipeline**: `StandardScaler → RandomForestRegressor(n_estimators=100, max_depth=8)`
- **Purpose**: quantifies how much each other soil property influences the target. Powers the `/api/predict-map?model_type=rf` endpoint.
- **Training data**: up to 2,000 co-located pixel samples from all datasets

### 6.2 Temporal Models (trained for CHIRPS and MODIS only)

Only datasets with 6+ years of data are eligible. CHIRPS has 25 years (2000–2024), MODIS has 23 years (2001–2023).

**Temporal Ridge** (`{name}_temporal_ridge.joblib`)
- **Input**: year (e.g. 2022)
- **Output**: spatial mean value for that year
- **Pipeline**: `PolynomialFeatures(degree=2) → Ridge(alpha=1)`
- **Train/test split**: chronological 80/20 (last 20% of years = test set, simulates real forecasting)
- **Refit**: on all data after evaluation before saving to production

**Temporal MLP** (`{name}_temporal_mlp.joblib`)
- Same as Temporal Ridge but neural network
- **Pipeline**: `StandardScaler → MLPRegressor(hidden=(64,32), ReLU, early_stopping=True)`

**Best model** (`{name}_temporal_best.joblib`)
- Whichever of Ridge/MLP had lower test RMSE is saved again under this name
- `temporal_inference.py` tries this file first

**Metrics** (`{name}_temporal_metrics.json`)
- Test RMSE, MAE, R² saved alongside the models
- Returned by `/api/infer` in the `test_metrics` field so the UI can show model quality

### 6.3 Temporal Inference — Fallback Chain

`temporal_inference.predict_year(dataset_name, target_year)`:

1. Load `{name}_temporal_best.joblib` ← tries first
2. Load `{name}_temporal_mlp.joblib`
3. Load `{name}_temporal_ridge.joblib`
4. Fit a Ridge polynomial on-the-fly from the TEMPORAL_REGISTRY data (no saved model needed)
5. If none work → return `{supported: false}`

### 6.4 Spatial Inference — Predicted GeoTIFF

`spatial_inference.predict_map_raster(dataset_name, year, model_type)`:

**RF strategy:** loads primary-band rasters for all other datasets, stacks as feature columns `[h×w, n_features]`, runs the RF model pixel-by-pixel. Falls back to returning the raw raster if RF fails.

**Temporal scaling strategy:** loads the temporal model, predicts mean for `target_year`, computes `scale = predicted_mean / actual_mean`, multiplies every valid pixel by `scale`. This preserves spatial patterns but uniformly shifts them — it is a simplification that does not capture spatially heterogeneous change.

### 6.5 Pixel Sampling Limits

| Context | Limit | Why |
|---------|-------|-----|
| Ridge/MLP depth models | 1,000 px per depth band | Keep training fast |
| RF cross-dataset model | 2,000 px per dataset | Fast + enough for 100-estimator RF |
| Temporal models | 5,000 px per year, then mean | Represent the whole raster fairly |

### 6.6 Pre-trained RF Soil Texture Classifier

`backend/ml_models/train_rf.py` trains a dedicated classifier for the Soil Texture Class dataset:

- **Features**: Organic Carbon, Soil pH, Bulk Density, Sand %, Clay % (all surface b0)
- **Labels**: Soil Texture Class (independent raster — no label leakage)
- **Training samples**: 215,660 valid pixels across Spain
- **Test accuracy**: 93.03%
- **Feature importance**: Clay 49%, Sand 40%, Organic Carbon 4%, pH 3%, Bulk Density 3%
- **Classes present in Spain**: Clay, Clay Loam, Sandy Clay Loam, Loam, Silt Loam, Silt, Loamy Sand, Sand

---

## 7. The Exhibition System

The Exhibition System is a mechanistic, process-based soil simulation for an interactive museum/exhibition context. Users configure a simulation and get back 50–100 years of projected soil change.

### 7.1 The 5 Land Management Philosophies

Defined in `backend/soil_model/philosophies.py`. Each philosophy maps to concrete parameters that drive every simulation sub-module.

| Philosophy | Icon | Core approach |
|------------|------|--------------|
| **Let Nature Recover** | 🌿 | Zero intervention. Natural succession: bare soil → maquis → oak woodland. Self-sustaining but slow. |
| **Traditional Farming** | 🫛 | Dehesa-style agroforestry: sparse holm oak + rotational livestock grazing + compost. Iberian Peninsula's 2,000-year land use. |
| **Agroforestry** | 🌳 | Intentional mixed tree planting with cover crops and reduced tillage. Balances food production with soil building. |
| **Intensive Regenerative** | ♻️ | High-density cover cropping, biochar amendment, no-till, compost. Maximum soil intervention for fast carbon sequestration. |
| **Precision Sustainable** | 🔬 | Data-driven, targeted inputs. Optimised irrigation, precision fertilisation, reduced inputs. |

Each philosophy specifies: species, planting density, initial vegetation cover, soil amendments (biochar, compost, fertilizer N), tillage flag, grazing flag, grazing intensity, managed fire flag, RUSLE P and C factors, and expected 50-year outcomes for SOC, erosion, biodiversity, and carbon.

### 7.2 The 4 Climate Scenarios

Defined in `backend/climate_scenarios/ssp_data.py`. Based on **IPCC AR6 WG1** projections for the **Mediterranean / Catalonia region**, calibrated to a Barcelona baseline (T_mean = 16.2°C, precip = 580 mm/yr from CHIRPS 2000–2024).

| Scenario | Warming by 2100 (above 2020) | Precip change by 2100 | CO₂ by 2100 |
|----------|-----------------------------|-----------------------|-------------|
| **SSP1-2.6** | +1.3°C | −5% | ~400 ppm |
| **SSP2-4.5** | +2.7°C | −20% | ~600 ppm |
| **SSP3-7.0** | +3.6°C | −30% | ~860 ppm |
| **SSP5-8.5** | +5.0°C | −35% | ~1,100 ppm |

The data module interpolates annually between IPCC AR6 benchmark years (2020, 2025, 2030, 2040, 2050, 2060, 2075, 2100) using `scipy.interpolate.interp1d`. It also models:
- Summer precipitation (Mediterranean amplification — declines faster than annual)
- Extreme precipitation events (days with >20 mm/day)
- CO₂ fertilization effect on vegetation NPP

### 7.3 The Simulation Engine

`backend/soil_model/engine.py` runs a **20×20 spatial grid × 3 depth layers × N ensemble members** simulation.

All array operations are fully vectorized with numpy — the only loop is over years (outer) and depth layers (3 iterations). Target performance: <3 seconds for a 100-year run with 10 ensemble members × 400 cells.

#### Sub-modules

**Carbon — RothC model** (`carbon.py`)

Implements the **Rothamsted Carbon (RothC) model** with 5 pool structure:
- **DPM** (Decomposable Plant Material) — labile fresh organic matter
- **RPM** (Resistant Plant Material) — structural fresh organic matter
- **BIO** (Microbial Biomass) — living soil microorganisms
- **HUM** (Humified OM) — stable, recalcitrant humus
- **IOM** (Inert Organic Matter) — permanent fraction (no decomposition)

Turnover rates are modified by:
- Temperature (Q₁₀ function with IPCC AR6 warming trajectory)
- Soil moisture (water deficit suppresses decomposition)
- Clay content (higher clay = slower BIO and HUM turnover)
- CO₂ fertilization of plant inputs (CO₂ increases NPP → more DPM/RPM inputs)

**Water balance** (`water.py`)

Annual water balance using **Hargreaves PET** (calibrated for Barcelona latitude 41.4°N):
- Potential evapotranspiration from temperature and extraterrestrial radiation
- Actual evapotranspiration limited by soil moisture and vegetation cover
- Soil moisture deficit drives drought stress
- Runoff generation feeds erosion R-factor

**Vegetation** (`vegetation.py`)

Vegetation biomass growth using **Chapman-Richards growth equation**: `B = Bmax × (1 − exp(−k×age))^p`

Per-species parameters (maquis, agroforestry/dehesa, annual crops, cover crops) define:
- `Bmax`: maximum standing biomass
- `k`: growth rate constant
- `p`: shape parameter
- Litter input rates (DPM/RPM ratio)
- Root exudate contribution to SOC

Disturbance events (fire, drought, pest) reset stand age and biomass. Post-disturbance recovery uses the same growth equation.

**Biology** (`biology.py`)

Tracks soil biological state:
- **BII** (Biodiversity Intactness Index) — aggregate biodiversity measure
- **Mycorrhizal network density** — fungal network coverage fraction
- **Earthworm biomass index** — macrofauna abundance proxy
- **Aggregate stability** — soil structural stability (affects erosion K-factor)

Biology responds to SOC, tillage disturbance, grazing intensity, amendment additions, and vegetation cover.

**Erosion — RUSLE model** (`erosion.py`)

Implements **RUSLE** (Revised Universal Soil Loss Equation): `A = R × K × LS × C × P` (t/ha/yr)

- **R** (rainfall erosivity): derived from precipitation and extreme event frequency, scaled by scenario
- **K** (soil erodibility): derived from sand/clay/OC from GeoTIFFs, modified by aggregate stability
- **LS** (slope-length factor): computed from a synthetic 20×20 DEM for Barcelona terrain (Collserola hills, Garraf massif, Llobregat plain)
- **C** (cover factor): evolves with vegetation cover, mulch, and philosophy-specific practices
- **P** (support practice factor): philosophy-specific (contour farming, grazing management, etc.)

**D8 sediment routing** routes eroded material downslope across the 20×20 grid using D8 flow direction encoding.

**Disturbances** (`disturbances.py`)

Stochastic events sampled each year based on base probabilities modified by climate scenario:
- **Drought**: increases with temperature/precip change, triggers vegetation mortality and SOC release
- **Wildfire**: Mediterranean fire regime, accelerated under dry scenarios, resets vegetation
- **Pest/disease outbreak**: reduces vegetation productivity and root turnover

### 7.4 Initial Conditions

`backend/soil_init/extract_conditions.py` samples the real downloaded GeoTIFFs around a user-provided lat/lon (defaulting to Barcelona, 41.40°N, 2.15°E) and extracts a 20×20 grid of:
- Organic Carbon (g/kg) at surface
- Clay Content (%)
- Sand Content (%)
- Bulk Density (t/m³)
- Soil pH

These real values initialise the RothC carbon pools, the RUSLE K-factor, and the water balance at simulation start.

### 7.5 Simulation Output

`POST /api/exhibition/simulate` returns a structured JSON with time series (one entry per year) containing:

```json
{
  "years": [1, 2, 3, ...],
  "soc_mean": [...],        "soc_p10": [...],       "soc_p90": [...],
  "erosion_mean": [...],    "erosion_p10": [...],    "erosion_p90": [...],
  "bii_mean": [...],        "bii_p10": [...],        "bii_p90": [...],
  "water_deficit_mean": [...],
  "carbon_stock_mean": [...],
  "philosophy": { ...full philosophy metadata... },
  "climate_scenario": { ...SSP display info... },
  "initial_conditions": { ...real pixel stats... },
  "learn": { "title": "...", "body": "...", "pros": [...], "cons": [...] }
}
```

Ensemble uncertainty bands (`p10`/`p90`) come from running `n_ensemble` parallel Monte Carlo members, each with independently sampled stochastic disturbances.

---

## 8. The Frontend

Three JavaScript files loaded in order in `index.html`. No build step, no framework, no bundler.

### 8.1 `local-data.js` — Local Data Tab

**What it does:**
- Calls `/api/local-datasets` to get all available GeoTIFF files
- Renders a collapsible file tree grouped by typology (soil / climate / land_cover)
- Each file item, when clicked, fetches the GeoTIFF from `/api/files/{path}` as raw bytes and renders it on the Leaflet map using `GeoRasterLayer`
- Multiple layers can be stacked simultaneously with individual opacity sliders
- Clicking the map samples the pixel value using `sampleGeoRaster()`

**Key functions:**
- `computeDisplayRange(gr)` — computes p2–p90/p98 percentile stretch for colour scaling. Includes **gap-detection heuristic** for undeclared nodata sentinel values (see Section 9). Caches result on `gr._displayRange`.
- `makePixelFn(dataset, typology, georaster)` — returns the `pixelValuesToColorFn` callback for GeoRasterLayer. Handles MODIS discrete colours separately from continuous ramps.
- `toggleLayer(fileInfo)` — loads or unloads a GeoTIFF layer
- `sampleGeoRaster(gr, lat, lng)` — manual pixel lookup at a coordinate

**Colour palettes:** each dataset has a 5-stop hex colour ramp defined in the `PALETTES` object. MODIS uses a discrete 18-entry array matching IGBP class indices.

### 8.2 `gee-map.js` — Predictions Tab Map

Initialises a second Leaflet map (`geeMap`) for the Predictions tab.

**Key functions:**
- `visualizeGEEDataset(displayName, internalName, year)` — loads a dataset for a year. Calls `/api/map` → fetches GeoTIFF bytes → renders with GeoRasterLayer.
- `visualizeLocalBand(displayName, internalName, bandKey)` — loads a specific depth band.
- `visualizePredictedMap(displayName, internalName, year, modelType)` — calls `/api/predict-map` and renders the returned GeoTIFF as a prediction overlay.
- `updatePredLegend(key, min, max, year, modelType)` — updates the floating legend with dataset name, year, and value range.
- `computeDisplayRange(gr)` — identical gap-detection logic as in `local-data.js`, cached on `gr._displayRange`.

### 8.3 `main.js` — Predictions Tab Controls & Charts

Manages the dataset selector, year slider, model type dropdown, and three chart tabs.

**Key state:**
- `_currentDatasetIsTemporal` — whether the selected dataset has temporal files
- `datasetMetadata` — list of datasets from `/api/datasets`
- `activeChart` — which chart tab is active (`timeseries`, `correlation`, `forecast`)

**Key functions:**
- `initDashboard()` — called on `DOMContentLoaded`. Fetches datasets + model status + backend health.
- `loadDataset(ds)` — called when user picks a new dataset. Updates description, year slider range, model type dropdown visibility, loads the base raster, and loads charts automatically.
- `updateYearSliderForDataset(ds)` — hides the year slider entirely for soil datasets. For temporal datasets, clamps max to `max_downloaded_year + 10` (e.g. 2034 for CHIRPS).
- `inferAndVisualize(year)` — called by the View button for temporal datasets:
  - Calls `/api/infer` to check if real data exists for that year
  - If real data → calls `visualizeGEEDataset()` with that year
  - If ML prediction needed → calls `visualizePredictedMap()` with the selected model
  - If `supported: false` → shows base raster, displays a "not supported" notice
- `loadCharts(ds)` — loads whichever chart tab is active for the current dataset
- `renderTimeSeriesChart()` — renders depth profile as Chart.js line chart
- `renderCorrelationChart()` — renders Pearson correlation as Chart.js bar chart
- `renderForecastChart()` — renders depth-trend extrapolation as Chart.js line chart with 95% CI shading

**Year slider label:**
- Temporal datasets: `"Real data: 2000–2024 · ML extrapolation: 2025–2034"`
- Soil datasets: slider group hidden entirely

---

## 9. Colour Rendering & Known Rendering Quirks

### The Sentinel Value Problem

GeoTIFF files for soil datasets do not declare `nodata` in their GeoTIFF metadata (`gr.noDataValue` is `null`). The uint8 sentinel value **255** is used for nodata pixels but is invisible to the `georaster` library.

When `computeDisplayRange` computed p2–p98, it included the 255 values, producing a range like `[4, 255]` instead of `[4, 12]` for Soil Texture. All valid pixels (1–12) compressed to `t ≈ 0.01–0.05` (nearly the same colour), while nodata pixels rendered at `t=1.0` (saturated). Different zoom levels showed different mixes → apparent colour shifts with zoom.

### The Fix: Gap-Detection Heuristic

```javascript
const p90 = vals[Math.floor(vals.length * 0.90)];
const p98 = vals[Math.floor(vals.length * 0.98)];
const hasOutlier = p90 > 0 && p98 > p90 * 5;
// If p98 is 5× larger than p90 → there is a sentinel cluster at the high end
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

This is implemented identically in both `gee-map.js` and `local-data.js`. The `_displayRange` result is cached on the georaster object to avoid re-scanning all pixels every tile render.

---

## 10. GEE Integration

Google Earth Engine is **optional**. The backend tries to initialise at startup:

```python
ee.Initialize(project="abm-sim-485823")
```

If it fails (no credentials, no internet), the app starts normally and serves all local files. GEE is only used as a fallback in `/api/map` if no local file exists for the requested dataset + year.

### GEE Code Editor Script

`gee_master_application.js` is a **self-contained** Google Earth Engine Code Editor script. It does not depend on the Python backend — it queries OpenLandMap assets directly from GEE.

```
1. Go to https://code.earthengine.google.com
2. New script → paste gee_master_application.js → Run
3. Interactive UI appears with dataset selector, map, and charts
```

To authenticate for the Python backend:
```bash
earthengine authenticate
```

---

## 11. Adding a New Dataset

To add a completely new dataset (e.g. NDVI, land surface temperature):

1. **Download the data.** Add logic to `download_gee_data.py` to export the new GEE asset into `data_downloader/{typology}/year={YYYY}/` (temporal) or `data_downloader/{typology}/` (static). Follow the `{DatasetName}.{band}.tif` filename convention.

2. **Register metadata.** Add an entry to `_DATASET_META` in `utils.py`:
   ```python
   'NDVI': {'display': 'NDVI (index)', 'units': 'index', 'description': '...'}
   ```
   The registry scanners (`_scan_local_files`, `_scan_temporal_files`) will auto-discover the new files.

3. **Add a colour ramp.** Add an entry to `GEE_PALETTES` in `gee-map.js` and `PALETTES` in `local-data.js`.

4. **Train models.** Run `POST /api/train` to generate `.joblib` files for the new dataset.

No changes to `app.py` are needed — all endpoints are generic.

---

## 12. Downloading More Data

To extend coverage (different region, more years, or more datasets):

```python
# Edit backend/data_downloader/download_gee_data.py
COUNTRY_NAME = 'France'           # change region
SPAIN_BOUNDS = [-5.2, 42.3, 9.8, 51.1]  # update bounding box

# For temporal data, add years:
"start": "2025-01-01",
"end":   "2025-12-31",
```

Then run:
```bash
python backend/data_downloader/download_gee_data.py
# Requires: earthengine authenticate (one-time)

python -m backend.ml_models.train   # retrain on new data
```

---

## 13. API Reference

### Request / Response: `POST /api/exhibition/simulate`

**Request body:**
```json
{
  "philosophy": "let_nature_recover",
  "climate_scenario": "ssp245",
  "years": 50,
  "n_ensemble": 10,
  "lat": 41.40,
  "lon": 2.15
}
```

- `philosophy`: one of `let_nature_recover`, `traditional_farming`, `agroforestry`, `intensive_regen`, `precision_sustainable`
- `climate_scenario`: one of `ssp126`, `ssp245`, `ssp370`, `ssp585`
- `years`: 10–100
- `n_ensemble`: 1–20 (more = smoother uncertainty bands, slower)
- `lat/lon`: anchor point for initial conditions extraction from GeoTIFFs (lat 40–43, lon 0–4)

---

## 14. Technical Stack

| Component | Technology |
|-----------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Map rendering | Leaflet 1.9 + GeoRasterLayer (client-side GeoTIFF) |
| Charts | Chart.js |
| Backend | FastAPI + uvicorn |
| Raster I/O | rasterio |
| Numerics | numpy, scipy |
| ML models | scikit-learn (Ridge, MLP, Random Forest), xgboost |
| Model persistence | joblib |
| Carbon model | Custom RothC implementation (numpy, fully vectorized) |
| Climate projections | IPCC AR6 WG1 data + scipy interpolation |
| Erosion model | RUSLE + D8 routing (custom numpy) |
| GEE (optional) | earthengine-api |
| Data format | GeoTIFF (rasterio), EPSG:4326 |

---

## 15. Troubleshooting

| Issue | Fix |
|-------|-----|
| `uvicorn: command not found` | Use `py -m uvicorn backend.app:app --reload` |
| Map tiles not loading | GEE credentials needed — run `earthengine authenticate` |
| Statistics show `null` | Clicked outside Spain raster bounds — click inside Spain |
| Prediction returns "not supported" | That dataset (soil) has no temporal data — year slider is disabled for these |
| RF model not found | Run `python -m backend.ml_models.train` or click "Train Models" in the UI |
| Colours look wrong / all same colour | Sentinel-value rendering bug — check that `computeDisplayRange` gap-detection is active in the JS |
| `rasterio` install fails on Windows | Try `pip install rasterio --find-links https://girder.github.io/large_image_wheels` |
| Exhibition simulate returns 500 | Ensure `soil_model/` and `climate_scenarios/` modules are importable — check `/api/exhibition/status` |
| Training takes too long | Reduce pixel sampling limits in `train.py` (`_MAX_PER_BAND`, `_MAX_CROSS`) |

---

## 16. Suggested Next Steps

These are natural extensions that fit cleanly into the existing architecture:

- **More datasets**: Add NDVI, Land Surface Temperature, soil moisture from GEE. The registry auto-discovers files — only colour ramps need adding.
- **Pixel-level temporal models**: Instead of scaling the whole raster by a ratio, train a per-pixel model using each location's multi-year series. Requires multi-year soil data (OpenLandMap is currently a single snapshot).
- **Erosion risk composite**: Combine Organic Carbon + Sand/Clay + Precipitation into a derived erosion risk index raster, computed on-the-fly in `spatial_inference.py`.
- **Region drawing**: Let users draw a polygon on the map and run analysis on just that region using rasterio masking. The bbox infrastructure already exists in `data_loader.py`.
- **Time-lapse animation**: Loop through downloaded years and animate the Leaflet map layer using `setInterval`.
- **Tile server**: Replace raw GeoTIFF serving with Cloud-Optimised GeoTIFF (COG) + TiTiler for zoom-level-aware tile delivery without sending full file bytes to the browser.
- **Model comparison view**: Show test RMSE, R², MAE side-by-side for Ridge vs MLP in the UI, pulled from the `*_temporal_metrics.json` files already saved.
- **Exhibition frontend**: Build a full touch-screen exhibition UI (React or vanilla) that wraps the `/api/exhibition/simulate` endpoint with the philosophy chooser, climate scenario picker, animated time series charts, and the educational "learn" panels.
- **Additional philosophies**: The philosophy system is data-driven — adding a 6th philosophy requires only a new dict entry in `philosophies.py`.

---

**Region**: Spain + Catalonia / Barcelona
**Branch**: `verify_downloads`
**ML Status**: Trained — Ridge/MLP/RF for all 6 soil datasets; Temporal Ridge/MLP for CHIRPS and MODIS
**Exhibition Status**: Full backend simulation engine operational
**Last updated**: March 2026
