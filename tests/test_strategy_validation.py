"""Guard strategy and engine allocation inputs against silent capital misallocation."""
from types import SimpleNamespace

import numpy as np
import pytest

from lgm import engine
from lgm.strategies import IPS, Strategy


@pytest.mark.parametrize(("field", "value"), [
    ("lock_2027", 1.01),
    ("lock_2028", -0.01),
    ("lock_2031", np.nan),
    ("equity_share", True),
    ("band", np.inf),
    ("floor_share_2031", -0.1),
    ("floor_share", 1.1),
    ("contribution_share", False),
    ("equity_share_end", np.nan),
    ("ratchet_share", 1.1),
])
def test_strategy_fraction_controls_are_bounded(field, value):
    with pytest.raises(ValueError, match=field):
        Strategy("invalid", **{field: value})


@pytest.mark.parametrize("weights", [
    (), (0.5, 0.4), (0.5, -0.1, 0.6), (np.nan, 0.5, 0.5), (True, False),
])
def test_strategy_region_weights_must_be_finite_nonnegative_and_sum_to_one(weights):
    with pytest.raises(ValueError, match="region_weights"):
        Strategy("invalid", region_weights=weights)


@pytest.mark.parametrize("kwargs", [
    {"bond_vehicle": "BND"},
    {"floor_year": 2033},
    {"ratchet_trigger": -1.0},
    {"ratchet_trigger": np.inf},
])
def test_strategy_rejects_unsupported_discrete_and_ratchet_inputs(kwargs):
    with pytest.raises(ValueError):
        Strategy("invalid", **kwargs)


def test_strategy_normalizes_weights_to_a_float_tuple():
    st = Strategy("valid", region_weights=np.array([0.6, 0.3, 0.1]))
    assert st.region_weights == (0.6, 0.3, 0.1)


@pytest.mark.parametrize(("strategy", "cfg", "message"), [
    (Strategy("wrong equity count", region_weights=(0.5, 0.5)), engine.EngineConfig(), "region_weights"),
    (IPS, engine.EngineConfig(eq_er=(0.001, 0.002)), "cfg.eq_er"),
    (IPS, engine.EngineConfig(eq_er=(0.001, np.nan, 0.002)), "cfg.eq_er"),
    (IPS, engine.EngineConfig(eq_er=(0.001, True, 0.002)), "cfg.eq_er"),
])
def test_engine_rejects_allocation_vectors_not_matching_the_equity_universe(strategy, cfg, message):
    sc = SimpleNamespace(n=2, eq_log=np.zeros((2, engine.M_2033, 3)))
    with pytest.raises(ValueError, match=message):
        engine.run(strategy, sc, cfg)
