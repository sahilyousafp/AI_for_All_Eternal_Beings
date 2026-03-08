"""
FastAPI router for the Soil Futures Exhibition System.

Prefix: /api/exhibition/
Mounted in backend/app.py via app.include_router(router).

Endpoints:
  GET  /api/exhibition/philosophies        — list all 5 philosophies
  GET  /api/exhibition/climate-scenarios   — list 4 SSP scenarios
  POST /api/exhibition/simulate            — run full simulation
  GET  /api/exhibition/initial-conditions  — get 20×20 grid data
  GET  /api/exhibition/status              — health check
"""
import time
import traceback

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/exhibition", tags=["exhibition"])


# ── Request / Response models ─────────────────────────────────────────────

class SimulateRequest(BaseModel):
    philosophy:       str = Field(..., description="Philosophy key from /philosophies")
    climate_scenario: str = Field("ssp245", description="SSP scenario ID")
    years:            int = Field(default=50, ge=10, le=100, description="Simulation years (10–100)")
    n_ensemble:       int = Field(default=10, ge=1, le=20, description="Ensemble members")
    lat:              float = Field(default=41.40, ge=40.0, le=43.0)
    lon:              float = Field(default=2.15,  ge=0.0,  le=4.0)


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/status")
def exhibition_status():
    """Health check — confirms exhibition modules are importable."""
    try:
        from backend.soil_model.philosophies import list_philosophies
        from backend.climate_scenarios.ssp_data import get_scenario_display
        n_phil = len(list_philosophies())
        n_scen = len(get_scenario_display())
        return {
            "status":       "ok",
            "philosophies": n_phil,
            "scenarios":    n_scen,
            "ready":        True,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc), "ready": False}


@router.get("/philosophies")
def list_philosophies_endpoint():
    """Return all 5 land management philosophies for the exhibition chooser."""
    from backend.soil_model.philosophies import list_philosophies
    return {"philosophies": list_philosophies()}


@router.get("/climate-scenarios")
def climate_scenarios_endpoint():
    """Return 4 SSP climate scenario options."""
    from backend.climate_scenarios.ssp_data import get_scenario_display
    return {"scenarios": get_scenario_display()}


@router.get("/initial-conditions")
def initial_conditions_endpoint(
    lat: float = Query(default=41.40, ge=40.0, le=43.0),
    lon: float = Query(default=2.15,  ge=0.0,  le=4.0),
):
    """
    Return the 20×20 grid of initial soil conditions from real GeoTIFFs.
    Used by the frontend to display the starting state before simulation.
    Returns serialisable summary statistics (not full arrays).
    """
    try:
        from backend.soil_init.extract_conditions import extract_initial_conditions
        import numpy as np

        ic = extract_initial_conditions(use_grid=True)

        def _safe_mean(arr):
            if arr is None:
                return None
            try:
                return float(np.nanmean(arr))
            except Exception:
                return None

        def _grid_to_list(arr):
            if arr is None:
                return None
            try:
                if arr.ndim == 3:
                    return arr[:, :, 0].tolist()  # surface layer only
                return arr.tolist()
            except Exception:
                return None

        return {
            "grid_shape":          [20, 20],
            "region":              ic.get("region", {}),
            "summary": {
                "mean_oc_surface_g_kg":    round(_safe_mean(ic.get("organic_carbon_layer0")) or 0, 2),
                "mean_bulk_density_t_m3":  round(_safe_mean(ic.get("bulk_density")) or 0, 3),
                "mean_soil_ph":            round(_safe_mean(ic.get("soil_ph")) or 0, 2),
                "mean_clay_pct":           round(_safe_mean(ic.get("clay_pct")) or 0, 1),
                "mean_awc_m3_m3":          round(_safe_mean(ic.get("awc")) or 0, 3),
                "chirps_baseline_precip":  round(ic.get("chirps_baseline_precip", 580.0), 1),
            },
            "spatial": {
                "organic_carbon":      _grid_to_list(ic.get("organic_carbon_layer0")),
                "clay_pct":            _grid_to_list(ic.get("clay_pct")),
                "aggregate_stability": _grid_to_list(ic.get("aggregate_stability")),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"IC extraction failed: {exc}")


@router.post("/simulate")
def simulate_endpoint(req: SimulateRequest):
    """
    Run the full coupled soil simulation.

    Validates philosophy and scenario, extracts initial conditions,
    runs the engine, returns full timeseries + spatial output.

    Response schema:
      years, grid_shape, ensemble_size, timeseries, spatial_final,
      spatial_timeseries, events, confidence, philosophy, climate_scenario,
      runtime_seconds
    """
    from backend.soil_model.philosophies import get_philosophy, PHILOSOPHIES
    from backend.climate_scenarios.ssp_data import get_scenario_display

    # Validate inputs
    valid_philosophies = list(PHILOSOPHIES.keys())
    if req.philosophy not in valid_philosophies:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown philosophy '{req.philosophy}'. "
                   f"Valid options: {valid_philosophies}"
        )

    valid_scenarios = {s["id"] for s in get_scenario_display()}
    if req.climate_scenario not in valid_scenarios:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scenario '{req.climate_scenario}'. "
                   f"Valid options: {sorted(valid_scenarios)}"
        )

    t0 = time.time()
    try:
        from backend.soil_init.extract_conditions import extract_initial_conditions
        from backend.soil_model.engine import simulate

        # Extract initial conditions for the 20×20 Barcelona region
        initial_conditions = extract_initial_conditions(use_grid=True)

        # Run simulation
        result = simulate(
            philosophy=req.philosophy,
            climate_scenario=req.climate_scenario,
            years=req.years,
            initial_conditions=initial_conditions,
            n_ensemble=req.n_ensemble,
        )

        runtime = round(time.time() - t0, 2)
        result["runtime_seconds"] = runtime
        return result

    except Exception as exc:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed: {exc}\n\nTraceback:\n{tb}"
        )
