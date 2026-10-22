"""How much do the results depend on the stock-rate correlation?

Usage: python scripts/stock_rate_corr.py [n_scenarios]
The equity-rate block of the shock covariance comes from Aug 2017-Sep 2026 (the youngest fund's
history), where the S&P 500's monthly correlation with the 5-year zero rate change is -0.16. That
window splits into +0.41 (2017-2021) and -0.47 (2022-2026); over longer history the sign follows the
inflation regime: 1994-1999 -0.30, 2000-2021 +0.36, 1994-2026 +0.09. Positive means rates fall when
stocks fall, so an unlocked ladder gets dearer just when the growth assets are down.

Each variant scales the equity x rate-factor block of the covariance so that the Black-Litterman core's
month-1 correlation with the 5-year rate change hits a target, leaving every volatility and every
other correlation unchanged, then scores the strategies under the headline ESG.
Writes reports/stock_rate_corr.csv.
"""
import dataclasses as dc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import calibrate, engine, nelson_siegel as ns
from lgm.data import yahoo
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS, S1, S2, S6, S9

OUT = Path(__file__).resolve().parents[1] / "reports" / "stock_rate_corr.csv"
WINDOWS = [("1994", "1999"), ("2000", "2021"), ("2017-08", "2021"), ("2022", "2026"), ("2017-08", "2026"), ("1994", "2026")]
STRATEGIES = [IPS, S1, S2, S6, S9]


def history() -> dict[str, float]:
    fh = calibrate.factor_history(start="1990-01-01")
    z5 = pd.Series(ns.zero(fh.values, np.array([5.0]))[:, 0], index=fh.index) * 100
    spy = yahoo.monthly_returns(["SPY"], start="1993-01-01")["SPY"]
    df = pd.concat([spy.rename("eq"), z5.diff().rename("dr")], axis=1, sort=True).dropna()
    return {f"{a}..{b}": float(df.loc[a:b, "eq"].corr(df.loc[a:b, "dr"])) for a, b in WINDOWS}


def scaled(cov: np.ndarray, K: int, c: float) -> tuple[np.ndarray, float]:
    """Cross block times c. Beyond |c| = 1 the result can be slightly indefinite; then negative
    eigenvalues are clipped and the variances restored. Returns the matrix and the most negative
    eigenvalue before the repair (0 if none was needed)."""
    out = cov.copy()
    out[:K, K:K + 3] *= c
    out[K:K + 3, :K] *= c
    vals, vecs = np.linalg.eigh(out)
    if vals.min() >= 0:
        return out, 0.0
    fixed = vecs @ np.diag(np.maximum(vals, 1e-12)) @ vecs.T
    d = np.sqrt(np.diag(cov) / np.diag(fixed))
    return fixed * np.outer(d, d), float(vals.min())


def month1_corr(p, w: np.ndarray, n: int) -> float:
    sc = simulate(p, n=n, seed=11)
    eq = np.expm1(sc.eq_log[:, 0, :len(w)]) @ w
    d5 = ns.zero(sc.beta[:, 1] - sc.beta[:, 0], np.array([5.0]))[:, 0]
    return float(np.corrcoef(eq, d5)[0, 1])


def main(n: int = 20_000):
    hist = history()
    for k, v in hist.items():
        print(f"history {k}: corr(SPY, 5y change) {v:+.2f}")
    core = build_core()
    K, w = len(CORE), np.asarray(core["w_bl"]) / np.sum(core["w_bl"])
    geo = core["table"]["bl_geo_total"].values
    base = esg_params(core["cal"], geo)
    er = np.array([g.expense_ratio for g in CORE])
    c0 = month1_corr(base, w, n)
    targets = {"today (2017-08..2026)": None, "2022..2026": hist["2022..2026"], "zero": 0.0,
               "1994..2026": hist["1994..2026"], "2000..2021": hist["2000..2021"]}
    rows = []
    for label, tgt in targets.items():
        c = 1.0 if tgt is None else tgt / c0
        cov, repaired = scaled(base.cov, K, c)
        if repaired:
            print(f"{label}: scale {c:.2f}, min eigenvalue {repaired:.1e} clipped")
        p = dc.replace(base, cov=cov)
        realised = month1_corr(p, w, n)
        sc = simulate(p, n=n, seed=11)
        for st in STRATEGIES:
            s = engine.summarize(engine.run(dc.replace(st, region_weights=tuple(w)), sc, engine.EngineConfig(eq_er=tuple(er))))
            rows.append({"variant": label, "target_corr": tgt, "block_scale": c, "psd_repair_min_eig": repaired, "model_corr_month1": realised,
                         "strategy": st.name, "median": s["median"], "p5": s["p5"], "cvar5": s["cvar5"], "funded": s["funded"]})
            print(f"{label:22s} corr {realised:+.2f} {st.name[:40]:40s} median {s['median']:,.0f} p5 {s['p5']:,.0f} "
                  f"cvar5 {s['cvar5']:,.0f} funded {s['funded']:.1%}")
    df = pd.DataFrame(rows)
    base_rows = df[df.variant == "today (2017-08..2026)"].set_index("strategy")
    for col in ("median", "p5", "cvar5"):
        df[f"{col}_vs_today"] = df[col] - df.strategy.map(base_rows[col])
    df.round(4).to_csv(OUT, index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
