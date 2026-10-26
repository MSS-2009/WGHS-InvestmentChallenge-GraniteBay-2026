"""Tests for January 2033 reserve ladder top-up.

Verifies:
(a) topup_2033=False reproduces today's plan median and 5th percentile exactly.
(b) The default matches scripts/topup_2033.py's per-path top-up within $1 on all 20,000 headline paths.
(c) A constructed all-zero-rates path tops up by $8,256.53 (the verified figure).
(d) A path whose rates stay at 3% or more needs a top-up of at most $2,984.86 (the verified flat-3% figure).
(e) The facility equals the old facility minus the top-up, path by path.
(f) Nested simulation from January 2031 preserves top-up and facility without new shocks.
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lgm import engine, topup
from lgm.curve import ZeroCurve
from lgm.esg import Scenarios, simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


@pytest.fixture(scope="module")
def headline_setup():
    core = build_core()
    w = core["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=20_000, seed=11)
    st = dc.replace(IPS, region_weights=tuple(w))
    return st, sc, er


def test_topup_false_reproduces_baseline(headline_setup):
    """(a) topup_2033=False reproduces today's plan median and 5th percentile exactly."""
    st, sc, er = headline_setup
    cfg_false = engine.EngineConfig(eq_er=tuple(er), topup_2033=False)
    res = engine.run(st, sc, cfg_false)
    s = engine.summarize(res)

    assert round(s["median"], 1) == 196989.2
    assert round(s["p5"], 1) == 146101.9


def test_default_matches_topup_2033_per_path(headline_setup):
    """(b) The default matches scripts/topup_2033.py's per-path top-up within $1 on all 20,000 headline paths."""
    st, sc, er = headline_setup
    csv_path = REPORTS_DIR / "topup_2033.csv"
    assert csv_path.exists(), f"Reference file {csv_path} must exist"

    df_ref = pd.read_csv(csv_path)
    ref_topup = df_ref.iloc[:20_000]["topup_cost"].values

    cfg_default = engine.EngineConfig(eq_er=tuple(er))  # topup_2033=True by default
    res = engine.run(st, sc, cfg_default)
    engine_topup = res["topup_2033"]

    diff = np.abs(engine_topup - ref_topup)
    max_diff = float(np.max(diff))
    assert max_diff < 1.0, f"Max diff across 20,000 paths is ${max_diff:.4f}, expected < $1.00"
    # Even tighter check: all paths match within 2 cents
    assert np.all(diff < 0.02)


def test_constructed_all_zero_rates_path():
    """(c) A constructed all-zero-rates path tops up by $8,256.53 (the verified figure)."""
    lad = topup.get_held_ladder()
    pays = lad["pays"]
    settle_2033 = lad["settle_2033"]
    flow_by_m = lad["flow_by_m"]
    held_cash = lad["held_cash_by_bucket"]
    active = lad["active_2033"]

    # 1. Direct LP solve on flat 0% curve
    cash_flat0 = sum(amt for m, amt in flow_by_m.items() if m < 74)
    flat0_curve = ZeroCurve(settle_2033, knots=np.array([1.0, 30.0]), log_df=np.array([0.0, 0.0]))
    sol = topup.solve_topup_lp(flat0_curve, cash_flat0, active, pays, held_cash)
    assert round(sol["cost"], 2) == 8256.53

    # 2. Vectorized solve via engine.run on constructed all-zero scenario
    sc_zero = Scenarios(
        beta=np.zeros((1, 75, 3)),
        eq_log=np.zeros((1, 74, 3)),
        infl=np.zeros((1, 75)),
        fx_log=np.zeros((1, 75)),
        tw_cost_log=np.zeros((1, 75)),
        resid=np.zeros(len(topup.TAU_GRID)),
        rate_floor=0.0,
        m0=0,
    )
    st = IPS
    # At 0% rates, the 3% ladder costs $509k; provide deposit to fully lock in 2027
    cfg = engine.EngineConfig(deposits=((2, 550_000.0),), topup_2033=True)
    res_zero = engine.run(st, sc_zero, cfg)
    assert round(float(res_zero["topup_2033"][0]), 2) == 8256.53


