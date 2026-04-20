import os
import threading
from datetime import datetime

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.ml_models.utils import (
    DATASETS, TEMPORAL_REGISTRY, LOCAL_REGISTRY, DATA_DIR,
    find_dataset, primary_band, temporal_primary_band, available_years,
)
from backend.ml_models.time_series import time_series_model
from backend.ml_models.prediction import prediction_model
from backend.ml_models.change_detection import change_detection_model
from backend.ml_models.correlation import correlation_model
from backend.ml_models.forecast import forecast_model
from backend.ml_models.data_loader import load_point_statistics

_SAVED_DIR = os.path.join(os.path.dirname(__file__), "ml_models", "saved_models")

app = FastAPI(
    title="OpenLandMap Analytics Backend",
    description="Soil & environmental analytics powered by real GeoTIFF data and ML.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# GEE — optional; app starts fine without credentials
# ---------------------------------------------------------------------------

GEE_AVAILABLE = False
try:
    import ee
    ee.Initialize(project="abm-sim-485823")
    GEE_AVAILABLE = True
    print("Earth Engine initialised.")
except Exception as _gee_err:
    print(f"Earth Engine unavailable: {_gee_err}")
    print("Local GeoTIFF files will be served directly.")


def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/status")
def status():
    return {
        "status":        "ok",
        "timestamp":     _now_iso(),
        "gee_available": GEE_AVAILABLE,
    }


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

@app.get("/api/datasets")
def list_datasets():
    return {"items": DATASETS}


# ---------------------------------------------------------------------------
# Available years per dataset
# ---------------------------------------------------------------------------

@app.get("/api/years")
def years():
    """Return sorted available years for each temporal dataset."""
    return {
        name: sorted(year_data.keys())
        for name, year_data in TEMPORAL_REGISTRY.items()
    }


# ---------------------------------------------------------------------------
# Local file serving — GeoTIFF bytes served directly
# ---------------------------------------------------------------------------

@app.get("/api/files/{path:path}")
def serve_file(path: str):
    """Serve any file under data_downloader/ by relative path."""
    full_path = os.path.normpath(os.path.join(DATA_DIR, path))
    # Security: ensure path stays within DATA_DIR
    if not full_path.startswith(os.path.normpath(DATA_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return FileResponse(full_path, media_type="image/tiff")


# ---------------------------------------------------------------------------
# Local dataset registry for band selector
# ---------------------------------------------------------------------------

@app.get("/api/local-datasets")
def local_datasets():
    """Return all local files grouped by typology for the file tree."""
    result: dict = {}

    # 1. Static / depth-banded files (soil + single-year climate/land_cover)
    for name, entry in LOCAL_REGISTRY.items():
        typology = entry.get("typology", "other")
        files    = entry.get("local_files", {})
        if typology not in result:
            result[typology] = []
        for band, path in files.items():
            if not os.path.isfile(path):
                continue
            filename = os.path.basename(path)
            rel      = os.path.relpath(path, DATA_DIR).replace("\\", "/")
            result[typology].append({
                "dataset":  name,
                "band":     band,
                "url":      f"/api/files/{rel}",
                "filename": filename,
                "year":     None,
            })

    # 2. Temporal files (year=XXXX sub-folders)
    for name, year_data in TEMPORAL_REGISTRY.items():
        # Determine typology from LOCAL_REGISTRY if available
        typology = LOCAL_REGISTRY.get(name, {}).get("typology", "climate")
        if typology not in result:
            result[typology] = []
        for year, bands in year_data.items():
            for band, path in bands.items():
                if not os.path.isfile(path):
                    continue
                filename = os.path.basename(path)
                rel      = os.path.relpath(path, DATA_DIR).replace("\\", "/")
                result[typology].append({
                    "dataset":  name,
                    "band":     band,
                    "url":      f"/api/files/{rel}",
                    "filename": filename,
                    "year":     int(year),
                })

    return result


# ---------------------------------------------------------------------------
# Map tiles — local GeoTIFF first, GEE fallback
# ---------------------------------------------------------------------------

@app.get("/api/map")
def get_map_layer(dataset: str = Query(...), year: int = Query(None)):
    selected = find_dataset(dataset)
    if not selected:
        return {"error": f"Dataset '{dataset}' not found."}

    internal = selected.get("internal_name", "")

    # 1. Try temporal file for the requested year
    if year is not None:
        band_path = temporal_primary_band(internal, year)
        if band_path and os.path.isfile(band_path):
            rel = os.path.relpath(band_path, DATA_DIR).replace("\\", "/")
            return {"localUrl": f"/api/files/{rel}", "internal_name": internal}

    # 2. Primary static band (soil / composite datasets)
    band_path = primary_band(selected)
    if band_path and os.path.isfile(band_path):
        rel = os.path.relpath(band_path, DATA_DIR).replace("\\", "/")
        return {"localUrl": f"/api/files/{rel}", "internal_name": internal}

    # 3. GEE fallback
    if not GEE_AVAILABLE:
        return {"error": "No local file available and Earth Engine is not initialised."}

    try:
        image      = ee.Image(selected["asset"]).select(0)
        vis_params = selected.get("visualization", {})
        map_id     = image.getMapId(vis_params)
        return {
            "dataset":      selected["name"],
            "internal_name": internal,
            "urlFormat":    map_id["tile_fetcher"].url_format,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Infer: real data for year or ML prediction
# ---------------------------------------------------------------------------

_SOIL_FORECAST_DATASETS = {"Organic_Carbon", "Bulk_Density", "Soil_pH"}


@app.get("/api/infer")
def infer(
    dataset: str   = Query(...),
    year:    int   = Query(...),
    lat:     float = Query(41.40),
    lon:     float = Query(2.15),
    ssp:     str   = Query("ssp245"),
):
    """Return real GeoTIFF data if it exists for `year`, else an ML prediction.

    For Organic_Carbon, Bulk_Density and Soil_pH a RothC process model is used
    instead of the temporal Ridge/MLP fallback chain.
    """
    from backend.ml_models.temporal_inference import predict_year

    selected = find_dataset(dataset)
    if not selected:
        return {"error": f"Dataset '{dataset}' not found."}

    internal        = selected.get("internal_name", "")
    years_with_data = available_years(internal)

    # ── Soil properties: use RothC process model ──────────────────────────────
    if internal in _SOIL_FORECAST_DATASETS:
        from backend.ml_models.soil_forecast import forecast_soil_property
        pred = forecast_soil_property(
            lat=lat, lon=lon,
            target_year=year,
            property_name=internal,
            ssp_scenario=ssp,
        )
        if pred is not None:
            return {
                "has_data":        False,
                "supported":       True,
                "available_years": years_with_data or [],
                "year":            year,
                "units":           selected.get("units", ""),
                **pred,
            }

    # Datasets with no downloaded temporal files have no valid year prediction.
    if not years_with_data:
        return {
            "has_data":        False,
            "supported":       False,
            "available_years": [],
            "year":            year,
            "reason":          "This dataset has no temporal data. Year-based prediction is not available.",
        }

    band_path = temporal_primary_band(internal, year)
    has_data  = bool(band_path and os.path.isfile(band_path))

    if has_data:
        return {
            "has_data":        True,
            "supported":       True,
            "available_years": years_with_data,
            "year":            year,
        }

    pred = predict_year(internal, year, years_with_data)
    return {
        "has_data":        False,
        "supported":       pred.get("supported", True),
        "available_years": years_with_data,
        "year":            year,
        "units":           selected.get("units", ""),
        **pred,
    }


# ---------------------------------------------------------------------------
# Statistics — real raster sampling
# ---------------------------------------------------------------------------

@app.get("/api/statistics")
def statistics(
    dataset: str   = Query(...),
    lat:     float = Query(41.39),
    lon:     float = Query(2.17),
    year:    int   = Query(None),
):
    selected = find_dataset(dataset)
    stats    = load_point_statistics(selected["name"], lat, lon, window_px=5)

    if stats is None:
        return {
            "dataset":    selected["name"],
            "lat":        lat,
            "lon":        lon,
            "statistics": {"mean": None, "min": None, "max": None, "stdDev": None},
            "note":       "Point outside raster coverage.",
            "generated":  _now_iso(),
        }

    return {
        "dataset":    selected["name"],
        "lat":        lat,
        "lon":        lon,
        "statistics": stats,
        "generated":  _now_iso(),
    }


# ---------------------------------------------------------------------------
# Analytics — all responses include labels + values for the frontend
# ---------------------------------------------------------------------------

@app.get("/api/analysis/time-series")
def time_series(
    dataset:    str = Query(...),
    start_year: int = 0,
    end_year:   int = 200,
):
    selected = find_dataset(dataset)
    result   = time_series_model(selected, start_year, end_year)
    points   = result.get("points", [])
    return {
        "dataset":     result.get("dataset", dataset),
        "labels":      [str(p["year"]) for p in points],
        "values":      [p["value"]     for p in points],
        "units":       result.get("units", ""),
        "description": result.get("x_label", "Depth profile"),
    }


@app.get("/api/analysis/prediction")
def prediction(
    dataset:    str   = Query(...),
    start_year: int   = Query(...),
    end_year:   int   = Query(...),
    lat_min:    float = Query(...),
    lon_min:    float = Query(...),
    lat_max:    float = Query(...),
    lon_max:    float = Query(...),
):
    selected = find_dataset(dataset)
    return prediction_model(
        selected, start_year, end_year,
        lat_min, lon_min, lat_max, lon_max,
    )


@app.get("/api/analysis/change-detection")
def change_detection(
    dataset: str = Query(...),
    year_a:  int = 0,
    year_b:  int = 200,
):
    selected = find_dataset(dataset)
    return change_detection_model(selected, year_a, year_b)


@app.get("/api/analysis/correlation")
def correlation(dataset: str = Query(...)):
    selected = find_dataset(dataset)
    result   = correlation_model(selected)
    corr     = result.get("correlation", {})
    return {
        "dataset":        result.get("dataset", dataset),
        "labels":         [k.replace("_", " ").title() for k in corr],
        "values":         list(corr.values()),
        "n_pixels":       result.get("n_pixels", 0),
        "interpretation": "Green = positive correlation · Red = inverse relationship",
    }


@app.get("/api/analysis/forecast")
def forecast(dataset: str = Query(...), years: int = 5):
    selected     = find_dataset(dataset)
    result       = forecast_model(selected, years)

    if "error" in result:
        return {
            "dataset": result.get("dataset", dataset),
            "labels":  [],
            "values":  [],
            "error":   result["error"],
        }

    pts    = result.get("forecast", [])
    labels = [str(p["year"])  for p in pts]
    values = [p["value"]      for p in pts]
    trend  = result.get("trend", {})

    return {
        "dataset":  result.get("dataset", dataset),
        "labels":   labels,
        "values":   values,
        "units":    result.get("units", selected.get("units", "")),
        "model":    f"Linear trend (slope={trend.get('slope', 0):.4f}, R²={trend.get('r_squared', 0):.3f})",
        "baseline": round(values[0], 3) if values else None,
        "subtitle": f"{result.get('x_label', 'Depth (cm)')} · p={trend.get('p_value', 0):.4f}",
        "x_label":  result.get("x_label", "Depth (cm)"),
        "trend":    trend,
    }


# ---------------------------------------------------------------------------
# Pre-computed forecast cache
# ---------------------------------------------------------------------------

@app.get("/api/forecasts/cached")
def forecasts_cached(dataset: str = Query(...)):
    from backend.ml_models.precompute_forecasts import load_cache

    cache = load_cache()
    if cache is None or dataset not in cache:
        raise HTTPException(status_code=404, detail="No cached forecast available.")

    raw  = cache[dataset]
    pts  = raw.get("forecast", [])
    labels = [str(p["year"]) for p in pts]
    values = [p["value"]     for p in pts]
    trend  = raw.get("trend", {})

    return {
        "dataset":  raw.get("dataset", dataset),
        "labels":   labels,
        "values":   values,
        "units":    raw.get("units", ""),
        "model":    f"Linear trend (R²={trend.get('r_squared', 0):.3f})",
        "baseline": round(values[0], 3) if values else None,
        "subtitle": raw.get("x_label", ""),
        "x_label":  raw.get("x_label", ""),
        "trend":    trend,
    }


# ---------------------------------------------------------------------------
# ML spatial prediction map — returns raw GeoTIFF bytes
# ---------------------------------------------------------------------------

@app.get("/api/predict-map")
def predict_map(
    dataset:    str = Query(...),
    year:       int = Query(...),
    model_type: str = Query(...),
):
    from backend.ml_models.spatial_inference import predict_map_raster

    selected = find_dataset(dataset)
    if not selected:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' not found.")

    internal = selected.get("internal_name", "")

    # ridge and mlp used year-as-depth proxy — not a valid temporal prediction.
    if model_type in ("ridge", "mlp"):
        raise HTTPException(
            status_code=400,
            detail=f"Model type '{model_type}' is a depth-band model and cannot produce "
                   f"temporal spatial predictions. Use 'rf', 'temporal_ridge', or 'temporal_mlp'.",
        )

    data = predict_map_raster(internal, year, model_type)

    if data is None:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed for '{dataset}' with model '{model_type}'.",
        )
    return Response(content=data, media_type="image/tiff")


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------

@app.get("/api/model-status")
def model_status():
    result = {}
    for name in LOCAL_REGISTRY:
        result[name] = {
            "ridge":          os.path.isfile(os.path.join(_SAVED_DIR, f"{name}_ridge.joblib")),
            "mlp":            os.path.isfile(os.path.join(_SAVED_DIR, f"{name}_mlp.joblib")),
            "rf":             os.path.isfile(os.path.join(_SAVED_DIR, f"{name}_rf.joblib")),
            "temporal_ridge": os.path.isfile(os.path.join(_SAVED_DIR, f"{name}_temporal_ridge.joblib")),
            "temporal_mlp":   os.path.isfile(os.path.join(_SAVED_DIR, f"{name}_temporal_mlp.joblib")),
            "temporal_rf":    os.path.isfile(os.path.join(_SAVED_DIR, f"{name}_temporal_rf.joblib")),
        }
    return result


# ---------------------------------------------------------------------------
# Model training — runs in background thread
# ---------------------------------------------------------------------------

_train_state: dict = {"status": "idle", "result": None, "error": None}
_train_lock = threading.Lock()


@app.post("/api/train")
def train():
    with _train_lock:
        if _train_state["status"] == "training":
            return {"status": "already_training"}
        _train_state["status"] = "training"
        _train_state["result"] = None
        _train_state["error"]  = None

    def _run():
        from backend.ml_models.train import train_all
        from backend.ml_models.precompute_forecasts import refresh_cache
        try:
            result = train_all()
            refresh_cache()
            with _train_lock:
                _train_state["status"] = "done"
                _train_state["result"] = result
        except Exception as exc:
            with _train_lock:
                _train_state["status"] = "error"
                _train_state["error"]  = str(exc)

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@app.get("/api/train/status")
def train_status():
    with _train_lock:
        return dict(_train_state)


# ---------------------------------------------------------------------------
# Exhibition system
# ---------------------------------------------------------------------------

from backend.exhibition_api import router as exhibition_router
app.include_router(exhibition_router)

# Serve exhibition frontend at /exhibition/
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "exhibition")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/exhibition", StaticFiles(directory=_FRONTEND_DIR, html=True), name="exhibition")
