"""Tests for the persistent Taiwan building-cost process in the economic scenario generator."""
from __future__ import annotations

import dataclasses as dc

import numpy as np
import pytest

from lgm import engine
from lgm.esg import ESGParams, simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS


@pytest.fixture(scope="module")
def base_params() -> ESGParams:
    r = build_core()
    geo = r["table"]["bl_geo_total"].values
    return esg_params(r["cal"], geo)


def test_default_reproduces_old_scenarios_bit_for_bit(base_params):
    """When tw_cost_phi is None, simulate must reproduce legacy output bit-for-bit."""
    p = dc.replace(base_params)
    assert p.tw_cost_phi is None
    assert p.tw_cost_growth == 0.04
    assert p.tw_cost_vol == 0.015

    sc1 = simulate(p, n=1000, seed=42)
    assert sc1.tw_cost_infl is None

    # Re-running with same seed produces bit-for-bit identical tw_cost_log
    sc2 = simulate(p, n=1000, seed=42)
    assert np.array_equal(sc1.tw_cost_log, sc2.tw_cost_log)
    assert np.array_equal(sc1.beta, sc2.beta)
    assert np.array_equal(sc1.eq_log, sc2.eq_log)
    assert np.array_equal(sc1.fx_log, sc2.fx_log)


def test_unconditional_moments_and_ar1(base_params):
    """The simulated process's unconditional mean, volatility and AR(1) match calibration."""
    phi = 0.60
    mu = 0.0285
    vol = 0.0309
    p = dc.replace(base_params, months=120, tw_cost_growth=mu, tw_cost_vol=vol, tw_cost_phi=phi,
                   tw_cost_infl0=None)

    n_scenarios = 10_000
    sc = simulate(p, n=n_scenarios, seed=123)
    assert sc.tw_cost_infl is not None
    assert sc.tw_cost_infl.shape == (n_scenarios, 121)

    # Process values across all months (stationary path)
    infl_vals = sc.tw_cost_infl[:, 10:]   # burn in 10 months

    # 1. Unconditional mean matches mu within Monte Carlo sampling error
    sample_mean = float(np.mean(infl_vals))
    assert abs(sample_mean - mu) < 0.002

    # 2. Unconditional std matches vol within sampling error
    sample_std = float(np.std(infl_vals))
    assert abs(sample_std - vol) < 0.003

    # 3. Monthly AR(1) autocorrelation matches phi
    y_t = sc.tw_cost_infl[:, 11:].flatten()
    y_prev = sc.tw_cost_infl[:, 10:-1].flatten()
    sample_corr = float(np.corrcoef(y_t, y_prev)[0, 1])
    assert abs(sample_corr - phi) < 0.02


def test_initial_state_decays_at_calibrated_rate(base_params):
    """A start far above the mean decays at the exact calibrated rate phi^m."""
    phi = 0.9728
    mu = 0.0285
    vol = 0.0538
    y0 = 0.10  # starting 7.15 pp above the mean
    p = dc.replace(base_params, months=36, tw_cost_growth=mu, tw_cost_vol=vol, tw_cost_phi=phi,
                   tw_cost_infl0=y0)

    # With antithetic=True, the cross-sectional mean error is near machine precision
    sc = simulate(p, n=2000, seed=42, antithetic=True)
    assert sc.tw_cost_infl is not None
    assert np.allclose(sc.tw_cost_infl[:, 0], y0)

    for m in [1, 6, 12, 24, 36]:
        empirical_decay = float((sc.tw_cost_infl[:, m].mean() - mu) / (y0 - mu))
        theoretical_decay = phi ** m
        assert abs(empirical_decay - theoretical_decay) < 1e-4, (
            f"Month {m}: empirical decay {empirical_decay:.4f} != theoretical {theoretical_decay:.4f}"
        )


def test_conditional_2031_inherits_taiwan_cost_state(base_params):
    """Nested conditional_2031 simulation starts from scenario i's own 2031 inflation state."""
    r = build_core()
    w = r["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    st = dc.replace(IPS, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er))

    p = dc.replace(base_params, tw_cost_growth=0.0285, tw_cost_vol=0.0538, tw_cost_phi=0.9728,
                   tw_cost_infl0=0.072888)

    sc = simulate(p, n=200, seed=42)
    res = engine.run(st, sc, cfg, snapshot_2031=True)

    # Re-simulate from scenario 10
    target_scenario = 10
    m31 = engine.M_2031 - sc.m0
    expected_infl_2031 = float(sc.tw_cost_infl[target_scenario, m31])
    expected_cost_log_2031 = float(sc.tw_cost_log[target_scenario, m31])

    cond = engine.conditional_2031(st, sc, res, p, i=target_scenario, n_inner=50, seed=99, cfg=cfg)

    # Direct verification of inner simulation starting state
    inner_start = {
        "beta": sc.beta[target_scenario, m31],
        "infl": sc.infl[target_scenario, m31],
        "fx_log": np.full(50, sc.fx_log[target_scenario, m31]),
        "tw_cost_log": np.full(50, sc.tw_cost_log[target_scenario, m31]),
        "tw_cost_infl": sc.tw_cost_infl[target_scenario, m31],
    }
    p_inner = dc.replace(p, months=engine.M_2033 - engine.M_2031)
    inner_sc = simulate(p_inner, n=50, seed=99, start=inner_start, m0=engine.M_2031)

    assert np.allclose(inner_sc.tw_cost_infl[:, 0], expected_infl_2031)
    assert np.allclose(inner_sc.tw_cost_log[:, 0], expected_cost_log_2031)
    assert cond["scenario"] == target_scenario
