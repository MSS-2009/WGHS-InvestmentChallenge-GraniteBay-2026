"""Correlation of Taiwan building-cost growth with USD/TWD and with US stocks, by horizon (history and
the generator).

Usage: python scripts/taiwan_fx_corr.py
History: DGBAS construction cost index against Fed H.10 USD/TWD (month ends 2000-2026) and against the
S&P 500 (SPY total return, 2000-2026), correlation of k-month log changes. Model: the headline
generator (growth.scoring.esg_params), cumulative changes from the start; the equity side is the
Black-Litterman core. Writes reports/taiwan_fx_corr.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.calibrate import usd_twd_monthly
from lgm.data import taiwan, yahoo
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params

OUT = Path(__file__).resolve().parents[1] / "reports" / "taiwan_fx_corr.csv"


def main():
    j = pd.concat([np.log(taiwan.cci()).rename("c"), np.log(usd_twd_monthly()).rename("fx")], axis=1).dropna()
    spy = np.log1p(yahoo.monthly_returns(["SPY"], start="1993-01-01")["SPY"]).cumsum()
    je = pd.concat([np.log(taiwan.cci()).rename("c"), spy.rename("eq")], axis=1, sort=True).dropna().loc["2000":]
    r = build_core()
    w = np.asarray(r["w_bl"]) / np.sum(r["w_bl"])
    sc = simulate(esg_params(r["cal"], r["table"]["bl_geo_total"].values), n=20_000, seed=11)
    eq = np.cumsum(np.log(np.exp(sc.eq_log[:, :, :len(w)]) @ w), axis=1)       # core log value after each month
    rows = []
    for k in (1, 3, 12, 24, 36, 72):
        d, de = j.diff(k).dropna(), je.diff(k).dropna()
        dc, dfx = sc.tw_cost_log[:, k] - sc.tw_cost_log[:, 0], sc.fx_log[:, k] - sc.fx_log[:, 0]
        rows.append({"horizon_m": k, "history_corr": round(float(d.corr().iloc[0, 1]), 3),
                     "history_windows": len(d), "independent_windows": len(d) // k,
                     "model_corr": round(float(np.corrcoef(dc, dfx)[0, 1]), 3),
                     "history_corr_equity": round(float(de.corr().iloc[0, 1]), 3),
                     "model_corr_equity": round(float(np.corrcoef(dc, eq[:, k - 1])[0, 1]), 3)})
        print(rows[-1])
    pd.DataFrame(rows).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
