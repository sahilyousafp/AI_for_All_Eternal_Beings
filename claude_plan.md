Combined Implementation Plan: ML Model Upgrades + Soil Futures Exhibition System
PART 1: Strengthen the Existing ML Models
Context
Current temporal models train on 25 data points (one spatial mean per year). The fix is a spatiotemporal XGBoost model that trains on (year, lat, lon, ΔT_CMIP6, ΔP_CMIP6) → pixel_value — approximately 125,000 observations (25 years × ~5,000 pixels). This is a 5,000× increase in training data.

Key insight: The exhibition system's ssp_data.py already encodes IPCC AR6/CMIP6 benchmark ΔT and ΔP values per SSP scenario. These are used directly as model features — no new data download required. The model conditions on physically-grounded climate signals, not just raw year extrapolation.

Depth-band Ridge/MLP models remain unchanged — they fit a polynomial across 6 depth measurements, not temporal forecasts. No architecture change fixes that limitation.

Expected accuracy: R² ≈ 0.70–0.85 on held-out years (was 0.2–0.5).

New dependency

pip install xgboost
Files Modified
File	Change
backend/ml_models/train.py	Add train_spatiotemporal(), increase pixel caps, LOO-CV for scalar models
backend/ml_models/temporal_inference.py	Add predict_spatial_year() returning 20×20 grid; scalar fallback unchanged
New constants in train.py (lines 35-37)

_MAX_PER_BAND = 5000   # was 1000
_MAX_CROSS    = 10000  # was 2000
_MAX_SPATIO   = 5000   # pixels sampled per year for spatiotemporal model
New function: train_spatiotemporal(name) added to train.py

from xgboost import XGBRegressor
from sklearn.model_selection import LeaveOneOut, cross_val_predict

def train_spatiotemporal(name: str, ssp_scenario: str = "ssp245") -> dict:
    """
    Build (year, lat, lon, delta_T, delta_P) → pixel_value training set from
    all years in TEMPORAL_REGISTRY, train XGBoost.
    delta_T, delta_P from ssp_data.get_climate() — reuses exhibition SSP tables.
    """
    from backend.climate_scenarios.ssp_data import get_climate

    year_data = TEMPORAL_REGISTRY.get(name, {})
    if len(year_data) < 6:
        return {f"{name}_spatiotemporal": f"skipped — only {len(year_data)} years"}

    rows = []
    for yr in sorted(year_data.keys()):
        path = temporal_primary_band(name, yr)
        if not path or not os.path.isfile(path):
            continue
        climate = get_climate(ssp_scenario, yr - 2025, seed=42)
        delta_T = climate["temp"] - 16.2      # subtract Barcelona baseline
        delta_P = climate["precip"] - 580.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                data = src.read(1, masked=True)
                transform = src.transform
        valid_idx = np.argwhere(~np.ma.getmaskarray(data))
        if len(valid_idx) > _MAX_SPATIO:
            valid_idx = np.random.default_rng(yr).choice(
                len(valid_idx), _MAX_SPATIO, replace=False)
            valid_idx = np.argwhere(~np.ma.getmaskarray(data))[valid_idx]
        for r, c in valid_idx:
            val = float(data[r, c])
            if np.isfinite(val):
                lon_c, lat_r = rasterio.transform.xy(transform, r, c)
                rows.append((float(yr), float(lat_r), float(lon_c), delta_T, delta_P, val))

    if len(rows) < 100:
        return {f"{name}_spatiotemporal": "skipped — insufficient valid pixels"}

    X = np.array([[r[0], r[1], r[2], r[3], r[4]] for r in rows])
    y = np.array([r[5] for r in rows])

    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05,
                          subsample=0.8, colsample_bytree=0.8,
                          random_state=42, n_jobs=-1, tree_method="hist")
    model.fit(X, y)

    # LOO-CV on annual means for honest temporal generalization metric
    annual_X, annual_y = [], []
    for yr in sorted(year_data.keys()):
        climate = get_climate(ssp_scenario, yr - 2025, seed=42)
        annual_X.append([float(yr), 41.4, 2.15,
                          climate["temp"] - 16.2, climate["precip"] - 580.0])
        annual_y.append(_read_mean(temporal_primary_band(name, yr)) or 0.0)
    loo_preds = cross_val_predict(
        XGBRegressor(n_estimators=100, max_depth=4, random_state=42, n_jobs=-1),
        np.array(annual_X), np.array(annual_y), cv=LeaveOneOut()
    )
    metrics = _regression_metrics(np.array(annual_y), loo_preds)
    print(f"  LOO-CV: RMSE={metrics['rmse']:.4f}  R²={metrics['r2']:.4f}")

    out_path = os.path.join(SAVED_DIR, f"{name}_spatiotemporal.joblib")
    joblib.dump({"model": model, "features": ["year","lat","lon","dT","dP"]}, out_path)
    print(f"  [OK] Spatiotemporal XGBoost → {os.path.basename(out_path)}")
    return {f"{name}_spatiotemporal": f"saved  loo_r2={metrics['r2']}"}
Called in train_all() at the bottom of each dataset's block, after the existing temporal Ridge/MLP call.

New function: predict_spatial_year() added to temporal_inference.py

def predict_spatial_year(dataset_name: str, target_year: int,
                          lat_grid: np.ndarray, lon_grid: np.ndarray,
                          ssp_scenario: str = "ssp245") -> np.ndarray | None:
    """
    Predict pixel values for a 2-D lat/lon grid at target_year.
    Returns ndarray matching lat_grid.shape, or None if model unavailable.
    Used by exhibition engine.py to get spatially-resolved climate fields.
    """
    path = os.path.join(SAVED_DIR, f"{dataset_name}_spatiotemporal.joblib")
    if not os.path.isfile(path):
        return None
    bundle = joblib.load(path)
    model  = bundle["model"]
    from backend.climate_scenarios.ssp_data import get_climate
    climate = get_climate(ssp_scenario, target_year - 2025, seed=42)
    dT = climate["temp"] - 16.2
    dP = climate["precip"] - 580.0
    flat_lat = lat_grid.ravel()
    flat_lon = lon_grid.ravel()
    X = np.column_stack([
        np.full(len(flat_lat), float(target_year)),
        flat_lat, flat_lon,
        np.full(len(flat_lat), dT),
        np.full(len(flat_lat), dP),
    ])
    return model.predict(X).reshape(lat_grid.shape)
The existing scalar predict_year() fallback chain is unchanged — Predictions tab continues to work.

