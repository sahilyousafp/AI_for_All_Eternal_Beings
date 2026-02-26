# OpenLandMap Analytics Platform

A full-stack geospatial analytics platform for soil and environmental monitoring. Combines a FastAPI backend, Leaflet dashboard, Google Earth Engine tile streaming, and trained ML models — all running on locally downloaded Spain rasters (no cloud compute required for ML).

---

## What's Built

| Layer | Status | Details |
|---|---|---|
| Web Dashboard | Live | Leaflet map + sidebar controls + 4 chart tabs |
| FastAPI Backend | Live | 8 endpoints, real raster data, GEE optional |
| GEE Map Tiles | Live (needs credentials) | Streams OpenLandMap layers via GEE |
| Data — Spain | Downloaded | 50 GeoTIFFs at 2.5km, clipped to Spain + Canaries |
| Random Forest | Trained | 93% accuracy, 215k pixels, 10 soil texture classes |
| Depth Profile | Live | Real 6-layer vertical profile (0–200 cm) per dataset |
| Linear Forecast | Live | scipy linregress on depth profile + CI extrapolation |
| Change Detection | Live | Real surface (0 cm) vs deep (200 cm) gradient |
| Correlation | Live | Pearson r vs precipitation, land cover, other soil props |

---

## Project Structure

```
AI_for_All_Eternal_Beings/
├── backend/
│   ├── app.py                          ← FastAPI — 8 endpoints, real raster sampling
│   ├── requirements.txt                ← All dependencies including ML libs
│   ├── data_downloader/
│   │   ├── download_gee_data.py        ← Script to download more data via GEE
│   │   ├── soil/                       ← 36 GeoTIFFs (6 properties × 6 depths)
│   │   ├── climate/                    ← CHIRPS precipitation (2020)
│   │   └── land_cover/                 ← MODIS land cover (2020, 13 bands)
│   └── ml_models/
│       ├── data_loader.py              ← rasterio-based raster loading & pixel extraction
│       ├── train_rf.py                 ← One-time RF training script
│       ├── utils.py                    ← Dataset config & find_dataset()
│       ├── time_series.py              ← Real depth profile (0–200 cm)
│       ├── forecast.py                 ← Linear trend + CI extrapolation
│       ├── change_detection.py         ← Surface vs deep gradient
│       ├── correlation.py              ← Pearson r from rasterio resampling
│       ├── prediction.py               ← RF inference on any bbox
│       └── models/
│           ├── rf_soil_classifier.joblib  ← Trained RF (83 MB)
│           └── rf_scaler.joblib           ← Fitted StandardScaler
├── frontend/
│   ├── index.html                      ← Dashboard UI (map + sidebar + chart tabs)
│   ├── main.js                         ← API calls, chart rendering, event handling
│   └── gee-map.js                      ← Leaflet map + GEE tile layer
├── gee_master_application.js           ← GEE Code Editor script (standalone)
├── PLATFORM_ARCHITECTURE.md
├── ML_IMPLEMENTATION_GUIDE.md
└── README.md
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. (One-time) Train the RF model
Skip if `backend/ml_models/models/rf_soil_classifier.joblib` already exists.
```bash
python -m backend.ml_models.train_rf
```
Expected output: ~93% test accuracy, model saved to `models/`.

### 3. Start the backend
```bash
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```
The API starts cleanly even without GEE credentials. All ML endpoints use local rasters.

### 4. Open the dashboard
Open `frontend/index.html` directly in a browser (no build step, no server needed).

Map centres on Spain. Click a chart tab to load real data.

---

## API Endpoints

| Endpoint | Data Source | Returns |
|---|---|---|
| `GET /api/status` | — | Health check + GEE availability flag |
| `GET /api/datasets` | Config | 6 dataset definitions with vis params |
| `GET /api/map?dataset=` | GEE (requires credentials) | Tile URL for Leaflet |
| `GET /api/statistics?dataset=&lat=&lon=` | Local raster | Real mean/min/max/std from 5×5 pixel window |
| `GET /api/analysis/time-series?dataset=` | Local rasters | 6-point depth profile (0–200 cm) |
| `GET /api/analysis/forecast?dataset=&years=` | Local rasters | Linear trend + CI, extrapolated to 1000 cm |
| `GET /api/analysis/change-detection?dataset=` | Local rasters | Surface (0 cm) vs deep (200 cm) delta |
| `GET /api/analysis/correlation?dataset=` | Local rasters | Pearson r vs precipitation, land cover, soil props |
| `GET /api/analysis/prediction?dataset=&lat_min=&lon_min=&lat_max=&lon_max=` | RF model | Class confidence per depth layer for bbox |

---

## Datasets

All from **OpenLandMap** — free, global, 250m resolution (downloaded at 2.5km for Spain):

| Dataset | Units | Depth Layers |
|---|---|---|
| Organic Carbon | g/kg | b0, b10, b30, b60, b100, b200 |
| Soil pH (H2O) | pH | b0, b10, b30, b60, b100, b200 |
| Bulk Density | t/m3 | b0, b10, b30, b60, b100, b200 |
| Sand Content | % | b0, b10, b30, b60, b100, b200 |
| Clay Content | % | b0, b10, b30, b60, b100, b200 |
| Soil Texture Class | USDA class 1–12 | b0, b10, b30, b60, b100, b200 |

Additional: CHIRPS precipitation (2020 mean) + MODIS land cover (2020).

**Region**: Spain + Canary + Balearic Islands (`[-18.2, 27.5, 4.6, 43.9]`)

---

## ML Details

### Random Forest — Soil Texture Classifier
- **Features**: Organic Carbon, Soil pH, Bulk Density, Sand %, Clay % (surface b0)
- **Labels**: Soil Texture Class raster (independent — no label leakage)
- **Training samples**: 215,660 valid pixels
- **Test accuracy**: 93.03%
- **Top features**: Clay (49%), Sand (40%), OrgC (4%), pH (3%), BulkDens (3%)
- **Classes present in Spain**: Clay, Clay Loam, Sandy Clay Loam, Loam, Silt Loam, Silt, Loamy Sand, Sand

### Depth Profile (replaces fake "Time Series")
OpenLandMap soil datasets are static snapshots — there is no temporal dimension. The depth profile shows how each property changes from surface (0 cm) to 200 cm, which is real, meaningful vertical data.

### Linear Trend (Forecast tab)
Fits `scipy.stats.linregress` to the 6 known depth points and extrapolates beyond 200 cm with 95% prediction intervals. R² typically >0.95 for Organic Carbon and pH.

### Correlation
Resamples CHIRPS and MODIS rasters to the soil grid via `rasterio.warp.reproject`, then computes `scipy.stats.pearsonr` over all co-located valid pixels (~590k). All p-values are effectively 0 at this sample size.

---

## Downloading More Data

To extend coverage (different region or more years), edit `backend/data_downloader/download_gee_data.py`:

```python
COUNTRY_NAME = 'France'          # change region
SPAIN_BOUNDS = [...]             # update bounding box

