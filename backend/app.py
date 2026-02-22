import math
import os
from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.ml_models.utils import DATASETS, find_dataset
from backend.ml_models.time_series import time_series_model
from backend.ml_models.prediction import prediction_model
from backend.ml_models.change_detection import change_detection_model
from backend.ml_models.correlation import correlation_model
from backend.ml_models.forecast import forecast_model


app = FastAPI(
    title="OpenLandMap Analytics Backend",
    description="Provides dataset metadata, statistics, and placeholder analytics for the dashboard.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Serve the downloaded GeoTIFFs as static files
DATA_DIR = os.path.join(os.path.dirname(__file__), "data_downloader")
if os.path.isdir(DATA_DIR):
    app.mount("/data", StaticFiles(directory=DATA_DIR), name="local_data")

import ee

try:
    ee.Initialize(project='abm-sim-485823')
except Exception as e:
    print(f"Warning: Earth Engine initialization failed. Error: {e}")

@app.get("/api/map")
def get_map_layer(dataset: str = Query(...)):
    selected = find_dataset(dataset)
    try:
        # Select the first band (e.g., surface 'b0' depth) since palette requires a single band
        image = ee.Image(selected["asset"]).select(0)
        vis_params = selected.get("visualization", {})
        map_id = image.getMapId(vis_params)
        return {
            "dataset": selected["name"],
            "urlFormat": map_id["tile_fetcher"].url_format,
        }
    except Exception as e:
        print(f"Error generating GEE Layer: {e}")
        return {"error": str(e)}

def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


@app.get("/api/status")
def status():
    return {"status": "ok", "timestamp": _now_iso()}


@app.get("/api/local-datasets")
def local_datasets():
    """Scans the data_downloader directory and returns all GeoTIFFs grouped by typology."""
    result = {}
    typologies = ["soil", "climate", "land_cover"]
    for typology in typologies:
        folder = os.path.join(DATA_DIR, typology)
        if not os.path.isdir(folder):
            continue
        files = sorted(f for f in os.listdir(folder) if f.endswith(".tif"))
        result[typology] = [
            {
                "filename": f,
                "url": f"/data/{typology}/{f}",
                # Parse dataset name and band from filename like "Organic_Carbon.b0.tif"
                "dataset": f.rsplit(".", 2)[0],
                "band": f.rsplit(".", 2)[1] if f.count(".") >= 2 else "default",
            }
            for f in files
        ]
    return result


@app.get("/api/datasets")
def list_datasets():
    return {"items": DATASETS}


@app.get("/api/statistics")
def statistics(dataset: str = Query(...), lat: float = 0.0, lon: float = 0.0):
    selected = find_dataset(dataset)
    base = (len(selected["name"]) * 1.2 + abs(lat) + abs(lon)) % 80
    mean = round(base + 12 + math.sin(lat + lon), 2)
    min_value = round(mean - 5 + math.cos(lat - lon), 2)
    max_value = round(mean + 6 + math.sin(lat * 0.3), 2)
    std_dev = round((max_value - min_value) / 3, 2)
    return {
        "dataset": selected["name"],
        "lat": lat,
        "lon": lon,
        "statistics": {"mean": mean, "min": min_value, "max": max_value, "stdDev": std_dev},
        "generated": _now_iso(),
    }


@app.get("/api/analysis/time-series")
def time_series(
    dataset: str = Query(...),
    start_year: int = 2000,
    end_year: int = 2100,
):
    selected = find_dataset(dataset)
    return time_series_model(selected, start_year, end_year)


@app.get("/api/analysis/prediction")
def prediction(
    dataset: str = Query(...),
    start_year: int = Query(...),
    end_year: int = Query(...),
    lat_min: float = Query(...),
    lon_min: float = Query(...),
    lat_max: float = Query(...),
    lon_max: float = Query(...),
):
    selected = find_dataset(dataset)
    return prediction_model(selected, start_year, end_year, lat_min, lon_min, lat_max, lon_max)



@app.get("/api/analysis/change-detection")
def change_detection(
    dataset: str = Query(...),
    year_a: int = 2000,
    year_b: int = 2023,
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
