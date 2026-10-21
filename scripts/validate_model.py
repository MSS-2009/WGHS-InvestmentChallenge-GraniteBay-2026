"""How good is the model? Statistical checks, convergence, historical replay and BL sensitivity.

Usage: python scripts/validate_model.py [n_scenarios]
Writes reports/validation_esg.csv, validation_convergence.csv, backtest.csv, bl_sensitivity.csv.
"""
import copy
import dataclasses as dc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.backtest import history_paths
from lgm.calibrate import factor_history
from lgm.data import yahoo
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.nelson_siegel import zero as ns_zero
from lgm.strategies import IPS, S1, S2, S9

OUT = Path(__file__).resolve().parents[1] / "reports"
YEARS = engine.M_2033 / 12


def esg_checks(core: dict, n: int) -> pd.DataFrame:
    """Does the generator reproduce its inputs, and are its rate paths plausible against history?"""
    t, cal = core["table"], core["cal"]
    geo = t["bl_geo_total"].values
    sc = simulate(esg_params(cal, geo), n=n, seed=11)
    K = len(CORE)
    rows = []
    hist = np.log1p(yahoo.monthly_returns([g.history for g in CORE], start="2000-01-01")).loc["2005-01-01":"2026-09-30"]
    for k, g in enumerate(CORE):
        r = sc.eq_log[:, :, k]
        cum = r.sum(1)
        h = hist[g.history]
        rows.append({"check": f"{g.etf} volatility", "target": cal["ann_vol"][g.history],
                     "model": float(r.std() * np.sqrt(12)), "history_2005_2026": float(h.std() * np.sqrt(12))})
        rows.append({"check": f"{g.etf} median annual return", "target": geo[k],
                     "model": float(np.expm1(np.median(cum) / YEARS)), "history_2005_2026": float(np.expm1(h.mean() * 12))})
        rows.append({"check": f"{g.etf} monthly excess kurtosis", "target": np.nan,
                     "model": float(pd.Series(r[:2000].ravel()).kurt()), "history_2005_2026": float(h.kurt())})
    i_v, i_e = [g.key for g in CORE].index("us_value"), [g.key for g in CORE].index("europe")
    rows.append({"check": "Correlation VTV-VGK", "target": float(cal["corr"].iloc[i_v, i_e]),
                 "model": float(np.corrcoef(sc.eq_log[:, :, i_v].ravel(), sc.eq_log[:, :, i_e].ravel())[0, 1]),
                 "history_2005_2026": float(hist[CORE[i_v].history].corr(hist[CORE[i_e].history]))})
    # 10-year zero yield in January 2033 vs history's 74-month changes
    y0 = float(np.expm1(sc.zero_cc(0, [10.0])[0, 0]))
    y33 = np.expm1(sc.zero_cc(engine.M_2033, [10.0])[:, 0])
    fh = factor_history()
    y_hist = np.expm1(ns_zero(fh.values, np.array([10.0]))[:, 0])
    d_hist = pd.Series(y_hist[engine.M_2033:] - y_hist[:-engine.M_2033])
    d_mod = y33 - y0
    for q in (5, 50, 95):
        rows.append({"check": f"10-year yield change to Jan 2033, p{q}", "target": np.nan,
                     "model": float(np.percentile(d_mod, q)), "history_2005_2026": float(np.percentile(d_hist, q))})
    rows.append({"check": "10-year yield today (Oct 20, 2026)", "target": y0, "model": y0, "history_2005_2026": np.nan})
    return pd.DataFrame(rows)


def convergence(core: dict, n: int, seeds=range(1, 9)) -> pd.DataFrame:
    geo = core["table"]["bl_geo_total"].values
    p = esg_params(core["cal"], geo)
    st = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    rows = []
    for s in seeds:
        r = engine.summarize(engine.run(st, simulate(p, n=n, seed=s), cfg))
        rows.append({"seed": s, **{k: r[k] for k in ("funded", "p5", "median", "p95", "cvar5")}})
    df = pd.DataFrame(rows)
    se = df.std() / np.sqrt(len(df))
    print(f"convergence over {len(df)} seeds x {n:,}: median {df['median'].mean():,.0f} +/- {se['median']:,.0f} (s.e.),"
          f" p5 {df['p5'].mean():,.0f} +/- {se['p5']:,.0f}")
    return df


