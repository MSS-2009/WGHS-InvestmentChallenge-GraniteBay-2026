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
    flat = dict(eq_er=(0.0,) * 9, compound_costs=False)          # count tickets, not their lost returns
    nine = engine.run(st, sc, engine.EngineConfig(**flat))
    three = engine.run(st, sc, engine.EngineConfig(**flat, fund_groups=((0, 1, 2), (3, 4, 5, 6), (7, 8))))
    # each trading event (two deposits plus any band rebalance) saves six equity tickets
    saved = three["assets_2033"] - nine["assets_2033"]
    per_event = 6 * engine.COMMISSION_ETF
    assert (saved >= 2 * per_event).all() and np.allclose(saved % per_event, 0)


def test_commissions_compound_at_the_portfolio_return():
    # All in VGIT at a flat 5%: one $25 ticket on each deposit (Jan 2027, Jan 2028), and nothing else.
    st = dc.replace(S2, equity_share=0.0, bond_vehicle="VGIT")
    sc = _flat(0.05)
    plain = engine.run(st, sc, engine.EngineConfig(compound_costs=False))
    compounded = engine.run(st, sc, engine.EngineConfig(compound_costs=True))
    g = 1.05 ** (1 / 12) - engine.ER["VGIT"] / 12
    lost = engine.COMMISSION_ETF * (g ** 72 - 1) + engine.COMMISSION_ETF * (g ** 60 - 1)
    assert np.allclose(plain["assets_2033"] - compounded["assets_2033"], lost, rtol=1e-9)


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


def test_settlement_sells_each_fund_still_held_once():
    # 60/40 in three equity slots held as one fund (VTI) plus VGIT: two sale tickets in Jan 2033
    st = dc.replace(S2, bond_vehicle="VGIT")
    sc = _flat(0.05)
    kw = dict(compound_costs=False, fund_groups=((0, 1, 2),))
    sold = engine.run(st, sc, engine.EngineConfig(**kw))
    kept = engine.run(st, sc, engine.EngineConfig(**kw, sell_at_settlement=False))
    assert np.allclose(kept["assets_2033"] - sold["assets_2033"], 2 * engine.COMMISSION_ETF)
    # a 35-name basket counted as one slot sells its 34 extra names too
    extra = engine.run(st, sc, engine.EngineConfig(**kw, extra_tickets=34))
    extra_kept = engine.run(st, sc, engine.EngineConfig(**kw, extra_tickets=34, sell_at_settlement=False))
    assert np.allclose(extra_kept["assets_2033"] - extra["assets_2033"], (2 + 34) * engine.COMMISSION_ETF)


def test_equity_correlations_shrink_toward_their_average_not_zero():
    import numpy as np
    from lgm.calibrate import calibrate_assets
    from lgm.growth.universe import CORE

    tickers = [g.history for g in CORE]
    k = len(tickers)
    off = ~np.eye(k, dtype=bool)
    zero = calibrate_assets(tickers, equity_shrink_target="zero")["corr"].values
    mean = calibrate_assets(tickers, equity_shrink_target="mean")["corr"].values
    # the zero target pulls the average equity correlation down by the shrinkage; the mean target keeps it
    assert mean[:k, :k][off].mean() > zero[:k, :k][off].mean() + 0.03
    assert np.allclose(mean[k:, :], zero[k:, :]) and np.allclose(mean[:k, k:], zero[:k, k:])   # nothing else moves
    assert np.linalg.eigvalsh(mean).min() > 0


def test_market_anchoring_moves_the_level_not_the_weights():
    import numpy as np
    import yaml

    from lgm.growth import core as C

    cfg = yaml.safe_load(C.CFG.read_text())
    a = C.build_core()
    b = C.build_core(cfg=dict(cfg, anchor_market_to_consensus=False))
    assert np.allclose(a["w_bl"], b["w_bl"], atol=1e-9)
    assert abs(float(a["w_mkt"] @ (a["table"]["bl_excess"] - a["table"]["pi_excess"]))) < 1e-12
    assert np.allclose(np.diff(a["table"]["bl_excess"] - b["table"]["bl_excess"]), 0)   # a uniform shift


def test_short_history_funds_borrow_a_longer_proxys_volatility():
    from lgm.calibrate import VOL_PROXIES, calibrate_assets
    from lgm.growth.universe import CORE

    t = [g.history for g in CORE]
    on, off = calibrate_assets(t)["ann_vol"], calibrate_assets(t, vol_proxies={})["ann_vol"]
    for fund in VOL_PROXIES:
        assert on[fund] > off[fund] * 1.05                   # 2008 raises them
    assert all(on[x] == off[x] for x in t if x not in VOL_PROXIES)



def test_the_2031_floor_move_is_one_ticket_per_fund():
    """Moving money into the floor and rebalancing the rest trades each fund once: nine equity funds and
    IBTM, plus a separate IBTM ticket only when the sleeve's bonds are VGIT."""
    from lgm.strategies import IPS

    sc = _flat(0.05, k=9)
    sc.eq_log[:] = np.log(1.05) / 12                    # everything earns 5%: no band rebalancing
    cfg = engine.EngineConfig(eq_er=(0.0,) * 9, compound_costs=False)
    for vehicle, tickets in (("IBTM", 10), ("VGIT", 11)):
        st = dc.replace(IPS, region_weights=tuple(np.full(9, 1 / 9)), bond_vehicle=vehicle)
        floor = engine.run(st, sc, cfg)["costs_2033"]
        none = engine.run(dc.replace(st, floor_share_2031=0.0), sc, cfg)["costs_2033"]
        assert np.allclose(floor - none, tickets * engine.COMMISSION_ETF)
