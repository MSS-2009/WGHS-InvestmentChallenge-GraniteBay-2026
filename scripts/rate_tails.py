"""Validation script for interest-rate tails across horizons and model options.

Generates reports/rate_tails.csv comparing historical rate changes against
today's model and candidate tail treatments (Gaussian rates, independent t,
and partly shared mixing variables).
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from lgm import calibrate, esg, profiles, nelson_siegel as ns

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_CSV = REPORTS_DIR / "rate_tails.csv"

HORIZONS = [1, 2, 3, 12, 74]
TENORS = [5.0, 10.0]


def run_rate_tails(n: int = 20_000, seed: int = 11) -> pd.DataFrame:
    rows = []

    # 1. Historical data (1994-2026 month-ends)
    fh = calibrate.factor_history(start="1994-01-01")
    eq = calibrate.yahoo.monthly_returns(["VTI", "VEA", "VWO"], start="2000-01-01")
    eq_us = eq["VTI"]
    eq_core = 0.6 * eq["VTI"] + 0.3 * eq["VEA"] + 0.1 * eq["VWO"]

    z5_hist = pd.Series(ns.zero(fh.values, np.array([5.0]))[:, 0], index=fh.index) * 100.0
    dz5_hist = z5_hist.diff().dropna()
    df_us = pd.concat([eq_us.rename("eq"), dz5_hist.rename("dr")], axis=1, sort=True).dropna()
    df_core = pd.concat([eq_core.rename("eq"), dz5_hist.rename("dr")], axis=1, sort=True).dropna()

    full_us_h, crash_us_h = calibrate.crash_correlation(df_us["eq"], df_us["dr"])
    full_core_h, crash_core_h = calibrate.crash_correlation(df_core["eq"], df_core["dr"])

    for tau in TENORS:
        z = pd.Series(ns.zero(fh.values, np.array([tau]))[:, 0], index=fh.index) * 100.0
        for h in HORIZONS:
            dh = z.diff(h).dropna()
            rows.append({
                "variant": "history",
                "tenor": f"{int(tau)}y",
                "horizon_m": h,
                "sd": round(float(dh.std()), 4),
                "excess_kurt": round(float(stats.kurtosis(dh)), 4),
                "min": round(float(dh.min()), 4),
                "p0_1": round(float(np.percentile(dh, 0.1)), 4),
                "p99_9": round(float(np.percentile(dh, 99.9)), 4),
                "max": round(float(dh.max()), 4),
                "full_corr_us": round(full_us_h, 4),
                "crash_corr_us": round(crash_us_h, 4),
                "full_corr_core": round(full_core_h, 4),
                "crash_corr_core": round(crash_core_h, 4),
            })

    # 2. Simulated model options (20,000 scenarios, seed 11)
    p_base = profiles.cs_team(t_dof=5.0)

    sim_variants = [
        ("today_t5", dc.replace(p_base, rate_dof=None, rate_shared=0.0)),
        ("rate_gaussian", dc.replace(p_base, rate_dof="gaussian", rate_shared=0.0)),
        ("rate_indep_t14", dc.replace(p_base, rate_dof=14.0, rate_shared=0.0)),
        ("rate_indep_t8", dc.replace(p_base, rate_dof=8.0, rate_shared=0.0)),
        ("rate_shared_0.10", dc.replace(p_base, rate_dof="gaussian", rate_shared=0.10)),
        ("rate_shared_0.25", dc.replace(p_base, rate_dof="gaussian", rate_shared=0.25)),
        ("model_gaussian", dc.replace(p_base, t_dof=None, rate_dof=None, rate_shared=0.0)),
    ]

    for vname, p in sim_variants:
        sc = esg.simulate(p, n=n, seed=seed)

        # Month 1 crash correlations
        eq_us_sim = sc.eq_log[:, 0, 0]
        eq_core_sim = 0.6 * sc.eq_log[:, 0, 0] + 0.3 * sc.eq_log[:, 0, 1] + 0.1 * sc.eq_log[:, 0, 2]
        dr5_1m_sim = (sc.zero_cc(1, 5.0)[:, 0] - sc.zero_cc(0, 5.0)[:, 0]) * 100.0

        full_us_s, crash_us_s = calibrate.crash_correlation(eq_us_sim, dr5_1m_sim)
        full_core_s, crash_core_s = calibrate.crash_correlation(eq_core_sim, dr5_1m_sim)

        for tau in TENORS:
            # Yield curve at all months (M+1, N)
            rates = np.array([sc.zero_cc(m, tau)[:, 0] for m in range(p.months + 1)]) * 100.0

            for h in HORIZONS:
                dh = rates[h] - rates[0]
                rows.append({
                    "variant": vname,
                    "tenor": f"{int(tau)}y",
                    "horizon_m": h,
                    "sd": round(float(dh.std()), 4),
                    "excess_kurt": round(float(stats.kurtosis(dh)), 4),
                    "min": round(float(dh.min()), 4),
                    "p0_1": round(float(np.percentile(dh, 0.1)), 4),
                    "p99_9": round(float(np.percentile(dh, 99.9)), 4),
                    "max": round(float(dh.max()), 4),
                    "full_corr_us": round(full_us_s, 4),
                    "crash_corr_us": round(crash_us_s, 4),
                    "full_corr_core": round(full_core_s, 4),
                    "crash_corr_core": round(crash_core_s, 4),
                })

    df = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    return df


if __name__ == "__main__":
    df = run_rate_tails()
    print(f"Wrote {len(df)} rows to {OUTPUT_CSV}")
    print("\n=== 5-Year Zero Rate Tail Comparison (1m and 2m horizons) ===")
    p5 = df[(df["tenor"] == "5y") & (df["horizon_m"].isin([1, 2]))]
    print(p5[["variant", "horizon_m", "sd", "excess_kurt", "min", "p0_1", "max", "crash_corr_us"]].to_string(index=False))
