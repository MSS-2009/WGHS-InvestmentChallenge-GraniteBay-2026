import dataclasses as dc

import numpy as np
import pandas as pd

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


def test_history_paths_real_taiwan_cost():
    from lgm.data import taiwan

    tickers = [g.history for g in CORE]
    sc_def, starts = history_paths(tickers, real_tw_cost=False)
    sc_real, starts_real = history_paths(tickers, real_tw_cost=True)

    assert starts == starts_real
    assert len(starts) == 184

    # Default has exact 4% straight line
    expected_4pct = np.arange(engine.M_2033 + 1) / 12 * np.log1p(0.04)
    assert np.allclose(sc_def.tw_cost_log[0], expected_4pct)
    assert np.allclose(sc_def.tw_cost_log[-1], expected_4pct)

    # Real Taiwan cost paths vary by historical window and start at 0
    assert sc_real.tw_cost_log.shape == (184, engine.M_2033 + 1)
    assert np.allclose(sc_real.tw_cost_log[:, 0], 0.0)
    assert not np.allclose(sc_real.tw_cost_log[0], sc_real.tw_cost_log[-1])

    # Spot-check first path against raw DGBAS series
    cci = taiwan.cci()
    s0 = starts[0]
    first_path_dates = [s0 + pd.offsets.MonthEnd(m) for m in range(engine.M_2033 + 1)]
    expected_first_path = np.log(cci.loc[first_path_dates].values / cci.loc[s0])
    assert np.allclose(sc_real.tw_cost_log[0], expected_first_path)