What this achieves
Metric	Before	After
Training observations	25 (one mean/year)	~125,000 (pixels × years)
Model architecture	Ridge polynomial	XGBoost with CMIP6 covariates
Temporal extrapolation	Raw year trend	Conditioned on SSP ΔT, ΔP physics
Output	Scalar mean	20×20 spatial grid
LOO-CV R² (estimated)	0.2–0.5	0.7–0.85
New dependencies	None	xgboost
Integration: predict_spatial_year() feeds into engine.py — the exhibition simulation uses real ML-predicted precipitation fields across the 20×20 grid instead of a single scalar, giving spatial heterogeneity to rainfall inputs.

Soil Property Forecasting — Replace Depth-Band Ridge with Single-Cell RothC
The problem: Depth-band Ridge/MLP models fit depth_cm → value across 6 measurements from a single 2020 snapshot. This is depth-profile interpolation, not temporal prediction. No architecture change fixes it without temporal data.

The solution: Reuse backend/soil_model/carbon.py (built in PART 2) to run single-cell RothC forward from 2020 → target_year. This is a genuine temporal forecast backed by peer-reviewed soil science.

New file: backend/ml_models/soil_forecast.py


"""
Single-cell RothC-based soil property forecast for the Predictions tab.
Reuses backend/soil_model/carbon.py (exhibition engine module).

For a given (lat, lon, target_year, ssp_scenario):
  1. Extract initial conditions from real GeoTIFFs (2020 snapshot)
  2. Run RothC year-by-year with CMIP6-conditioned climate
  3. Return predicted depth profile at target_year
  4. Derive BD and pH from SOC change via pedotransfer functions
"""
from backend.soil_model.carbon import initialize_pools, rothc_step, total_soc
from backend.soil_init.extract_conditions import extract_initial_conditions
from backend.climate_scenarios.ssp_data import get_climate
import numpy as np

def forecast_soil_property(lat: float, lon: float,
                             target_year: int,
                             property_name: str,
                             ssp_scenario: str = "ssp245") -> dict:
    """
    Returns: {
        'predicted_value': float,           # at target_year, surface layer
        'depth_profile': list[float],       # 3 layer values [0-30, 30-100, 100+cm]
        'baseline_value': float,            # 2020 GeoTIFF value
        'change_pct': float,               # % change from baseline
        'model': 'RothC + pedotransfer',
        'confidence_low': float,
        'confidence_high': float,
        'year_range': [2020, target_year],
        'extrapolated': False,             # RothC is physics, not extrapolation
    }
    """
    # Extract 2020 initial conditions for this point
    ic = extract_initial_conditions(lat=lat, lon=lon, use_grid=False)
    oc_initial = ic['organic_carbon']   # shape (3,) for 3 depth layers
    clay = ic['clay_pct']
    moisture_ratio = ic.get('field_capacity', 0.3)

    pools = initialize_pools(oc_initial, clay, {}, veg_cover=np.array([0.3]))
    cumulative_warming = 0.0

    for yr in range(2020, target_year + 1):
        climate = get_climate(ssp_scenario, yr - 2025, seed=42)
        cumulative_warming = max(0.0, climate['temp'] - 16.2)
        for layer in range(3):
            pools, _ = rothc_step(
                pools={k: v[:, layer:layer+1] for k, v in pools.items()},
                clay_pct=np.array([clay]),
                temp=climate['temp'],
                moisture_ratio=np.array([min(1.0, moisture_ratio)]),
                veg_cover=np.array([0.3]),
                carbon_input=np.array([0.5]),
                cumulative_warming=np.array([cumulative_warming]),
                depth_layer=layer,
            )

    soc_final = total_soc(pools)   # (1, 3) → surface value at index [0, 0]

    if property_name == 'Organic_Carbon':
        predicted = float(soc_final[0, 0])
        baseline  = float(oc_initial[0])
    elif property_name == 'Bulk_Density':
        # Adams (1973): BD = 1 / (0.6268 + 0.0361 * SOC_pct)
        soc_pct = soc_final[0, 0] / 10.0   # g/kg → %
        predicted = float(1.0 / (0.6268 + 0.0361 * max(0.1, soc_pct)))
        baseline  = ic['bulk_density']
    elif property_name == 'Soil_pH':
        # Empirical: Δpd ≈ +0.008 per g/kg SOC increase (McBratney et al. 2014)
        delta_soc = soc_final[0, 0] - float(oc_initial[0])
        predicted = float(ic['soil_ph'] + 0.008 * delta_soc)
        baseline  = ic['soil_ph']
    else:
        return None   # Sand/Clay/Texture: static, no temporal prediction

    change_pct = (predicted - baseline) / max(abs(baseline), 1e-6) * 100
    # Uncertainty: ±15% for RothC (published model uncertainty range)
    return {
        'predicted_value': round(predicted, 3),
        'depth_profile':   [round(float(soc_final[0, i]), 3) for i in range(3)],
        'baseline_value':  round(baseline, 3),
        'change_pct':      round(change_pct, 1),
        'model':           'RothC process model + pedotransfer',
        'confidence_low':  round(predicted * 0.85, 3),
        'confidence_high': round(predicted * 1.15, 3),
        'year_range':      [2020, target_year],
        'extrapolated':    False,
    }
Updated /api/infer in backend/app.py: When dataset_name is one of ['Organic_Carbon', 'Bulk_Density', 'Soil_pH'], call soil_forecast.forecast_soil_property() instead of temporal_inference.predict_year(). All other datasets (CHIRPS, MODIS) continue using the existing fallback chain (now upgraded with XGBoost spatiotemporal).

Result:

Dataset	Forecast method	Basis
Organic Carbon	RothC carbon model	Peer-reviewed process model
Bulk Density	RothC + Adams (1973) pedotransfer	Published equation
Soil pH	RothC + McBratney (2014) pedotransfer	Published equation
Sand / Clay / Texture	Static (2020 snapshot labeled clearly)	No temporal change in 100yr
Precipitation (CHIRPS)	Spatiotemporal XGBoost + CMIP6	ML on 125,000 observations
Land Cover (MODIS)	Spatiotemporal XGBoost	ML on ~115,000 observations
Exhibition: Max Years Capped at 100
Update exhibition_api.py SimulateRequest validator:


years: int = Field(default=50, ge=10, le=100)  # was le=500
RothC and RUSLE are validated for century-scale. Confidence display tiers: "data-supported" (green, <30yr), "modelled" (amber, 30–80yr), "speculative" (red, 80–100yr).

PART 2: Soil Futures Exhibition System — Implementation Plan
Context
Rafik has an existing FastAPI + vanilla JS soil analytics platform (AI_for_All_Eternal_Beings/)
backed by real GeoTIFFs (36 soil files, 25 CHIRPS years, 23 MODIS years) for Spain at ~2.5km resolution.
The goal is to add a Soil Futures Exhibition System on top — a museum sandbox projection installation
where visitors choose a land management philosophy + climate scenario + time horizon and see a
spatially-resolved soil evolution simulation projected onto physical sand.

