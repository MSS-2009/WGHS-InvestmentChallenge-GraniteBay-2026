"""Do rates fall when stocks crash? Tests the 'crash co-movement' gap left by docs/loop/r4_rates_findings.md.

Usage: python scripts/crash_comovement.py
History: the 60/30/10 VTI/VEA/VWO core and VTI alone against the monthly change in the 5-year zero
rate (Nelson-Siegel, Treasury), Aug 2007-today (VEA's first month). For the worst 5% of equity months:
the correlation within them (the r4 statistic), its p-value against a bivariate normal with the
full-sample correlation and the same truncation, a bootstrap interval, and what matters for a buyer of
an unlocked ladder: the average rate change in those months, history against the model.
Writes reports/crash_comovement.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import calibrate, nelson_siegel as ns
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE

OUT = Path(__file__).resolve().parents[1] / "reports" / "crash_comovement.csv"
Q = 0.05


def crash_stats(eq: np.ndarray, dr: np.ndarray) -> dict:
    full, crash = calibrate.crash_correlation(eq, dr, q=Q)
    m = eq <= np.quantile(eq, Q)
    return {"n_months": len(eq), "n_crash": int(m.sum()), "full_corr": full, "crash_corr": crash,
            "crash_mean_dr": float(dr[m].mean()), "crash_share_rates_down": float((dr[m] < 0).mean()),
            "all_mean_dr": float(dr.mean())}


def main(n_null: int = 5000, n_boot: int = 2000, n_sim: int = 20_000):
    fh = calibrate.factor_history(start="1994-01-01")
    px = calibrate.yahoo.monthly_returns(["VTI", "VEA", "VWO"], start="2000-01-01")
    z5 = pd.Series(ns.zero(fh.values, np.array([5.0]))[:, 0], index=fh.index) * 100
    rng = np.random.default_rng(0)
    rows = []
    for name, eq in (("core 60/30/10", 0.6 * px.VTI + 0.3 * px.VEA + 0.1 * px.VWO), ("VTI", px.VTI)):
        df = pd.concat([eq.rename("eq"), z5.diff().rename("dr")], axis=1, sort=True).dropna()
        e, d = df["eq"].values, df["dr"].values
        s = crash_stats(e, d)
        n, rho = len(e), s["full_corr"]
        null = []
        for _ in range(n_null):
            x = rng.standard_normal(n)
            null.append(calibrate.crash_correlation(x, rho * x + np.sqrt(1 - rho ** 2) * rng.standard_normal(n), q=Q)[1])
        boot = [calibrate.crash_correlation(e[i], d[i], q=Q)[1] for i in (rng.integers(0, n, n) for _ in range(n_boot))]
        boot_mean = [d[i][e[i] <= np.quantile(e[i], Q)].mean() for i in (rng.integers(0, n, n) for _ in range(n_boot))]
        s.update({"source": "history", "equity": name, "crash_corr_pvalue": float((np.array(null) >= s["crash_corr"]).mean()),
                  "crash_corr_ci90": (float(np.nanquantile(boot, .05)), float(np.nanquantile(boot, .95))),
                  "crash_mean_dr_ci90": (float(np.quantile(boot_mean, .05)), float(np.quantile(boot_mean, .95)))})
        rows.append(s)

    # Model: month-1 shocks of today's headline ESG, equity core at its Black-Litterman weights
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=n_sim, seed=11)
    w = np.asarray(core["w_bl"]) / np.sum(core["w_bl"])
    eq_m = np.expm1(sc.eq_log[:, 0, :len(CORE)]) @ w
    z0 = ns.zero(sc.beta[:, 0], np.array([5.0]))[:, 0]
    z1 = ns.zero(sc.beta[:, 1], np.array([5.0]))[:, 0]
    s = crash_stats(eq_m, (z1 - z0) * 100)
    s.update({"source": "model (month 1)", "equity": "Black-Litterman core"})
    rows.append(s)
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    for r in rows:
        print(f"{r['source']:16s} {r['equity']:22s} n={r['n_months']:6d} crash n={r['n_crash']:5d}: corr all "
              f"{r['full_corr']:+.2f}, in crashes {r['crash_corr']:+.2f}"
              + (f" (p {r['crash_corr_pvalue']:.2f}, 90% CI {r['crash_corr_ci90'][0]:+.2f}..{r['crash_corr_ci90'][1]:+.2f})"
                 if r["source"] == "history" else "")
              + f"; mean 5y change in crashes {r['crash_mean_dr']:+.3f} pts"
              + (f" (90% CI {r['crash_mean_dr_ci90'][0]:+.3f}..{r['crash_mean_dr_ci90'][1]:+.3f})" if r["source"] == "history" else "")
              + f", rates down in {r['crash_share_rates_down']:.0%}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
