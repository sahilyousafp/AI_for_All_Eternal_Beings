"""Tests for SSP climate scenario module."""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.climate_scenarios.ssp_data import (
    get_climate, get_scenario_display, BASELINE_TEMP_C, BASELINE_PRECIP
)


def test_get_climate_returns_required_keys():
    climate = get_climate("ssp245", 0)
    required = {"temp", "precip", "summer_precip", "extreme_precip_days", "co2", "pet", "drought_index"}
    assert required.issubset(set(climate.keys())), f"Missing keys: {required - set(climate.keys())}"


def test_climate_at_year_zero_near_baseline():
    """Year 0 (2025) should be close to baseline."""
    c = get_climate("ssp245", 0, seed=42)
    assert abs(c["temp"] - BASELINE_TEMP_C) < 2.0, f"Temp {c['temp']} far from baseline {BASELINE_TEMP_C}"


def test_warmer_scenario_higher_temp():
    """SSP5-8.5 should always be warmer than SSP1-2.6 at 2100."""
    c_low  = get_climate("ssp126", 75, seed=42)   # 2100
    c_high = get_climate("ssp585", 75, seed=42)
    assert c_high["temp"] > c_low["temp"], "SSP5-8.5 must be warmer than SSP1-2.6"


def test_drier_under_high_emissions_at_2100():
    """SSP5-8.5 should have less precipitation than SSP1-2.6 at 2100."""
    c_low  = get_climate("ssp126", 75, seed=42)
    c_high = get_climate("ssp585", 75, seed=42)
    assert c_high["precip"] < c_low["precip"], "SSP5-8.5 should be drier"


def test_co2_increases_with_emissions():
    c_low  = get_climate("ssp126", 75, seed=42)
    c_high = get_climate("ssp585", 75, seed=42)
    assert c_high["co2"] > c_low["co2"], "Higher emission scenario → higher CO2"


def test_pet_positive():
    for scen in ("ssp126", "ssp245", "ssp370", "ssp585"):
        c = get_climate(scen, 50, seed=1)
        assert c["pet"] > 0, f"PET must be positive for {scen}"


def test_drought_index_bounded():
    for yr in (0, 25, 50, 75):
        c = get_climate("ssp585", yr, seed=0)
        assert 0.0 <= c["drought_index"] <= 1.0, f"Drought index out of [0,1] at year {yr}"


def test_unknown_scenario_defaults_to_ssp245():
    c_unknown = get_climate("ssp999", 50, seed=0)
    c_default = get_climate("ssp245", 50, seed=0)
    assert abs(c_unknown["temp"] - c_default["temp"]) < 1e-6


def test_get_scenario_display_has_four():
    scenarios = get_scenario_display()
    assert len(scenarios) == 4
    ids = {s["id"] for s in scenarios}
    assert ids == {"ssp126", "ssp245", "ssp370", "ssp585"}


def test_seed_reproducibility():
    c1 = get_climate("ssp245", 30, seed=99)
    c2 = get_climate("ssp245", 30, seed=99)
    assert c1["temp"] == c2["temp"] and c1["precip"] == c2["precip"]
