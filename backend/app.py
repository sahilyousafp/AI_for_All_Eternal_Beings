from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.ml_models.utils import DATASETS, find_dataset
from backend.ml_models.time_series import time_series_model
from backend.ml_models.prediction import prediction_model
from backend.ml_models.change_detection import change_detection_model
from backend.ml_models.correlation import correlation_model
from backend.ml_models.forecast import forecast_model
from backend.ml_models.data_loader import load_point_statistics


app = FastAPI(
    title="OpenLandMap Analytics Backend",
    description="Soil & environmental analytics powered by real GeoTIFF data and ML.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
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
    print("✅ Earth Engine initialised.")
except Exception as _gee_err:
    print(f"⚠️  Earth Engine unavailable: {_gee_err}")
    print("   Map tiles will not load. All other endpoints use local rasters.")


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
# Map tiles (requires GEE)
# ---------------------------------------------------------------------------

@app.get("/api/map")
def get_map_layer(dataset: str = Query(...)):
    if not GEE_AVAILABLE:
        return {"error": "Earth Engine is not initialised. Map tiles unavailable."}

    selected = find_dataset(dataset)
    try:
        image      = ee.Image(selected["asset"]).select(0)
        vis_params = selected.get("visualization", {})
        map_id     = image.getMapId(vis_params)
        return {
            "dataset":   selected["name"],
            "urlFormat": map_id["tile_fetcher"].url_format,
        }
    except Exception as exc:
        print(f"GEE map error: {exc}")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Statistics — real raster sampling
# ---------------------------------------------------------------------------

@app.get("/api/statistics")
def statistics(dataset: str = Query(...), lat: float = 40.4, lon: float = -3.7):
    selected = find_dataset(dataset)
    stats    = load_point_statistics(selected["name"], lat, lon, window_px=5)

    if stats is None:
        return {
            "dataset":    selected["name"],
            "lat":        lat,
            "lon":        lon,
            "statistics": {"mean": None, "min": None, "max": None, "stdDev": None},
            "note":       "Point outside Spain raster coverage.",
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
# Analytics
# ---------------------------------------------------------------------------

@app.get("/api/analysis/time-series")
def time_series(
    dataset:    str = Query(...),
    start_year: int = 0,
    end_year:   int = 200,
):
    selected = find_dataset(dataset)
    return time_series_model(selected, start_year, end_year)


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
    return correlation_model(selected)


@app.get("/api/analysis/forecast")
def forecast(dataset: str = Query(...), years: int = 5):
    selected = find_dataset(dataset)
    return forecast_model(selected, years)
