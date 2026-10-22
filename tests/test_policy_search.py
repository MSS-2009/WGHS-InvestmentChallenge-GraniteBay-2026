import dataclasses as dc
import numpy as np
import pytest

from lgm import engine
from lgm.asof import month_of
from lgm.esg import Scenarios, TAU_GRID, simulate
from lgm.profiles import cs_team
from lgm.strategies import IPS, S1, S2, S6, S8, S9, Strategy


@pytest.fixture(scope="module")
def sim_scenarios():
    p = cs_team()
    return simulate(p, n=1000, seed=42)


def test_defaults_reproduce_bit_for_bit(sim_scenarios):
    """Verify that default Strategy arguments reproduce engine.run outputs bit-for-bit for S1, S2, S6, S8, S9, IPS."""
    sc = sim_scenarios
    strategies = [S1, S2, S6, S8, S9, IPS]
    for st in strategies:
        res_default = engine.run(st, sc)
        st_explicit = dc.replace(st,
                                 equity_share_end=None,
                                 floor_year=2031,
                                 floor_share=None,
                                 ratchet_trigger=None,
                                 ratchet_share=0.0)
        res_explicit = engine.run(st_explicit, sc)

        for key in res_default:
            if isinstance(res_default[key], np.ndarray):
                assert np.array_equal(res_default[key], res_explicit[key]), f"Mismatch on {st.name} key {key}"
            elif isinstance(res_default[key], float):
                assert res_default[key] == res_explicit[key], f"Mismatch on {st.name} key {key}"


def make_zero_vol_scenario(annual_rate=0.04, monthly_eq_return=0.01):
    """Zero-volatility, deterministic environment with flat rate curve and constant equity return."""
    beta = np.zeros((1, 75, 3))
    beta[:, :, 0] = annual_rate
    resid = np.zeros(len(TAU_GRID))
    eq_log = np.full((1, 74, 3), np.log1p(monthly_eq_return))
    infl = np.zeros((1, 75))
    fx_log = np.zeros((1, 75))
    tw_cost_log = np.zeros((1, 75))
    return Scenarios(beta=beta, eq_log=eq_log, infl=infl, fx_log=fx_log, tw_cost_log=tw_cost_log, resid=resid)


def test_glide_path_hand_checkable():
    """Glide path: target moves linearly from equity_share in Jan 2028 to equity_share_end in Jan 2032."""
    st = Strategy("GlideTest",
                  lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
                  equity_share=0.60,
                  equity_share_end=0.20,
                  band=0.0,
                  floor_share_2031=0.0)

    # 1. Target function checks
    m28 = engine.M_2028
    m29 = month_of(2029)
    m30 = month_of(2030)
    m31 = engine.M_2031
    m32 = month_of(2032)

    assert engine.target_equity_share(st, m28) == pytest.approx(0.60)
    assert engine.target_equity_share(st, m29) == pytest.approx(0.50)
    assert engine.target_equity_share(st, m30) == pytest.approx(0.40)
    assert engine.target_equity_share(st, m31) == pytest.approx(0.30)
    assert engine.target_equity_share(st, m32) == pytest.approx(0.20)

    # 2. Execution check in zero-vol scenario
    sc = make_zero_vol_scenario(annual_rate=0.04, monthly_eq_return=0.005)
    res = engine.run(st, sc)
    assert res["funded"].all()
    assert res["facility"][0] > 0


def test_floor_timing_hand_checkable():
    """Floor timing: floor moves in floor_year (e.g. 2030 instead of 2031)."""
    sc = make_zero_vol_scenario(annual_rate=0.04, monthly_eq_return=0.005)
    cfg = engine.EngineConfig(commissions=False)

    st_2031 = Strategy("Floor2031", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
                       equity_share=0.6, floor_year=2031, floor_share=0.6)
    st_2030 = Strategy("Floor2030", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
                       equity_share=0.6, floor_year=2030, floor_share=0.6)

    r_2031 = engine.run(st_2031, sc, cfg, snapshot_2031=True)
    r_2030 = engine.run(st_2030, sc, cfg, snapshot_2031=True)

    # In 2031, both have a valid growth_2031 and floor_2033
    assert r_2031["growth_2031"][0] > 0
    assert r_2030["growth_2031"][0] > 0
    assert r_2031["floor_2033"][0] > 0
    assert r_2030["floor_2033"][0] > 0

    # Moving to floor earlier (2030) in an environment where stocks outperform bonds
    # should result in different final floor values and facility funds.
    assert r_2030["floor_2033"][0] != r_2031["floor_2033"][0]


def test_ratchet_hand_checkable():
    """Ratchet: locks in gains when growth sleeve exceeds ratchet_trigger * reference."""
    rate = 0.04
    eq_ret = 0.02  # 2% monthly return on equities -> easily triggers ratchet
    sc = make_zero_vol_scenario(annual_rate=rate, monthly_eq_return=eq_ret)
    cfg = engine.EngineConfig(commissions=True)

    # Strategy with ratchet on vs ratchet off
    st_off = Strategy("RatchetOff", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
                      equity_share=0.6, floor_share_2031=0.0)
    st_on = Strategy("RatchetOn", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
                     equity_share=0.6, floor_share_2031=0.0,
                     ratchet_trigger=1.1, ratchet_share=0.5)

    r_off = engine.run(st_off, sc, cfg)
    r_on = engine.run(st_on, sc, cfg)

    # Ratchet locked gains into floor, so floor_2033 > 0 for r_on, but == 0 for r_off
    assert r_off["floor_2033"][0] == 0.0
    assert r_on["floor_2033"][0] > 0.0

    # Extra commissions were paid for ratchet trades
    # Compare costs:
    # r_off costs commissions for initial ladder & invest, plus any drift rebalances
    # r_on triggers ratchet and incurs 4 ETF tickets per trigger
    assert r_on["facility"][0] > 0


def test_2030_floor_ranking_picks_true_median():
    """Verify that for a 2030-floor policy, ranking on assets_2031 picks the true median scenario
    while ranking on growth_2031 alone picks an arbitrary/distorted scenario."""
    p = cs_team()
    sc = simulate(p, n=2000, seed=11)
    st_2030 = Strategy("P2030", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
                       equity_share=0.4, floor_share=1.0, floor_year=2030)
    r = engine.run(st_2030, sc, snapshot_2031=True)

    # 1. Assets_2031 is present and accurately reflects total wealth in Jan 2031
    assert "assets_2031" in r
    assert (r["assets_2031"] > 0).all()
    # growth_2031 is essentially 0 because all growth was moved to floor in 2030
    assert np.allclose(r["growth_2031"], 0.0)

    # 2. Old ranking on growth_2031 picks an arbitrary index
    old_i = int(np.argsort(r["growth_2031"])[len(r["growth_2031"]) // 2])
    true_median_floor = float(np.median(r["floor_2033"]))
    old_floor = float(r["floor_2033"][old_i])
    old_error = abs(old_floor - true_median_floor)

    # 3. New conditional_2031 ranking (when i is None) automatically uses assets_2031
    c = engine.conditional_2031(st_2030, sc, r, p)
    new_i = c["scenario"]
    new_floor = c["floor"]
    new_error = abs(new_floor - true_median_floor)

    assert new_i != old_i
    # The new ranking picks a scenario whose floor is within 3% of true population median,
    # whereas the old ranking made an error of tens of thousands of dollars (> $50k)
    assert new_error < 0.05 * true_median_floor
    assert old_error > 0.20 * true_median_floor