# For temporal data add years to the collections:
"start": "2015-01-01",
"end":   "2015-12-31",
```

Then re-run:
```bash
python backend/data_downloader/download_gee_data.py
python -m backend.ml_models.train_rf   # retrain on new data
```

---

## Technical Stack

| Component | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS, Leaflet 1.9 |
| Backend | FastAPI + uvicorn |
| Raster I/O | rasterio |
| ML | scikit-learn (RandomForestClassifier) |
| Stats | scipy (linregress, pearsonr) |
| Numerics | numpy |
| Model persistence | joblib |
| GEE (optional) | earthengine-api |

---

## GEE Script (Standalone)

`gee_master_application.js` is a self-contained Google Earth Engine Code Editor script. It does not depend on the Python backend — it queries OpenLandMap assets directly from GEE.

```
1. Go to https://code.earthengine.google.com
2. New script → paste gee_master_application.js → Run
3. Interactive UI appears with dataset selector, map, and charts
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `uvicorn: command not found` | Use `py -m uvicorn backend.app:app --reload` |
| Map tiles not loading | GEE credentials needed — run `earthengine authenticate` |
| Prediction returns "no coverage" | Zoom into Spain before clicking Predict |
| RF model not found | Run `python -m backend.ml_models.train_rf` |
| Statistics show `null` | Clicked outside Spain raster bounds — click inside Spain |
| `rasterio` install fails | Try `pip install rasterio --find-links https://girder.github.io/large_image_wheels` |

---

**Branch**: Rafik's-Branch
**Region**: Spain
**ML Status**: Trained — 93% accuracy
**Last updated**: February 2026