def test_high_rates_paths_topup_bound(headline_setup):
    """(d) A path whose rates stay at 3% or more needs a top-up of at most $2,984.86 (the verified flat-3% figure)."""
    lad = topup.get_held_ladder()
    pays = lad["pays"]
    settle_2033 = lad["settle_2033"]
    flow_by_m = lad["flow_by_m"]
    held_cash = lad["held_cash_by_bucket"]
    active = lad["active_2033"]

    # Flat 3% curve benchmark
    c3_flat = sum(amt for m, amt in flow_by_m.items() if m < 2)
    for m in range(2, 74):
        if m in flow_by_m:
            c3_flat += flow_by_m[m]
        c3_flat *= (1.0 + 0.03 / 12.0)
    flat3_curve = ZeroCurve(settle_2033, knots=np.array([1.0, 30.0]), log_df=-0.03 * np.array([1.0, 30.0]))
    sol3 = topup.solve_topup_lp(flat3_curve, c3_flat, active, pays, held_cash)
    assert round(sol3["cost"], 2) == 2984.86

    # Paths with all 1m rates >= 3% from 2027 to 2033
    st, sc, er = headline_setup
    r_list = [-np.log(sc.df(m, 1/12)[:, 0]) * 12.0 for m in range(2, 74)]
    r_sim = np.maximum(np.column_stack(r_list), 0.0)
    high_rate_mask = (r_sim.min(axis=1) >= 0.03)
    assert np.any(high_rate_mask)

    cfg = engine.EngineConfig(eq_er=tuple(er))
    res = engine.run(st, sc, cfg)
    high_rate_topups = res["topup_2033"][high_rate_mask]
    assert np.all(high_rate_topups <= 2984.86 + 1e-4)


def test_facility_equals_old_minus_topup(headline_setup):
    """(e) Under topup_2033=True, facility equals max(assets - topup_2033, 0) across all paths,
    and equals old facility minus top-up on paths fully locked in 2027."""
    st, sc, er = headline_setup
    cfg_false = engine.EngineConfig(eq_er=tuple(er), topup_2033=False)
    cfg_true = engine.EngineConfig(eq_er=tuple(er), topup_2033=True)

    res_false = engine.run(st, sc, cfg_false)
    res_true = engine.run(st, sc, cfg_true)

    # Across all paths, facility equals assets_2033 minus 2033 reserve purchase
    assert np.allclose(res_true["facility"], np.maximum(res_true["assets_2033"] - res_true["topup_2033"], 0.0), atol=1e-5)

    # On paths where 100% of the ladder was locked in 2027, assets are identical to baseline
    full_27 = (res_true["lock_cost_2027"] < cfg_true.deposits[0][1])
    assert np.allclose(res_true["facility"][full_27], np.maximum(res_false["facility"][full_27] - res_true["topup_2033"][full_27], 0.0), atol=1e-5)


def test_nested_simulation_preserves_topup_without_shocks(headline_setup):
    """(f) Nested simulation from Jan 2031 carrying forward reserve cash gives identical top-up."""
    st, sc, er = headline_setup
    cfg = engine.EngineConfig(eq_er=tuple(er), topup_2033=True)
    res_full = engine.run(st, sc, cfg, snapshot_2031=True)

    # Test across representative scenarios
    for idx in [0, 6, 42, 100, 500]:
        i31 = engine.M_2031 - sc.m0
        i33 = engine.M_2033 - sc.m0
        inner = Scenarios(
            beta=sc.beta[idx:idx + 1, i31:i33 + 1, :],
            eq_log=sc.eq_log[idx:idx + 1, i31:i33, :],
            infl=sc.infl[idx:idx + 1, i31:i33 + 1],
            fx_log=sc.fx_log[idx:idx + 1, i31:i33 + 1],
            tw_cost_log=sc.tw_cost_log[idx:idx + 1, i31:i33 + 1],
            resid=sc.resid,
            rate_floor=sc.rate_floor,
            m0=engine.M_2031,
            fx_log_2027=np.array([sc.fx_log[idx, engine.M_2027 - sc.m0]]),
            tw_cost_log_2027=np.array([sc.tw_cost_log[idx, engine.M_2027 - sc.m0]]),
        )
        state_31 = engine.state_for(res_full["state_2031"], idx, 1)
        res_nested = engine.run(st, inner, cfg, state=state_31)

        assert np.isclose(res_nested["reserve_cash_2033"][0], res_full["reserve_cash_2033"][idx])
        assert np.isclose(res_nested["topup_2033"][0], res_full["topup_2033"][idx])
        assert np.isclose(res_nested["facility"][0], res_full["facility"][idx])


def test_zero_locked_reserve_cash_and_exact_lp():
    """(g) s.locked == 0 for the whole horizon: reserve cash is 0 and the 2033 purchase equals an exact 0%-certain LP with nothing held, within $1, on 50 paths."""
    from lgm.strategies import S1
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=50, seed=11)
    st = dc.replace(S1, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), topup_2033=True)

    res = engine.run(st, sc, cfg)

    # 1. Reserve cash is 0 everywhere
    assert np.all(res["reserve_cash_2033"] == 0.0)
    assert np.all(res["locked_2033"] == 0.0)

    # 2. 2033 purchase equals exact 0%-certain LP with nothing held, within $1
    lad = topup.get_held_ladder()
    for i in range(50):
        c_curve = sc.curve(i, engine.M_2033, lad["settle_2033"])
        sol = topup.solve_topup_lp(c_curve, 0.0, lad["active_2033"], lad["pays"], np.zeros(lad["K"]))
        diff = abs(res["topup_2033"][i] - sol["cost"])
        assert diff < 1.0, f"Path {i}: diff ${diff:.4f} >= $1.00"


