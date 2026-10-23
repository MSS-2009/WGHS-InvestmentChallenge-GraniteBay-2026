"""Validation study of the fitted Taiwan construction cost process against history.

Generates reports/taiwan_validation.csv containing:
1. Unconditional validation: 72-month growth percentiles (p5, p50, p95) for model vs history.
2. Conditional validation: 72-month growth for every historical window starting with 12m inflation > 5%,
   compared against model predictive distribution started from that month's state.
3. Drift sensitivity: Real facility median under full-sample (2.85%), 20-year (2.62%), and 10-year (3.78%) drifts.
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.data import taiwan
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "taiwan_validation.csv"

# AR(2) calibrated parameters
P1 = 0.6546
P2 = -0.0939
SIG_EPS = 0.007137
DRIFT_FULL = 0.0285
DRIFT_20Y = 0.0262
DRIFT_10Y = 0.0378

# Latest readings (Aug and Sep 2026)
Y_AUG_2026 = 0.00284974
Y_SEP_2026 = 0.00650706


def main():
    print("=" * 80)
    print("TAIWAN COST PROCESS VALIDATION STUDY")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Unconditional Validation: 72-month Cumulative Growth Distribution
    # -------------------------------------------------------------------------
    s = taiwan.cci()
    g72_hist = (s / s.shift(72) - 1.0).dropna()
    h_p5 = float(np.percentile(g72_hist, 5))
    h_p50 = float(np.median(g72_hist))
    h_p95 = float(np.percentile(g72_hist, 95))

    # Model unconditional simulation (stationary start from mean)
    r = build_core()
    w = r["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    geo = r["table"]["bl_geo_total"].values

    st = dc.replace(IPS, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er), commissions=True)
    base_p = esg_params(r["cal"], geo)

    p_uncond = dc.replace(
        base_p,
        tw_cost_growth=DRIFT_FULL,
        tw_cost_phi=(P1, P2),
        tw_cost_sig_eps=SIG_EPS,
        tw_cost_state0=None,
    )
    sc_uncond = simulate(p_uncond, n=20000, seed=11)
    # 72m cost growth from m=2 (Jan 2027) to m=74 (Jan 2033)
    cg_uncond = np.expm1(sc_uncond.tw_cost_log[:, 74] - sc_uncond.tw_cost_log[:, 2])
    m_p5 = float(np.percentile(cg_uncond, 5))
    m_p50 = float(np.median(cg_uncond))
    m_p95 = float(np.percentile(cg_uncond, 95))

    print(f"\nUnconditional 72-month Cost Growth (N={len(g72_hist)} historical windows vs N=20,000 MC):")
    print(f"  History: p5={h_p5*100:5.2f}% | p50={h_p50*100:5.2f}% | p95={h_p95*100:5.2f}%")
    print(f"  Model:   p5={m_p5*100:5.2f}% | p50={m_p50*100:5.2f}% | p95={m_p95*100:5.2f}%")

    uncond_rows = [
        {
            "category": "unconditional",
            "item": "historical_rolling_72m",
            "start_12m_infl": np.nan,
            "hist_72m_growth": np.nan,
            "model_72m_p5": round(h_p5, 4),
            "model_72m_p50": round(h_p50, 4),
            "model_72m_p95": round(h_p95, 4),
            "nominal_median": np.nan,
            "real_median": np.nan,
            "notes": f"All 357 rolling 72m historical windows (1991-2026); min={g72_hist.min():.2%}, max={g72_hist.max():.2%}",
        },
        {
            "category": "unconditional",
            "item": "model_fitted_from_mean",
            "start_12m_infl": np.nan,
            "hist_72m_growth": np.nan,
            "model_72m_p5": round(m_p5, 4),
            "model_72m_p50": round(m_p50, 4),
            "model_72m_p95": round(m_p95, 4),
            "nominal_median": np.nan,
            "real_median": np.nan,
            "notes": "Fitted AR(2) (phi1=0.6546, phi2=-0.0939, sig=0.007137) started at stationary distribution",
        },
    ]

    # -------------------------------------------------------------------------
    # 2. Conditional Validation: Windows Starting with 12m Inflation > 5%
    # -------------------------------------------------------------------------
    log_p = np.log(s)
    dy = log_p.diff().dropna()
    infl_12m = s / s.shift(12) - 1.0
    growth_72m_fwd = s.shift(-72) / s - 1.0

    # Common shocks for conditional simulation
    n_cond = 4000
    M = 72
    rng = np.random.default_rng(42)
    half = n_cond // 2
    z_half = rng.standard_normal((half, M))
    z_cond = np.concatenate([z_half, -z_half], axis=0)[:n_cond]
    mu_monthly = np.log1p(DRIFT_FULL) / 12.0

    def sim_forward_from_state(y2, y1):
        y_sim = np.empty((n_cond, M))
        for m in range(M):
            prev1 = y1 if m == 0 else y_sim[:, m - 1]
            prev2 = y2 if m == 0 else (y1 if m == 1 else y_sim[:, m - 2])
            y_sim[:, m] = mu_monthly + P1 * (prev1 - mu_monthly) + P2 * (prev2 - mu_monthly) + SIG_EPS * z_cond[:, m]
        cg = np.expm1(np.sum(y_sim, axis=1))
        return float(np.percentile(cg, 5)), float(np.median(cg)), float(np.percentile(cg, 95))

    hi_infl = s[(infl_12m > 0.05) & (growth_72m_fwd.notna())]
    print(f"\nConditional Validation on {len(hi_infl)} Windows with 12m Inflation > 5%:")

    def get_episode_name(dt):
        if dt < pd.Timestamp("1995-01-01"):
            return "Episode 1: 1992-1993 Post-Boom"
        elif dt < pd.Timestamp("2005-06-01"):
            return "Episode 2: 2003-2005 Commodity Supercycle"
        elif dt < pd.Timestamp("2009-01-01"):
            return "Episode 3: 2006-2008 Pre-GFC Commodity Spike"
        else:
            return "Episode 4: 2010 Post-GFC Rebound"

    cond_rows = []
    covered = 0
    for dt in hi_infl.index:
        idx = s.index.get_loc(dt)
        y1 = dy.loc[dt]
        prev_dt = s.index[idx - 1]
        y2 = dy.loc[prev_dt]
        act_12m = infl_12m.loc[dt]
        act_72m = growth_72m_fwd.loc[dt]
        cp5, cp50, cp95 = sim_forward_from_state(y2, y1)
        if cp5 <= act_72m <= cp95:
            covered += 1

        ep_name = get_episode_name(dt)
        cond_rows.append({
            "category": "conditional_window",
            "item": dt.strftime("%Y-%m"),
            "start_12m_infl": round(act_12m, 4),
            "hist_72m_growth": round(act_72m, 4),
            "model_72m_p5": round(cp5, 4),
            "model_72m_p50": round(cp50, 4),
            "model_72m_p95": round(cp95, 4),
            "nominal_median": np.nan,
            "real_median": np.nan,
            "notes": ep_name,
        })

    print(f"  Coverage: {covered} / {len(hi_infl)} windows ({covered/len(hi_infl):.1%}) fell within model [p5, p95]")
    print("  Distinct independent historical episodes identified: 4 (1992-93, 2003-05, 2006-08, 2010)")

    # -------------------------------------------------------------------------
    # 3. Drift Sensitivity Analysis
    # -------------------------------------------------------------------------
    drift_specs = [
        ("full_sample", DRIFT_FULL, "35-year full sample (1991-2026) mean annual growth (2.85%)"),
        ("last_20y", DRIFT_20Y, "Last 20 years (2006-2026) mean annual growth (2.62%)"),
        ("last_10y", DRIFT_10Y, "Last 10 years (2016-2026) mean annual growth (3.78%)"),
    ]

    drift_rows = []
    print("\nDrift Sensitivity on Real Facility Median (N=20,000 MC):")
    for d_name, d_val, d_note in drift_specs:
        # From Mean
        p_dm = dc.replace(
            base_p,
            tw_cost_growth=d_val,
            tw_cost_phi=(P1, P2),
            tw_cost_sig_eps=SIG_EPS,
            tw_cost_state0=None,
        )
        sc_dm = simulate(p_dm, n=20000, seed=11)
        res_dm = engine.run(st, sc_dm, cfg)
        nom_dm = float(np.median(res_dm["facility"]))
        real_dm = float(np.median(res_dm["facility_real_tw2027"]))
        cg_dm = float(np.median(np.expm1(sc_dm.tw_cost_log[:, 74] - sc_dm.tw_cost_log[:, 2])))

        # From Today
        p_dt = dc.replace(
            base_p,
            tw_cost_growth=d_val,
            tw_cost_phi=(P1, P2),
            tw_cost_sig_eps=SIG_EPS,
            tw_cost_state0=(Y_AUG_2026, Y_SEP_2026),
        )
        sc_dt = simulate(p_dt, n=20000, seed=11)
        res_dt = engine.run(st, sc_dt, cfg)
        nom_dt = float(np.median(res_dt["facility"]))
        real_dt = float(np.median(res_dt["facility_real_tw2027"]))
        cg_dt = float(np.median(np.expm1(sc_dt.tw_cost_log[:, 74] - sc_dt.tw_cost_log[:, 2])))

        drift_rows.append({
            "category": "drift_sensitivity",
            "item": f"fitted_from_mean_{d_name}",
            "start_12m_infl": round(d_val, 4),
            "hist_72m_growth": np.nan,
            "model_72m_p5": round(float(np.percentile(res_dm["facility_real_tw2027"], 5)), 1),
            "model_72m_p50": round(real_dm, 1),
            "model_72m_p95": round(float(np.percentile(res_dm["facility_real_tw2027"], 95)), 1),
            "nominal_median": round(nom_dm, 1),
            "real_median": round(real_dm, 1),
            "notes": f"{d_note} | 72m CostGrowth={cg_dm:.2%}",
        })
        drift_rows.append({
            "category": "drift_sensitivity",
            "item": f"fitted_from_today_{d_name}",
            "start_12m_infl": round(d_val, 4),
            "hist_72m_growth": np.nan,
            "model_72m_p5": round(float(np.percentile(res_dt["facility_real_tw2027"], 5)), 1),
            "model_72m_p50": round(real_dt, 1),
            "model_72m_p95": round(float(np.percentile(res_dt["facility_real_tw2027"], 95)), 1),
            "nominal_median": round(nom_dt, 1),
            "real_median": round(real_dt, 1),
            "notes": f"Started at Aug/Sep 2026 readings | {d_note} | 72m CostGrowth={cg_dt:.2%}",
        })

        print(f"  {d_name:12s} ({d_val*100:5.2f}%): From Mean RealMed=${real_dm:>8.1f} | "
              f"From Today RealMed=${real_dt:>8.1f} | Delta=${real_dt - real_dm:>+6.1f} ({(real_dt/real_dm - 1)*100:>+5.2f}%)")

    # -------------------------------------------------------------------------
    # 4. Save to reports/taiwan_validation.csv
    # -------------------------------------------------------------------------
    all_rows = uncond_rows + cond_rows + drift_rows
    df_all = pd.DataFrame(all_rows)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(REPORT_PATH, index=False)
    print(f"\nWrote {REPORT_PATH} with {len(df_all)} rows.")


if __name__ == "__main__":
    main()
