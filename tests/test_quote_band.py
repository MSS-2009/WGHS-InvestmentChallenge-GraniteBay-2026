"""The 2031 quote taken over a band of scenarios (engine.conditional_2031_band)."""
import dataclasses as dc
from types import SimpleNamespace

import numpy as np
import pytest

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS


def _quote_stub(n=3):
    state = engine.State(
        eq=np.zeros((n, 3)), vgit=np.zeros(n), ibtm_face=np.zeros(n), floor_face=np.zeros(n),
        cash=np.zeros(n), locked=np.zeros((n, engine.N_PAY)), costs=np.zeros(n),
    )
    sc = SimpleNamespace(n=n)
    res = {
        "state_2031": state,
        "floor_2033": np.ones(n),
        "growth_2031": np.arange(n, dtype=float),
        "assets_2031": np.arange(n, dtype=float),
    }
    return sc, res


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


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"q": -0.1}, "q must be in"),
    ({"q": np.nan}, "q must be a finite"),
    ({"width": -0.1}, "width must be in"),
    ({"width": True}, "width must be a finite"),
    ({"k": 0}, "k must be a positive integer"),
    ({"n_inner": 0}, "n_inner must be a positive integer"),
    ({"seed": True}, "seed must be a nonnegative integer"),
])
def test_band_rejects_invalid_selection_controls(kwargs, message):
    with pytest.raises(ValueError, match=message):
        engine.conditional_2031_band(None, None, None, None, **kwargs)


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"k": 4}, "k must be no greater than"),
    ({"percentiles": ()}, "percentiles must be a nonempty"),
    ({"percentiles": (5, 5)}, "percentiles must be a nonempty"),
    ({"percentiles": (101,)}, "percentiles must be a nonempty"),
])
def test_band_rejects_impossible_scenario_counts_and_percentiles(kwargs, message):
    sc, res = _quote_stub()
    call_kwargs = {"k": 3, **kwargs}
    with pytest.raises(ValueError, match=message):
        engine.conditional_2031_band(IPS, sc, res, None, **call_kwargs)


@pytest.mark.parametrize("i", [-1, 3, True, 1.5])
def test_single_quote_rejects_invalid_scenario_index(i):
    sc, res = _quote_stub()
    with pytest.raises(ValueError, match="i must be an integer scenario index"):
        engine.conditional_2031(IPS, sc, res, None, i=i)


def test_single_quote_requires_a_2031_state_snapshot():
    sc, res = _quote_stub()
    del res["state_2031"]
    with pytest.raises(ValueError, match="snapshot_2031=True"):
        engine.conditional_2031(IPS, sc, res, None, i=0)


def test_single_quote_rejects_invalid_configuration_and_drift_flag():
    with pytest.raises(ValueError, match="engine.EngineConfig"):
        engine.conditional_2031(IPS, None, None, None, cfg={})
    with pytest.raises(ValueError, match="keep_drift must be boolean"):
        engine.conditional_2031(IPS, None, None, None, keep_drift="false")
