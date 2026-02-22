# ML Models — OpenLandMap Analytics Platform

> **Saved models directory:** `backend/ml_models/saved_models/`  
> **Training script:** `backend/ml_models/train.py`  
> **Inference engine:** `backend/ml_models/temporal_inference.py`

---

## How to Run Training

### Prerequisites

```bash
# From the repository root (activate your virtualenv first)
pip install -r backend/requirements.txt
```

### Run all training

```bash
python -m backend.ml_models.train
```

This scans all local GeoTIFFs in `backend/data_downloader/`, trains every applicable model, saves `.joblib` files and `_metrics.json` files to `saved_models/`, and prints a full summary.

Expected runtime: **2–5 minutes** depending on CPU.

### What training produces

```
saved_models/
├── {dataset}_ridge.joblib              # Depth-band Ridge (soil only)
├── {dataset}_mlp.joblib                # Depth-band MLP   (soil only)
├── {dataset}_rf.joblib                 # Cross-dataset RF influence (all datasets)
├── {dataset}_temporal_ridge.joblib     # Year Ridge, refitted on all years (CHIRPS, MODIS)
├── {dataset}_temporal_mlp.joblib       # Year MLP,   refitted on all years (CHIRPS, MODIS)
├── {dataset}_temporal_rf.joblib        # Year RF,    refitted on all years (CHIRPS, MODIS)
├── {dataset}_temporal_best.joblib      # Best model bundle (selected by test RMSE)
└── {dataset}_temporal_metrics.json     # Evaluation metrics from chronological split
```

### Re-triggering from the UI

Click **Train Models** in the dashboard side panel — this calls `POST /api/train` which runs `train_all()` in a background thread and streams progress via `GET /api/train/status`.

---

## Data Architecture

The platform trains from two distinct types of local data:

### Type A — Soil Datasets (static, depth-banded)

Six soil datasets live as flat GeoTIFFs in `backend/data_downloader/soil/`. Each dataset has **six depth bands**:

| Band key | Physical depth | Temporal proxy interpretation |
|----------|---------------|-------------------------------|
| `b0`     | 0–5 cm        | Present surface (≈ current state) |
| `b10`    | 10–30 cm      | Near-surface, recent decades |
| `b30`    | 30–60 cm      | Mid-century analog |
| `b60`    | 60–100 cm     | Mid-20th century analog |
| `b100`   | 100–200 cm    | Early 20th century analog |
| `b200`   | 200+ cm       | Pre-modern baseline |

Because these datasets are a **single spatial snapshot** with no real time axis, depth bands serve as a temporal proxy: deeper layers reflect older soil conditions. Models trained on this axis can extrapolate forward in time (1 cm ≡ 1 year beyond the surface).

### Type B — Temporal Datasets (year-by-year)

Two datasets have real annual GeoTIFFs downloaded year-by-year into `year=XXXX/` subfolders:

| Dataset | Folder | Available years | Files |
|---------|--------|----------------|-------|
| Precipitation CHIRPS | `climate/year=YYYY/` | 2000–2024 (25 years) | `Precipitation_CHIRPS.precipitation.tif` |
| MODIS Land Cover | `land_cover/year=YYYY/` | 2001–2023 (23 years) | `MODIS_Land_Cover.LC_Type1.tif` |

For these datasets, temporal ML models are trained directly on the **year → spatial mean** relationship using real observed data across all available years.

---

## Model 1 — Ridge Regression (Depth-Band, Soil Only)

**File:** `{dataset}_ridge.joblib`  
**Applies to:** Bulk Density, Clay Content, Organic Carbon, Sand Content, Soil Texture, Soil pH  
**Used by:** Forecast tab (depth-profile fallback), temporal inference step 5 (depth-band proxy)

### Architecture

```
Input: depth_cm ∈ {0, 10, 30, 60, 100, 200}
    │
    ▼
PolynomialFeatures(degree=2, include_bias=True)
    Expands: [1, d, d²]
    │
    ▼
Ridge(alpha=10.0)
    Minimises: ‖Xw − y‖² + 10‖w‖²
    │
    ▼
Output: predicted property value at depth d
```

### Training procedure

For each depth band:
1. Read the GeoTIFF with `rasterio`
2. Sample up to **1,000 valid pixels** (exclude nodata / NaN)
3. Pair `(depth_cm, pixel_value)` — repeat depth value for every sampled pixel
4. Fit Ridge pipeline on the combined array (typically 4,000–6,000 points)

