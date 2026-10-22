"""Variant study comparing Taiwan cost processes and historical replay.

Outputs:
- reports/taiwan_variants.csv
- updates to config/taiwan.yaml
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import backtest, engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "taiwan_variants.csv"
CONFIG_PATH = ROOT / "config" / "taiwan.yaml"


def main(n: int = 20_000, seed: int = 11):
    # 1. Headline Portfolio Setup (identical to scripts/report_numbers.py)
    r = build_core()
    w = r["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    geo = r["table"]["bl_geo_total"].values

    st = dc.replace(IPS, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er), commissions=True)

    base_p = esg_params(r["cal"], geo)

    # 2. Variants Definition
    # Latest Taiwan DGBAS readings (Sep 2026):
    # YoY simple inflation: 7.2888% (0.072888)
    # Monthly annualized log change: 0.078085
    variants = {
        "current": dc.replace(
            base_p,
            tw_cost_growth=0.04,
            tw_cost_vol=0.015,
            tw_cost_phi=None,
            tw_cost_infl0=None,
            tw_cost_corr=None,
        ),
        "iid_dropin": dc.replace(
            base_p,
            tw_cost_growth=0.0285,
            tw_cost_vol=0.0538,
            tw_cost_phi=None,
            tw_cost_infl0=None,
            tw_cost_corr=None,
        ),
        "persistent_from_mean": dc.replace(
            base_p,
            tw_cost_growth=0.0285,
            tw_cost_vol=0.0538,
            tw_cost_phi=0.9728,
            tw_cost_infl0=0.0285,
            tw_cost_corr=None,
        ),
        "persistent_from_today": dc.replace(
            base_p,
            tw_cost_growth=0.0285,
            tw_cost_vol=0.0538,
            tw_cost_phi=0.9728,
            tw_cost_infl0=0.072888,
            tw_cost_corr=None,
        ),
        "persistent_monthly_today": dc.replace(
            base_p,
            tw_cost_growth=0.0285,
            tw_cost_vol=0.0309,
            tw_cost_phi=0.5983,
            tw_cost_infl0=0.078085,
            tw_cost_corr=None,
        ),
    }

    results = []
    print("=" * 80)
    print("TAIWAN COST SPECIFICATION VARIANTS (Monte Carlo, N = 20,000)")
    print("=" * 80)

    for name, p in variants.items():
        sc = simulate(p, n=n, seed=seed)
        res = engine.run(st, sc, cfg)

        nom = res["facility"]
        nom_med = float(np.median(nom))

        real = res["facility_real_tw2027"]
        r_p5 = float(np.percentile(real, 5))
        r_p10 = float(np.percentile(real, 10))
        r_med = float(np.median(real))
        r_p90 = float(np.percentile(real, 90))
        r_p95 = float(np.percentile(real, 95))

        # 72-month cumulative cost growth from Jan 2027 (m=2) to Jan 2033 (m=74)
        i33 = engine.M_2033 - sc.m0
        i27 = max(engine.M_2027 - sc.m0, 0)
        cg = np.expm1(sc.tw_cost_log[:, i33] - sc.tw_cost_log[:, i27])
        cg_p5 = float(np.percentile(cg, 5))
        cg_p50 = float(np.percentile(cg, 50))
        cg_p95 = float(np.percentile(cg, 95))

        row = {
            "variant": name,
            "nominal_median": round(nom_med, 1),
            "real_p5": round(r_p5, 1),
            "real_p10": round(r_p10, 1),
            "real_median": round(r_med, 1),
            "real_p90": round(r_p90, 1),
            "real_p95": round(r_p95, 1),
            "cost_growth_72m_p5": round(cg_p5, 4),
            "cost_growth_72m_p50": round(cg_p50, 4),
            "cost_growth_72m_p95": round(cg_p95, 4),
        }
        results.append(row)
        print(f"{name:25s} | NomMed: ${nom_med:>8.1f} | RealMed: ${r_med:>8.1f} [p5: ${r_p5:>7.1f}, p95: ${r_p95:>8.1f}] | "
              f"CostGrowth: {cg_p50*100:>5.2f}% [{cg_p5*100:>5.2f}%, {cg_p95*100:>5.2f}%]")

    # 3. Historical Replay Comparison (184 overlapping paths)
    print("\n" + "=" * 80)
    print("HISTORICAL REPLAY ON 184 OVERLAPPING 74-MONTH PATHS (2005-2026)")
    print("=" * 80)

    # 4% line replay
    sc_h_4p, starts = backtest.history_paths([g.history for g in CORE], recentre=geo, real_tw_cost=False)
    res_h_4p = engine.run(st, sc_h_4p, cfg)
    real_4p = res_h_4p["facility_real_tw2027"]
    cg_4p = np.expm1(sc_h_4p.tw_cost_log[:, 74] - sc_h_4p.tw_cost_log[:, 2])

    # Real DGBAS CCI index replay
    sc_h_real, _ = backtest.history_paths([g.history for g in CORE], recentre=geo, real_tw_cost=True)
    res_h_real = engine.run(st, sc_h_real, cfg)
    real_real = res_h_real["facility_real_tw2027"]
    cg_real = np.expm1(sc_h_real.tw_cost_log[:, 74] - sc_h_real.tw_cost_log[:, 2])

    hist_rows = [
        {
            "variant": "historical_replay_4pct_line",
            "nominal_median": round(float(np.median(res_h_4p["facility"])), 1),
            "real_p5": round(float(np.percentile(real_4p, 5)), 1),
            "real_p10": round(float(np.percentile(real_4p, 10)), 1),
            "real_median": round(float(np.median(real_4p)), 1),
            "real_p90": round(float(np.percentile(real_4p, 90)), 1),
            "real_p95": round(float(np.percentile(real_4p, 95)), 1),
            "cost_growth_72m_p5": round(float(np.percentile(cg_4p, 5)), 4),
            "cost_growth_72m_p50": round(float(np.median(cg_4p)), 4),
            "cost_growth_72m_p95": round(float(np.percentile(cg_4p, 95)), 4),
        },
        {
            "variant": "historical_replay_real_cci",
            "nominal_median": round(float(np.median(res_h_real["facility"])), 1),
            "real_p5": round(float(np.percentile(real_real, 5)), 1),
            "real_p10": round(float(np.percentile(real_real, 10)), 1),
            "real_median": round(float(np.median(real_real)), 1),
            "real_p90": round(float(np.percentile(real_real, 90)), 1),
            "real_p95": round(float(np.percentile(real_real, 95)), 1),
            "cost_growth_72m_p5": round(float(np.percentile(cg_real, 5)), 4),
            "cost_growth_72m_p50": round(float(np.median(cg_real)), 4),
            "cost_growth_72m_p95": round(float(np.percentile(cg_real, 95)), 4),
        },
    ]

    for h in hist_rows:
        results.append(h)
        print(f"{h['variant']:28s} | RealMed: ${h['real_median']:>8.1f} [p5: ${h['real_p5']:>7.1f}, p95: ${h['real_p95']:>8.1f}] | "
              f"CostGrowth: {h['cost_growth_72m_p50']*100:>5.2f}% [{h['cost_growth_72m_p5']*100:>5.2f}%, {h['cost_growth_72m_p95']*100:>5.2f}%]")

    # 4. Save reports/taiwan_variants.csv
    df_out = pd.DataFrame(results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(REPORT_PATH, index=False)
    print(f"\nWrote {REPORT_PATH}")

    # 5. Update config/taiwan.yaml
    config_yaml = f"""# Taiwan Building-Cost Model Parameters and Calibrations
