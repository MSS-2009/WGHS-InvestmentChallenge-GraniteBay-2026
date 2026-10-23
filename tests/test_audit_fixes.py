"""Regression tests for the October 21, 2026 code audit and the fixes that followed it."""
import copy
import dataclasses as dc
import datetime as dt
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import yaml

from lgm import asof, engine, ladder
from lgm.curve import bootstrap
from lgm.data import yahoo
from lgm.data.treasury import par_curve
from lgm.esg import simulate
from lgm.growth import qualitative
from lgm.instruments import TreasuryBond
from lgm.profiles import cs_team
from lgm.strategies import S9

ROOT = Path(__file__).resolve().parents[1]
OCT21 = yaml.safe_load((ROOT / "tests" / "data" / "wins_account_2026-10-21.yaml").read_text())   # before the Oct 23 trades


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def zc():
    return bootstrap(par_curve(asof.CURVE_DATE))


def test_timeline_follows_the_curve_date():
    assert asof.START == dt.date(2026, 11, 1)
    assert (engine.M_2027, engine.M_2028, engine.M_2031, engine.M_2033) == (2, 14, 50, 74)
    assert engine.REBAL_MONTHS == (26, 38, 62) and engine.IBTM_MATURITY_M == 73.5


def test_ladder_check_judges_every_payment_not_just_the_last():
    lc = _script("wins_ladder_check")
    at0 = lc.coverage(0.0, OCT21)
    assert min(at0["surplus"]) < 0 < at0["surplus"][-1]      # a middle payment is short, the last is not
    assert lc.main(0.0, OCT21) == 1 and lc.main(0.03, OCT21) == 0


def test_ladder_check_top_up_closes_the_gap():
    lc = _script("wins_ladder_check")
    c = lc.coverage(0.0, OCT21)
    extra = lc.top_up(c, 0.0)
    acct = copy.deepcopy(OCT21)
    for lab, dollars in extra.items():
        f = acct["ladder"]["funds"][lab]
        f["shares"] += int(np.ceil(dollars / f["price"]))
    assert min(lc.coverage(0.0, acct)["surplus"]) >= 0


def test_engine_ladder_premium_matches_the_lp(zc):
    assert engine.EngineConfig().kappa0 == pytest.approx(ladder.premium(zc, 0.03), abs=0.001)
    assert ladder.premium(zc, 0.0) > ladder.premium(zc, 0.03) > ladder.premium(zc, 0.04)


def test_month_end_coupons_keep_their_day():
    b = TreasuryBond("x", 0.04, dt.date(2030, 8, 31))
    dates = b.coupon_dates(dt.date(2028, 12, 31))
    assert dates == [dt.date(2029, 2, 28), dt.date(2029, 8, 31), dt.date(2030, 2, 28), dt.date(2030, 8, 31)]


def test_rate_stress_persists_when_the_long_run_level_moves_too():
    p = cs_team()
    d = np.array([-0.0075, 0.0, 0.0])
    start = {"beta": np.tile(p.beta0, (2000, 1)), "infl": np.full(2000, p.infl0), "fx_log": np.zeros(2000),
             "tw_cost_log": np.zeros(2000), "beta_shift": d}
    fading = simulate(p, n=2000, seed=3, start=start).beta[:, -1, 0].mean()
    lasting = simulate(dc.replace(p, beta_mu=p.beta_mu + d), n=2000, seed=3, start=start).beta[:, -1, 0].mean()
    assert lasting - p.beta0[0] == pytest.approx(-0.0075, abs=0.001)
    assert fading - p.beta0[0] > -0.006                     # without moving beta_mu, much of the shock decays


def test_negative_equity_scores_as_high_leverage():
    row = {"sector": "Consumer Discretionary", "industry": "Hotels", "roe": -27.0, "debt_to_equity": None,
           "op_margin_avg4": 20.0, "op_margin": 22.0, "net_margin": 12.0, "fcf_conversion": 1.4}
    missing = dict(row, roe=None, net_margin=None)          # genuinely missing data stays neutral
    assert qualitative.financial_quality(row) < qualitative.financial_quality(missing)


def test_conditional_2031_returns_its_distribution():
    p = cs_team()
    sc = simulate(p, n=400, seed=2)
    r = engine.run(S9, sc, snapshot_2031=True)
    c = engine.conditional_2031(S9, sc, r, p, n_inner=300)
    assert c["inner"].shape == (300,) and c["p10"] == pytest.approx(np.percentile(c["inner"], 10))


def test_close_on_reads_the_cache_without_the_network(monkeypatch):
    def offline(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(yahoo.requests, "get", offline)
    assert yahoo.close_on("VUG", asof.PRICE_DATE) > 0


def test_wins_orders_include_the_ladder_top_up(capsys):
    """The order list buys what the ladder check says is missing before sizing the growth sleeve."""
    _script("wins_rebalance").main(account=copy.deepcopy(OCT21))
    out = capsys.readouterr().out
    buys = {line.split()[1]: int(line.split()[2]) for line in out.splitlines() if line.strip().startswith("Buy")}
    assert buys.get("IBTO", 0) >= 6                 # the 2034 payment is $189 short at 0% interest
    left = float(out.rsplit("about $", 1)[1].split()[0].replace(",", ""))
    assert left > 0


def test_rounding_residue_pays_no_commission():
    """A deposit spent entirely on the ladder leaves about 1e-10 of rounding; it must not buy ten tickets."""
    sc = simulate(cs_team(), n=3, seed=1)
    z = np.zeros(3)
    s = engine.State(eq=np.zeros((3, 3)), vgit=z.copy(), ibtm_face=z.copy(), floor_face=z.copy(), cash=z.copy(),
                     locked=np.zeros((3, 10)), costs=z.copy())
    engine._invest(s, sc, engine.M_2027, S9, np.array([1e-10, -1e-10, 5_000.0]), engine.EngineConfig())
    assert s.costs[0] == 0 and s.costs[1] == 0 and s.costs[2] == engine.COMMISSION_ETF * 4
