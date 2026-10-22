"""The opt-in rate slope on the ladder premium (`EngineConfig.kappa_rate_slope`)."""
import dataclasses as dc

import numpy as np
import pytest

from lgm import engine
from lgm.esg import TAU_GRID, Scenarios
from lgm.strategies import IPS


def _flat(rates: list[float], k: int = 3) -> Scenarios:
    """One scenario per rate, each flat at that rate for the whole horizon."""
    n, m = len(rates), engine.M_2033
    beta = np.zeros((n, m + 1, 3))
    beta[..., 0] = np.log1p(np.asarray(rates))[:, None]
    z = lambda shape: np.zeros(shape)
    return Scenarios(beta, z((n, m, k)), z((n, m + 1)), z((n, m + 1)), z((n, m + 1)), np.zeros(len(TAU_GRID)))


def test_slope_needs_a_reference_rate():
    with pytest.raises(ValueError):
        engine.kappa(engine.M_2027, engine.EngineConfig(kappa_rate_slope=0.5), _flat([0.05]))


def test_slope_moves_the_premium_with_the_rate_and_is_off_by_default():
    sc = _flat([0.04, 0.05, 0.06])
    ref = float(sc.zero_cc(0, 5.0)[1, 0])
    k0 = engine.kappa(engine.M_2027, engine.EngineConfig())
    assert engine.kappa(engine.M_2027, engine.EngineConfig(), sc) == k0
    k = engine.kappa(engine.M_2027, engine.EngineConfig(kappa_rate_slope=0.5, kappa_rate_ref=ref), sc)[:, 0]
    assert k[1] == pytest.approx(k0)
    assert np.allclose(np.diff(k), 0.5 * np.diff(sc.zero_cc(engine.M_2027, 5.0)[:, 0]))


def test_at_the_reference_rate_the_slope_changes_nothing():
    sc = _flat([0.05, 0.05])
    ref = float(sc.zero_cc(0, 5.0)[0, 0])
    a = engine.run(IPS, sc, engine.EngineConfig())
    b = engine.run(IPS, sc, engine.EngineConfig(kappa_rate_slope=0.5, kappa_rate_ref=ref))
    assert np.allclose(a["facility"], b["facility"])