Training uses **all pixels from all bands together** — not aggregated means — so the model learns the distribution, not just a point estimate.

### Inference (forecasting)

```python
# Soil forecast: depth 201–300 cm → years 2026–2125
future_depths = np.arange(201, 201 + 100).reshape(-1, 1)
predictions   = ridge_pipeline.predict(future_depths)
```

---

## Model 2 — MLP Regressor (Depth-Band, Soil Only)

**File:** `{dataset}_mlp.joblib`  
**Applies to:** Soil datasets (same six as Ridge)  
**Used by:** Forecast tab (preferred over depth-band Ridge for non-linear soil profiles)

### Architecture

```
Input: depth_cm (scalar)
    │
    ▼
StandardScaler  →  zero-mean, unit-variance
    │
    ▼
Dense(64, ReLU)   hidden layer 1
    │
    ▼
Dense(32, ReLU)   hidden layer 2
    │
    ▼
Dense(1, linear)  output
    │
    ▼
Output: predicted property value
```

**sklearn config:**

```python
MLPRegressor(
    hidden_layer_sizes=(64, 32),
    activation='relu',
    max_iter=500,
    random_state=42,
    early_stopping=True,
    validation_fraction=0.15,
    n_iter_no_change=20,
)
```

### Why MLP in addition to Ridge?

Ridge constrains predictions to a polynomial curve, which may miss step-changes or plateaus common in soil depth profiles. The MLP learns the shape of the profile without that constraint. It is used preferentially when available. `early_stopping=True` prevents overfitting on the ~3,000-pixel training set.

---

## Model 3 — Random Forest (Cross-Dataset Influence)

**File:** `{dataset}_rf.joblib` → `{"model": pipeline, "features": [display_names]}`  
**Applies to:** All eight datasets  
**Used by:** Dataset Influence chart (correlation tab)

### Architecture

```
Features: [primary-band pixel values of all OTHER datasets]
    │
    ▼
StandardScaler
    │
    ▼
RandomForestRegressor(
    n_estimators=100, max_depth=8,
    random_state=42, n_jobs=-1,
)
    │
    ▼
feature_importances_  (Gini impurity decrease, sums to 1.0)
```

### How cross-dataset training works

1. Read the **primary band** (shallowest depth band `b0`, or first available) of every dataset
2. Sample up to **2,000 spatially aligned pixels** present in all datasets
3. Build feature matrix `X` of shape `(N, D−1)` — all datasets except target
4. Train RF to predict target dataset's pixel values
5. Extract `feature_importances_`, then sign each by `sign(Pearson r(target, feature))`

### Interpreting the importance chart

```
importance_signed[i] = gini_importance[i] × sign(pearson_r(target, feature_i))
```

| Bar direction | Meaning |
|---------------|---------|
| Positive (right) | Higher values in this dataset → higher values in target |
| Negative (left)  | Higher values in this dataset → lower values in target |
| Bar length       | Influence strength (0 = none, 1 = total dependence) |

**Example — Organic Carbon:**
- Clay Content → strongly positive (clay retains organic matter)
- Bulk Density → strongly negative (compacted soils have less organic carbon)
- Sand Content → mildly negative (sandy soils drain organic matter quickly)

---

## Models 4–6 — Temporal Time-Series Models (CHIRPS & MODIS)

**Files:**
- `{dataset}_temporal_ridge.joblib` — Ridge polynomial on year axis
- `{dataset}_temporal_mlp.joblib` — MLP neural net on year axis
- `{dataset}_temporal_rf.joblib` — Random Forest with polynomial year features
- `{dataset}_temporal_best.joblib` — Best of the three (selected by test RMSE, then refit on all years)
- `{dataset}_temporal_metrics.json` — Evaluation metrics from the chronological split

**Applies to:** Precipitation CHIRPS, MODIS Land Cover  
**Used by:** `/api/infer` endpoint — called when user selects a year outside the downloaded range

### Why separate temporal models?

Depth-band proxy models (Models 1–2) are physically motivated only for soil. For climate and land cover datasets, we have real annual observations from 2000–2024 and 2001–2023 respectively. These temporal models are trained directly on the `(year → spatial mean value)` time series, giving far more accurate extrapolations.

### Training Procedure

The core function is `train_temporal_models(name)` in `train.py`. It follows these steps:

#### Step 1 — Build the time series

