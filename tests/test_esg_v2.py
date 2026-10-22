"""Tests for ESG v2 enhancements: expected-return uncertainty and volatility clustering."""
import numpy as np
import pytest

from lgm import engine
from lgm.calibrate import calibrate_cma_dispersion
from lgm.esg import ESGParams, Scenarios, simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS


def test_eq_mu_cov_none_reproduces_exact():
    """Setting eq_mu_cov=None reproduces baseline scenarios exactly."""
    core = build_core()
    p1 = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p2 = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p2.eq_mu_cov = None

    sc1 = simulate(p1, n=2000, seed=42)
    sc2 = simulate(p2, n=2000, seed=42)

    assert np.array_equal(sc1.eq_log, sc2.eq_log)
    assert np.array_equal(sc1.beta, sc2.beta)
    assert np.array_equal(sc1.infl, sc2.infl)
    assert np.array_equal(sc1.fx_log, sc2.fx_log)
    assert np.array_equal(sc1.tw_cost_log, sc2.tw_cost_log)


def test_calibrate_cma_dispersion():
    """CMA cross-firm dispersion produces valid covariance matrix matching region structure."""
    cov = calibrate_cma_dispersion()
    K = len(CORE)
    assert cov.shape == (K, K)
    assert np.allclose(cov, cov.T)
    # Eigenvalues must be non-negative (PSD)
    eigs = np.linalg.eigvalsh(cov)
    assert np.all(eigs >= -1e-12)

    # Assets in the same region must share identical variances and covariances:
    # US large growth (0), US large value (1), US small cap (2)
    assert np.isclose(cov[0, 0], cov[1, 1])
    assert np.isclose(cov[0, 1], cov[0, 0])
    # Europe (3) and Japan (4) are both intl_dev
    assert np.isclose(cov[3, 3], cov[4, 4])
    assert np.isclose(cov[3, 4], cov[3, 3])


def test_eq_mu_cov_spread_and_antithetic():
    """With eq_mu_cov, cross-scenario spread matches covariance and antithetic pairs mirror."""
    core = build_core()
    cov_cma = calibrate_cma_dispersion()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_mu_cov = cov_cma

    n = 30000
    sc = simulate(p, n=n, seed=7)
    assert sc.eq_drift_err is not None
    half = n // 2

    # Antithetic mirroring
    assert np.allclose(sc.eq_drift_err[:half], -sc.eq_drift_err[half:])
    assert np.allclose(sc.eq_drift_err.mean(axis=0), 0.0)

    # Spread of the drawn drifts matches cov_cma within sampling error
    drift_cov = np.cov(sc.eq_drift_err, rowvar=False)
    assert np.allclose(drift_cov, cov_cma, atol=2.5e-5)

    # Cross-scenario spread of annualised mean log returns
    # Var(12 * mean_m) = Var(drift) + (144 / M) * Var(shock)
    ann_mean = sc.eq_log.mean(axis=1) * 12
    sample_ann_cov = np.cov(ann_mean, rowvar=False)
    expected_ann_cov = cov_cma + (144.0 / p.months) * p.cov[:len(CORE), :len(CORE)]
    assert np.allclose(sample_ann_cov, expected_ann_cov, atol=1e-3)


def test_conditional_2031_drift_handling():
    """Nested simulation conditional_2031 respects keep_drift parameter."""
    core = build_core()
    cov_cma = calibrate_cma_dispersion()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_mu_cov = cov_cma

    sc = simulate(p, n=500, seed=11)
    import dataclasses as dc
    st = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    r = engine.run(st, sc, cfg, snapshot_2031=True)

    # With keep_drift=True (default), inner simulation preserves scenario i's drawn drift
    target_idx = 10
    expected_drift = sc.eq_drift_err[target_idx]

    start = {"beta": sc.beta[target_idx, engine.M_2031 - sc.m0],
             "infl": sc.infl[target_idx, engine.M_2031 - sc.m0],
             "fx_log": np.full(100, sc.fx_log[target_idx, engine.M_2031 - sc.m0]),
             "tw_cost_log": np.full(100, sc.tw_cost_log[target_idx, engine.M_2031 - sc.m0]),
             "eq_drift_err": expected_drift}
    inner = simulate(p, n=100, seed=99, start=start, m0=engine.M_2031)
    assert np.allclose(inner.eq_drift_err, expected_drift)

    # Calling conditional_2031 directly runs without error
    cond_kept = engine.conditional_2031(st, sc, r, p, i=target_idx, n_inner=200, cfg=cfg, keep_drift=True)
    cond_redrawn = engine.conditional_2031(st, sc, r, p, i=target_idx, n_inner=200, cfg=cfg, keep_drift=False)
    assert "floor" in cond_kept
    assert "floor" in cond_redrawn
