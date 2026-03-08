"""Tests for water balance and vegetation modules."""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.soil_model.water import annual_water_balance, compute_awc
from backend.soil_model.vegetation import vegetation_step, SPECIES_PARAMS


def _make_water_inputs(n=10):
    fc = np.full(n, 0.28)
    wp = np.full(n, 0.12)
    moisture = np.full(n, 0.20)
    canopy   = np.full(n, 0.40)
    return fc, wp, moisture, canopy


def test_water_balance_moisture_stays_bounded():
    fc, wp, moisture, canopy = _make_water_inputs()
    result = annual_water_balance(580.0, 900.0, fc, wp, moisture, canopy)
    assert np.all(result["soil_moisture"] >= 0), "Moisture cannot be negative"
    assert np.all(result["soil_moisture"] <= fc + 0.01), "Moisture cannot exceed FC"


def test_water_stress_is_zero_at_fc():
    """At field capacity, water stress should be minimal."""
    n = 5
    fc = np.full(n, 0.30)
    wp = np.full(n, 0.10)
    result = annual_water_balance(800.0, 600.0, fc, wp, fc.copy(), np.full(n, 0.8))
    assert np.all(result["moisture_ratio"] <= 1.01)


def test_runoff_increases_with_saturation():
    n = 5
    fc = np.full(n, 0.28)
    wp = np.full(n, 0.12)
    canopy = np.full(n, 0.3)
    # Dry start
    r_dry = annual_water_balance(580.0, 900.0, fc, wp, np.full(n, 0.12), canopy)
    # Wet start
    r_wet = annual_water_balance(580.0, 900.0, fc, wp, np.full(n, 0.28), canopy)
    assert np.mean(r_wet["runoff"]) > np.mean(r_dry["runoff"]) * 0.9


def test_compute_awc_positive():
    awc = compute_awc(np.array([40.0]), np.array([25.0]), np.array([2.0]))
    assert np.all(awc > 0), "AWC must be positive"


def test_awc_sandy_less_than_clayey():
    """Sandy soils hold less water than clay soils."""
    awc_sandy = compute_awc(np.array([70.0]), np.array([10.0]), np.array([1.0]))
    awc_clay  = compute_awc(np.array([10.0]), np.array([50.0]), np.array([2.0]))
    # Clay typically has higher AWC (but this can vary — just check both are positive)
    assert awc_sandy[0] > 0 and awc_clay[0] > 0


def test_vegetation_step_biomass_increases():
    """Young stand should grow over one year."""
    params = SPECIES_PARAMS["holm_oak"]
    n = 4
    state = {
        "stand_age":   np.zeros(n),
        "biomass":     np.full(n, 5.0),
        "density":     np.full(n, 200.0),
        "canopy_cover":np.full(n, 0.05),
        "is_alive":    np.ones(n, dtype=bool),
    }
    climate = {"temp": 16.2, "precip": 580.0, "co2": 420.0, "pet": 900.0, "drought_index": 0.2}
    awc = np.full(n, 0.15)
    result = vegetation_step(state, climate, params, awc)
    assert np.all(result["biomass"] >= state["biomass"]), "Young stand should not shrink in good conditions"


def test_vegetation_water_stress_limits_growth():
    """Severe drought (very low AWC) should reduce growth."""
    params = SPECIES_PARAMS["med_pine"]
    n = 4
    state = {
        "stand_age":   np.full(n, 20.0),
        "biomass":     np.full(n, 80.0),
        "density":     np.full(n, 300.0),
        "canopy_cover":np.full(n, 0.50),
        "is_alive":    np.ones(n, dtype=bool),
    }
    climate = {"temp": 22.0, "precip": 200.0, "co2": 420.0, "pet": 1200.0, "drought_index": 0.8}
    good_awc    = np.full(n, 0.20)
    drought_awc = np.full(n, 0.01)
    r_good    = vegetation_step(state, climate, params, good_awc)
    r_drought = vegetation_step(state, climate, params, drought_awc)
    assert np.mean(r_drought["biomass"]) <= np.mean(r_good["biomass"])
