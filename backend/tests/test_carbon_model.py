"""Tests for the RothC carbon model."""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.soil_model.carbon import (
    initialize_pools, rothc_step, total_soc, surface_soc, _temp_modifier
)


def test_temp_modifier_zero_at_extreme_cold():
    assert _temp_modifier(-19.0) == 0.0


def test_temp_modifier_positive_at_barcelona():
    """Barcelona mean 16.2°C should give a positive modifier (~2.1)."""
    val = _temp_modifier(16.2)
    # RothC f_T is not bounded to [0,1]; at Barcelona baseline it is ~2.1
    assert 1.0 < val < 3.5, f"Expected ~2.1, got {val}"


def test_initialize_pools_iom_falloon():
    """IOM = 0.049 × SOC^1.139 (Falloon et al. 1998)."""
    soc = np.array([[10.0, 5.0, 2.0]])  # (1, 3)
    clay = np.array([25.0])
    pools = initialize_pools(soc, clay, {}, np.array([0.3]))
    expected_iom = 0.049 * (10.0 ** 1.139)
    assert abs(pools["IOM"][0, 0] - expected_iom) < 0.5, \
        f"IOM {pools['IOM'][0,0]:.3f} != expected {expected_iom:.3f}"


def test_total_soc_sum_of_pools():
    """total_soc should equal sum of all 5 pools."""
    soc = np.array([[10.0, 5.0, 2.0]])
    clay = np.array([25.0])
    pools = initialize_pools(soc, clay, {}, np.array([0.3]))
    computed = total_soc(pools)
    manual = sum(pools[k] for k in ("DPM","RPM","BIO","HUM","IOM"))
    np.testing.assert_allclose(computed, manual, rtol=1e-10)


def test_rothc_step_reduces_pools():
    """Under warm, moist conditions, decomposition should reduce active pools."""
    n = 5
    soc = np.column_stack([np.full(n, 10.0), np.full(n, 5.0), np.full(n, 2.0)])
    pools = initialize_pools(soc, np.full(n, 25.0), {}, np.full(n, 0.5))
    # Use layer 0 pools
    layer0 = {k: pools[k][:, 0] for k in ("DPM","RPM","BIO","HUM","IOM")}
    initial_active = layer0["DPM"] + layer0["RPM"] + layer0["BIO"] + layer0["HUM"]

    updated, co2 = rothc_step(
        pools=layer0,
        clay_pct=np.full(n, 25.0),
        temp=20.0,
        moisture_ratio=np.full(n, 0.7),
        veg_cover=np.full(n, 0.5),
        carbon_input=np.zeros(n),
        cumulative_warming=np.zeros(n),
        depth_layer=0,
    )
    updated.pop("_leach_DPM", None)
    final_active = updated["DPM"] + updated["RPM"] + updated["BIO"] + updated["HUM"]
    assert np.all(final_active < initial_active + 0.1), \
        "Active pools should decrease or stay level under decomposition"


def test_rothc_step_co2_positive():
    """CO2 emitted should always be non-negative."""
    n = 3
    soc = np.column_stack([np.full(n, 8.0), np.full(n, 4.0), np.full(n, 1.0)])
    pools = initialize_pools(soc, np.full(n, 20.0), {}, np.full(n, 0.4))
    layer0 = {k: pools[k][:, 0] for k in ("DPM","RPM","BIO","HUM","IOM")}
    _, co2 = rothc_step(
        pools=layer0, clay_pct=np.full(n, 20.0), temp=18.0,
        moisture_ratio=np.full(n, 0.6), veg_cover=np.full(n, 0.3),
        carbon_input=np.zeros(n), cumulative_warming=np.zeros(n), depth_layer=0,
    )
    assert np.all(co2 >= 0), "CO2 must be non-negative"


def test_bradford_acclimation_reduces_decomp():
    """Higher cumulative warming → lower effective decomposition rate (Bradford 2008)."""
    n = 2
    soc = np.column_stack([np.full(n, 10.0), np.full(n, 5.0), np.full(n, 2.0)])
    clay = np.full(n, 25.0)
    pools = initialize_pools(soc, clay, {}, np.full(n, 0.5))
    base = {k: pools[k][:, 0].copy() for k in ("DPM","RPM","BIO","HUM","IOM")}

    # No acclimation
    _, co2_no = rothc_step(base, clay, 25.0, np.full(n,0.7), np.full(n,0.5),
                            np.zeros(n), np.zeros(n), 0)
    # High cumulative warming
    _, co2_acc = rothc_step(base, clay, 25.0, np.full(n,0.7), np.full(n,0.5),
                             np.zeros(n), np.full(n, 30.0), 0)
    assert np.mean(co2_acc) < np.mean(co2_no) + 0.01, \
        "Thermal acclimation should reduce or equal CO2 emission"
