import os
import threading
import warnings
from datetime import datetime

import numpy as np
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from backend.ml_models.utils import (
    DATASETS, find_dataset, primary_band, TEMPORAL_REGISTRY,
    available_years, temporal_primary_band,
)
from backend.ml_models.time_series import time_series_model
from backend.ml_models.forecast import forecast_model
from backend.ml_models.correlation import correlation_model


app = FastAPI(
    title="OpenLandMap Analytics Backend",
    description="Local-data analytics powered by GeoTIFF + scikit-learn ML models.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Static file serving (with CORS headers for cross-origin GeoTIFF fetches) ──
class CORSStaticFiles(StaticFiles):
    """StaticFiles subclass that adds CORS headers so the frontend (port 5500)
    can fetch GeoTIFF binaries from the backend (port 8000) without browser blocks."""
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def cors_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", b"*"))
                headers.append((b"access-control-allow-methods", b"GET, HEAD, OPTIONS"))
                headers.append((b"cache-control", b"public, max-age=3600"))
                message = dict(message, headers=headers)
            await send(message)
        await super().__call__(scope, receive, cors_send)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_downloader")
if os.path.isdir(DATA_DIR):
    app.mount("/data", CORSStaticFiles(directory=DATA_DIR), name="local_data")

try:
    import ee
    ee.Initialize(project="abm-sim-485823")
except Exception as e:
    print(f"Warning: Earth Engine init failed (local-data mode active). {e}")

# ── Training background task ──────────────────────────────────────────────────
_training_lock = threading.Lock()
_training_status: dict = {"status": "idle", "result": {}, "error": None}


def _run_training() -> None:
    global _training_status
    try:
        from backend.ml_models.train import train_all
        result = train_all()
        with _training_lock:
            _training_status = {"status": "done", "result": result, "error": None}
        # Auto-refresh forecast cache after training
        try:
            from backend.ml_models.precompute_forecasts import refresh_cache
            refresh_cache(years=200)
        except Exception as exc:
            print(f"[forecast cache] Post-training refresh failed: {exc}")
    except Exception as exc:
        with _training_lock:
            _training_status = {"status": "error", "result": {}, "error": str(exc)}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── Status & metadata ─────────────────────────────────────────────────────────
@app.get("/api/status")
def status():
    return {"status": "ok", "timestamp": _now_iso()}


@app.get("/api/datasets")
def list_datasets():
    return {"items": DATASETS}


@app.get("/api/local-datasets")
def local_datasets():
    from backend.ml_models.utils import LOCAL_REGISTRY
    result = {}
    for typology in ("soil", "climate", "land_cover"):
        folder = os.path.join(DATA_DIR, typology)
        if not os.path.isdir(folder):
            continue
        flat_files = sorted(f for f in os.listdir(folder) if f.endswith(".tif"))
        entries = [
            {
                "filename": f,
                "url": f"/data/{typology}/{f}",
                "dataset": f.rsplit(".", 2)[0],
                "band": f.rsplit(".", 2)[1] if f.count(".") >= 2 else "default",
                "year": LOCAL_REGISTRY.get(f.rsplit(".", 2)[0], {}).get("year", None),
            }
            for f in flat_files
        ]
        # Include year-based files too
        for entry in sorted(os.listdir(folder)):
            import re
            m = re.match(r'^year=(\d{4})$', entry)
            if not m:
                continue
            year = int(m.group(1))
            year_folder = os.path.join(folder, entry)
            for f in sorted(os.listdir(year_folder)):
                if not f.endswith(".tif"):
                    continue
                entries.append({
                    "filename": f,
                    "url": f"/data/{typology}/year={year}/{f}",
                    "dataset": f.rsplit(".", 2)[0],
                    "band": f.rsplit(".", 2)[1] if f.count(".") >= 2 else "default",
                    "year": year,
                })
        result[typology] = entries
    return result


@app.get("/api/model-status")
def model_status():
    """Returns which saved models exist per dataset (all 5 model types)."""
    from backend.ml_models.utils import LOCAL_REGISTRY
    saved_dir = os.path.join(os.path.dirname(__file__), "ml_models", "saved_models")
    suffixes  = ("ridge", "mlp", "rf", "temporal_ridge", "temporal_mlp", "temporal_rf")
    out: dict[str, dict] = {}
    for name in LOCAL_REGISTRY:
        out[name] = {
            suffix: os.path.isfile(os.path.join(saved_dir, f"{name}_{suffix}.joblib"))
            for suffix in suffixes
        }
    return out


# ── Training ──────────────────────────────────────────────────────────────────
@app.post("/api/train")
def start_training():
    """Kick off background ML training. Returns immediately."""
    with _training_lock:
        if _training_status["status"] == "training":
            return {"status": "already_training"}
        _training_status.update({"status": "training", "result": {}, "error": None})
    t = threading.Thread(target=_run_training, daemon=True)
    t.start()
    return {"status": "training_started"}


@app.get("/api/train/status")
def get_training_status():
    return _training_status


# ── Map layer (local GeoTIFF URL, with optional year for temporal datasets) ────
@app.get("/api/map")
def get_map_layer(dataset: str = Query(...), year: int = Query(None)):
    selected = find_dataset(dataset)
    name     = selected.get("internal_name", "")
    typology = selected.get("typology", "")

    # If a year is requested and we have temporal data for it, use that file
    if year is not None:
        path = temporal_primary_band(name, year)
        if path and os.path.isfile(path):
            filename = os.path.basename(path)
            return {
                "dataset":       selected["name"],
                "internal_name": name,
                "year":          year,
                "localUrl":      f"/data/{typology}/year={year}/{filename}",
                "has_data":      True,
            }

    # Fallback: primary static band
    path = primary_band(selected)
    if not path:
        return {"error": "No local file found for dataset"}
    filename = os.path.basename(path)
    return {
        "dataset":       selected["name"],
        "internal_name": name,
        "year":          None,
        "localUrl":      f"/data/{typology}/{filename}",
        "has_data":      True,
    }



# ── Spatial ML prediction map ─────────────────────────────────────────────────
@app.get("/api/predict-map")
def predict_map_api(
    dataset:    str = Query(...),
    year:       int = Query(2025),
    model_type: str = Query("rf"),
):
    """
    Generate a spatial prediction raster (GeoTIFF) for `dataset` at `year`
    using the specified `model_type` (rf | ridge | mlp | temporal_ridge | temporal_mlp).
    Returns the raw GeoTIFF bytes.
    """
    from backend.ml_models.spatial_inference import predict_map_raster

    selected      = find_dataset(dataset)
    internal_name = selected.get("internal_name", "")
    if not internal_name:
        raise HTTPException(status_code=404, detail="Dataset not found")

    tif_bytes = predict_map_raster(internal_name, year, model_type)
    if not tif_bytes:
        raise HTTPException(
            status_code=404,
            detail=f"No '{model_type}' model available for '{dataset}', or inference failed."
        )
    return Response(content=tif_bytes, media_type="image/tiff")


# ── Available years per dataset ───────────────────────────────────────────────
@app.get("/api/years")
def dataset_years():
    """Return dict of {internal_name: [sorted_years]} for all temporal datasets."""
    return {
        name: sorted(year_data.keys())
        for name, year_data in TEMPORAL_REGISTRY.items()
        if year_data
    }


# ── Cached forecast data ──────────────────────────────────────────────────────
@app.get("/api/forecasts/cached")
def get_cached_forecasts(dataset: str = Query(None)):
    """
    Return pre-computed 200-year forecast(s).
    If `dataset` is given, return only that dataset's forecast.
    Triggers on-demand computation if cache is missing.
    """
    from backend.ml_models.precompute_forecasts import load_cache, refresh_cache
    cache = load_cache()
    if cache is None:
        # First call with no cache — compute now (may take a few seconds)
        cache = refresh_cache(years=200)
    if dataset:
        if dataset not in cache:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' not in forecast cache.")
        return cache[dataset]
    return cache


@app.post("/api/forecasts/refresh")
def refresh_forecasts_endpoint():
    """Trigger a synchronous forecast cache refresh (admin use)."""
    from backend.ml_models.precompute_forecasts import refresh_cache
    data = refresh_cache(years=200)
    return {"refreshed": len(data), "datasets": list(data.keys())}


# ── Year inference: real data or ML prediction ────────────────────────────────
@app.get("/api/infer")
def infer_year(dataset: str = Query(...), year: int = Query(...)):
    """
    Check whether `year` has real downloaded data for `dataset`.
    If yes  → return has_data=True and the GeoTIFF URL.
    If no   → run the temporal ML model and return a predicted value.
    """
    from backend.ml_models.temporal_inference import predict_year

    selected = find_dataset(dataset)
    name     = selected.get("internal_name", "")
    typology = selected.get("typology", "")
    years    = available_years(name)

    if year in years:
        path     = temporal_primary_band(name, year)
        filename = os.path.basename(path) if path else ""
        return {
            "has_data":       True,
            "year":           year,
            "dataset":        dataset,
            "internal_name":  name,
            "available_years": years,
            "local_url":      f"/data/{typology}/year={year}/{filename}" if path else None,
        }

    # No real data for this year — predict with ML
    prediction = predict_year(name, year, years)
    units = selected.get("units", "")
    return {
        "has_data":        False,
        "year":            year,
        "dataset":         dataset,
        "internal_name":   name,
        "available_years": years,
        "units":           units,
        **prediction,
    }


# ── Statistics ────────────────────────────────────────────────────────────────
@app.get("/api/statistics")
def statistics(dataset: str = Query(...), lat: float = 0.0, lon: float = 0.0, year: int = Query(None)):
    selected = find_dataset(dataset)
    name     = selected.get("internal_name", "")
    # For temporal datasets, use the year-specific file when a year is provided
    path = None
    if year is not None:
        path = temporal_primary_band(name, year)
    if not path:
        path = primary_band(selected)
    mean_val = min_val = max_val = std_val = None
    if path and os.path.isfile(path):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", NotGeoreferencedWarning)
                with rasterio.open(path) as src:
                    data = src.read(1, masked=True)
            vals = data.compressed().astype(float)
            if len(vals) > 0:
                mean_val = round(float(np.mean(vals)), 2)
                min_val  = round(float(np.min(vals)),  2)
                max_val  = round(float(np.max(vals)),  2)
                std_val  = round(float(np.std(vals)),  2)
        except Exception as exc:
            print(f"Statistics error: {exc}")
    return {
        "dataset": selected["name"],
        "lat": lat, "lon": lon,
        "statistics": {"mean": mean_val, "min": min_val, "max": max_val, "stdDev": std_val},
        "generated": _now_iso(),
    }


# ── Analysis endpoints (3 distinct, non-redundant models) ─────────────────────
@app.get("/api/analysis/time-series")
def time_series(dataset: str = Query(...), start_year: int = 2000, end_year: int = 2100):
    return time_series_model(find_dataset(dataset), start_year, end_year)


@app.get("/api/analysis/forecast")
def forecast(dataset: str = Query(...), years: int = 100):
    return forecast_model(find_dataset(dataset), years)


@app.get("/api/analysis/correlation")
def correlation(dataset: str = Query(...)):
    return correlation_model(find_dataset(dataset))