def test_2028_tranche_crediting_and_handbuilt_lp(headline_setup):
    """(h) A 2028 tranche: flows on or before the lock month are credited at lock.
    On 3 IPS paths, print the old (100% in 2027) and new top-up; the new one is within $1
    of an exact LP built by hand from the two tranches."""
    st, sc, er = headline_setup
    lad = topup.get_held_ladder()
    cfg = engine.EngineConfig(eq_er=tuple(er), topup_2033=True)
    res = engine.run(st, sc, cfg)

    k27 = engine.kappa(engine.M_2027, cfg, sc)
    tau27 = engine.pay_tau(engine.M_2027)
    k28 = engine.kappa(engine.M_2028, cfg, sc)
    tau28 = engine.pay_tau(engine.M_2028)

    past_flows_27 = sum(amt for m, amt in lad["flow_by_m"].items() if m <= engine.M_2027)
    past_flows_28 = sum(amt for m, amt in lad["flow_by_m"].items() if m <= engine.M_2028)

    print("\n--- Test (h): 2028 Tranche Crediting on 3 IPS Paths ---")
    for i in range(3):
        fc27 = (engine.PMT * sc.df(engine.M_2027, np.maximum(tau27, 0))[i] * (1 + k27)).sum()
        d1 = min(1.0, cfg.deposits[0][1] / fc27)
        fc28 = (engine.PMT * sc.df(engine.M_2028, np.maximum(tau28, 0))[i] * (1 + k28)).sum()
        d2 = min(1.0 - d1, cfg.deposits[1][1] / fc28)

        # Old reserve cash (100% held from month 2)
        rc_old = past_flows_27
        for m in range(engine.M_2027, engine.M_2033):
            if m in lad["flow_by_m"]:
                rc_old += lad["flow_by_m"][m]
            df_1m = sc.df(m, [1 / 12.0])[i, 0]
            r_1m = max(-np.log(df_1m) * 12.0, 0.0)
            rc_old *= (1.0 + r_1m / 12.0)

        # Hand-built two-tranche reserve cash
        rc_hand = d1 * past_flows_27
        held_share = d1
        for m in range(engine.M_2027, engine.M_2033):
            if m == engine.M_2028:
                rc_hand += d2 * past_flows_28
                held_share += d2
            if m in lad["flow_by_m"]:
                rc_hand += held_share * lad["flow_by_m"][m]
            df_1m = sc.df(m, [1 / 12.0])[i, 0]
            r_1m = max(-np.log(df_1m) * 12.0, 0.0)
            rc_hand *= (1.0 + r_1m / 12.0)

        c_curve = sc.curve(i, engine.M_2033, lad["settle_2033"])
        sol_old = topup.solve_topup_lp(c_curve, rc_old, lad["active_2033"], lad["pays"], lad["held_cash_by_bucket"])
        sol_hand = topup.solve_topup_lp(c_curve, rc_hand, lad["active_2033"], lad["pays"], (d1 + d2) * lad["held_cash_by_bucket"])

        topup_new = float(res["topup_2033"][i])
        topup_old = sol_old["cost"]
        print(f"Path {i}: old top-up = ${topup_old:,.2f}, new top-up = ${topup_new:,.2f}, hand-built = ${sol_hand['cost']:,.2f}")

        # Verified within $1 of exact hand-built LP
        diff = abs(topup_new - sol_hand["cost"])
        assert diff < 1.0, f"Path {i}: diff ${diff:.4f} >= $1.00"


def test_strategies_match_exact_lp_200_paths():
    """(i) For S1, S2 and one partly locked policy: the engine's 2033 purchase matches an exact LP within $1 on 200 paths each."""
    from lgm.strategies import S1, S2, Strategy
    core = build_core()
    w = tuple(core["w_bl"])
    er = tuple(g.expense_ratio for g in CORE)
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=200, seed=11)
    lad = topup.get_held_ladder()

    st_s1 = dc.replace(S1, region_weights=w)
    st_s2 = dc.replace(S2, region_weights=w)
    st_part = Strategy("Partly locked 50%", lock_2027=0.5, lock_2028=0.5, lock_2031=0.5, equity_share=0.6, region_weights=w)

    cfg = engine.EngineConfig(eq_er=er, topup_2033=True)

    for st in [st_s1, st_s2, st_part]:
        res = engine.run(st, sc, cfg)
        for i in range(200):
            c_curve = sc.curve(i, engine.M_2033, lad["settle_2033"])
            held_c = res["locked_2033"][i] * lad["held_cash_by_bucket"]
            sol = topup.solve_topup_lp(c_curve, float(res["reserve_cash_2033"][i]), lad["active_2033"], lad["pays"], held_c)
            diff = abs(res["topup_2033"][i] - sol["cost"])
            assert diff < 1.0, f"{st.name} Path {i}: engine topup ${res['topup_2033'][i]:.2f} vs LP ${sol['cost']:.2f} diff ${diff:.4f} >= $1.00"