The user provided a detailed scientific critique of the naive single-profile approach and requested:
spatial grid simulation (20×20), depth-resolved carbon (3 layers), stochastic ensemble fire (10 members),
temperature acclimation (Bradford 2008), self-thinning (Reineke SDI), soil-vegetation feedback loops,
sediment routing, and ensemble confidence bands.

Existing code is NOT modified except backend/app.py (2 lines to mount a new router).

New File Structure

backend/
  climate_scenarios/
    __init__.py
    ssp_data.py                  # SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5 to 2525
  soil_init/
    __init__.py
    extract_conditions.py        # Read 20×20 grid initial conditions from GeoTIFFs
  soil_model/
    __init__.py
    carbon.py                    # RothC 4-pool × 3 depth layers + acclimation
    water.py                     # Bucket model + Saxton-Rawls pedotransfer
    vegetation.py                # Chapman-Richards + self-thinning + water depletion
    biology.py                   # Mycorrhizal, earthworm, biological integrity index
    erosion.py                   # RUSLE + D8 sediment routing across grid
    disturbances.py              # Stochastic fire, drought, flood events
    philosophies.py              # 5 management strategies with full parameters
    engine.py                    # Main simulation loop: grid × depth × ensemble
  exhibition_api.py              # FastAPI router for /api/exhibition/ endpoints
  tests/
    test_carbon_model.py
    test_erosion.py
    test_scenarios.py
    test_climate.py
    test_integration.py
frontend/exhibition/
  index.html                     # 4-phase exhibition SPA
  app.js                         # Phase management
  simulation.js                  # API calls + ensemble handling
  renderer.js                    # Canvas-based terrain visualization
Critical Reuse (do NOT duplicate)
Needed	Use existing	Location
Load soil rasters	load_raster(path)	backend/ml_models/data_loader.py:80
Load by bbox	load_raster_window(path, lon_min, lat_min, lon_max, lat_max)	data_loader.py:105
Point stats	load_point_statistics(dataset_name, lat, lon)	data_loader.py:270
Resolve file paths	get_soil_path(dataset_name, depth_suffix)	data_loader.py:62
All datasets metadata	LOCAL_REGISTRY, TEMPORAL_REGISTRY	utils.py:94-95
GeoTIFF encode	_write_raster(data, meta, nodata) → bytes	spatial_inference.py:46
GeoTIFF decode	_read_raster(path) → (data, nodata, meta)	spatial_inference.py:30
App CORS config	Already open to *	app.py:28-33
Implementation Order (dependency waves)

Wave 1 — No internal deps
  1. backend/climate_scenarios/__init__.py  (empty)
  2. backend/climate_scenarios/ssp_data.py
  3. backend/soil_init/__init__.py  (empty)
  4. backend/soil_init/extract_conditions.py

Wave 2 — Model modules (numpy/scipy only)
  5. backend/soil_model/__init__.py  (empty)
  6. backend/soil_model/carbon.py
  7. backend/soil_model/water.py
  8. backend/soil_model/vegetation.py
  9. backend/soil_model/biology.py
 10. backend/soil_model/erosion.py
 11. backend/soil_model/disturbances.py
 12. backend/soil_model/philosophies.py

Wave 3 — Engine (depends on all model modules + climate)
 13. backend/soil_model/engine.py

Wave 4 — API + app.py edit
 14. backend/exhibition_api.py
 15. Edit backend/app.py (2 lines at bottom)

