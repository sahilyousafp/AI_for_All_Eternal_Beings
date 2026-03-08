"""Tests for RUSLE erosion model."""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.soil_model.erosion import compute_erosion, _init_slope_grid


def _make_soil_state(rows=20, cols=20):
    return {
        "sand_pct":            np.full((rows, cols), 40.0),
        "clay_pct":            np.full((rows, cols), 25.0),
        "silt_pct":            np.full((rows, cols), 35.0),
        "organic_carbon":      np.full((rows, cols), 8.0),
        "aggregate_stability": np.full((rows, cols), 0.5),
        "post_fire_year":      0,
    }

def _make_veg_state(cover=0.5, rows=20, cols=20):
    return {"canopy_cover": np.full((rows, cols), cover)}

def _base_climate():
    return {"precip": 580.0, "extreme_precip_days": 4.5, "temp": 16.2, "drought_index": 0.2}

def _base_params():
    return {"P_factor": 1.0, "C_factor_mulch": 0.0}


def test_slope_grid_shape():
    slope, flow = _init_slope_grid({"grid_rows": 20, "grid_cols": 20})
    assert slope.shape == (20, 20)
    assert flow.shape  == (20, 20)


def test_slope_in_realistic_range():
    slope, _ = _init_slope_grid({"grid_rows": 20, "grid_cols": 20})
    assert np.all(slope >= 0.5), "All slopes should be >= 0.5 degrees"
    assert np.all(slope <= 35.0), "All slopes should be <= 35 degrees"


def test_erosion_rate_positive():
    result = compute_erosion(_base_climate(), _make_soil_state(), _make_veg_state(), _base_params())
    assert np.all(result["erosion_rate"] >= 0), "Erosion rate must be non-negative"


def test_high_cover_reduces_erosion():
    """Full canopy cover should give lower erosion than bare soil."""
    result_bare   = compute_erosion(_base_climate(), _make_soil_state(), _make_veg_state(0.0), _base_params())
    result_forest = compute_erosion(_base_climate(), _make_soil_state(), _make_veg_state(0.9), _base_params())
    assert np.mean(result_forest["erosion_rate"]) < np.mean(result_bare["erosion_rate"]), \
        "Forest cover should reduce erosion"


def test_terracing_reduces_erosion():
    params_none     = {"P_factor": 1.0,  "C_factor_mulch": 0.0}
    params_terraced = {"P_factor": 0.15, "C_factor_mulch": 0.0}
    r_none     = compute_erosion(_base_climate(), _make_soil_state(), _make_veg_state(), params_none)
    r_terraced = compute_erosion(_base_climate(), _make_soil_state(), _make_veg_state(), params_terraced)
    assert np.mean(r_terraced["erosion_rate"]) < np.mean(r_none["erosion_rate"]) * 0.5


def test_higher_precip_more_erosion():
    c_dry  = {"precip": 300.0, "extreme_precip_days": 2.0, "temp": 16.2, "drought_index": 0.5}
    c_wet  = {"precip": 900.0, "extreme_precip_days": 8.0, "temp": 16.2, "drought_index": 0.1}
    r_dry  = compute_erosion(c_dry,  _make_soil_state(), _make_veg_state(), _base_params())
    r_wet  = compute_erosion(c_wet,  _make_soil_state(), _make_veg_state(), _base_params())
    assert r_wet["R_factor"] > r_dry["R_factor"], "Higher rainfall → higher R factor"


def test_soc_erosion_loss_bounded():
    result = compute_erosion(_base_climate(), _make_soil_state(), _make_veg_state(), _base_params())
    # SOC loss cannot exceed 10% of total erosion rate
    ratio = result["soc_erosion_loss"] / np.maximum(result["erosion_rate"], 0.01)
    assert np.all(ratio <= 0.11), "SOC erosion loss bounded at 10% of erosion rate"
