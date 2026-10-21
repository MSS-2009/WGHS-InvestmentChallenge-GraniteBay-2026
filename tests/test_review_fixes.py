"""Regression tests for the issues found in the independent code review (October 2026)."""
import dataclasses as dc

import numpy as np

from lgm import engine
from lgm.esg import TAU_GRID, Scenarios
from lgm.growth.core import to_arithmetic
from lgm.strategies import S2


def _flat(rate: float, n: int = 4, k: int = 3) -> Scenarios:
    m = engine.M_2033
    beta = np.zeros((n, m + 1, 3))
    beta[..., 0] = np.log1p(rate)
    z = lambda shape: np.zeros(shape)
    return Scenarios(beta, z((n, m, k)), z((n, m + 1)), z((n, m + 1)), z((n, m + 1)), np.zeros(len(TAU_GRID)))


def test_vgit_compounds_an_annual_yield_correctly():
    st = dc.replace(S2, equity_share=0.0, bond_vehicle="VGIT")
    r = engine.run(st, _flat(0.05), engine.EngineConfig(commissions=False))
    g = 1.05 ** (1 / 12) - engine.ER["VGIT"] / 12
    expected = 300_000 * g ** 72 + 150_000 * g ** 60
    assert np.allclose(r["assets_2033"], expected, rtol=1e-9)


def test_commissions_count_funds_held_not_weight_slots():
    sc = _flat(0.05, k=9)
    w = tuple(np.full(9, 1 / 9))
    st = dc.replace(S2, region_weights=w)
    nine = engine.run(st, sc, engine.EngineConfig(eq_er=(0.0,) * 9))
    three = engine.run(st, sc, engine.EngineConfig(eq_er=(0.0,) * 9, fund_groups=((0, 1, 2), (3, 4, 5, 6), (7, 8))))
    # each trading event (two deposits plus any band rebalance) saves six equity tickets
    saved = three["assets_2033"] - nine["assets_2033"]
    per_event = 6 * engine.COMMISSION_ETF
    assert (saved >= 2 * per_event).all() and np.allclose(saved % per_event, 0)


def test_zero_weight_slots_are_not_charged():
    sc = _flat(0.05, k=4)
    with_empty = dc.replace(S2, region_weights=(0.5, 0.3, 0.2, 0.0))
    a = engine.run(with_empty, sc, engine.EngineConfig(eq_er=(0.0,) * 4))
    sc3 = _flat(0.05, k=3)
    b = engine.run(dc.replace(S2, region_weights=(0.5, 0.3, 0.2)), sc3, engine.EngineConfig(eq_er=(0.0,) * 3))
    assert np.allclose(a["assets_2033"], b["assets_2033"])


def test_view_conversion_uses_basket_variances():
    cov = np.array([[0.04, 0.02, 0.0], [0.02, 0.09, 0.0], [0.0, 0.0, 0.0225]])
    P = np.array([[0.5, 0.5, -1.0], [1.0, 0.0, -1.0]])
    q = to_arithmetic(P, np.zeros(2), cov)
    basket = np.array([0.5, 0.5, 0.0])
    assert np.isclose(q[0], 0.5 * (basket @ cov @ basket - 0.0225))
    assert np.isclose(q[1], 0.5 * (0.04 - 0.0225))


def test_plans_without_a_floor_rebalance_in_january_2031():
    sc = _flat(0.05)
    sc.eq_log[:] = 0.03                      # stocks rise 3% a month, so the mix drifts out of its band
    st = dc.replace(S2, region_weights=(0.6, 0.3, 0.1))
    r = engine.run(st, sc, engine.EngineConfig(commissions=False), snapshot_2031=True)
    s = r["state_2031"]
    share = s.eq.sum(1) / (s.eq.sum(1) + s.vgit + s.cash)
    assert np.allclose(share, 0.6)