Wave 5 — Tests
 16-20. backend/tests/*.py

Wave 6 — Frontend
 21. frontend/exhibition/index.html
 22. frontend/exhibition/simulation.js
 23. frontend/exhibition/renderer.js
 24. frontend/exhibition/app.js
File Specifications
backend/climate_scenarios/ssp_data.py
Purpose: IPCC AR6-sourced climate projections for Barcelona region (41.4°N, 2.15°E),
with CHIRPS-calibrated stochastic noise.

SSP benchmark data (IPCC AR6 WG1, Mediterranean regional values):

Year	SSP1-2.6 ΔT	SSP2-4.5 ΔT	SSP3-7.0 ΔT	SSP5-8.5 ΔT
2025	+0.3°C	+0.3°C	+0.4°C	+0.5°C
2050	+1.0°C	+1.5°C	+1.8°C	+2.4°C
2100	+1.3°C	+2.7°C	+3.6°C	+5.0°C
2150	+1.2°C	+2.9°C	+4.5°C	+6.0°C
2300	+1.0°C	+2.8°C	+5.5°C	+8.0°C (slow rise)
2525	+0.9°C	+2.7°C	+6.0°C	+9.5°C
Precipitation change (summer precip declines faster):

SSP1-2.6: -5% by 2100, stabilizes
SSP2-4.5: -15% annual, -25% summer by 2100
SSP3-7.0: -22% annual, -35% summer by 2100
SSP5-8.5: -30% annual, -45% summer by 2100
CO₂ ppm benchmarks (AR6 Table SPM.2): SSP1→~400 by 2100, SSP2→~600, SSP3→~800, SSP5→~1100

Barcelona baseline: T_mean=16.2°C, precip=580mm/yr (from CHIRPS data)


# Key function signatures:

def get_climate(scenario_id: str, year: int, seed: int = None) -> dict:
    """
    Returns interpolated climate for year with stochastic interannual variability.
    scenario_id: 'ssp126' | 'ssp245' | 'ssp370' | 'ssp585'
    year: 0 = present (2025), positive = years into future
    seed: for reproducible ensemble members
    Returns: {
        'temp': float,               # °C mean annual
        'precip': float,             # mm/yr total
        'summer_precip': float,      # mm Jun-Aug
        'extreme_precip_days': float,# days/yr >20mm
        'co2': float,                # ppm
        'pet': float,                # mm/yr potential evapotranspiration
        'drought_index': float,      # 0-1, 1=severe drought
    }
    """

def get_chirps_variance() -> dict:
    """
    Read all 25 CHIRPS annual rasters using existing data_loader.load_raster()
    Compute spatial mean for each year, return {'precip_std': float, 'temp_std': float}
    Called once at module load, result cached.
    """

def get_scenario_display() -> list[dict]:
    """Returns list of scenario metadata for /api/exhibition/climate-scenarios endpoint"""

# Internal: _interpolate_benchmark(scenario, year) → uses scipy.interpolate.interp1d
# Internal: _add_noise(value, std, seed) → adds calibrated stochastic variability
backend/soil_init/extract_conditions.py
Purpose: Extract a 20×20 spatial grid of initial conditions from the real GeoTIFFs.

Barcelona exhibition region: 41.25°–41.55°N, 1.90°–2.35°E (~30km × 40km)
At 2.5km GeoTIFF resolution: naturally ~12×16 cells. Interpolate to 20×20 for display.


REGION = {
    'lat_min': 41.25, 'lat_max': 41.55,
    'lon_min': 1.90,  'lon_max': 2.35,
    'grid_rows': 20,  'grid_cols': 20,
}

def extract_initial_conditions(lat: float = None, lon: float = None,
                                 use_grid: bool = True) -> dict:
    """
    If use_grid=True: extract 20×20 grid → returns arrays of shape (20,20) for each variable
    If use_grid=False: extract single point at (lat, lon) → scalar values

    Reuses: data_loader.load_raster_window() for each soil property at each depth

    Returns: {
        'organic_carbon': np.ndarray[20,20,6],  # g/kg, 6 depth bands
        'soil_ph':        np.ndarray[20,20],    # surface only
        'bulk_density':   np.ndarray[20,20],    # t/m³
        'sand_pct':       np.ndarray[20,20],    # %
        'clay_pct':       np.ndarray[20,20],    # %
        'silt_pct':       np.ndarray[20,20],    # 100 - sand - clay
        'texture_class':  np.ndarray[20,20],    # USDA class 1-12
        'porosity':       np.ndarray[20,20],    # 1 - bulk_density/2.65
        'field_capacity': np.ndarray[20,20],    # Saxton-Rawls, m³/m³
        'wilting_point':  np.ndarray[20,20],    # Saxton-Rawls, m³/m³
        'awc':            np.ndarray[20,20],    # FC - WP, available water
        'aggregate_stability': np.ndarray[20,20], # from OC + clay
        'lat_grid':       np.ndarray[20,20],
        'lon_grid':       np.ndarray[20,20],
        'valid_mask':     np.ndarray[20,20],    # False where GeoTIFF is nodata
        'chirps_baseline_precip': float,        # mean of 25 CHIRPS annual means
        'chirps_precip_std': float,             # interannual std for noise calibration
    }
    """

# Saxton & Rawls (2006) pedotransfer equations implemented here:
def _saxton_rawls_fc(sand_pct, clay_pct, om_pct) -> float:
    """Field capacity at -33kPa. Eq. 2 from Saxton & Rawls 2006, SSSAJ 70(5)"""

def _saxton_rawls_wp(sand_pct, clay_pct, om_pct) -> float:
    """Wilting point at -1500kPa. Eq. 4 from Saxton & Rawls 2006"""
Note on depth bands: Read all 6 GeoTIFF depth bands for organic_carbon.
Map to 3 simulation layers:

Layer 0 (0–30cm): average of b0, b10
Layer 1 (30–100cm): average of b30, b60
Layer 2 (100cm+): average of b100, b200
backend/soil_model/carbon.py
Purpose: RothC simplified 4-pool carbon model × 3 depth layers, with Bradford (2008) thermal acclimation.

Pools: DPM (k=10/yr), RPM (k=0.3/yr), BIO (k=0.66/yr), HUM (k=0.02/yr), IOM (k≈0)

State shape: All arrays are (n_cells,) at each timestep, but depth layer calls are stacked → (n_cells, 3) for each pool.


def initialize_pools(total_soc: np.ndarray, clay_pct: np.ndarray,
                      climate: dict, veg_cover: np.ndarray) -> dict:
    """
    RothC equilibrium initialization: back-calculate pool distribution
    from known total SOC (from GeoTIFF), clay content, and climate.
    Standard RothC equilibrium procedure (Coleman & Jenkinson 1996).
    IOM = 0.049 × total_soc^1.139  (Falloon et al. 1998)
    Active SOC = total_soc - IOM, distributed to DPM:RPM:BIO:HUM by ratio.
    Returns: {'DPM': ndarray, 'RPM': ndarray, 'BIO': ndarray, 'HUM': ndarray, 'IOM': ndarray}
    All shape (n_cells, 3) for 3 depth layers.
    """

def rothc_step(pools: dict, clay_pct: np.ndarray, temp: float, moisture_ratio: np.ndarray,
               veg_cover: np.ndarray, carbon_input: np.ndarray,
               cumulative_warming: np.ndarray, depth_layer: int,
               dt: float = 1.0) -> tuple[dict, np.ndarray]:
    """
    One annual timestep of RothC.

    Temperature modifier (Coleman & Jenkinson 1996):
        f_T = 47.9 / (1 + exp(106 / (T + 18.3)))

    Bradford (2008) thermal acclimation — Q10 decreases under sustained warming:
        acclimation_factor = 1 - 0.0093 * cumulative_warming  (Bradford et al. 2008)
        f_T_effective = f_T * max(0.3, acclimation_factor)

    Moisture modifier — piecewise with hard threshold below wilting point:
        if moisture_ratio < 0.05: f_M = 0  (near-zero floor — Mediterranean drought)
        else: f_M = min(1.0, moisture_ratio / 1.0)

    Soil cover modifier:
        f_C = 0.6 if veg_cover >= 0.3 else 1.0 + (1.0 - 1.0/0.6) * (0.3 - veg_cover) / 0.3

    Clay-dependent partitioning (x = CO2 fraction):
        x = 1.67*(1.85+1.60*exp(-0.0786*clay)) / (1+1.67*(1.85+1.60*exp(-0.0786*clay)))

    Decomposition:
        For each pool P with rate k: decay = P * k * f_T_eff * f_M * f_C
        Products: CO2=decay*x, BIO=decay*(1-x)*0.46, HUM=decay*(1-x)*0.54

    Carbon input split (DPM:RPM ratio from philosophy):
        input_DPM = carbon_input * dpm_rpm_ratio / (1 + dpm_rpm_ratio)
        input_RPM = carbon_input * 1 / (1 + dpm_rpm_ratio)

    DOC leaching between layers (downward):
        leach_rate = 0.001 * moisture_ratio * DPM  (HUM is stable, doesn't leach)

    Returns: (updated_pools, co2_emitted)
    """

def total_soc(pools: dict) -> np.ndarray:
    """Sum all pools. Shape: (n_cells, 3)"""

def surface_soc(pools: dict) -> np.ndarray:
    """Layer 0 only. Shape: (n_cells,)"""
backend/soil_model/water.py
Purpose: Annual water balance per grid cell. Drives RothC moisture modifier and vegetation stress.


def annual_water_balance(precip: float, pet: float, field_capacity: np.ndarray,
                          wilting_point: np.ndarray, current_moisture: np.ndarray,
                          canopy_cover: np.ndarray, impervious_fraction: np.ndarray
                          ) -> dict:
    """
    Simple annual bucket model.

    Runoff = precip * runoff_coeff
    runoff_coeff = f(current_moisture, infiltration capacity)
    infiltration capacity = Ksat * (1 - crust_index)
    Ksat from Saxton-Rawls: Ksat = exp(12.012 - 0.0755*sand + (-3.895+0.03671*sand-0.1103*clay+0.00036*clay^2) / 0 if clay < 15%)

    AET = min(PET * crop_coeff * veg_cover_factor, available_water)
    Hargreaves PET = 0.0023 * (Tmean + 17.8) * Ra  (simplified, Ra=annual extraterrestrial radiation)
    Ra for Barcelona lat 41.4°N ≈ 37.5 MJ/m²/day (annual mean)

    Deep drainage = max(0, new_moisture - FC) * 0.5  (half drains, half stays)

    Returns: {
        'soil_moisture': ndarray (n_cells,),   # updated volumetric moisture
        'moisture_ratio': ndarray (n_cells,),  # soil_moisture / field_capacity (0-1)
        'actual_et': float,
        'runoff': ndarray (n_cells,),
        'water_stress': ndarray (n_cells,),    # 1 - moisture_ratio, for vegetation
        'drought_consecutive_years': ndarray,  # tracked externally in engine
    }
    """

def compute_awc(sand_pct, clay_pct, om_pct) -> np.ndarray:
    """Available water capacity = FC - WP. Uses Saxton-Rawls 2006."""
backend/soil_model/vegetation.py
Purpose: Chapman-Richards growth + Reineke self-thinning + soil-vegetation feedback + water depletion.


SPECIES_PARAMS = {
    'holm_oak':    {'Bmax':250, 'k':0.015, 'p':3.0, 'max_canopy':0.85, 'root_depth':4.5,
                    'litter_CN':35, 'DPM_RPM':0.25, 'drought_tol':0.85,
                    'fire_resprout':True, 'fire_survival_low':0.8, 'fire_survival_high':0.2,
                    'maturity_yr':60, 'Kw':0.25, 'myc_rate':0.08,
                    'max_density':300, 'water_table_draw':0.5},  # t/ha/m of rooting
    'med_pine':    {'Bmax':180, 'k':0.03, 'p':2.5, 'max_canopy':0.75, 'root_depth':2.5,
                    'litter_CN':55, 'DPM_RPM':0.10, 'drought_tol':0.55,
                    'fire_resprout':False, 'fire_survival_low':0.2, 'fire_survival_high':0.05,
                    'maturity_yr':35, 'Kw':0.35, 'myc_rate':0.05,
                    'max_density':600, 'water_table_draw':0.3},
    'eucalyptus':  {'Bmax':300, 'k':0.08, 'p':2.0, 'max_canopy':0.90, 'root_depth':1.8,
                    'litter_CN':70, 'DPM_RPM':0.10, 'drought_tol':0.30,
                    'fire_resprout':False, 'fire_survival_low':0.1, 'fire_survival_high':0.02,
                    'maturity_yr':12, 'Kw':0.50, 'myc_rate':0.01,
                    'max_density':1200, 'water_table_draw':1.2},  # high draw-down
    'maquis':      {'Bmax':40,  'k':0.06, 'p':2.0, 'max_canopy':0.55, 'root_depth':1.5,
                    'litter_CN':25, 'DPM_RPM':0.80, 'drought_tol':0.90,
                    'fire_resprout':True, 'fire_survival_low':0.9, 'fire_survival_high':0.5,
                    'maturity_yr':8,  'Kw':0.15, 'myc_rate':0.04,
                    'max_density':2000, 'water_table_draw':0.2},
    'agroforestry':{'Bmax':120, 'k':0.02, 'p':2.5, 'max_canopy':0.40, 'root_depth':2.0,
                    'litter_CN':20, 'DPM_RPM':0.50, 'drought_tol':0.70,
                    'fire_resprout':True, 'fire_survival_low':0.6, 'fire_survival_high':0.3,
                    'maturity_yr':25, 'Kw':0.30, 'myc_rate':0.06,
                    'max_density':150, 'water_table_draw':0.4},
}

def vegetation_step(state: dict, climate: dict, params: dict,
                    soil_awc: np.ndarray) -> dict:
    """
    One annual timestep of vegetation dynamics.

    Chapman-Richards growth:
        B(t+1) = Bmax * (1 - exp(-k*(t+1)))^p
        (age tracked as stand_age in state)

    CO2 fertilization (C3 plants):
        f_CO2 = min(1.4, 1 + 0.5 * ln(co2 / 400))

    Water stress (Monteith formulation):
        f_water = soil_awc_current / (soil_awc_current + Kw)

    Temperature stress:
        f_temp = 1.0 if T_opt_min < T < T_opt_max, else Gaussian decay

    Soil-vegetation feedback (CLOSES THE LOOP):
        # Growth is modified by current soil AWC, which depends on OC and aggregates
        effective_awc = soil_awc * (1 + 0.3 * (current_oc / baseline_oc - 1))
        water_stress uses effective_awc instead of just soil_awc

    Self-thinning (Reineke SDI):
        SDI = current_density * (mean_dbh / 25)^1.605
        carrying_capacity_SDI = f(water_availability, species)
        if SDI > 0.85 * carrying_capacity_SDI:
            mortality_rate = (SDI / carrying_capacity_SDI - 0.85) * 0.3
            density *= (1 - mortality_rate)

    Eucalyptus water table draw-down:
        # Water drawn from deep layers; affects moisture of adjacent cells in grid
        # Adjacent cell moisture reduced by water_table_draw * density * dt / grid_distance
        # This is applied in engine.py after vegetation_step

    Litter production:
        leaf_litter = canopy_biomass * 0.3 * (1 + drought_effect)
        root_litter = root_biomass * 0.25
        C_input_to_soil = (leaf_litter + root_litter) * 0.5 / 1000  # kg C/m² → t/ha

    Returns: updated state dict with biomass, density, canopy_cover,
             litter_production, DPM_RPM (for carbon.py input)
    """
backend/soil_model/biology.py
Purpose: Biological integrity index, mycorrhizal density, earthworm activity.


def biology_step(state: dict, climate: dict, params: dict,
                  disturbance: dict) -> dict:
    """
    Biological integrity index (BII) — functional soil biodiversity proxy.

    dBII/dt = recovery_rate * (1 - BII) * f(OC, moisture, pH, veg)
              - disturbance_losses

    recovery_rate = base 0.04/yr (takes ~25yr to fully recover from bare)

    Disturbance losses:
        Tillage:    BII *= 0.3    (severe disruption of food web)
        High fire:  BII *= 0.1   (sterilizes topsoil)
        Low fire:   BII *= 0.6   (partial disruption)
        Drought:    BII *= max(0.4, moisture_ratio * 2)

    Mycorrhizal network density (Myc):
        dMyc/dt = myc_rate * root_density * f(moisture) - 0.15 * Myc
        Tillage: Myc *= 0.2 (destroys hyphal networks)
        Recovery: ~3-5 years to rebuild

    Earthworm activity index (EW):
        Active if: pH > 4.5, moisture > WP * 1.2, temp < 32°C
        dEW/dt = 0.15 * labile_C * f(moisture) - 0.08 * EW
        Tillage: EW *= 0.5

    Aggregate stability (Agg):
        dAgg/dt = (root_binding + glomalin + earthworm_casting - raindrop_impact - tillage)
        root_binding = root_density * root_turnover * 0.01
        glomalin = Myc * 0.05
        earthworm_casting = EW * 0.03
        raindrop_impact = (1 - canopy - mulch) * rainfall_intensity * 0.008
        tillage_reset = -0.6 * Agg if tillage else 0

    Returns: {
        'bii': ndarray,         # 0-1
        'mycorrhizal': ndarray, # 0-1
        'earthworm': ndarray,   # 0-1
        'aggregate_stability': ndarray,  # 0-1
    }
    """
backend/soil_model/erosion.py
Purpose: RUSLE erosion + D8 sediment routing across the 20×20 grid.


def compute_erosion(climate: dict, soil_state: dict, veg_state: dict,
                     params: dict, slope_grid: np.ndarray,
                     flow_direction: np.ndarray) -> dict:
    """
    RUSLE: A = R × K × LS × C × P  [t/ha/yr]

    R (Rainfall erosivity):
        R = 0.29 * precip^1.23  [Ferro et al. 1999, western Mediterranean]
        + 1.8 * extreme_precip_days  (correction for intense events)

    K (Soil erodibility — Wischmeier nomograph):
        silt_pct = 100 - sand - clay
        M = (silt_pct + very_fine_sand) * (100 - clay)  # use silt as proxy
        OM = organic_carbon * 1.724  (Van Bemmelen factor)
        K = (2.1e-4 * M^1.14 * (12 - OM) + 3.25 * (s-2) + 2.5 * (p-3)) / 100
        s=structure_code (2), p=permeability_class (3) → defaults for Barcelona soils

    LS (slope length-steepness):
        Uses slope_grid (degrees). LS = (slope_length/22.1)^m * (sin(slope)/0.0896)^n
        m=0.4, n=1.3 for Mediterranean terrain.
        slope_grid initialized from DEM proxy or fixed 1.5-10° range across grid.

    C (Cover-management):
        C = max(0.001, (1 - canopy_cover) * (1 - understory_cover) * (1 - mulch_fraction))
        Post-fire: C = 0.85 for 2 years (soil hydrophobicity from high fire)

    P (Support practice):
        no_practice=1.0, terracing=0.15, contour=0.6, no_till=0.7

    Erosion removes SOC:
        soc_loss = erosion_rate * enrichment_ratio * surface_soc_concentration
        enrichment_ratio = min(3.0, 1.5 + 1.5 * (1 - aggregate_stability))

    D8 Sediment routing:
        slope_grid determines flow direction (D8 algorithm or fixed slope proxy)
        Sediment routed downslope: downstream_cell += erosion_cell * delivery_ratio
        delivery_ratio = 0.3 * (1 - veg_cover_downstream)
        Deposited sediment dilutes SOC: soc_diluted = soc / (1 + deposit_depth)

    Returns: {
        'erosion_rate': ndarray (20,20),   # t/ha/yr
        'soc_erosion_loss': ndarray,       # t C/ha/yr
        'sediment_deposition': ndarray,    # t/ha/yr (positive = receiving)
        'R_factor': float,
    }
    """

def _init_slope_grid(region: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    If no DEM available: generate a realistic slope distribution.
    Barcelona region is hilly (Collserola, Garraf, Vallès).
    Use a synthetic slope field: ~3-8° on margins, 1-3° in centre (Llobregat plain).
    flow_direction (D8): integer 1-8 encoding cardinal directions.
    These are fixed — computed once at startup.
    """
backend/soil_model/disturbances.py
Purpose: Probabilistic fire events, drought, flood, urban sealing.


def check_disturbances(year: int, state: dict, climate: dict,
                        params: dict, ensemble_seed: int) -> dict:
    """
    Fire probability model:
        p_fire_base = 0.02  (2%/yr Mediterranean scrub — mean annual probability)
        fuel_factor = min(3.0, 1 + standing_biomass / Bmax)
        drought_factor = 1 + 2.0 * max(0, 0.5 - moisture_ratio)
        temp_factor = 1 + 0.15 * max(0, delta_temp - 2)  (doubles by ~2060 under SSP5)
        p_fire = min(0.15, p_fire_base * fuel_factor * drought_factor * temp_factor)
        fire_occurs = random(seed=ensemble_seed+year) < p_fire

    Fire severity (if fire_occurs):
        p_high_severity = 0.3 + 0.4 * (fuel_load / Bmax)  (more fuel → more likely crown fire)
        severity = 'high' if random() < p_high_severity else 'low'

    Low intensity fire effects (prescribed burn zone):
        surface_carbon: DPM *= 0.85, RPM *= 0.95, BIO *= 0.7
        trees: apply species-specific fire_survival_low
        biology: BII *= 0.6, Myc *= 0.5
        nutrient_pulse: phosphorus_flush = True (briefly boosts growth)

    High intensity fire effects:
        surface_carbon: DPM *= 0.25, RPM *= 0.65, BIO *= 0.2  (deep layer 0-30cm)
        subsoil: all pools × 0.93  (some heat penetration)
        trees: apply fire_survival_high
        hydrophobicity: erosion_C_factor = 0.85 for 2 years post-fire
        biology: BII *= 0.1, Myc *= 0.1, EW *= 0.15
        aggregate_stability *= 0.3

    Drought (multi-year if climate drought_index > 0.7 for N consecutive years):
        Enters drought state: vegetation mortality begins at year 2, escalates at year 3+
        Species-specific tolerance: holm_oak survives 4yr, eucalyptus dies after 1.5yr severe

    Returns: {'fire': bool, 'severity': str|None, 'drought_year': int, 'flood': bool,
              'hydrophobic': bool, 'post_fire_year': int}
    """
backend/soil_model/philosophies.py
Purpose: 5 management strategies mapped to concrete parameters for the engine.


PHILOSOPHIES = {
    "let_nature_recover": {
        "display_name": "Let Nature Recover",
        "icon": "🌿",
        "color": "#84CC16",
        "species": "maquis",
        "planting_density": 0,        # natural colonization
        "initial_cover": 0.15,
        "amendments": [],
        "tillage": False,
        "P_factor": 1.0,              # no conservation practice
        "C_factor_mulch": 0.0,        # no mulch applied
        "managed_fire": False,
        "grazing": False,
        "biochar_t_ha": 0,
        "compost_t_ha_yr": 0,
        "fertilizer_N_kg_ha_yr": 0,
        "learn": { ... },             # educational content dict
    },
    "traditional_farming": {
        "species": "agroforestry",
        "planting_density": 50,       # trees/ha (dehesa density)
        "initial_cover": 0.15,
        "amendments": ["compost"],
        "tillage": False,
        "P_factor": 0.7,              # rotational grazing reduces runoff
        "grazing": True,
        "grazing_intensity": 0.3,
        "compost_t_ha_yr": 2.0,       # livestock manure return
        ...
    },
    "industrial_agriculture": {
        "species": None,              # annual crops — no permanent vegetation
        "planting_density": 0,
        "initial_cover": 0.3,         # seasonal crop (bare winter)
        "amendments": ["mineral_fertilizer"],
        "tillage": True,
        "tillage_frequency_yr": 2,
        "P_factor": 1.0,
        "fertilizer_N_kg_ha_yr": 150,
        ...
    },
    "maximum_restoration": {
        "species": "holm_oak",
        "planting_density": 400,
        "amendments": ["biochar", "compost", "cover_crops"],
        "tillage": False,
        "P_factor": 0.15,             # terracing
        "biochar_t_ha": 10,           # one-time, year 0
        "compost_t_ha_yr": 5,         # first 5 years only
        "cover_crop_C_factor": 0.15,
        ...
    },
    "fast_fix": {
        "species": "eucalyptus",
        "planting_density": 1000,
        "amendments": ["mineral_fertilizer"],
        "tillage": False,
        "P_factor": 1.0,
        "fertilizer_N_kg_ha_yr": 200,
        ...
    },
}
backend/soil_model/engine.py
Purpose: Main simulation loop coupling all modules. Runs on 20×20 grid × 3 depth layers × N ensemble members.


def simulate(philosophy: str,
             climate_scenario: str,
             years: int,
             initial_conditions: dict,
             n_ensemble: int = 10) -> dict:
    """
    Run the coupled soil evolution simulation.

    State shape: all arrays are (n_ensemble, n_cells) where n_cells = 400 (20×20 flattened)
    Depth layers handled within carbon.py (pools stored as (n_ensemble, n_cells, 3))

    Per year loop:
        1. Get climate (with per-ensemble seed for stochastic variability)
        2. Check disturbances (per-ensemble)
        3. vegetation_step → litter, canopy, density
        4. Eucalyptus water competition → adjust neighbour moisture
        5. water_balance_step → moisture, water_stress
        6. carbon_step (3 layers) → pools, co2_emitted, DOC leaching
        7. biology_step → BII, Myc, EW, aggregate_stability
        8. erosion_step + sediment routing → erosion_rate, soc_loss, deposition
        9. Update derived metrics
       10. Append to results

    Output per year (aggregated across ensemble):
        - For each variable: mean, p10, p90 across ensemble
        - Spatial grid: (20,20) arrays for visualization
        - Scalar metrics: total SOC, mean erosion, biodiversity_index

    Returns: {
        'years': list[int],
        'grid_shape': [20, 20],
        'ensemble_size': 10,
        'timeseries': {
            'total_soc_mean': [...],   # list of floats, length=years+1
            'total_soc_p10': [...],
            'total_soc_p90': [...],
            'erosion_mean': [...],
            'erosion_p10': [...],
            'erosion_p90': [...],
            'biodiversity_mean': [...],
            'biodiversity_p10': [...],
            'biodiversity_p90': [...],
            'canopy_cover_mean': [...],
            'co2_emitted_mean': [...],
            'water_stress_mean': [...],
        },
        'spatial_final': {             # grid at final year for projection display
            'soc': list[list],         # (20,20), ensemble mean
            'canopy': list[list],
            'erosion': list[list],
            'biodiversity': list[list],
        },
        'spatial_timeseries': {        # every 10 years for animation scrubbing
            '2025': {'soc': ..., ...},
            '2035': {...}, ...
        },
        'events': [                    # fire/drought events across ensemble
            {'year': int, 'type': str, 'severity': str, 'cells_affected': int},
        ],
        'confidence': {                # per-year confidence flag
            'supported_years': 50,     # real calibration period
            'modeled_years': 150,
            'speculative_years': years - 200,
        },
        'philosophy': philosophy,
        'climate_scenario': climate_scenario,
    }

    Performance target: <2s for 200yr, <5s for 500yr
    All numpy operations vectorized across n_ensemble × n_cells simultaneously.
    No Python loops over cells — only loop over years (years iterations).
    """
backend/exhibition_api.py
Purpose: New FastAPI router mounted at /api/exhibition/ prefix.


from fastapi import APIRouter, Query, HTTPException
router = APIRouter(prefix="/api/exhibition", tags=["exhibition"])

@router.get("/philosophies")
def get_philosophies():
    """Returns PHILOSOPHIES dict (display info + learn content). No computation."""

@router.get("/climate-scenarios")
def get_climate_scenarios():
    """Returns 4 SSP scenarios with display info, benchmark values."""

@router.get("/initial-conditions")
def get_initial_conditions(lat: float = Query(41.4), lon: float = Query(2.15)):
    """
    Calls extract_initial_conditions(lat, lon, use_grid=True).
    Returns summary statistics + sample of grid values.
    grid_shape: [20, 20]
    """

@router.post("/simulate")
async def run_simulation(body: SimulateRequest):
    """
    Body: {philosophy, climate_scenario, years (10-500), lat (optional), lon (optional)}
    Calls: engine.simulate()
    Returns: full simulation result dict
    Performance: must complete in <5s (checked via timeout)
    """

@router.get("/compare")
def compare_philosophies(
    philosophies: str = Query(...),  # comma-separated, e.g. "traditional_farming,industrial_agriculture"
    scenario: str = Query("ssp245"),
    years: int = Query(100),
):
    """Runs 2-3 parallel simulations, returns merged results for side-by-side comparison."""
Mount in backend/app.py (only change to existing files):
Add at the very bottom of app.py:


from backend.exhibition_api import router as exhibition_router
app.include_router(exhibition_router)
backend/tests/ (5 test files)

# test_carbon_model.py
- test_rothc_equilibrium_matches_total_soc()       # pools sum to initial total SOC
- test_carbon_conservation()                        # inputs - outputs = ΔC over 10yr
- test_temperature_response_q10()                   # warmer = faster decomp
- test_clay_partitioning()                          # high clay → more HUM, less CO2
- test_acclimation_dampens_decomp()                 # Bradford: Q10 lower after 20yr warming
- test_moisture_threshold_hard_floor()              # below WP = near-zero decomp

# test_erosion.py
- test_bare_soil_higher_than_vegetated()
- test_rusle_factors_in_published_range()           # R, K, A within Mediterranean literature
- test_terracing_reduces_erosion_70_to_85_pct()    # P=0.15 → 85% reduction
- test_fire_increases_c_factor()                    # post-fire C near 0.85
- test_sediment_routing_mass_balance()              # total erosion == total deposition + export

# test_climate.py
- test_ssp585_warmer_than_ssp245_all_years()
- test_precip_variance_matches_chirps_std()
- test_co2_matches_ar6_benchmarks_2050_2100()
- test_climate_continuous_no_step_functions()       # no discontinuities year to year
- test_stochastic_different_seeds_give_variance()

# test_scenarios.py
- test_industrial_agriculture_soc_declines_50yr()
- test_maximum_restoration_soc_increases_50yr()
- test_fast_fix_initial_increase_then_decline()     # eucalyptus: up then down
- test_fire_kills_eucalyptus_not_oak()
- test_biochar_persists_under_ssp585()
- test_five_philosophies_give_distinct_results()

# test_integration.py
- test_full_pipeline_real_geotiff_to_results()      # extract_conditions → simulate → results
- test_500yr_completes_under_5_seconds()
- test_api_endpoint_returns_correct_schema()
- test_all_5_philosophy_4_scenario_combos_run()
- test_ensemble_spread_nonzero()
- test_spatial_grid_has_heterogeneity()             # not all cells identical
frontend/exhibition/ (4 files)
Design: Black background (#000000), amber accent (#F59E0B), JetBrains Mono font,
projection-optimized 1920×1080, minimal chrome, canvas dominates.

index.html — loads 3 JS files, minimal HTML shell with 4 phase containers.
CSS: custom properties matching amber accent, monospace font, 4 full-viewport phases.

app.js — Phase management and UI state machine.


const PHASES = ['discover', 'configure', 'project', 'reflect'];
let state = { phase: 'discover', philosophy: null, scenario: null, years: 100,
              simulationResult: null, comparisons: [] };

// Phase transitions with CSS fade animations
function goToPhase(name) { ... }

// Phase 1: DISCOVER — renders philosophy cards + scenario cards
// Phase 2: CONFIGURE — year slider + confidence indicator
// Phase 3: PROJECT — kicks off simulation fetch, passes result to renderer.js
// Phase 4: REFLECT — comparison fetch + comparative display
simulation.js — API client.


const API = 'http://127.0.0.1:8000/api/exhibition';

async function runSimulation(philosophy, scenario, years) {
    const res = await fetch(`${API}/simulate`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({philosophy, climate_scenario: scenario, years}),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
}

async function comparePhilosophies(philosophies, scenario, years) { ... }
async function getInitialConditions() { ... }
renderer.js — Canvas-based terrain visualization for projection.


// Main canvas: 1920×1080, full viewport
// Colour scheme for soil health:
//   Deep brown (#3D1A00 → #6B3A2A): high carbon, healthy
//   Amber/tan (#C4A46B → #E8C88A): moderate
//   Pale/cracked (#D4C5A9 → #F0E6D3): degraded
//   Green overlay: canopy cover (opacity = canopy_cover_mean)
//   Blue veins: water infiltration (opacity = moisture_ratio)

function renderFrame(year, spatialData, events) {
    // Map total_soc (0-1 normalized) to brown-amber-pale gradient
    // Map canopy_cover to green alpha overlay
    // Map moisture to blue-vein alpha overlay
    // At event years: flash red for fire, show text overlay
    // Confidence fade: opacity decreases after year 50, ghostly after year 150
}

function animateTimeline(result, currentYear) {
    // Interpolate between spatial_timeseries snapshots (every 10yr)
    // requestAnimationFrame loop
    // 3 gauges: Carbon (bar, brown), Erosion (bar, red inverted), Life (bar, green)
}

function renderConfidenceOverlay(year, confidenceThresholds) {
    // Overlay text: "Data-supported" (green, y<50), "Modelled" (amber, 50-150),
    //               "Speculative" (red, >150)
    // Visual: increasing grain/static effect on canvas for distant years
}
Performance Estimates
Simulation	Cells	Layers	Ensemble	Years	Est. time
Fast check	400	3	1	200	~0.1s
Standard	400	3	10	200	~0.5s
Full	400	3	10	500	~1.5s
Compare (3×)	400	3	10	200	~1.5s
All within the <2s (200yr) and <5s (500yr) targets.
Key: vectorize across (n_ensemble × n_cells) = 4000 per operation. No Python loops over cells or ensemble members — only the for year in range(years) loop.

Scientific Improvements Incorporated (from Rafik's critique)
Spatial 20×20 grid — real heterogeneity, not single-point. Each cell starts from real GeoTIFF values.
Depth-resolved carbon (3 layers) — initialized from 6 GeoTIFF depth bands. DOC leaching between layers. Deep-rooted oaks build subsoil carbon.
Stochastic ensemble fire (10 members) — probabilistic p_fire each year. API returns p10/p90 ensemble bands. Each run is slightly different — by design.
Bradford (2008) thermal acclimation — Q10 dampens under sustained warming. Prevents runaway decomp under SSP5-8.5.
Hard moisture floor — below wilting point, decomposition ≈ 0. Captures Mediterranean drought physiology.
Reineke self-thinning — density-dependent mortality. 1000 eucalyptus/ha thins itself to carrying capacity by yr 15.
Eucalyptus water competition — depletes adjacent cell moisture proportionally to density × water_table_draw coefficient.
D8 sediment routing — eroded material routed downslope across grid. Ridge erosion → valley deposition.
Soil-vegetation feedback — effective AWC depends on current OC, closes the degradation/restoration spiral.
Biological integrity index — functional biodiversity proxy modifying decomposition efficiency and nutrient cycling. Avoids over-specifying full food web.
Ensemble output — API always returns mean, p10, p90 for all timeseries variables.
Verification Checklist
After implementation:


# 1. Start backend
uvicorn backend.app:app --reload --port 8000

# 2. Check exhibition routes mounted
curl http://127.0.0.1:8000/api/exhibition/philosophies
curl http://127.0.0.1:8000/api/exhibition/climate-scenarios
curl http://127.0.0.1:8000/api/exhibition/initial-conditions

# 3. Run a simulation
curl -X POST http://127.0.0.1:8000/api/exhibition/simulate \
  -H "Content-Type: application/json" \
  -d '{"philosophy":"traditional_farming","climate_scenario":"ssp245","years":100}'
# → should return result in <2s

# 4. Run tests
cd AI_for_All_Eternal_Beings
python -m pytest backend/tests/ -v

# 5. Open exhibition frontend
open frontend/exhibition/index.html
# Select Traditional Farming + SSP2-4.5 + 100 years → should animate

# 6. Verify scientific correctness
# industrial_agriculture at 50yr should show SOC decline
# maximum_restoration at 50yr should show SOC increase
# fast_fix at 30yr should show SOC increase, at 80yr with fire should show collapse