def backtest(core: dict) -> pd.DataFrame:
    t, w_mkt = core["table"], core["w_mkt"]
    idx = {g.key: i for i, g in enumerate(CORE)}

    def basket(keys, total):
        v = np.zeros(len(CORE))
        s = sum(w_mkt[idx[k]] for k in keys)
        for k in keys:
            v[idx[k]] = total * w_mkt[idx[k]] / s
        return v

    base = basket(["us_growth", "us_value", "us_small"], 0.6) + basket(["europe", "japan", "pacific", "canada"], 0.3) \
        + basket(["em_xchina", "china"], 0.1)
    er = tuple(g.expense_ratio for g in CORE)
    three = engine.EngineConfig(eq_er=er, fund_groups=((0, 1, 2), (3, 4, 5, 6), (7, 8)))   # VTI, VEA, VWO
    plans = [("IPS, Black-Litterman core", IPS, core["w_bl"], engine.EngineConfig(eq_er=er)),
             ("IPS, 60/30/10 ETFs", IPS, base, three), ("S9 Plans v2 P5", S9, base, three),
             ("S2 60/40, reserve bought in 2033", S2, base, three), ("S1 all equity, reserve bought in 2033", S1, base, three)]
    rows = []
    for label, rec in (("History as it happened", None), ("History re-centred on BL expected returns", t["bl_geo_total"].values)):
        sc, starts = history_paths([g.history for g in CORE], recentre=rec)
        for name, st, w, cfg in plans:
            r = engine.run(dc.replace(st, region_weights=tuple(w)), sc, cfg)
            f = r["facility"]
            i = int(np.argmin(f))
            rows.append({"paths": label, "n_paths": sc.n, "first_start": starts[0].date(), "last_start": starts[-1].date(),
                         "strategy": name, "funded": float(r["funded"].mean()), "p5": np.percentile(f, 5),
                         "median": float(np.median(f)), "p95": np.percentile(f, 95), "worst": float(f.min()),
                         "worst_start": starts[i].date()})
    return pd.DataFrame(rows)


def bl_sensitivity(core: dict) -> pd.DataFrame:
    rows = []
    cov, w_mkt = core["cov"], core["w_mkt"]
    for tau in (0.025, 0.05, 0.10):
        for sd in (0.015, 0.025, 0.05):
            cfg = copy.deepcopy(core["cfg"])
            cfg["tau"], cfg["single_source_std"] = tau, sd
            r = build_core(cfg=cfg, cal=core["cal"])
            a = r["w_bl"] - w_mkt
            rows.append({"tau": tau, "value_view_std": sd, **dict(zip([g.etf for g in CORE], r["w_bl"].round(4))),
                         "tracking_error_vs_market": float(np.sqrt(a @ cov @ a)),
                         **{f"single_optimum_{g.etf}": x for g, x in zip(CORE, r["table"]["w_bl_point"].round(4))}})
    return pd.DataFrame(rows)


def main(n: int = 20_000):
    core = build_core()
    e = esg_checks(core, n)
    e.round(4).to_csv(OUT / "validation_esg.csv", index=False)
    c = convergence(core, n)
    c.round(2).to_csv(OUT / "validation_convergence.csv", index=False)
    b = backtest(core)
    b.round(3).to_csv(OUT / "backtest.csv", index=False)
    s = bl_sensitivity(core)
    s.round(4).to_csv(OUT / "bl_sensitivity.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(e.round(4).to_string(index=False))
        print(b.drop(columns=["first_start", "last_start"]).round(0).to_string(index=False))
        print(s.round(3).to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
