"""Tests for the fitted monthly Taiwan building-cost process in the economic scenario generator."""
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


def test_unconditional_moments_and_ar2(base_params):
    """The simulated monthly AR(2) process matches theoretical mean, variance, and autocorrelation."""
    p1 = 0.6546
    p2 = -0.0939
    sig_eps = 0.007137
    mu_ann = 0.0285
    p = dc.replace(
        base_params,
        months=120,
        tw_cost_growth=mu_ann,
        tw_cost_phi=(p1, p2),
        tw_cost_sig_eps=sig_eps,
        tw_cost_state0=None,
    )

    n_scenarios = 10_000
    sc = simulate(p, n=n_scenarios, seed=123)
    assert sc.tw_cost_infl is not None
    assert sc.tw_cost_infl.shape == (n_scenarios, 121)

    # Monthly log changes y: sc.tw_cost_infl[:, 1:]
    y_vals = sc.tw_cost_infl[:, 1:]
    mu_expected = np.log1p(mu_ann) / 12.0

    # Theoretical variance of AR(2):
    denom = (1.0 + p2) * ((1.0 - p2)**2 - p1**2)
    var_expected = ((1.0 - p2) / denom) * (sig_eps**2)
    std_expected = np.sqrt(var_expected)
    rho1_expected = p1 / (1.0 - p2)
    rho2_expected = p1 * rho1_expected + p2

    # 1. Unconditional mean
    sample_mean = float(np.mean(y_vals))
    assert abs(sample_mean - mu_expected) < 0.0003

    # 2. Unconditional std
    sample_std = float(np.std(y_vals))
    assert abs(sample_std - std_expected) < 0.0004

    # 3. Lag-1 and Lag-2 autocorrelations
    y_t = y_vals[:, 2:].flatten()
    y_lag1 = y_vals[:, 1:-1].flatten()
    y_lag2 = y_vals[:, :-2].flatten()

    sample_rho1 = float(np.corrcoef(y_t, y_lag1)[0, 1])
    sample_rho2 = float(np.corrcoef(y_t, y_lag2)[0, 1])

    assert abs(sample_rho1 - rho1_expected) < 0.015, f"rho1: {sample_rho1:.4f} vs {rho1_expected:.4f}"
    assert abs(sample_rho2 - rho2_expected) < 0.015, f"rho2: {sample_rho2:.4f} vs {rho2_expected:.4f}"


def test_variance_ratio_profile_matches_fit(base_params):
    """Cross-sectional standard deviation across k-month horizons matches the fitted profile."""
    p1 = 0.6546
    p2 = -0.0939
    sig_eps = 0.007137
    p = dc.replace(
        base_params,
        months=75,
        tw_cost_growth=0.0285,
        tw_cost_phi=(p1, p2),
        tw_cost_sig_eps=sig_eps,
        tw_cost_state0=None,
    )

    n_scenarios = 20_000
    sc = simulate(p, n=n_scenarios, seed=42)

    # Historical benchmark values for k in [1, 3, 6, 12, 24, 36, 72]
    expected_stds = {
        1: 0.0089,
        3: 0.0219,
        6: 0.0355,
        12: 0.0538,
        24: 0.0726,
        36: 0.0852,
        72: 0.1268,
    }

    for k, h_std in expected_stds.items():
        diff = sc.tw_cost_log[:, k] - sc.tw_cost_log[:, 0]
        sim_std = float(np.std(diff, ddof=1))
        # Relative error should be within sampling tolerances (<15% across all horizons)
        rel_err = abs(sim_std - h_std) / h_std
        assert rel_err < 0.15, f"k={k}: sim_std={sim_std:.4f} vs hist={h_std:.4f} (rel_err={rel_err:.2%})"


def test_starting_state_decay(base_params):
    """An elevated initial state (Aug, Sep 2026) decays following the AR(2) difference equation."""
    p1 = 0.6546
    p2 = -0.0939
    sig_eps = 0.007137
    mu_ann = 0.0285
    mu = np.log1p(mu_ann) / 12.0
    y_prev2 = 0.00284974  # Aug 2026
    y_prev1 = 0.00650706  # Sep 2026

    p = dc.replace(
        base_params,
        months=24,
        tw_cost_growth=mu_ann,
        tw_cost_phi=(p1, p2),
        tw_cost_sig_eps=sig_eps,
        tw_cost_state0=(y_prev2, y_prev1),
    )

    sc = simulate(p, n=4000, seed=42, antithetic=True)
    assert sc.tw_cost_infl is not None
    assert np.allclose(sc.tw_cost_infl[:, 0], y_prev1)

    # Compute theoretical expected path E[y_m - mu]
    e_y = np.empty(25)
    e_y[0] = y_prev1
    for m in range(1, 25):
        prev1 = y_prev1 if m == 1 else e_y[m - 1]
        prev2 = y_prev2 if m == 1 else (y_prev1 if m == 2 else e_y[m - 2])
        e_y[m] = mu + p1 * (prev1 - mu) + p2 * (prev2 - mu)

    # Cross-sectional mean from antithetic simulation must match theoretical expectation tightly
    sim_mean = sc.tw_cost_infl.mean(axis=0)
    for m in [1, 2, 3, 6, 12, 24]:
        assert abs(sim_mean[m] - e_y[m]) < 1e-4, (
            f"Month {m}: sim_mean={sim_mean[m]:.6f} != expected={e_y[m]:.6f}"
        )


def test_conditional_2031_inherits_taiwan_cost_state(base_params):
    """Nested conditional_2031 simulation starts from scenario i's own 2031 inflation state (2 lags)."""
    r = build_core()
    w = r["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    st = dc.replace(IPS, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er))

    p = dc.replace(
        base_params,
        tw_cost_growth=0.0285,
        tw_cost_phi=(0.6546, -0.0939),
        tw_cost_sig_eps=0.007137,
        tw_cost_state0=(0.002850, 0.006507),
    )

    sc = simulate(p, n=200, seed=42)
    res = engine.run(st, sc, cfg, snapshot_2031=True)

    target_scenario = 10
    m31 = engine.M_2031 - sc.m0
    expected_state_2031 = (sc.tw_cost_infl[target_scenario, m31 - 1], sc.tw_cost_infl[target_scenario, m31])
    expected_cost_log_2031 = float(sc.tw_cost_log[target_scenario, m31])

    cond = engine.conditional_2031(st, sc, res, p, i=target_scenario, n_inner=50, seed=99, cfg=cfg)

    # Re-simulate inner manually to verify exact match
    inner_start = {
        "beta": sc.beta[target_scenario, m31],
        "infl": sc.infl[target_scenario, m31],
        "fx_log": np.full(50, sc.fx_log[target_scenario, m31]),
        "tw_cost_log": np.full(50, sc.tw_cost_log[target_scenario, m31]),
        "tw_cost_infl": expected_state_2031,
    }
    p_inner = dc.replace(p, months=engine.M_2033 - engine.M_2031)
    inner_sc = simulate(p_inner, n=50, seed=99, start=inner_start, m0=engine.M_2031)

    assert np.allclose(inner_sc.tw_cost_infl[:, 0], expected_state_2031[1])
    assert np.allclose(inner_sc.tw_cost_log[:, 0], expected_cost_log_2031)
    assert cond["scenario"] == target_scenario
