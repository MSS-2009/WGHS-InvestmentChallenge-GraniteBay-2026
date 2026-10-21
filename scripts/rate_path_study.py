"""Which expected path for rates should the scenario generator use?

Usage: python scripts/rate_path_study.py
From every month-end since 1994 whose outcome is known, forecast the zero curve 74 months ahead
(the gap between today and Laura's January 2033 settlement) three ways, then score each against
the curve that actually happened:
  unchanged      today's curve (the model's current assumption)
  forwards       the curve's own forward rates (pure expectations hypothesis)
  kim_wright     forwards minus the Kim-Wright term premium (expected short rates plus today's
                 term premium on a bond of that maturity)
The score that matters most for Laura is the error in the cost of ten $50,000 payments in 2033.
It then runs the recommended plan with the Kim-Wright path as a scenario, today.
Writes reports/rate_path_study.csv and reports/rate_path_scenario.json.
"""
import dataclasses as dc
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.calibrate import factor_history
from lgm.curve import bootstrap
from lgm.data import fed
from lgm.data.treasury import par_curve
from lgm.esg import initial_state, simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.nelson_siegel import loadings
from lgm.nelson_siegel import zero as ns_zero
from lgm.strategies import IPS

OUT = Path(__file__).resolve().parents[1] / "reports"
H = engine.M_2033 / 12                       # years ahead
TENORS = np.array([2.0, 5.0, 10.0])
PAY = np.arange(10, dtype=float) + 1e-6       # the ten payments, 0-9 years after settlement


def curves(beta: np.ndarray, tau: np.ndarray) -> np.ndarray:
    return ns_zero(beta, tau)                 # continuously compounded


def kw_adjustment(kw_row: pd.Series, h: float, tau: np.ndarray) -> np.ndarray:
    """Expected change versus forwards: minus the average forward term premium between h and
    h + tau, plus today's term premium on a tau-year bond (held fixed)."""
    grid = np.arange(1, 11, dtype=float)
    fftp = kw_row[[f"FFTP{i}" for i in range(1, 11)]].values.astype(float)
    fytp = kw_row[[f"FYTP{i}" for i in range(1, 11)]].values.astype(float)
    out = []
    for t in np.atleast_1d(tau):
        s = np.linspace(h, h + t, 41)
        avg_fwd_tp = np.interp(np.minimum(s, 10), grid, fftp).mean()
        out.append(-avg_fwd_tp + np.interp(min(t, 10), grid, fytp))
    return np.array(out)


def main():
    fh = factor_history()
    fh.index = fh.index + pd.offsets.MonthEnd(0)
    kw = fed.kim_wright().resample("ME").last()
    months = int(round(H * 12))
    rows = []
    for i, t in enumerate(fh.index[:-months]):
        later = fh.index[i + months]
        if later not in fh.index or t not in kw.index:
            continue
        b0, b1 = fh.loc[t].values, fh.loc[later].values
        actual = curves(b1, TENORS)
        actual_pay = curves(b1, PAY)
        unchanged, unchanged_pay = curves(b0, TENORS), curves(b0, PAY)
        long_ = curves(b0, H + TENORS) * (H + TENORS)
        fwd = (long_ - curves(b0, np.array([H]))[0] * H) / TENORS
        long_p = curves(b0, H + PAY) * (H + PAY)
        fwd_pay = (long_p - curves(b0, np.array([H]))[0] * H) / PAY
        adj, adj_p = kw_adjustment(kw.loc[t], H, TENORS), kw_adjustment(kw.loc[t], H, PAY)
        cost = lambda z: float((50_000 * np.exp(-z * PAY)).sum())
        true_cost = cost(actual_pay)
        for name, z, zp in (("unchanged", unchanged, unchanged_pay), ("forwards", fwd, fwd_pay),
                            ("kim_wright", fwd + adj, fwd_pay + adj_p)):
            rows.append({"date": t.date(), "method": name, **{f"err_{int(k)}y": float(z[j] - actual[j]) for j, k in enumerate(TENORS)},
                         "cost_err_pct": cost(zp) / true_cost - 1})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "rate_path_study.csv", index=False)
    stats = df.groupby("method").agg(**{f"bias_{c}": (c, "mean") for c in ["err_2y", "err_5y", "err_10y", "cost_err_pct"]},
                                     **{f"rmse_{c}": (c, lambda x: float(np.sqrt((x ** 2).mean()))) for c in ["err_2y", "err_5y", "err_10y", "cost_err_pct"]})
    print(f"{df['date'].nunique()} forecast dates, {df['date'].min()} to {df['date'].max()}, horizon {months} months")
    print(stats.round(4).T.to_string())
    for era, (a, b) in {"1994-2006 starts": ("1994", "2006"), "2007-2020 starts": ("2007", "2020")}.items():
        sub = df[(pd.to_datetime(df["date"]) >= a) & (pd.to_datetime(df["date"]) <= f"{b}-12-31")]
        print(era, sub.groupby("method")["cost_err_pct"].agg(lambda x: float(np.sqrt((x ** 2).mean()))).round(4).to_dict())


def scenario(curve_date: str = "2026-10-20", kw_month: str = "2026-09-30", n: int = 20_000):
    """The plan under today's Kim-Wright expected path: shift the factors' long-run target so the
    expected January 2033 curve matches it, given each factor's mean reversion."""
    kw = fed.kim_wright().resample("ME").last()
    beta0, _ = initial_state(bootstrap(par_curve(curve_date)))
    tau = np.array([0.5, 1, 2, 3, 5, 7, 10])
    fwd = (ns_zero(beta0, H + tau) * (H + tau) - ns_zero(beta0, np.array([H]))[0] * H) / tau
    target = fwd + kw_adjustment(kw.loc[kw_month], H, tau)
    d_beta, *_ = np.linalg.lstsq(loadings(tau), target - ns_zero(beta0, tau), rcond=None)
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_kw = dc.replace(p, beta_mu=p.beta0 + d_beta / (1 - p.phi ** engine.M_2033))
    st = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    out = {"expected_2033_curve": {f"{t:g}y": {"today": round(float(a), 4), "kim_wright": round(float(b), 4)}
                                   for t, a, b in zip(tau, ns_zero(beta0, tau), target)}}
    for name, pp in (("unchanged", p), ("kim_wright", p_kw)):
        r = engine.run(st, simulate(pp, n=n, seed=11), cfg)
        out[name] = {"median": round(float(np.median(r["facility"]))), "p5": round(float(np.percentile(r["facility"], 5)))}
    (OUT / "rate_path_scenario.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
    scenario()