For each year in `TEMPORAL_REGISTRY[name]`:
1. Open the year's GeoTIFF with `rasterio`
2. Sample up to **5,000 valid pixels** (excludes nodata/NaN)
3. Compute the **spatial mean** of sampled pixels
4. Record `(year, mean_value)` pair

The result is a 1-D series of `(year, mean_value)` pairs covering all available years.

#### Step 2 — Chronological train/test split (80/20)

Years are sorted chronologically and split — the **last 20% of years** become the test set. This is the only valid approach for time-series evaluation (random shuffling would leak future information into the training set).

| Dataset | Total years | Train set | Test set |
|---------|-------------|-----------|----------|
| CHIRPS | 25 (2000–2024) | 2000–2019 (20 yrs) | 2020–2024 (5 yrs) |
| MODIS  | 23 (2001–2023) | 2001–2018 (18 yrs) | 2019–2023 (5 yrs) |

#### Step 3 — Fit three candidate models on the train split

| Model | Pipeline | Key hyperparameters |
|-------|----------|---------------------|
| **Temporal Ridge** | `PolynomialFeatures(degree=2)` → `Ridge(alpha=1.0)` | Regularised polynomial curve |
| **Temporal MLP**  | `StandardScaler` → `MLPRegressor(64×32, ReLU)` | Early stopping, `max_iter=2000` |
| **Temporal RF**   | `PolynomialFeatures(degree=3)` → `StandardScaler` → `RandomForest(200 trees, depth 5)` | `min_samples_leaf=2` prevents overfitting |

All three see only the **training years** during fitting. The test years are never used during training.

#### Step 4 — Evaluate on the held-out test set

```python
y_pred = model.predict(X_test)   # X_test = test years as column vector
metrics = {
    "rmse": sqrt(mean((y_test - y_pred)²)),
    "mae":  mean(|y_test - y_pred|),
    "r2":   1 - SS_res / SS_tot,
}
```

#### Step 5 — Select the best model by test RMSE

```python
best_name = min(results, key=lambda k: results[k]["test"]["rmse"])
```

**Actual results from current training run:**

| Dataset | Ridge RMSE | MLP RMSE | RF RMSE | **Best** |
|---------|-----------|----------|---------|----------|
| CHIRPS  | **1.521** mm/yr | 2.207 mm/yr | 1.535 mm/yr | **Ridge** |
| MODIS   | 0.114 class | 1.541 class | **0.080** class | **RF** |

#### Step 6 — Refit ALL models on the full year range

After evaluation, every model (Ridge, MLP, RF) is refit on the **complete dataset** (train + test years combined). This ensures the deployed models incorporate all available signal — including the most recent years — while the evaluation split gives honest performance estimates.

```python
X_all = all_years.reshape(-1, 1)   # e.g. 2000–2024 for CHIRPS
model.fit(X_all, all_values)        # trained on ALL 25 years
```