# Calibrated from official DGBAS Construction Cost Index (1991-01 to 2026-09)
# Generated by scripts/taiwan_variants.py; findings in docs/loop/r2_taiwan_findings.md

# Option 1: Drop-in replacement for existing ESGParams (preserves i.i.d. architecture)
# Uses historical 35-year drift (2.85%) and effective annual volatility (5.38%)
# matching the 12-month and 72-month cumulative dispersion under an i.i.d. walk.
iid_dropin:
  tw_cost_growth: 0.0285   # Full sample mean annual growth (reports/taiwan_costs.json: 0.0282-0.0286)
  tw_cost_vol: 0.0538      # 12-month standard deviation (reports/taiwan_costs.json: std_12m=0.0538)
  t_dof: null              # i.i.d. Gaussian increments as in existing esg.py

# Option 2: Structurally faithful persistent process (12-month inflation regime)
# Captures strong multi-year inflation persistence (phi=0.9728) and today's elevated starting state.
persistent_from_today:
  tw_cost_growth: 0.0285   # Long-run annual mean log drift (full sample: 2.82%, 20-yr: 2.62%)
  tw_cost_vol: 0.0538      # Annual volatility of 12-month inflation rate
  tw_cost_phi: 0.9728      # Monthly AR(1) persistence of 12-month inflation rate
  tw_cost_infl0: 0.072888  # Latest official DGBAS reading (Sep 2026: +7.29% YoY)
  correlations:
    us_cpi: 0.4783         # Correlation with US CPI inflation (joint global commodity shocks)
    usd_twd: -0.1256       # Correlation with USD/TWD monthly log changes
    tw_cpi: 0.0754         # Correlation with domestic Taiwan CPI

persistent_from_mean:
  tw_cost_growth: 0.0285
  tw_cost_vol: 0.0538
  tw_cost_phi: 0.9728
  tw_cost_infl0: 0.0285    # Stationary start from long-run mean (unconditional baseline)
"""
    CONFIG_PATH.write_text(config_yaml)
    print(f"Wrote {CONFIG_PATH}")


if __name__ == "__main__":
    main()
