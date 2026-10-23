import numpy as np
import pandas as pd
import pytest

from lgm import engine
from lgm.esg import simulate
from lgm.growth import qualitative
from lgm.growth.portfolio import carve, style_weights, whole_shares
from lgm.growth.universe import CORE
from lgm.profiles import cs_team
from lgm.strategies import IPS


def test_carve_takes_satellite_from_us_large_only():
    w = np.full(len(CORE), 1 / len(CORE))
    out = carve(w, 0.2)
    assert out.sum() == pytest.approx(1.0) and out[-1] == 0.2
    keys = [g.key for g in CORE]
    changed = [keys[i] for i in np.flatnonzero(~np.isclose(out[:-1], w))]
    assert sorted(changed) == ["us_growth", "us_value"]


def test_style_weights_recover_a_known_mix():
    rng = np.random.default_rng(0)
    f = rng.normal(0, 0.04, (5000, 3))
    target = f @ np.array([0.1, 0.7, 0.2]) + rng.normal(0, 0.01, 5000)
    cov = np.cov(np.c_[f, target].T)
    assert style_weights(cov, [0, 1, 2], 3) == pytest.approx([0.1, 0.7, 0.2], abs=0.02)


def test_whole_shares_stay_within_budget_and_close_to_target():
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    px = pd.Series({"A": 101.0, "B": 37.5, "C": 1200.0})
    n = whole_shares(w, px, 10_000)
    spent = (n * px).sum()
    assert spent <= 10_000 and spent > 10_000 - px.max()
    assert abs(n["A"] * px["A"] / 10_000 - 0.5) < 0.02


def test_hrp_weights_are_positive_and_favour_low_variance():
    rng = np.random.default_rng(1)
    r = pd.DataFrame(rng.normal(0, [0.02, 0.04, 0.08], (240, 3)), columns=list("abc"))
    w = qualitative.hrp_weights(r)
    assert w.sum() == pytest.approx(1.0) and (w > 0).all()
    assert w["a"] > w["b"] > w["c"]


def test_basket_commissions_are_charged_per_ticket():
    p = cs_team()
    sc = simulate(p, n=500, seed=3)
    base = engine.run(IPS, sc, engine.EngineConfig())
    sat = engine.run(IPS, sc, engine.EngineConfig(extra_tickets=34, annual_cost=150))
    extra = base["assets_2033"] - sat["assets_2033"]
    assert (extra > 0).all()
    # at least the Jan 2028 purchase and the forced 2031 rebalance, plus six years of reconstitution
    assert extra.min() >= 2 * 34 * engine.COMMISSION_ETF + 150 * 5.9
