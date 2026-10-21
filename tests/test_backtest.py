import dataclasses as dc

import numpy as np

from lgm import engine
from lgm.backtest import history_paths
from lgm.growth.universe import CORE
from lgm.strategies import IPS


def test_history_paths_start_on_todays_curve_and_fund_the_payments():
    sc, starts = history_paths([g.history for g in CORE])
    assert sc.eq_log.shape == (len(starts), engine.M_2033, len(CORE))
    # every path starts from today's curve, so month-0 rates are identical across paths
    assert np.allclose(sc.zero_cc(0, [2.0, 10.0]), sc.zero_cc(0, [2.0, 10.0])[0])
    w = np.full(len(CORE), 1 / len(CORE))
    r = engine.run(dc.replace(IPS, region_weights=tuple(w)), sc, engine.EngineConfig(eq_er=(0.0005,) * len(CORE)))
    assert r["funded"].all()


def test_recentring_matches_the_target_mean():
    target = np.full(len(CORE), 0.06)
    sc, _ = history_paths([g.history for g in CORE], recentre=target)
    assert abs(np.expm1(sc.eq_log.mean() * 12) - 0.06) < 1e-6
