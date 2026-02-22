"""
Pre-compute 200-year forecasts for all datasets and cache as JSON.
Run automatically after model training completes.

Output: backend/ml_models/saved_models/forecasts_cache.json
"""
import json
import os

CACHE_PATH = os.path.join(os.path.dirname(__file__), "saved_models", "forecasts_cache.json")


def run_all_forecasts(years: int = 200) -> dict:
    """Compute forecasts for every dataset. Returns {dataset_name: forecast_dict}."""
    from backend.ml_models.utils import DATASETS
    from backend.ml_models.forecast import forecast_model

    results = {}
    for ds in DATASETS:
        try:
            result = forecast_model(ds, years=years)
            results[ds["name"]] = result
            print(f"  [forecast] {ds['name']} — {len(result.get('labels', []))} points, model: {result.get('model', '?')}")
        except Exception as exc:
            print(f"  [forecast] {ds['name']} — FAILED: {exc}")
            results[ds["name"]] = {"dataset": ds["name"], "labels": [], "values": [], "model": "error", "units": ds.get("units", "")}
    return results


def save_cache(data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"[forecast cache] Saved {len(data)} forecasts → {CACHE_PATH}")


def load_cache() -> dict | None:
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def refresh_cache(years: int = 200) -> dict:
    """Run all forecasts and overwrite cache. Returns the new cache."""
    data = run_all_forecasts(years)
    save_cache(data)
    return data
