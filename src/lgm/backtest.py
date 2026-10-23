"""Historical replay: run the strategy rules on real 2005-2026 paths instead of simulated ones.

Each start month gives one 74-month path. Rate changes and equity returns are history's, applied
from today's curve, so a replay asks "what if the next six years repeat the six years after that
month?" With `recentre`, each asset's returns are shifted so their full-sample mean matches the
model's expected return: history's volatility, crashes and sequencing stay, its unusually strong
US decade does not.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import engine
from .asof import CURVE_DATE, DATA_END
from .calibrate import factor_history, usd_twd_monthly
from .curve import bootstrap
from .data import fred, treasury, yahoo
from .esg import Scenarios, initial_state

PROXY = {"EMXC": "EEM", "MCHI": "FXI"}     # longer histories for the two young funds


def history_paths(history_tickers: list[str], start: str = "2005-04-30", end: str = DATA_END,
                  months: int = engine.M_2033, recentre: np.ndarray | None = None,
                  curve_date: str = CURVE_DATE,
                  real_tw_cost: bool = True) -> tuple[Scenarios, list[pd.Timestamp]]:
    tickers = [PROXY.get(t, t) for t in history_tickers]
    eq = np.log1p(yahoo.monthly_returns(tickers, start="2000-01-01")).loc[start:end]
    if recentre is not None:
        # Overlapping windows use the middle months more often, so centre on the mean the paths see
        n_paths = len(eq) - months
        cover = np.zeros(len(eq))
        for j in range(n_paths):
            cover[j + 1:j + 1 + months] += 1
        seen = (eq.values * cover[:, None]).sum(0) / cover.sum()
        eq = eq - seen + np.log1p(np.asarray(recentre)) / 12
    fh = factor_history().loc[:end]
    fh.index = fh.index + pd.offsets.MonthEnd(0)
    fx = np.log(usd_twd_monthly())
    cpi = fred.cpi()["CPIAUCNS"]
    infl = (cpi / cpi.shift(12) - 1).dropna()
    infl.index = infl.index + pd.offsets.MonthEnd(0)
    idx = eq.index
    beta0, resid = initial_state(bootstrap(treasury.par_curve(curve_date)))
    starts, beta, eql, inf, fxl = [], [], [], [], []
    for j in range(len(idx) - months):
        s, path = idx[j], idx[j:j + months + 1]
        f = fh.reindex(path).ffill().values
        beta.append(beta0 + (f - f[0]))
        eql.append(eq.iloc[j + 1:j + 1 + months].values)
        inf.append(infl.reindex(path).ffill().values)
        x = fx.reindex(path).ffill().values
        fxl.append(x - x[0])
        starts.append(s)
    n = len(starts)
    if real_tw_cost:
        from .data import taiwan
        cci = taiwan.cci()
        tw_log = np.log(cci)
        tw_paths = []
        for j in range(len(idx) - months):
            path = idx[j:j + months + 1]
            c = tw_log.reindex(path).ffill().values
            tw_paths.append(c - c[0])
        tw = np.array(tw_paths)
    else:
        tw = np.tile(np.arange(months + 1) / 12 * np.log1p(0.04), (n, 1))
    sc = Scenarios(beta=np.array(beta), eq_log=np.array(eql), infl=np.array(inf), fx_log=np.array(fxl),
                   tw_cost_log=tw, resid=resid)
    return sc, starts
