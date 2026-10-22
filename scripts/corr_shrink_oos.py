"""Which correlation shrinkage forecasts best? Out-of-sample test of the generator's equity correlations.

Usage: python scripts/corr_shrink_oos.py
The generator estimates equity correlations on 109 months (the common window) and shrinks them with
Ledoit-Wolf (`calibrate.calibrate_assets`). This re-estimates them on rolling 109-month windows from
2005 (every 6 months) and scores each choice on the next 36 or 72 months: error in the correlations,
error in the market's and the core's volatility and in the core's active risk against the market (each
using the test window's own volatilities, so only correlations differ), and the realised volatility of
the minimum-variance portfolio built from them. Two panels: the 7 funds with history from 2005, and all
9 with EEM and FXI standing in for EMXC and MCHI before they existed. Writes reports/corr_shrink_oos.csv,
and reports/corr_shrink_ips.csv: the IPS headline (20,000 scenarios, seed 11) under each target.
"""
import dataclasses as dc
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from lgm import engine
from lgm.asof import DATA_END
from lgm.calibrate import calibrate_assets
from lgm.data import yahoo
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

OUT = Path(__file__).resolve().parents[1] / "reports" / "corr_shrink_oos.csv"
IPS_OUT = OUT.with_name("corr_shrink_ips.csv")
STAND_INS = {"EMXC": "EEM", "MCHI": "FXI"}
WINDOW, STEP = 109, 6


def lw_intensity(z: np.ndarray, target: np.ndarray) -> float:
    """Ledoit-Wolf's optimal intensity toward a fixed target (off-diagonal entries of standardised data)."""
    n, k = z.shape
    off = ~np.eye(k, dtype=bool)
    s = z.T @ z / n
    b = sum((np.outer(x, x) - s) ** 2 for x in z) / n ** 2
    return float(min(b[off].sum() / ((s - target)[off] ** 2).sum(), 1.0))


def candidates(est: pd.DataFrame) -> dict[str, np.ndarray]:
    z = ((est - est.mean()) / est.std()).to_numpy()
    k = z.shape[1]
    off = ~np.eye(k, dtype=bool)
    r = np.corrcoef(z, rowvar=False)
    mean_t = np.where(off, r[off].mean(), 1.0)
    d = LedoitWolf().fit(z).shrinkage_
    out = {"sample": r, "zero target, LW intensity": (1 - d) * r + d * np.eye(k),
           "mean target, LW intensity for zero": (1 - d) * r + d * mean_t}
    d_mean = lw_intensity(z, mean_t)
    out["mean target, its own LW intensity"] = (1 - d_mean) * r + d_mean * mean_t
    for x in (0.25, 0.5, 0.75):
        out[f"mean target, intensity {x:.2f}"] = (1 - x) * r + x * mean_t
    return out


def score(panel: pd.DataFrame, w_mkt: np.ndarray, w_core: np.ndarray, horizon: int) -> pd.DataFrame:
    k = panel.shape[1]
    off = ~np.eye(k, dtype=bool)
    rows = []
    for a in range(0, len(panel) - WINDOW - horizon + 1, STEP):
        est, test = panel.iloc[a:a + WINDOW], panel.iloc[a + WINDOW:a + WINDOW + horizon]
        rt, dt, de = np.corrcoef(test.to_numpy(), rowvar=False), test.std().to_numpy(), est.std().to_numpy()
        for name, rh in candidates(est).items():
            row = {"est_end": str(est.index[-1].date()), "candidate": name,
                   "corr_rmse": float(np.sqrt(((rh - rt)[off] ** 2).mean()))}
            for label, w in (("market", w_mkt), ("core", w_core), ("active", w_core - w_mkt)):
                row[f"{label}_vol_log_error"] = float(np.log(np.sqrt(w @ (dt[:, None] * rh * dt) @ w)
                                                             / np.sqrt(w @ (dt[:, None] * rt * dt) @ w)))
            g = np.linalg.solve(de[:, None] * rh * de, np.ones(k))
            g /= g.sum()
            row["min_variance_realised_vol"] = float(np.sqrt(12 * g @ (dt[:, None] * rt * dt) @ g))
            rows.append(row)
    return pd.DataFrame(rows)


def ips_headline(target: str, n: int = 20_000) -> dict:
    """The IPS headline as scripts/report_numbers.py computes it, with equity correlations shrunk toward `target`."""
    r = build_core(cal=calibrate_assets([g.history for g in CORE], equity_shrink_target=target))
    sc = simulate(esg_params(r["cal"], r["table"]["bl_geo_total"].values), n=n, seed=11)
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    s = engine.summarize(engine.run(dc.replace(IPS, region_weights=tuple(r["w_bl"])), sc, cfg))
    return {"target": target, "core_volatility": float(np.sqrt(r["w_bl"] @ r["cov"] @ r["w_bl"])),
            **{k: s[k] for k in ("median", "p5", "cvar5", "real_median")}}


def main():
    tickers = [g.history for g in CORE]
    panel = pd.DataFrame({t: np.log1p(yahoo.monthly_returns([STAND_INS.get(t, t)], start="2000-01-01")[STAND_INS.get(t, t)])
                          for t in tickers}).loc[:DATA_END].dropna()
    r = build_core()
    w_mkt, w_core = np.asarray(r["w_mkt"]), np.asarray(r["w_bl"])
    out = []
    for funds in (7, 9):
        wm, wc = w_mkt[:funds] / w_mkt[:funds].sum(), w_core[:funds] / w_core[:funds].sum()
        for horizon in (36, 72):
            df = score(panel.iloc[:, :funds], wm, wc, horizon)
            rms = lambda s: float(np.sqrt((s ** 2).mean()))
            agg = df.groupby("candidate", sort=False).agg(
                windows=("est_end", "size"), corr_rmse=("corr_rmse", "mean"),
                market_vol_bias=("market_vol_log_error", "mean"), market_vol_rms=("market_vol_log_error", rms),
                core_vol_bias=("core_vol_log_error", "mean"), active_risk_bias=("active_vol_log_error", "mean"),
                min_variance_vol=("min_variance_realised_vol", "mean")).reset_index()
            agg.insert(0, "horizon_m", horizon)
            agg.insert(0, "funds", funds)
            out.append(agg)
            print(f"\n{funds} funds, next {horizon} months ({len(df) // agg.shape[0]} windows, panel {panel.index[0]:%Y-%m} on)")
            print(agg.drop(columns=["funds", "horizon_m", "windows"]).round(4).to_string(index=False))
    pd.concat(out).round(4).to_csv(OUT, index=False)
    ips = pd.DataFrame([ips_headline(t) for t in ("zero", "mean")])
    ips.round(4).to_csv(IPS_OUT, index=False)
    print(ips.to_string(index=False))
    print(f"Wrote {OUT} and {IPS_OUT}")


if __name__ == "__main__":
    main()