The best model is saved both individually and as `_temporal_best.joblib` (a bundle containing the model object and the winning model's name).

#### Step 7 — Save metrics JSON

```json
{
  "dataset": "Precipitation_CHIRPS",
  "train_years": [2000, 2001, ..., 2019],
  "test_years":  [2020, 2021, 2022, 2023, 2024],
  "best_model": "Ridge",
  "models": {
    "Ridge": { "test_rmse": 1.5209, "test_mae": 1.35,   "test_r2": -0.014, "train_rmse": 0.9036 },
    "MLP":   { "test_rmse": 2.2073, "test_mae": 1.9297, "test_r2": -1.136, "train_rmse": 0.4821 },
    "RF":    { "test_rmse": 1.5345, "test_mae": 1.3416, "test_r2": -0.032, "train_rmse": 0.0211 }
  }
}
```

These metrics are served via `/api/infer` and displayed in the ML prediction overlay on the map.

---

## Temporal Inference Pipeline

When a user selects a year that falls outside the downloaded data range, `temporal_inference.py` runs this fallback chain:

```
predict_year(dataset_name, target_year)
    │
    ├─1─ {name}_temporal_best.joblib?   ──→ use best model (refitted on all years)
    │
    ├─2─ {name}_temporal_mlp.joblib?    ──→ use MLP
    │
    ├─3─ {name}_temporal_ridge.joblib?  ──→ use Ridge
    │
    ├─4─ Fit Ridge on-the-fly           ──→ from TEMPORAL_REGISTRY data (≥ 2 years)
    │
    ├─5─ Depth-band proxy Ridge         ──→ soil datasets: depth_cm = (target_year − 2025)
    │
    └─6─ Static mean                    ──→ last resort
```

Every response includes:

```json
{
  "predicted_value": 6.549,
  "model": "Temporal Ridge (best)",
  "confidence_low": 4.872,
  "confidence_high": 8.226,
  "year_range": [2000, 2024],
  "extrapolated": true,
  "test_metrics": { "test_rmse": 1.521, "test_mae": 1.35, "test_r2": -0.014 }
}
```

The **90% confidence interval** is derived from training residuals: `CI = pred ± 1.645 × RMSE_train`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/train` | Trigger full training run (background thread) |
| `GET`  | `/api/train/status` | Poll training progress |
| `GET`  | `/api/model-status` | List all saved `.joblib` files |
| `GET`  | `/api/years` | Return `{internal_name: [year, ...]}` for temporal datasets |
| `GET`  | `/api/infer?dataset=X&year=Y` | Check if year has real data; run ML if not |
| `GET`  | `/api/analysis/forecast` | 100-year depth-band forecast (Chart.js JSON) |
| `GET`  | `/api/analysis/time-series` | Depth profile chart (Chart.js JSON) |
| `GET`  | `/api/analysis/correlation` | Cross-dataset influence chart (Chart.js JSON) |

---

## Model Selection Rationale

| Model | Status | Reason |
|-------|--------|--------|
| Ridge (depth-band) | ✅ Kept | Smooth regularised extrapolation; interpretable; fast |
| MLP (depth-band) | ✅ Kept | Captures non-linear depth transitions without polynomial constraint |
| RF (cross-dataset influence) | ✅ Kept | Only model that directly quantifies inter-dataset influence |
| Ridge (temporal, year axis) | ✅ Kept | Best temporal model for CHIRPS (lowest test RMSE) |
| MLP (temporal, year axis) | ✅ Kept | Competitive on non-monotonic year trends |
| RF (temporal, year axis) | ✅ Kept | Best temporal model for MODIS (lowest test RMSE) |
| LSTM / RNN | ❌ Removed | Requires sequences of many time steps; overkill for 1-feature year series |
| SVM Regression | ❌ Removed | Redundant with MLP for this scale; slower; less interpretable |
| Gaussian Process | ❌ Removed | O(n³) scaling; overkill; calibration not needed here |
| XGBoost | ❌ Removed | Redundant with RF at this feature count; adds dependency |
| Change Detection | ❌ Not applicable | Requires co-registered multi-temporal rasters for pixel-level diff |

---

## Data Sources

```
backend/data_downloader/
├── soil/
│   ├── Bulk_Density.b0.tif  …  Bulk_Density.b200.tif        (6 bands)
│   ├── Clay_Content.b0.tif  …  Clay_Content.b200.tif         (6 bands)
│   ├── Organic_Carbon.b0.tif … Organic_Carbon.b200.tif       (6 bands)
│   ├── Sand_Content.b0.tif  …  Sand_Content.b200.tif         (6 bands)
│   ├── Soil_Texture.b0.tif  …  Soil_Texture.b200.tif         (6 bands)
│   └── Soil_pH.b0.tif       …  Soil_pH.b200.tif              (6 bands)
├── climate/
│   └── year=2000/ … year=2024/
│       └── Precipitation_CHIRPS.precipitation.tif           (25 years)
└── land_cover/
    └── year=2001/ … year=2023/
        └── MODIS_Land_Cover.LC_Type1.tif                    (23 years)
```

---

## Technical Notes

- **Pixel sampling:** Pixels are read with `rasterio`, nodata values excluded, then sampled by stride to cap memory use. Reproducibility is guaranteed via `random_state=42` in all stochastic models.
- **Chronological split — not random:** Time-series test sets must always use the most-recent observations as the test set. Random shuffling would leak future values into training and produce falsely optimistic metrics.
- **Refit on all years after evaluation:** The test split is used only to rank models and measure real-world accuracy. The final deployed model is refit on every available year so nothing is wasted.
- **Negative R²:** A negative R² means the model performs worse than simply predicting the mean. For CHIRPS and MODIS, year-to-year variation is small (signal ≈ noise), so near-zero or negative R² is expected — the RMSE remains small in absolute terms.
- **LinAlgWarning on Ridge:** Polynomial expansion on small datasets produces near-singular matrices. Ridge's L2 regularisation (`alpha`) handles this by design; the warning is harmless.
- **Windows encoding:** Run with `$env:PYTHONIOENCODING="utf-8"` if any print statements produce encoding errors on Windows.
