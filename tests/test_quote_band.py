"""The 2031 quote taken over a band of scenarios (engine.conditional_2031_band)."""
import dataclasses as dc

import numpy as np

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS


def _setup(n=2000):
    r = build_core()
    p = esg_params(r["cal"], r["table"]["bl_geo_total"].values)
    st = dc.replace(IPS, region_weights=tuple(r["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    sc = simulate(p, n=n, seed=11)
    return st, sc, engine.run(st, sc, cfg, snapshot_2031=True), p, cfg


def test_band_of_one_is_the_single_scenario_quote():
    st, sc, res, p, cfg = _setup()
    one = engine.conditional_2031(st, sc, res, p, n_inner=500, cfg=cfg)
    band = engine.conditional_2031_band(st, sc, res, p, width=0.0, k=1, n_inner=500, cfg=cfg)
    assert band["scenarios"] == [one["scenario"]]
    assert band["floor"] == one["floor"]
    assert np.isclose(band["p10"], np.percentile(one["inner"], 10))


def test_band_quote_is_the_median_of_its_scenarios():
    st, sc, res, p, cfg = _setup()
    band = engine.conditional_2031_band(st, sc, res, p, k=5, n_inner=500, cfg=cfg)
    floors = [res["floor_2033"][i] for i in band["scenarios"]]
    assert len(set(band["scenarios"])) == 5
    assert band["floor"] == float(np.median(floors))
    assert band["floor_range"] == (min(floors), max(floors))
    assert band["p10"] < band["p50"] < band["p90"]
