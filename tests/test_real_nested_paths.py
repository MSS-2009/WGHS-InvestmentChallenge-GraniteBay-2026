"""Nested 2031 simulations retain the correct January 2027 real-dollar baseline."""
from dataclasses import replace

import numpy as np

from lgm import engine
from lgm.esg import ESGParams, TAU_GRID, simulate
from lgm.strategies import Strategy


def _params(months):
    beta0 = np.array([np.log1p(0.04), 0.0, 0.0])
    return ESGParams(
        months=months,
        beta0=beta0,
        resid=np.zeros(len(TAU_GRID)),
        beta_mu=beta0.copy(),
        phi=np.zeros(3),
        cov=np.eye(8) * 1e-6,
        eq_geo=np.full(3, 0.04),
    )


def test_nested_real_facility_uses_january_2027_not_january_2031():
    outer = simulate(_params(engine.M_2033), n=2, seed=7)
    i27 = engine.M_2027
    assert np.array_equal(outer.fx_log_2027, outer.fx_log[:, i27])
    assert np.array_equal(outer.tw_cost_log_2027, outer.tw_cost_log[:, i27])

    i31 = engine.M_2031
    start = {
        "beta": outer.beta[0, i31],
        "infl": outer.infl[0, i31],
        "fx_log": np.full(2, outer.fx_log[0, i31]),
        "tw_cost_log": np.full(2, outer.tw_cost_log[0, i31]),
        "fx_log_2027": np.full(2, outer.fx_log_2027[0]),
        "tw_cost_log_2027": np.full(2, outer.tw_cost_log_2027[0]),
    }
    inner = simulate(replace(_params(engine.M_2033 - i31), tw_cost_phi=None), n=2,
                     seed=9, start=start, m0=i31)
    assert np.array_equal(inner.fx_log_2027, start["fx_log_2027"])
    assert np.array_equal(inner.tw_cost_log_2027, start["tw_cost_log_2027"])

    st = Strategy("all equity", equity_share=1.0, region_weights=(0.6, 0.3, 0.1), band=1.0)
    state = engine.State(
        eq=np.tile([600_000.0, 300_000.0, 100_000.0], (2, 1)),
        vgit=np.zeros(2), ibtm_face=np.zeros(2), floor_face=np.zeros(2), cash=np.zeros(2),
        locked=np.zeros((2, engine.N_PAY)), costs=np.zeros(2),
    )
    cfg = engine.EngineConfig(eq_er=(0.0, 0.0, 0.0), deposits=(), commissions=False)
    result = engine.run(st, inner, cfg, state=state)
    expected = result["facility"] * np.exp(inner.fx_log[:, -1] - inner.fx_log_2027) \
        / np.exp(inner.tw_cost_log[:, -1] - inner.tw_cost_log_2027)
    assert np.allclose(result["facility_real_tw2027"], expected)


def test_nested_real_facility_rejects_missing_january_2027_baseline():
    i31 = engine.M_2031
    nested = simulate(_params(engine.M_2033 - i31), n=1, seed=7,
                      start={"beta": np.array([np.log1p(0.04), 0.0, 0.0]),
                             "infl": 0.03, "fx_log": 0.1, "tw_cost_log": 0.2},
                      m0=i31)
    state = engine.State(
        eq=np.array([[600_000.0, 300_000.0, 100_000.0]]), vgit=np.zeros(1),
        ibtm_face=np.zeros(1), floor_face=np.zeros(1), cash=np.zeros(1),
        locked=np.zeros((1, engine.N_PAY)), costs=np.zeros(1),
    )
    st = Strategy("all equity", equity_share=1.0, region_weights=(0.6, 0.3, 0.1), band=1.0)
    cfg = engine.EngineConfig(eq_er=(0.0, 0.0, 0.0), deposits=(), commissions=False)
    import pytest

    with pytest.raises(ValueError, match="January 2027 FX and Taiwan-cost baselines"):
        engine.run(st, nested, cfg, state=state)
